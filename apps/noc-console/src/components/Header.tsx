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
  open: { label: 'Live', dot: 'bg-emerald-600', pill: 'bg-emerald-100 text-emerald-700' },
  connecting: { label: 'Connecting…', dot: 'bg-amber-500', pill: 'bg-amber-100 text-amber-700' },
  closed: { label: 'Offline', dot: 'bg-red-500', pill: 'bg-red-100 text-red-700' },
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
    <header className="flex flex-wrap items-center justify-between gap-4 py-1">
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-[14px] bg-navy font-display font-extrabold text-[15px] text-cyan">
          NS
        </div>
        <div className="font-display text-[22px] font-extrabold tracking-tight text-navy">
          NetSentinel <span className="ml-2 hidden font-sans text-[15px] font-medium text-bento-muted sm:inline">NOC Console</span>
        </div>
        <Tooltip content={TIPS.chipSynthetic} side="bottom">
          <span className="rounded-full bg-white border border-bento-border px-2.5 py-0.5 text-xs font-semibold text-bento-muted">
            Synthetic data
          </span>
        </Tooltip>
        {views.length > 1 && (
          <nav className="flex gap-1 sm:ml-4" aria-label="Dashboards">
            {views.map((v) => (
              <button
                key={v.id}
                type="button"
                aria-current={v.id === activeView ? 'page' : undefined}
                onClick={() => onSelectView?.(v.id)}
                className={`rounded-full px-3.5 py-1 text-xs font-bold transition-colors ${
                  v.id === activeView
                    ? 'bg-navy text-white'
                    : 'bg-white text-navy hover:bg-slate-200'
                }`}
              >
                {v.label}
              </button>
            ))}
          </nav>
        )}
      </div>
      <div className="flex items-center gap-2.5 text-xs">
        <Tooltip content={TIPS.chipLive} side="bottom">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-bold text-xs ${live.pill}`}
            data-testid="live-status"
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${live.dot} ${wsStatus === 'open' ? 'animate-pulse' : ''}`}
            />
            {live.label}
          </span>
        </Tooltip>
        <Tooltip content={TIPS.chipClock} side="bottom">
          <span className="rounded-full bg-white px-3.5 py-1 font-semibold text-navy shadow-sm">
            {istTime} IST
          </span>
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
                className="flex items-center gap-1.5 rounded-full bg-navy px-3 py-1 font-extrabold text-white shadow-sm hover:opacity-90"
              >
                <span>{user.username}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wider ${ROLE_STYLE[user.role] ?? ''}`}
                  data-testid="role-badge"
                >
                  {user.role}
                </span>
                <span aria-hidden="true" className="text-white/70">
                  ▾
                </span>
              </button>
            </Tooltip>
            {menuOpen && (
              <div
                role="menu"
                aria-label="Profile"
                className="absolute right-0 z-40 mt-1 w-64 rounded-xl border border-bento-border bg-white p-2 shadow-xl text-navy"
              >
                <p className="px-3 py-2 text-xs text-bento-muted">{ROLE_BLURB[user.role]}</p>
                {onChangePassword && (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      onChangePassword();
                    }}
                    className="block w-full rounded-lg px-3 py-1.5 text-left text-xs font-bold text-navy hover:bg-bento-bg"
                  >
                    Change password
                  </button>
                )}
                {onLogout && (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={onLogout}
                    className="block w-full rounded-lg px-3 py-1.5 text-left text-xs font-bold text-navy hover:bg-bento-bg"
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
