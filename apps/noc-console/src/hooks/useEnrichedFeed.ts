import { useEffect, useReducer, useRef, useCallback } from 'react';
import type { EnrichedAlarm, EnrichedWsMessage } from '../types.enriched';
import type { ConnectionStatus } from './useAlarmFeed';
import { withToken } from '../lib/auth';

export interface EnrichedState {
  alarms: EnrichedAlarm[];
  status: ConnectionStatus;
}

export type EnrichedAction =
  | { type: 'setStatus'; status: ConnectionStatus }
  | { type: 'setAlarms'; alarms: EnrichedAlarm[] }
  | { type: 'addAlarm'; alarm: EnrichedAlarm };

export function applyEnrichedMessage(
  prev: EnrichedAlarm[],
  msg: EnrichedWsMessage,
  max = 200
): EnrichedAlarm[] {
  if (msg.type === 'snapshot') {
    // Collapse repeats: the last message for a dedup key carries the highest count
    const latest = new Map<string, EnrichedAlarm>();
    msg.alarms.forEach((a) => {
      latest.delete(a.dedup.key);
      latest.set(a.dedup.key, a);
    });
    const sorted = [...latest.values()].reverse().sort(
      (a, b) =>
        new Date(b.alarmRaisedTime).getTime() -
        new Date(a.alarmRaisedTime).getTime()
    );
    return sorted.slice(0, max);
  }

  // enriched single alarm
  const existingIndex = prev.findIndex((a) => a.dedup.key === msg.alarm.dedup.key);
  if (existingIndex !== -1) {
    const updated = [
      msg.alarm,
      ...prev.slice(0, existingIndex),
      ...prev.slice(existingIndex + 1),
    ];
    return updated.slice(0, max);
  }

  const updated = [msg.alarm, ...prev];
  return updated.slice(0, max);
}

function enrichedReducer(
  state: EnrichedState,
  action: EnrichedAction
): EnrichedState {
  switch (action.type) {
    case 'setStatus':
      return { ...state, status: action.status };
    case 'setAlarms':
      return { ...state, alarms: action.alarms };
    case 'addAlarm':
      return {
        ...state,
        alarms: applyEnrichedMessage(state.alarms, {
          type: 'enriched',
          alarm: action.alarm,
        }),
      };
    default:
      return state;
  }
}

export function useEnrichedFeed() {
  const [state, dispatch] = useReducer(enrichedReducer, {
    alarms: [],
    status: 'connecting' as ConnectionStatus,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);
  const backoffRef = useRef(1000);
  const disposedRef = useRef(false);

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}/ws/enriched`;
    const ws = new WebSocket(withToken(url));
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
        const msg: EnrichedWsMessage = JSON.parse(event.data);
        if (msg.type === 'snapshot') {
          dispatch({ type: 'setAlarms', alarms: applyEnrichedMessage([], msg) });
        } else {
          dispatch({ type: 'addAlarm', alarm: msg.alarm });
        }
      } catch (e) {
        console.error('Failed to parse enriched WS message', e);
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
