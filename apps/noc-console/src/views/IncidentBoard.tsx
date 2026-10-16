import type React from 'react';
import { TIPS } from '../lib/tooltips';
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
const INFO = TIPS.panelIncidents;

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
        <span className="rounded-full bg-bento-bg px-2.5 py-0.5 text-xs font-bold text-navy tabular-nums whitespace-nowrap">
          {stats.alarms} alarms → {stats.incidents} incidents ({ratio}×)
        </span>
      }
    >
      <div className="flex h-full min-h-0 flex-col gap-2">
        {selectedId && (
          <div className="flex items-center justify-between rounded-xl border border-sky-300 bg-cyan/15 px-3 py-2">
            <span className="font-mono text-xs font-bold text-navy">Showing alarms for {selectedId}</span>
            <button
              type="button"
              onClick={() => onSelect(null)}
              className="text-xs font-bold text-sky-800 hover:underline"
              data-testid="clear-filter"
            >
              Clear filter
            </button>
          </div>
        )}
        {selectedId && selectedFooter && (
          <div className="rounded-xl border border-bento-border bg-bento-bg p-3">
            {selectedFooter}
          </div>
        )}
        <div className={`${ROW} ns-thead px-3 py-1.5`} role="row">
          <span>Site</span>
          <span>Severity</span>
          <span>Alarms</span>
          <span>Scope</span>
          <span>Duration</span>
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
                  className={`${ROW} w-full rounded-xl px-3 py-2.5 text-left text-xs transition-colors border-t border-bento-border first:border-0 ${
                    isSelected
                      ? 'bg-cyan/20 ring-2 ring-cyan'
                      : 'hover:bg-bento-bg'
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-mono font-extrabold text-sm text-navy">
                      {incident.rootSiteId}
                    </span>
                  </span>
                  <span data-testid={`severity-${incident.id}`} className="inline-flex">
                    <SeverityChip severity={incident.severity} />
                  </span>
                  <span className="inline-flex items-center justify-center min-w-[28px] h-7 px-2 rounded-lg bg-bento-bg font-display font-extrabold text-navy">
                    {incident.alarmCount}
                  </span>
                  <span className="text-bento-muted font-medium truncate">
                    {(incident.siteIds?.length ?? 0) === 1
                      ? 'at 1 site'
                      : `across ${incident.siteIds?.length ?? 0} sites`}
                  </span>
                  <span className="font-mono text-bento-muted font-semibold">
                    {durationLabel(incident.firstSeen, incident.lastSeen)}
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
