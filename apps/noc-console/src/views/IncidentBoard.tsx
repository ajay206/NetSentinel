import type React from 'react';
import { useMemo } from 'react';
import { sortIncidents, durationLabel } from '../lib/incidents';
import type { IncidentList } from '../types.incident';
import { Card, SeverityChip, StateMessage } from '../components/ui/Card';

interface IncidentBoardProps {
  data?: IncidentList;
  isLoading: boolean;
  isError: boolean;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Step 13b: workflow panel for the selected incident (actions hidden for viewers). */
  selectedFooter?: React.ReactNode;
}

const TITLE = 'Incident board';
const SUBTITLE = 'Related alarms grouped into incidents. Click one to filter the alarm feeds.';
const INFO =
  'incident-service groups alarms that are close in time (5 min) and in the network topology. ' +
  'The root site is the affected site closest to the core.';

const ROW = 'grid grid-cols-[5.75rem_6rem_minmax(0,1fr)_4rem_4.5rem] items-center gap-2';

export function IncidentBoard({
  data,
  isLoading,
  isError,
  selectedId,
  onSelect,
  selectedFooter,
}: IncidentBoardProps) {
  const sortedIncidents = useMemo(() => {
    if (!data?.items) return [];
    return sortIncidents(data.items);
  }, [data?.items]);

  if (isLoading) {
    return (
      <Card title={TITLE} subtitle={SUBTITLE} info={INFO} testId="loading-state">
        <StateMessage kind="loading">Loading incidents…</StateMessage>
      </Card>
    );
  }
  if (isError) {
    return (
      <Card title={TITLE} subtitle={SUBTITLE} info={INFO} testId="error-state">
        <StateMessage kind="error">Incident service unavailable</StateMessage>
      </Card>
    );
  }
  if (!data || sortedIncidents.length === 0) {
    return (
      <Card title={TITLE} subtitle={SUBTITLE} info={INFO} testId="empty-state">
        <StateMessage kind="empty">No incidents yet — run a scenario (e.g. make sim)</StateMessage>
      </Card>
    );
  }

  const stats = data.stats ?? { alarms: 0, incidents: 0, compressionRatio: 0 };
  const ratio = (stats.compressionRatio ?? 0).toFixed(1);

  return (
    <Card
      title={TITLE}
      subtitle={SUBTITLE}
      info={INFO}
      testId="incident-board"
      actions={
        <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300 tabular-nums whitespace-nowrap">
          {stats.alarms} alarms → {stats.incidents} incidents ({ratio}×)
        </span>
      }
    >
      <div className="flex h-full min-h-0 flex-col gap-2">
        {selectedId && (
          <div className="flex items-center justify-between rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2">
            <span className="font-mono text-xs text-sky-200">Showing alarms for {selectedId}</span>
            <button
              type="button"
              onClick={() => onSelect(null)}
              className="text-xs font-medium text-sky-300 hover:text-sky-200 underline"
              data-testid="clear-filter"
            >
              Clear filter
            </button>
          </div>
        )}
        {selectedId && selectedFooter && (
          <div className="rounded-lg border border-slate-700 bg-slate-950/60 p-3">
            {selectedFooter}
          </div>
        )}
        <div className={`${ROW} ns-thead px-3 py-1.5`} role="row">
          <span>Severity</span>
          <span>Root site</span>
          <span>Size</span>
          <span>Duration</span>
          <span>Status</span>
        </div>
        <ul className="ns-scroll space-y-1">
          {sortedIncidents.map((incident) => {
            const isSelected = selectedId === incident.id;
            return (
              <li key={incident.id}>
                <button
                  type="button"
                  onClick={() => onSelect(isSelected ? null : incident.id)}
                  aria-pressed={isSelected}
                  data-testid={`incident-${incident.id}`}
                  title={`${incident.id}: click to ${isSelected ? 'clear the filter' : 'filter the alarm feeds'}`}
                  className={`${ROW} w-full rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                    isSelected
                      ? 'bg-sky-500/10 ring-2 ring-sky-400'
                      : 'bg-slate-800/40 hover:bg-slate-800'
                  }`}
                >
                  <span data-testid={`severity-${incident.id}`} className="inline-flex">
                    <SeverityChip severity={incident.severity} />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-mono text-slate-200">
                      {incident.rootSiteId}
                    </span>
                    {incident.region && (
                      <span className="block truncate text-slate-500">{incident.region}</span>
                    )}
                  </span>
                  <span className="text-slate-400 tabular-nums">
                    {incident.alarmCount} {incident.alarmCount === 1 ? 'alarm' : 'alarms'} ·{' '}
                    {incident.siteIds?.length ?? 0}{' '}
                    {(incident.siteIds?.length ?? 0) === 1 ? 'site' : 'sites'}
                  </span>
                  <span className="font-mono text-slate-400">
                    {durationLabel(incident.firstSeen, incident.lastSeen)}
                  </span>
                  <span
                    data-testid={`status-${incident.id}`}
                    className={`w-fit rounded px-1.5 py-0.5 text-[11px] font-medium ${
                      incident.status === 'open'
                        ? 'bg-amber-500/20 text-amber-300'
                        : 'bg-slate-700 text-slate-400'
                    }`}
                  >
                    {incident.workflow?.state === 'resolved'
                      ? 'RESOLVED'
                      : incident.workflow?.state === 'acknowledged'
                        ? 'ACK'
                        : incident.status === 'open'
                          ? 'OPEN'
                          : 'CLEARED'}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </Card>
  );
}
