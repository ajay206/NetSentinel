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
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}/ws/alarms`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      dispatch({ type: 'setStatus', status: 'open' });
      backoffRef.current = 1000;
    };

    ws.onclose = () => {
      dispatch({ type: 'setStatus', status: 'closed' });
      if (!disposedRef.current) {
        backoffRef.current = Math.min(backoffRef.current * 2, 10000);
        reconnectRef.current = window.setTimeout(connect, backoffRef.current);
      }
    };

    ws.onerror = () => {
      ws.close();
    };

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
    connect();
    return () => {
      disposedRef.current = true;
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
      }
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.close();
      }
    };
  }, [connect]);

  return state;
}
