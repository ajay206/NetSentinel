import React from 'react';
import { InfoTip } from './ui/Card';

interface DemoPathProps {
  activePage: ConsolePage;
  onNavigate: (page: ConsolePage) => void;
}

export type ConsolePage = 'overview' | 'alarms' | 'network' | 'performance' | 'investigation';

const pages: { id: ConsolePage; label: string; description: string }[] = [
  { id: 'overview', label: 'Overview', description: 'Network status and incidents' },
  { id: 'alarms', label: 'Alarms', description: 'Live alarms and ticket approvals' },
  { id: 'network', label: 'Network', description: 'Topology and service impact' },
  { id: 'performance', label: 'Performance', description: 'KPI trends and anomalies' },
  { id: 'investigation', label: 'Investigation', description: 'Runbooks and AI assistance' },
];

export const DemoPath: React.FC<DemoPathProps> = ({ activePage, onNavigate }) => {

  return (
    <nav aria-label="Console pages" className="rounded-[20px] bg-white p-4 sm:p-5 lg:px-6 shadow-sm border border-bento-border">
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-xs font-extrabold uppercase tracking-wider text-bento-muted">Console pages</h2>
        <InfoTip text="Choose a page to focus on a specific part of network operations." label="console pages" />
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
        {pages.map((page) => {
          const selected = activePage === page.id;
          return (
            <button
              key={page.id}
              type="button"
              aria-current={selected ? 'page' : undefined}
              aria-label={`${page.label}: ${page.description}`}
              onClick={() => onNavigate(page.id)}
              className={`flex min-h-[58px] items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
                selected
                  ? 'border-navy bg-navy text-white shadow-sm'
                  : 'border-bento-border bg-bento-bg text-navy hover:border-slate-300 hover:bg-slate-100'
              }`}
            >
              <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg text-xs font-extrabold ${selected ? 'bg-white/15 text-white' : 'bg-white text-navy'}`}>
                {pages.indexOf(page) + 1}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-bold">{page.label}</span>
                <span className={`hidden truncate text-[11px] sm:block ${selected ? 'text-white/75' : 'text-bento-muted'}`}>{page.description}</span>
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
