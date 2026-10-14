import React, { useMemo } from 'react';
import { formatIST } from '../lib/time';
import { getSeverityStyles } from '../lib/severity';
import type { EnrichedAlarm } from '../types.enriched';
import type { ConnectionStatus } from '../hooks/useAlarmFeed';

interface EnrichedAlarmsProps {
  alarms: EnrichedAlarm[];
  status?: ConnectionStatus;
}

/** W4: alarms after alarm-ingest (normalised, enriched with topology, deduped, correlated). */
export const EnrichedAlarms: React.FC<EnrichedAlarmsProps> = ({ alarms, status }) => {
  const summary = useMemo(() => {
    const deduped = alarms.reduce((sum, a) => sum + Math.max(0, a.dedup.count - 1), 0);
    const groups = new Set(
      alarms.map((a) => a.correlation.groupId).filter((g): g is string => g !== null)
    ).size;
    return { total: alarms.length, deduped, groups };
  }, [alarms]);

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-slate-200 font-semibold">Enriched alarm feed</h2>
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
      </div>
      {alarms.length === 0 ? (
        <div className="py-6 text-center text-slate-500">
          <p>Waiting for enriched alarms — run `make ingest` and `make sim`</p>
        </div>
      ) : (
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-700">
                <th className="text-left py-1.5">Time (IST)</th>
                <th className="text-left py-1.5">Severity</th>
                <th className="text-left py-1.5">Site</th>
                <th className="text-left py-1.5">Region</th>
                <th className="text-left py-1.5">Node types</th>
                <th className="text-left py-1.5">Problem</th>
                <th className="text-left py-1.5">Dedup</th>
                <th className="text-left py-1.5">Correlation</th>
              </tr>
            </thead>
            <tbody>
              {alarms.map((a) => {
                const styles = getSeverityStyles(a.perceivedSeverity);
                return (
                  <tr
                    key={a.dedup.key}
                    className={`border-b border-slate-800 ${styles.rowBorder} hover:bg-slate-800/50`}
                  >
                    <td className="py-1.5 pl-2 text-slate-400 font-mono">
                      {formatIST(a.alarmRaisedTime)}
                    </td>
                    <td className="py-1.5">
                      <span className={`inline-flex px-1.5 rounded ${styles.badge}`}>
                        {a.perceivedSeverity}
                      </span>
                    </td>
                    <td className="py-1.5 text-slate-300">
                      <div>{a.siteId}</div>
                      {a.enrichment.siteName && (
                        <div className="text-slate-500">{a.enrichment.siteName}</div>
                      )}
                    </td>
                    <td className="py-1.5 text-slate-300">{a.enrichment.region}</td>
                    <td className="py-1.5 text-slate-400">
                      {a.enrichment.nodeTypes.join(', ') || '—'}
                    </td>
                    <td className="py-1.5 text-slate-400">{a.specificProblem}</td>
                    <td className="py-1.5">
                      {a.dedup.count > 1 ? (
                        <span className="px-1.5 rounded bg-violet-500/15 text-violet-300">
                          ×{a.dedup.count}
                        </span>
                      ) : (
                        <span className="text-slate-600">1</span>
                      )}
                    </td>
                    <td className="py-1.5">
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
