import React, { useEffect, useState } from 'react';
import type { ConnectionStatus } from '../hooks/useAlarmFeed';
import { formatIST } from '../lib/time';

interface HeaderProps {
  wsStatus: ConnectionStatus;
  /** W11: signed-in user; omitted in tests that only check the clock/status. */
  user?: { username: string; role: string };
  onLogout?: () => void;
}

const LIVE: Record<ConnectionStatus, { label: string; dot: string; pill: string }> = {
  open: { label: 'Live', dot: 'bg-emerald-400', pill: 'bg-emerald-500/10 text-emerald-300' },
  connecting: { label: 'Connecting…', dot: 'bg-amber-400', pill: 'bg-amber-500/10 text-amber-300' },
  closed: { label: 'Offline', dot: 'bg-red-400', pill: 'bg-red-500/10 text-red-300' },
};

export const Header: React.FC<HeaderProps> = ({ wsStatus, user, onLogout }) => {
  const [istTime, setIstTime] = useState(() => formatIST(new Date()));

  useEffect(() => {
    const timer = setInterval(() => setIstTime(formatIST(new Date())), 1000);
    return () => clearInterval(timer);
  }, []);

  const live = LIVE[wsStatus];

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-800 bg-slate-900/95 px-6 backdrop-blur">
      <div className="flex items-center gap-3">
        <span className="grid h-7 w-7 place-items-center rounded-md bg-sky-500 text-xs font-bold text-slate-950">
          NS
        </span>
        <span className="font-semibold text-slate-100">NetSentinel</span>
        <span className="text-slate-400">NOC Console</span>
        <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[11px] text-sky-300">
          Synthetic data
        </span>
      </div>
      <div className="flex items-center gap-4 text-sm">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${live.pill}`}
          data-testid="live-status"
          title="Live alarm stream (WebSocket)"
        >
          <span
            className={`h-2 w-2 rounded-full ${live.dot} ${wsStatus === 'open' ? 'animate-pulse' : ''}`}
          />
          {live.label}
        </span>
        <span className="font-mono text-xs text-slate-400">IST {istTime}</span>
        {user && (
          <span className="flex items-center gap-2" data-testid="user-badge">
            <span className="text-slate-200">{user.username}</span>
            <span className="rounded bg-violet-500/15 px-2 py-0.5 font-mono text-xs text-violet-300">
              {user.role}
            </span>
            {onLogout && (
              <button
                type="button"
                onClick={onLogout}
                className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-800"
              >
                Sign out
              </button>
            )}
          </span>
        )}
      </div>
    </header>
  );
};
