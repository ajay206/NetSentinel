import React from 'react';
import { Tip } from './ui/Tooltip';
import { TIPS } from '../lib/tooltips';
import { CardHeader } from './ui/Card';
import type { AnomalyItem, AnomalyList } from '../types.anomaly';
import { formatIST } from '../lib/time';
import { KPI_META } from '../types.kpi';

type Props = {
  data: AnomalyList | undefined;
  isLoading: boolean;
  isError: boolean;
  kpi: string;
  onKpiChange: (k: string) => void;
};

const KPI_OPTIONS = [
  'dlThroughputMbps',
  'prbUtilPct',
  'rrcSetupSuccessPct',
  'dropCallRatePct',
  'availabilityPct',
] as const;

export const AnomaliesPanel: React.FC<Props> = ({ data, isLoading, isError, kpi, onKpiChange }) => {
  const items = Array.isArray(data?.items) ? data.items : [];
  const count = items.length;

  const renderBadge = (item: AnomalyItem) => {
    const { score, method, direction } = item;
    let bg = 'bg-amber-500/15 text-amber-700';
    if (score >= 6) bg = 'bg-red-500/15 text-red-700';
    else if (score >= 4) bg = 'bg-orange-500/15 text-orange-700';

    const dirArrow = direction === 'high' ? '▲' : '▼';
    return (
      <span className="inline-flex items-center gap-1">
        <span className={`px-1.5 py-0.5 rounded ${bg} text-xs font-mono`}>
          z {score.toFixed(1)}
        </span>
        <span className={direction === 'high' ? 'text-red-700' : 'text-sky-700'}>{dirArrow}</span>
        <span className="text-slate-600">{method}</span>
      </span>
    );
  };

  return (
    <section className="ns-card text-xs">
      <CardHeader
        title="Unusual readings"
        subtitle="Cells where a performance measurement moved well outside its usual range."
        info={TIPS.panelAnomalies}
        actions={
          <div className="flex w-full items-center gap-2 sm:w-auto">
          <select
            aria-label="KPI"
            value={kpi}
            onChange={(e) => onKpiChange(e.target.value)}
            className="ns-control w-full sm:w-56"
          >
            {KPI_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {KPI_META[opt].label}
              </option>
            ))}
          </select>
          <span className="shrink-0 rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-bold text-slate-700">{count}</span>
        </div>
        }
      />

      {isLoading && <p className="text-bento-muted">Loading…</p>}
      {isError && <p className="text-red-700">Performance analysis is unavailable right now.</p>}
      {!isLoading && !isError && data && items.length === 0 && (
        <p className="text-bento-muted">No anomalies in the last {data.hours ?? 24} h</p>
      )}
      {!isLoading && !isError && items.length > 0 && (
        <div className="ns-table-wrap"><table className="w-full table-auto">
          <thead>
            <tr className="ns-thead">
              <th className="text-left">
                <Tip tip={TIPS.colCell}>Cell</Tip>
              </th>
              <th className="text-left">
                <Tip tip={TIPS.colRegion}>Region</Tip>
              </th>
              <th className="text-left">
                <Tip tip={TIPS.colTime}>Time</Tip>
              </th>
              <th className="text-left">
                <Tip tip={TIPS.colScore}>Score</Tip>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.cellId + item.ts} className="border-t border-bento-border">
                <td className="whitespace-nowrap font-mono">{item.cellId}</td>
                <td>{item.region}</td>
                <td className="whitespace-nowrap">{formatIST(item.ts)}</td>
                <td className="whitespace-nowrap">{renderBadge(item)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
    </section>
  );
};
