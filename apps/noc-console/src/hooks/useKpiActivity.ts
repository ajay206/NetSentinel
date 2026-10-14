import { useEffect, useRef, useState, useCallback } from 'react';
import type { KpiActivity, KpiWsMessage } from '../types';
import { withToken } from '../lib/auth';

export type KpiConnectionStatus = 'connecting' | 'open' | 'closed';

/**
 * Hook that maintains the latest KPI activity received via WebSocket.
 * It reconnects with exponential back‑off (capped at 10 seconds) and stops
 * reconnecting once the component is unmounted.
 *
 * Returns:
 *   - activity: the most recent KpiActivity or null if none received yet
 *   - status:   the WebSocket connection status
 */
export function useKpiActivity(): {
  activity: KpiActivity | null;
  status: KpiConnectionStatus;
} {
  const [activity, setActivity] = useState<KpiActivity | null>(null);
  const [status, setStatus] = useState<KpiConnectionStatus>('connecting');

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const backoffRef = useRef(1000); // start at 1 s
  const disposedRef = useRef(false);

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}/ws/kpis`;
    const ws = new WebSocket(withToken(url));
    wsRef.current = ws;

    ws.onopen = () => {
      // Defer state update to avoid setting state synchronously inside the effect body
      setTimeout(() => setStatus('open'), 0);
      backoffRef.current = 1000;
    };

    ws.onclose = () => {
      setTimeout(() => setStatus('closed'), 0);
      if (!disposedRef.current) {
        backoffRef.current = Math.min(backoffRef.current * 2, 10000);
        reconnectTimeoutRef.current = window.setTimeout(connect, backoffRef.current);
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: KpiWsMessage = JSON.parse(event.data);
        if (msg.type === 'kpiActivity') {
          const { type: _type, ...snapshot } = msg;
          void _type;
          setActivity(snapshot);
        }
        // ignore other message types
      } catch (e) {
        console.error('Failed to parse KPI WS message', e);
      }
    };
  }, []);

  useEffect(() => {
    disposedRef.current = false;
    connect();

    return () => {
      disposedRef.current = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
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

  return { activity, status };
}
