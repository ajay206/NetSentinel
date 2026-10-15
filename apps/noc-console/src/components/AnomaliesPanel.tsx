import React from 'react';
import { Tip } from './ui/Tooltip';
import { TIPS } from '../lib/tooltips';
import { CardHeader } from './ui/Card';
import type { AnomalyItem, AnomalyList } from '../types.anomaly';
import { formatIST } from '../lib/time';

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
    let bg = 'bg-amber-500/15 text-amber-400';
    if (score >= 6) bg = 'bg-red-500/15 text-red-400';
    else if (score >= 4) bg = 'bg-orange-500/15 text-orange-400';

    const dirArrow = direction === 'high' ? '▲' : '▼';
    return (
      <span className="inline-flex items-center gap-1">
        <span className={`px-1.5 py-0.5 rounded ${bg} text-xs font-mono`}>
          z {score.toFixed(1)}
        </span>
        <span className={direction === 'high' ? 'text-red-400' : 'text-sky-400'}>{dirArrow}</span>
        <span className="text-slate-500">{method}</span>
      </span>
    );
  };

  return (
    <section className="ns-card text-xs">
      <header className="flex justify-between items-center mb-2">
        <div>
          <CardHeader
            title="Anomalies"
            subtitle="Cells whose KPI left its normal range (robust z-score + CUSUM)."
            info={TIPS.panelAnomalies}
          />
        </div>
        <div className="flex items-center gap-2">
          <select
            value={kpi}
            onChange={(e) => onKpiChange(e.target.value)}
            className="bg-slate-800 text-slate-200 border border-slate-600 rounded px-1 py-0.5 text-xs"
          >
            {KPI_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
          <span className="px-2 py-0.5 bg-slate-700 rounded text-slate-300 text-xs">{count}</span>
        </div>
      </header>

      {isLoading && <p className="text-slate-400">Loading…</p>}
      {isError && <p className="text-red-400">ml-service unreachable — run make ml</p>}
      {!isLoading && !isError && data && items.length === 0 && (
        <p className="text-slate-400">No anomalies in the last {data.hours ?? 24} h</p>
      )}
      {!isLoading && !isError && items.length > 0 && (
        <table className="w-full table-auto">
          <thead className="text-slate-400">
            <tr>
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
              <tr key={item.cellId + item.ts} className="border-t border-slate-700">
                <td>{item.cellId}</td>
                <td>{item.region}</td>
                <td>{formatIST(item.ts)}</td>
                <td>{renderBadge(item)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};
