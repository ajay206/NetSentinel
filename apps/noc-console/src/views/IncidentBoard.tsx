import { useMemo } from 'react';
import { sortIncidents, durationLabel } from '../lib/incidents';
import type { Incident, IncidentList } from '../types.incident';

interface IncidentBoardProps {
  data?: IncidentList;
  isLoading: boolean;
  isError: boolean;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

const severityStyles: Record<Incident['severity'], string> = {
  critical: 'bg-red-500',
  major: 'bg-orange-500',
  minor: 'bg-yellow-400',
  warning: 'bg-sky-400',
  indeterminate: 'bg-slate-500',
  cleared: 'bg-slate-500',
};

const severityLabels: Record<Incident['severity'], string> = {
  critical: 'CRITICAL',
  major: 'MAJOR',
  minor: 'MINOR',
  warning: 'WARNING',
  indeterminate: 'INDETERMINATE',
  cleared: 'CLEARED',
};

export function IncidentBoard({
  data,
  isLoading,
  isError,
  selectedId,
  onSelect,
}: IncidentBoardProps) {
  const sortedIncidents = useMemo(() => {
    if (!data?.items) return [];
    return sortIncidents(data.items);
  }, [data?.items]);

  if (isLoading) {
    return (
      <div
        className="bg-slate-900 border border-slate-700 rounded-lg p-4"
        data-testid="loading-state"
      >
        Loading incidents…
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="bg-slate-900 border border-slate-700 rounded-lg p-4"
        data-testid="error-state"
      >
        Incident service unavailable
      </div>
    );
  }

  if (!data || sortedIncidents.length === 0) {
    return (
      <div
        className="bg-slate-900 border border-slate-700 rounded-lg p-4"
        data-testid="empty-state"
      >
        No incidents yet — run a scenario (e.g. make sim)
      </div>
    );
  }

  const stats = data.stats ?? { alarms: 0, incidents: 0, compressionRatio: 0 };
  const ratio = (stats.compressionRatio ?? 0).toFixed(1);

  return (
    <section className="bg-slate-900 border border-slate-700 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Incident board</h2>
        <div className="text-sm text-slate-400">
          {stats.alarms} alarms → {stats.incidents} incidents ({ratio}×)
        </div>
      </div>

      {selectedId && (
        <div className="flex items-center justify-between bg-slate-800 border border-slate-700 rounded-lg p-3">
          <span className="text-sm text-slate-300 font-mono">Showing alarms for {selectedId}</span>
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="text-sm text-sky-400 hover:text-sky-300 underline"
            data-testid="clear-filter"
          >
            Clear filter
          </button>
        </div>
      )}

      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {sortedIncidents.map((incident) => {
          const isSelected = selectedId === incident.id;
          const duration = durationLabel(incident.firstSeen, incident.lastSeen);
          return (
            <button
              key={incident.id}
              type="button"
              onClick={() => onSelect(isSelected ? null : incident.id)}
              aria-pressed={isSelected}
              data-testid={`incident-${incident.id}`}
              className={`
                bg-slate-900 border border-slate-700 rounded-lg p-4
                text-left transition-all
                ${isSelected ? 'ring-2 ring-sky-400 border-sky-500' : 'hover:border-slate-600'}
              `}
            >
              <div className="flex items-start justify-between gap-2 mb-3">
                <span
                  data-testid={`severity-${incident.id}`}
                  className={`
                    px-2 py-0.5 text-xs font-medium rounded text-white
                    ${severityStyles[incident.severity]}
                  `}
                >
                  {severityLabels[incident.severity]}
                </span>
                <span
                  data-testid={`status-${incident.id}`}
                  className={`
                    px-2 py-0.5 text-xs font-medium rounded
                    ${incident.status === 'open' ? 'bg-amber-500/20 text-amber-400' : 'bg-slate-700 text-slate-400'}
                  `}
                >
                  {incident.status === 'open' ? 'OPEN' : 'CLEARED'}
                </span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="font-mono text-slate-300">{incident.rootSiteId}</div>
                {incident.region && <div className="text-slate-400">{incident.region}</div>}
                <div className="text-slate-500">
                  {incident.alarmCount} alarms · {incident.siteIds?.length ?? 0} sites
                </div>
                <div className="text-slate-500 font-mono">{duration}</div>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
