import React, { useMemo } from 'react';
import { CardHeader, SeverityChip } from './ui/Card';
import { formatIST } from '../lib/time';
import type { EnrichedAlarm } from '../types.enriched';
import type { ConnectionStatus } from '../hooks/useAlarmFeed';

interface EnrichedAlarmsProps {
  alarms: EnrichedAlarm[];
  status?: ConnectionStatus;
  /** W7: click a row to classify it and open the SHAP drawer. */
  selectedKey?: string | null;
  onSelect?: (alarm: EnrichedAlarm) => void;
  selectedBadge?: React.ReactNode;
}

/** W4: alarms after alarm-ingest (normalised, enriched with topology, deduped, correlated). */
export const EnrichedAlarms: React.FC<EnrichedAlarmsProps> = ({
  alarms,
  status,
  selectedKey = null,
  onSelect,
  selectedBadge,
}) => {
  const summary = useMemo(() => {
    const deduped = alarms.reduce((sum, a) => sum + Math.max(0, a.dedup.count - 1), 0);
    const groups = new Set(
      alarms.map((a) => a.correlation.groupId).filter((g): g is string => g !== null)
    ).size;
    return { total: alarms.length, deduped, groups };
  }, [alarms]);

  return (
    <div className="ns-card">
      <CardHeader
        title="Enriched alarm feed"
        subtitle="Alarms after de-duplication and topology enrichment. Click a row to diagnose it."
        info="alarm-ingest adds the site name, region and equipment, merges duplicates (×N) and marks the root alarm of each correlated group (↳ points to the root site)."
        actions={
        <div className="flex gap-2 text-xs" data-testid="enriched-summary">
          {status && (
            <span
              className={`px-2 py-0.5 rounded ${
                status === 'open' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'
              }`}
            >
              {status === 'open' ? 'live' : status}
            </span>
          )}
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
            Alarms {summary.total}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
            Deduped {summary.deduped}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
            Groups {summary.groups}
          </span>
        </div>
        }
      />
      {alarms.length === 0 ? (
        <div className="flex flex-1 items-center justify-center py-8 text-sm text-slate-400">
          <p>Waiting for enriched alarms — run `make ingest` and `make sim`</p>
        </div>
      ) : (
        <div className="ns-scroll">
          <table className="w-full text-xs">
            <thead>
              <tr className="ns-thead">
                <th className="py-2 pl-2 pr-3 font-medium">Time (IST)</th>
                <th className="py-2 pr-3 font-medium">Severity</th>
                <th className="py-2 pr-3 font-medium">Site</th>
                <th className="py-2 pr-3 font-medium">Region</th>
                <th className="py-2 pr-3 font-medium">Node types</th>
                <th className="py-2 pr-3 font-medium">Problem</th>
                <th className="py-2 pr-3 font-medium">Repeats</th>
                <th className="py-2 pr-3 font-medium">Root / symptom</th>
              </tr>
            </thead>
            <tbody>
              {alarms.map((a) => {
                return (
                  <tr
                    key={a.dedup.key}
                    onClick={onSelect ? () => onSelect(a) : undefined}
                    aria-selected={selectedKey === a.dedup.key}
                    className={`border-b border-slate-800 hover:bg-slate-800/50 ${
                      onSelect ? 'cursor-pointer' : ''
                    } ${selectedKey === a.dedup.key ? 'bg-slate-800/70' : ''}`}
                  >
                    <td className="py-2 pl-2 pr-3 whitespace-nowrap text-slate-400 font-mono">
                      {formatIST(a.alarmRaisedTime)}
                    </td>
                    <td className="py-2 pr-3">
                      <SeverityChip severity={a.perceivedSeverity} />
                    </td>
                    <td className="py-2 pr-3 text-slate-300">
                      <div>{a.siteId}</div>
                      {a.enrichment.siteName && (
                        <div className="text-slate-500">{a.enrichment.siteName}</div>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-slate-300">{a.enrichment.region}</td>
                    <td className="py-2 pr-3 text-slate-400">
                      {a.enrichment.nodeTypes.join(', ') || '—'}
                    </td>
                    <td className="py-2 pr-3 text-slate-400">
                      <div>{a.specificProblem}</div>
                      {selectedKey === a.dedup.key && selectedBadge}
                    </td>
                    <td className="py-2 pr-3">
                      {a.dedup.count > 1 ? (
                        <span className="px-1.5 rounded bg-violet-500/15 text-violet-300">
                          ×{a.dedup.count}
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      {a.correlation.role === 'root' && (
                        <span className="text-red-400 font-medium">root</span>
                      )}
                      {a.correlation.role === 'symptom' && (
                        <span className="text-slate-300">↳ {a.correlation.rootSiteId}</span>
                      )}
                      {a.correlation.role === 'none' && (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
