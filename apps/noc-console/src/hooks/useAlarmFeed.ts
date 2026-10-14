import { useEffect, useReducer, useRef, useCallback } from 'react';
import type { Alarm, WsMessage } from '../types';

export type ConnectionStatus = 'connecting' | 'open' | 'closed';

export interface AlarmState {
  alarms: Alarm[];
  status: ConnectionStatus;
}

export type Action =
  | { type: 'setStatus'; status: ConnectionStatus }
  | { type: 'setAlarms'; alarms: Alarm[] }
  | { type: 'addAlarm'; alarm: Alarm };

export function applyMessage(
  prev: Alarm[],
  msg: WsMessage,
  max = 200
): Alarm[] {
  if (msg.type === 'snapshot') {
    const sorted = [...msg.alarms].sort(
      (a, b) =>
        new Date(b.alarmRaisedTime).getTime() -
        new Date(a.alarmRaisedTime).getTime()
    );
    return sorted.slice(0, max);
  }

  const exists = prev.some((a) => a.id === msg.alarm.id);
  if (exists) {
    return prev.map((a) =>
      a.id === msg.alarm.id ? msg.alarm : a
    );
  }

  const updated = [msg.alarm, ...prev];
  return updated.slice(0, max);
}

function reducer(state: AlarmState, action: Action): AlarmState {
  switch (action.type) {
    case 'setStatus':
      return { ...state, status: action.status };
    case 'setAlarms':
      return { ...state, alarms: action.alarms };
    case 'addAlarm':
      return {
        ...state,
        alarms: applyMessage(state.alarms, { type: 'alarm', alarm: action.alarm }),
      };
    default:
      return state;
  }
}

function alarmSocketUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const explicit = import.meta.env.VITE_WS_URL as string | undefined;
  if (explicit) {
    return explicit;
  }
  // Vite's HTTP proxy for WebSockets logs write EPIPE on a normal close
  // (Strict Mode remount, HMR, reconnect). In dev, talk to the gateway
  // directly; production still uses a relative URL behind the reverse proxy.
  if (import.meta.env.DEV) {
    const gateway = import.meta.env.VITE_GATEWAY_URL as string | undefined;
    if (gateway) {
      const u = new URL(gateway, location.origin);
      const wsProto = u.protocol === 'https:' ? 'wss' : 'ws';
      return `${wsProto}://${u.host}/ws/alarms`;
    }
    return `${proto}://127.0.0.1:8000/ws/alarms`;
  }
  return `${proto}://${location.host}/ws/alarms`;
}

export function useAlarmFeed() {
  const [state, dispatch] = useReducer(reducer, {
    alarms: [],
    status: 'connecting',
  });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);
  const backoffRef = useRef(1000);
  const disposedRef = useRef(false);

  const connect = useCallback(() => {
    if (disposedRef.current) {
      return;
    }
    const url = alarmSocketUrl();
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (wsRef.current !== ws) {
        return;
      }
      dispatch({ type: 'setStatus', status: 'open' });
      backoffRef.current = 1000;
    };

    ws.onclose = () => {
      if (wsRef.current !== ws) {
        return;
      }
      dispatch({ type: 'setStatus', status: 'closed' });
      if (!disposedRef.current) {
        backoffRef.current = Math.min(backoffRef.current * 2, 10000);
        reconnectRef.current = window.setTimeout(connect, backoffRef.current);
      }
    };

    // Do not call close() here: it races Vite's WS proxy and the browser
    // already follows onerror with onclose, which drives reconnect.

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        if (msg.type === 'snapshot') {
          dispatch({ type: 'setAlarms', alarms: applyMessage([], msg) });
        } else {
          dispatch({ type: 'addAlarm', alarm: msg.alarm });
        }
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };
  }, []);

  useEffect(() => {
    disposedRef.current = false;
    // Defer so React Strict Mode's immediate unmount never opens a socket.
    const startId = window.setTimeout(connect, 0);
    return () => {
      disposedRef.current = true;
      window.clearTimeout(startId);
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
        reconnectRef.current = null;
      }
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) {
        ws.onopen = null;
        ws.onclose = null;
        ws.onerror = null;
        ws.onmessage = null;
        if (
          ws.readyState === WebSocket.OPEN ||
          ws.readyState === WebSocket.CONNECTING
        ) {
          ws.close();
        }
      }
    };
  }, [connect]);

  return state;
}
