import React, { useMemo } from 'react';
import { Tip } from './ui/Tooltip';
import { TIPS } from '../lib/tooltips';
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
      alarms.map((a) => a.correlation.groupId).filter((g): g is string => g !== null),
    ).size;
    return { total: alarms.length, deduped, groups };
  }, [alarms]);

  return (
    <div className="ns-card">
      <CardHeader
        title="Enriched alarm feed"
        subtitle="Alarms after de-duplication and topology enrichment. Click a row to diagnose it."
        info={TIPS.panelEnriched}
        actions={
          <div className="flex flex-wrap gap-2 whitespace-nowrap text-xs" data-testid="enriched-summary">
            {status && (
              <span
                className={`px-2.5 py-0.5 rounded-full font-bold ${
                  status === 'open'
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-red-100 text-red-700'
                }`}
              >
                {status === 'open' ? 'live' : status}
              </span>
            )}
            <span className="px-2.5 py-0.5 rounded-full bg-bento-bg font-bold text-navy">
              Alarms {summary.total}
            </span>
            <span className="px-2.5 py-0.5 rounded-full bg-bento-bg font-bold text-navy">
              Deduped {summary.deduped}
            </span>
            <span className="px-2.5 py-0.5 rounded-full bg-bento-bg font-bold text-navy">
              Groups {summary.groups}
            </span>
          </div>
        }
      />
      {alarms.length === 0 ? (
        <div className="flex flex-1 items-center justify-center py-8 text-sm text-bento-muted font-medium">
          <p>Waiting for enriched alarms — run `make ingest` and `make sim`</p>
        </div>
      ) : (
        <div className="ns-table-wrap">
          <table className="w-full text-xs">
            <thead>
              <tr className="ns-thead">
                <th className="font-extrabold">
                  <Tip tip={TIPS.colTime}>Time (IST)</Tip>
                </th>
                <th className="font-extrabold">
                  <Tip tip={TIPS.colSeverity}>Severity</Tip>
                </th>
                <th className="font-extrabold">
                  <Tip tip={TIPS.colSite}>Site</Tip>
                </th>
                <th className="font-extrabold">
                  <Tip tip={TIPS.colRegion}>Region</Tip>
                </th>
                <th className="font-extrabold">
                  <Tip tip={TIPS.colNodeTypes}>Node types</Tip>
                </th>
                <th className="font-extrabold">
                  <Tip tip={TIPS.colProblem}>Problem</Tip>
                </th>
                <th className="font-extrabold">
                  <Tip tip={TIPS.colRepeats}>Repeats</Tip>
                </th>
                <th className="font-extrabold">
                  <Tip tip={TIPS.colRootSymptom}>Root / symptom</Tip>
                </th>
              </tr>
            </thead>
            <tbody>
              {alarms.map((a) => {
                return (
                  <tr
                    key={a.dedup.key}
                    onClick={onSelect ? () => onSelect(a) : undefined}
                    aria-selected={selectedKey === a.dedup.key}
                    className={`border-b border-bento-border hover:bg-bento-bg/80 ${
                      onSelect ? 'cursor-pointer' : ''
                    } ${selectedKey === a.dedup.key ? 'bg-cyan/15 font-semibold' : ''}`}
                  >
                    <td className="whitespace-nowrap text-bento-muted font-mono font-medium">
                      {formatIST(a.alarmRaisedTime)}
                    </td>
                    <td>
                      <SeverityChip severity={a.perceivedSeverity} />
                    </td>
                    <td className="text-navy font-bold font-display">
                      <div>{a.siteId}</div>
                      {a.enrichment.siteName && (
                        <div className="text-bento-muted font-sans font-normal text-[11px]">{a.enrichment.siteName}</div>
                      )}
                    </td>
                    <td className="text-navy font-medium">{a.enrichment.region}</td>
                    <td className="text-bento-muted">
                      {a.enrichment.nodeTypes.join(', ') || '—'}
                    </td>
                    <td className="min-w-[14rem] text-navy font-medium">
                      <div>{a.specificProblem}</div>
                      {selectedKey === a.dedup.key && selectedBadge}
                    </td>
                    <td>
                      {a.dedup.count > 1 ? (
                        <span className="px-2 py-0.5 rounded-md bg-bento-bg font-extrabold text-navy font-display">
                          ×{a.dedup.count}
                        </span>
                      ) : (
                        <span className="text-bento-muted">—</span>
                      )}
                    </td>
                    <td>
                      {a.correlation.role === 'root' && (
                        <span className="text-red-600 font-bold">root</span>
                      )}
                      {a.correlation.role === 'symptom' && (
                        <span className="text-navy font-medium">↳ {a.correlation.rootSiteId}</span>
                      )}
                      {a.correlation.role === 'none' && <span className="text-bento-muted">—</span>}
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
