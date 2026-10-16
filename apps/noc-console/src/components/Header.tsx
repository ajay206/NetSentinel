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
  open: { label: 'Live', dot: 'bg-emerald-400', pill: 'bg-emerald-400/15 text-emerald-100' },
  connecting: { label: 'Connecting…', dot: 'bg-amber-400', pill: 'bg-amber-400/15 text-amber-100' },
  closed: { label: 'Offline', dot: 'bg-red-400', pill: 'bg-red-400/15 text-red-100' },
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
  const [navOpen, setNavOpen] = useState(false);
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
  const showNav = views.length > 1;

  const navButtons = (compact: boolean) =>
    views.map((v) => (
      <button
        key={v.id}
        type="button"
        aria-current={v.id === activeView ? 'page' : undefined}
        onClick={() => {
          onSelectView?.(v.id);
          setNavOpen(false);
        }}
        className={`rounded px-3 py-1 text-sm ${compact ? 'w-full text-left' : ''} ${
          v.id === activeView
            ? 'bg-deck-cyanDark text-white'
            : 'text-white/75 hover:bg-white/10 hover:text-white'
        }`}
      >
        {v.label}
      </button>
    ));

  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-deck-navy text-white">
      <div className="flex min-h-14 flex-wrap items-center justify-between gap-2 px-3 py-2 sm:px-6">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          {showNav && (
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded md:hidden hover:bg-white/10"
              aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
              aria-expanded={navOpen}
              onClick={() => setNavOpen((o) => !o)}
            >
              <span aria-hidden="true" className="text-lg leading-none">
                {navOpen ? '✕' : '☰'}
              </span>
            </button>
          )}
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-deck-cyan text-xs font-bold text-deck-navy">
            NS
          </span>
          <span className="font-display font-semibold">NetSentinel</span>
          <span className="hidden text-white/70 sm:inline">NOC Console</span>
          <Tooltip content={TIPS.chipSynthetic} side="bottom">
            <span className="hidden rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-deck-cyan xs:inline sm:inline">
              Synthetic data
            </span>
          </Tooltip>
          {showNav && (
            <nav className="ml-2 hidden gap-1 md:flex" aria-label="Dashboards">
              {navButtons(false)}
            </nav>
          )}
        </div>
        <div className="flex min-w-0 items-center gap-2 text-sm sm:gap-4">
          <Tooltip content={TIPS.chipLive} side="bottom">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${live.pill}`}
              data-testid="live-status"
            >
              <span
                className={`h-2 w-2 rounded-full ${live.dot} ${wsStatus === 'open' ? 'animate-pulse' : ''}`}
              />
              <span className="hidden sm:inline">{live.label}</span>
            </span>
          </Tooltip>
          <Tooltip content={TIPS.chipClock} side="bottom">
            <span className="hidden font-mono text-xs text-white/70 md:inline">IST {istTime}</span>
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
                  className="flex max-w-[12rem] items-center gap-2 rounded px-2 py-1 hover:bg-white/10 sm:max-w-none"
                >
                  <span className="truncate">{user.username}</span>
                  <span
                    className="hidden rounded bg-white/15 px-2 py-0.5 font-mono text-xs text-white ring-1 ring-white/30 sm:inline"
                    data-testid="role-badge"
                  >
                    {user.role}
                  </span>
                  <span aria-hidden="true" className="text-white/50">
                    ▾
                  </span>
                </button>
              </Tooltip>
              {menuOpen && (
                <div
                  role="menu"
                  aria-label="Profile"
                  className="absolute right-0 z-40 mt-1 w-64 rounded-lg border border-slate-700 bg-white p-1 text-slate-100 shadow-card"
                >
                  <p className="px-3 py-2 text-xs text-slate-400">{ROLE_BLURB[user.role]}</p>
                  <span
                    className={`mx-3 mb-1 inline-flex rounded px-2 py-0.5 font-mono text-xs sm:hidden ${ROLE_STYLE[user.role] ?? ''}`}
                  >
                    {user.role}
                  </span>
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
      </div>
      {showNav && navOpen && (
        <nav className="flex flex-col gap-1 border-t border-white/10 px-3 py-2 md:hidden" aria-label="Dashboards">
          {navButtons(true)}
        </nav>
      )}
    </header>
  );
};
