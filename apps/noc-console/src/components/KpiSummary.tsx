import React from 'react';
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

type Tile = {
  testId: string;
  label: string;
  tip: string;
  value: React.ReactNode;
  sub: React.ReactNode;
  /** soft tint + accent */
  tint: string;
  accent: string;
  iconBg: string;
  icon: string;
};

/** Top-of-page summary bento grid: navy hero + tinted secondary KPIs. */
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
  const majorAlarms = Math.max(0, activeAlarms - criticalAlarms);

  const tiles: Tile[] = [
    {
      testId: 'kpi-incidents',
      label: 'Open Incidents',
      tip: 'The incident service groups alarms that are close in time and in the network.',
      value: openIncidents,
      sub: 'awaiting triage',
      tint: 'bg-[#E8F7FC]',
      accent: 'border-l-[#3BA8D4]',
      iconBg: 'bg-[#3BA8D4]/15 text-[#0E6A94]',
      icon: '◈',
    },
    {
      testId: 'kpi-compression',
      label: 'Alarm Compression',
      tip: 'How many alarms each incident replaces. Higher means less noise for the operator.',
      value:
        compressionRatio != null && Number.isFinite(compressionRatio)
          ? `${compressionRatio.toFixed(1)}×`
          : '—',
      sub: 'noise reduced',
      tint: 'bg-[#F3EEFF]',
      accent: 'border-l-[#7C3AED]',
      iconBg: 'bg-[#7C3AED]/15 text-[#5B21B6]',
      icon: '◎',
    },
    {
      testId: 'kpi-anomalies',
      label: 'KPI Anomalies',
      tip: 'Cells whose KPIs moved far from their learned baseline in the last 24 hours.',
      value: anomalies,
      sub: 'last 15 min',
      tint: 'bg-[#FFECE8]',
      accent: 'border-l-[#F97316]',
      iconBg: 'bg-[#F97316]/15 text-[#C2410C]',
      icon: '▴',
    },
    {
      testId: 'kpi-services',
      label: 'Services Healthy',
      tip: 'Backend services reporting healthy to the API gateway.',
      value: `${servicesUp}/${servicesTotal}`,
      sub: (
        <span className={`font-bold ${healthUnknown ? 'text-bento-muted' : allUp ? 'text-emerald-700' : 'text-amber-700'}`}>
          {healthUnknown ? 'Waiting for health' : allUp ? 'all green' : 'check health'}
        </span>
      ),
      tint: 'bg-[#E6F7F4]',
      accent: 'border-l-[#0D9488]',
      iconBg: 'bg-[#0D9488]/15 text-[#0F766E]',
      icon: '●',
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 lg:gap-6 xl:grid-cols-3" data-testid="kpi-summary">
      <div
        className="relative overflow-hidden rounded-[20px] bg-gradient-to-br from-[#09254A] via-[#0E3A6B] to-[#12507A] p-5 lg:p-6 text-white shadow-sm flex flex-col justify-between min-h-[160px] xl:row-span-2"
        data-testid="kpi-alarms"
      >
        <div className="absolute right-[-40px] bottom-[-40px] w-[180px] h-[180px] rounded-full bg-[radial-gradient(circle,rgba(109,207,246,0.35)_0%,transparent_70%)] pointer-events-none" />
        <div className="absolute left-[-20px] top-[-20px] w-[100px] h-[100px] rounded-full bg-[radial-gradient(circle,rgba(255,138,138,0.25)_0%,transparent_70%)] pointer-events-none" />
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-white/80">
              Active Alarms
            </span>
            <InfoTip text="Alarms in the live feed that are not cleared yet." />
          </div>
          <div className="font-display text-[52px] font-extrabold tracking-tight leading-none my-1.5 tabular-nums">
            {activeAlarms}
          </div>
          <div className="text-sm text-white/85 font-medium">
            <span className="text-[#FFB4B4] font-extrabold">{criticalAlarms} critical</span>
            {' · '}
            {majorAlarms} major
          </div>
        </div>
        {activeAlarms > 0 ? (
          <div className="inline-flex self-start mt-3 rounded-full bg-cyan/25 border border-cyan/50 px-3 py-1 text-xs font-bold text-white z-10">
            Alarm storm in progress
          </div>
        ) : (
          <div className="inline-flex self-start mt-3 rounded-full bg-white/10 border border-white/25 px-3 py-1 text-xs font-bold text-white/85 z-10">
            No active alarms
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:gap-6 xl:col-span-2">
        {tiles.map((tile) => (
          <div
            key={tile.testId}
            className={`relative overflow-hidden rounded-[20px] ${tile.tint} p-4 sm:p-5 lg:p-6 shadow-sm flex flex-col justify-center gap-2 border-l-4 ${tile.accent}`}
            data-testid={tile.testId}
          >
            <div className="flex items-center justify-between pl-2 gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span
                  className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg text-sm font-extrabold ${tile.iconBg}`}
                  aria-hidden
                >
                  {tile.icon}
                </span>
                <span className="text-[11px] font-bold uppercase leading-snug tracking-wider text-navy/70" title={tile.label}>
                  {tile.label}
                </span>
              </div>
              <InfoTip text={tile.tip} />
            </div>
            <div className="pl-2 font-display text-[32px] font-extrabold tracking-tight text-navy leading-tight tabular-nums">
              {tile.value}
            </div>
            <div className="pl-2 text-xs text-bento-muted font-medium">{tile.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
};
