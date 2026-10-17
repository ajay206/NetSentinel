import React from 'react';
import { TIPS } from '../lib/tooltips';
import { CardHeader } from './ui/Card';
import { KpiCell, KpiSeries, KpiName, KPI_META } from '../types.kpi';
import { formatIST } from '../lib/time';
import { anomalyIndices, buildPath, pointPosition } from '../lib/chart';

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
  /** W6: anomaly timestamps from ml-service, drawn as red dots. */
  anomalyTs?: string[];
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
  anomalyTs = [],
}) => {
  const values = series?.points.map((p) => p[kpi]) ?? [];

  const { d, min, max } = buildPath(values, 600, 160);
  const marks = anomalyIndices(series?.points.map((p) => p.ts) ?? [], anomalyTs)
    .map((i) => pointPosition(values, i, 600, 160))
    .filter((p): p is { x: number; y: number } => p !== null);

  const lastPoint = series?.points[series.points.length - 1];
  const lastValue = lastPoint ? lastPoint[kpi] : null;

  const meta = KPI_META[kpi];

  return (
    <div className="ns-card text-navy">
      <CardHeader
        title="Performance trends"
        subtitle="Choose a measurement, cell, and time period. Red dots mark unusual readings."
        info={TIPS.panelKpis}
        actions={
          marks.length > 0 && (
            <span
              data-testid="anomaly-badge"
              className="rounded-full bg-red-500/15 px-2.5 py-0.5 text-xs font-bold text-red-700"
            >
              {marks.length} anomal{marks.length === 1 ? 'y' : 'ies'}
            </span>
          )
        }
      />
      <div className="mb-4 grid min-w-0 grid-cols-2 gap-3 sm:grid-cols-[minmax(0,1.5fr)_minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <select
          className="ns-control w-full"
          value={cellId ?? ''}
          onChange={(e) => onCellChange(e.target.value)}
        >
          {cells.map((c) => (
            <option key={c.cellId} value={c.cellId}>
              {c.cellId} · {c.region}
            </option>
          ))}
        </select>

        <select
          className="ns-control w-full"
          value={kpi}
          onChange={(e) => onKpiChange(e.target.value as KpiName)}
        >
          {Object.entries(KPI_META).map(([key, { label }]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>

        <select
          className="ns-control w-full"
          value={agg}
          onChange={(e) => onAggChange(e.target.value as '15m' | '1h' | '1d')}
        >
          <option value="15m">15m</option>
          <option value="1h">1h</option>
          <option value="1d">1d</option>
        </select>

        <select
          className="ns-control w-full"
          value={hours}
          onChange={(e) => onHoursChange(Number(e.target.value))}
        >
          <option value={6}>6h</option>
          <option value={24}>24h</option>
          <option value={168}>7d</option>
        </select>
      </div>

      {isError ? (
        <div className="text-red-400">kpi-service unreachable</div>
      ) : isLoading ? (
        <div className="text-bento-muted">Loading…</div>
      ) : !series || series.points.length === 0 ? (
        <div className="text-bento-muted">No KPI data yet — run make kpi-service and make kpis</div>
      ) : (
        <div>
          <div className="flex gap-3 text-xs text-bento-muted mb-1" data-testid="kpi-stats">
            <span>
              min {min !== null ? min.toFixed(2) : '–'} {meta.unit}
            </span>
            <span>
              max {max !== null ? max.toFixed(2) : '–'} {meta.unit}
            </span>
            <span className="text-navy">
              last {lastValue !== null && lastValue !== undefined ? lastValue.toFixed(2) : '–'}{' '}
              {meta.unit}
            </span>
            <span className="ml-auto">
              {series.points.length} points · {series.agg}
            </span>
          </div>
          <svg
            className="w-full h-40 bg-bento-bg rounded border border-bento-border"
            viewBox="0 0 600 160"
            preserveAspectRatio="none"
            role="img"
            aria-label={`${meta.label} for ${series.cellId}`}
          >
            <path
              d={d}
              fill="none"
              stroke="#1677A0"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
            {marks.map((m, i) => (
              <circle
                key={i}
                data-testid="anomaly-mark"
                cx={m.x}
                cy={m.y}
                r={4}
                fill="#f87171"
                stroke="#FFFFFF"
              />
            ))}
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
