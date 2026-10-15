import React, { useEffect, useRef, useState } from 'react';
import type { ConnectionStatus } from '../hooks/useAlarmFeed';
import { formatIST } from '../lib/time';
import type { Role } from '../lib/auth';
import { TIPS } from '../lib/tooltips';
import { Tooltip } from './ui/Tooltip';
import { ROLE_BLURB, ROLE_STYLE } from '../lib/rbac';

interface HeaderProps {
  wsStatus: ConnectionStatus;
  /** W11: signed-in user; omitted in tests that only check the clock/status. */
  user?: { username: string; role: Role };
  onLogout?: () => void;
  /** Step 13b: opens the change-password dialog. */
  onChangePassword?: () => void;
  /** Step 13b: role-specific dashboards (Operations, Admin). */
  views?: { id: string; label: string }[];
  activeView?: string;
  onSelectView?: (id: string) => void;
}

const LIVE: Record<ConnectionStatus, { label: string; dot: string; pill: string }> = {
  open: { label: 'Live', dot: 'bg-emerald-400', pill: 'bg-emerald-500/10 text-emerald-300' },
  connecting: { label: 'Connecting…', dot: 'bg-amber-400', pill: 'bg-amber-500/10 text-amber-300' },
  closed: { label: 'Offline', dot: 'bg-red-400', pill: 'bg-red-500/10 text-red-300' },
};

export const Header: React.FC<HeaderProps> = ({
  wsStatus,
  user,
  onLogout,
  onChangePassword,
  views = [],
  activeView,
  onSelectView,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (
        e instanceof KeyboardEvent
          ? e.key === 'Escape'
          : !menuRef.current?.contains(e.target as Node)
      )
        setMenuOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [menuOpen]);
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
        <Tooltip content={TIPS.chipSynthetic} side="bottom">
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[11px] text-sky-300">
            Synthetic data
          </span>
        </Tooltip>
        {views.length > 1 && (
          <nav className="ml-4 flex gap-1" aria-label="Dashboards">
            {views.map((v) => (
              <button
                key={v.id}
                type="button"
                aria-current={v.id === activeView ? 'page' : undefined}
                onClick={() => onSelectView?.(v.id)}
                className={`rounded px-3 py-1 text-sm ${
                  v.id === activeView
                    ? 'bg-slate-800 text-slate-100'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                }`}
              >
                {v.label}
              </button>
            ))}
          </nav>
        )}
      </div>
      <div className="flex items-center gap-4 text-sm">
        <Tooltip content={TIPS.chipLive} side="bottom">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${live.pill}`}
            data-testid="live-status"
          >
            <span
              className={`h-2 w-2 rounded-full ${live.dot} ${wsStatus === 'open' ? 'animate-pulse' : ''}`}
            />
            {live.label}
          </span>
        </Tooltip>
        <Tooltip content={TIPS.chipClock} side="bottom">
          <span className="font-mono text-xs text-slate-400">IST {istTime}</span>
        </Tooltip>
        {user && (
          <div className="relative" ref={menuRef} data-testid="user-badge">
            <Tooltip
              content={`${ROLE_BLURB[user.role] ?? ''} ${TIPS.chipRole}`.trim()}
              side="bottom"
            >
              <button
                type="button"
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((o) => !o)}
                className="flex items-center gap-2 rounded px-2 py-1 hover:bg-slate-800"
              >
                <span className="text-slate-200">{user.username}</span>
                <span
                  className={`rounded px-2 py-0.5 font-mono text-xs ${ROLE_STYLE[user.role] ?? ''}`}
                  data-testid="role-badge"
                >
                  {user.role}
                </span>
                <span aria-hidden="true" className="text-slate-500">
                  ▾
                </span>
              </button>
            </Tooltip>
            {menuOpen && (
              <div
                role="menu"
                aria-label="Profile"
                className="absolute right-0 z-40 mt-1 w-64 rounded-lg border border-slate-700 bg-slate-900 p-1 shadow-xl"
              >
                <p className="px-3 py-2 text-xs text-slate-400">{ROLE_BLURB[user.role]}</p>
                {onChangePassword && (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      onChangePassword();
                    }}
                    className="block w-full rounded px-3 py-1.5 text-left text-sm text-slate-200 hover:bg-slate-800"
                  >
                    Change password
                  </button>
                )}
                {onLogout && (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={onLogout}
                    className="block w-full rounded px-3 py-1.5 text-left text-sm text-slate-200 hover:bg-slate-800"
                  >
                    Sign out
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
};
