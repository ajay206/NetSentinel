import React from 'react';
import { KpiCell, KpiSeries, KpiName, KPI_META } from '../types.kpi';
import { formatIST } from '../lib/time';
import { buildPath } from '../lib/chart';

interface Props {
  cells: KpiCell[];
  series: KpiSeries | undefined;
  isLoading: boolean;
  isError: boolean;
  cellId: string | null;
  onCellChange: (id: string) => void;
  kpi: KpiName;
  onKpiChange: (k: KpiName) => void;
  agg: '15m' | '1h' | '1d';
  onAggChange: (a: '15m' | '1h' | '1d') => void;
  hours: number;
  onHoursChange: (h: number) => void;
}

export const KpiCharts: React.FC<Props> = ({
  cells,
  series,
  isLoading,
  isError,
  cellId,
  onCellChange,
  kpi,
  onKpiChange,
  agg,
  onAggChange,
  hours,
  onHoursChange,
}) => {
  const values = series?.points.map(p => p[kpi]) ?? [];

  const { d, min, max } = buildPath(values, 600, 160);

  const lastPoint = series?.points[series.points.length - 1];
  const lastValue = lastPoint ? lastPoint[kpi] : null;

  const meta = KPI_META[kpi];

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-slate-200">
      <h2 className="text-slate-200 font-semibold mb-2">KPI charts</h2>
      <div className="flex flex-wrap gap-2 mb-4">
        <select
          className="bg-slate-800 text-slate-200 text-xs p-1 rounded"
          value={cellId ?? ''}
          onChange={e => onCellChange(e.target.value)}
        >
          {cells.map(c => (
            <option key={c.cellId} value={c.cellId}>
              {c.cellId} · {c.region}
            </option>
          ))}
        </select>

        <select
          className="bg-slate-800 text-slate-200 text-xs p-1 rounded"
          value={kpi}
          onChange={e => onKpiChange(e.target.value as KpiName)}
        >
          {Object.entries(KPI_META).map(([key, { label }]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>

        <select
          className="bg-slate-800 text-slate-200 text-xs p-1 rounded"
          value={agg}
          onChange={e => onAggChange(e.target.value as '15m' | '1h' | '1d')}
        >
          <option value="15m">15m</option>
          <option value="1h">1h</option>
          <option value="1d">1d</option>
        </select>

        <select
          className="bg-slate-800 text-slate-200 text-xs p-1 rounded"
          value={hours}
          onChange={e => onHoursChange(Number(e.target.value))}
        >
          <option value={6}>6h</option>
          <option value={24}>24h</option>
          <option value={168}>7d</option>
        </select>
      </div>

      {isError ? (
        <div className="text-red-400">kpi-service unreachable</div>
      ) : isLoading ? (
        <div className="text-slate-400">Loading…</div>
      ) : !series || series.points.length === 0 ? (
        <div className="text-slate-400">
          No KPI data yet — run make kpi-service and make kpis
        </div>
      ) : (
        <div>
          <div className="flex gap-3 text-xs text-slate-400 mb-1" data-testid="kpi-stats">
            <span>min {min !== null ? min.toFixed(2) : '–'} {meta.unit}</span>
            <span>max {max !== null ? max.toFixed(2) : '–'} {meta.unit}</span>
            <span className="text-slate-200">
              last {lastValue !== null && lastValue !== undefined ? lastValue.toFixed(2) : '–'}{' '}
              {meta.unit}
            </span>
            <span className="ml-auto">{series.points.length} points · {series.agg}</span>
          </div>
          <svg
            className="w-full h-40 bg-slate-950/40 rounded"
            viewBox="0 0 600 160"
            preserveAspectRatio="none"
            role="img"
            aria-label={`${meta.label} for ${series.cellId}`}
          >
            <path d={d} fill="none" stroke="#38bdf8" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          </svg>
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>{formatIST(series.from)}</span>
            <span>{formatIST(series.to)}</span>
          </div>
        </div>
      )}
    </div>
  );
};
