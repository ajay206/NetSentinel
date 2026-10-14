import React from 'react';
import { card } from '../theme';
import { InfoTip } from './ui/Card';

export interface KpiSummaryProps {
  activeAlarms: number;
  criticalAlarms: number;
  openIncidents: number;
  compressionRatio: number | null;
  anomalies: number;
  servicesUp: number;
  servicesTotal: number;
}

interface Tile {
  id: string;
  label: string;
  value: string;
  hint: string;
  info: string;
  tone: string;
}

/** Top-of-page summary: the five numbers an operator checks first. */
export const KpiSummary: React.FC<KpiSummaryProps> = ({
  activeAlarms,
  criticalAlarms,
  openIncidents,
  compressionRatio,
  anomalies,
  servicesUp,
  servicesTotal,
}) => {
  const healthUnknown = servicesTotal === 0;
  const allUp = !healthUnknown && servicesUp === servicesTotal;
  const tiles: Tile[] = [
    {
      id: 'alarms',
      label: 'Active alarms',
      value: String(activeAlarms),
      hint: `${criticalAlarms} critical`,
      info: 'Alarms in the live feed that are not cleared yet.',
      tone: criticalAlarms > 0 ? 'text-red-300' : 'text-slate-100',
    },
    {
      id: 'incidents',
      label: 'Open incidents',
      value: String(openIncidents),
      hint: 'Related alarms grouped by topology',
      info: 'The incident service groups alarms that are close in time and in the network.',
      tone: openIncidents > 0 ? 'text-orange-300' : 'text-slate-100',
    },
    {
      id: 'compression',
      label: 'Alarm compression',
      value:
        compressionRatio != null && Number.isFinite(compressionRatio)
          ? `${compressionRatio.toFixed(1)}×`
          : '—',
      hint: 'Alarms per incident',
      info: 'How many alarms each incident replaces. Higher means less noise for the operator.',
      tone: 'text-slate-100',
    },
    {
      id: 'anomalies',
      label: 'KPI anomalies (24h)',
      value: String(anomalies),
      hint: 'Cells outside their normal baseline',
      info: 'Cells whose KPIs moved far from their learned baseline in the last 24 hours.',
      tone: anomalies > 0 ? 'text-amber-300' : 'text-slate-100',
    },
    {
      id: 'services',
      label: 'Services healthy',
      value: `${servicesUp}/${servicesTotal}`,
      hint: healthUnknown ? 'Waiting for health' : allUp ? 'All systems go' : 'Check service health',
      info: 'Backend services reporting healthy to the API gateway.',
      tone: healthUnknown ? 'text-slate-100' : allUp ? 'text-emerald-300' : 'text-amber-300',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5" data-testid="kpi-summary">
      {tiles.map((t) => (
        <div key={t.id} className={`${card} p-4`} data-testid={`kpi-${t.id}`}>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              {t.label}
            </span>
            <InfoTip text={t.info} />
          </div>
          <div className={`mt-1 text-2xl font-semibold tabular-nums ${t.tone}`}>{t.value}</div>
          <div className="mt-0.5 truncate text-xs text-slate-500">{t.hint}</div>
        </div>
      ))}
    </div>
  );
};
