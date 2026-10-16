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

/** Top-of-page summary bento grid matching mockup (c.png / c.html). */
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

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5" data-testid="kpi-summary">
      {/* Tile 1: Hero KPI (Active Alarms) - Navy gradient card taking full height of KPI block on desktop */}
      <div
        className="relative overflow-hidden rounded-[20px] bg-gradient-to-br from-[#09254A] via-[#0E3A6B] to-[#12507A] p-5 text-white shadow-sm flex flex-col justify-between min-h-[160px] xl:row-span-2"
        data-testid="kpi-alarms"
      >
        <div className="absolute right-[-40px] bottom-[-40px] w-[180px] h-[180px] rounded-full bg-[radial-gradient(circle,rgba(109,207,246,0.35)_0%,transparent_70%)] pointer-events-none" />
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-white/65">
              Active Alarms
            </span>
            <InfoTip text="Alarms in the live feed that are not cleared yet." />
          </div>
          <div className="font-display text-[52px] font-extrabold tracking-tight leading-none my-1.5">
            {activeAlarms}
          </div>
          <div className="text-sm text-white/75 font-medium">
            <span className="text-[#FF8A8A] font-extrabold">{criticalAlarms} critical</span> · {majorAlarms} major
          </div>
        </div>
        <div className="inline-flex self-start mt-3 rounded-full bg-cyan/20 border border-cyan/35 px-3 py-1 text-xs font-bold text-cyan z-10">
          Alarm storm in progress
        </div>
      </div>

      {/* Grid of 4 secondary KPI tiles */}
      <div className="grid grid-cols-2 gap-3.5 xl:col-span-2 xl:grid-cols-2">
        {/* KPI 1: Open Incidents */}
        <div
          className="relative overflow-hidden rounded-[20px] bg-white p-4.5 shadow-sm flex flex-col justify-center gap-1 border-l-4 border-l-cyan"
          data-testid="kpi-incidents"
        >
          <div className="flex items-center justify-between pl-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-bento-muted">
              Open Incidents
            </span>
            <InfoTip text="The incident service groups alarms that are close in time and in the network." />
          </div>
          <div className="pl-2 font-display text-[32px] font-extrabold tracking-tight text-navy leading-tight">
            {openIncidents}
          </div>
          <div className="pl-2 text-xs text-bento-muted font-medium">awaiting triage</div>
        </div>

        {/* KPI 2: Alarm Compression */}
        <div
          className="relative overflow-hidden rounded-[20px] bg-white p-4.5 shadow-sm flex flex-col justify-center gap-1 border-l-4 border-l-[#8B5CF6]"
          data-testid="kpi-compression"
        >
          <div className="flex items-center justify-between pl-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-bento-muted">
              Alarm Compression
            </span>
            <InfoTip text="How many alarms each incident replaces. Higher means less noise for the operator." />
          </div>
          <div className="pl-2 font-display text-[32px] font-extrabold tracking-tight text-navy leading-tight">
            {compressionRatio != null && Number.isFinite(compressionRatio)
              ? `${compressionRatio.toFixed(1)}×`
              : '—'}
          </div>
          <div className="pl-2 text-xs text-bento-muted font-medium">noise reduced</div>
        </div>

        {/* KPI 3: KPI Anomalies */}
        <div
          className="relative overflow-hidden rounded-[20px] bg-white p-4.5 shadow-sm flex flex-col justify-center gap-1 border-l-4 border-l-amber"
          data-testid="kpi-anomalies"
        >
          <div className="flex items-center justify-between pl-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-bento-muted">
              KPI Anomalies
            </span>
            <InfoTip text="Cells whose KPIs moved far from their learned baseline in the last 24 hours." />
          </div>
          <div className="pl-2 font-display text-[32px] font-extrabold tracking-tight text-navy leading-tight">
            {anomalies}
          </div>
          <div className="pl-2 text-xs text-bento-muted font-medium">last 15 min</div>
        </div>

        {/* KPI 4: Services Healthy */}
        <div
          className="relative overflow-hidden rounded-[20px] bg-white p-4.5 shadow-sm flex flex-col justify-center gap-1 border-l-4 border-l-emerald-500"
          data-testid="kpi-services"
        >
          <div className="flex items-center justify-between pl-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-bento-muted">
              Services Healthy
            </span>
            <InfoTip text="Backend services reporting healthy to the API gateway." />
          </div>
          <div className="pl-2 font-display text-[32px] font-extrabold tracking-tight text-navy leading-tight">
            {servicesUp}/{servicesTotal}
          </div>
          <div className="pl-2 text-xs font-bold text-emerald-600">
            {healthUnknown ? 'Waiting for health' : allUp ? 'all green' : 'check health'}
          </div>
        </div>
      </div>
    </div>
  );
};
