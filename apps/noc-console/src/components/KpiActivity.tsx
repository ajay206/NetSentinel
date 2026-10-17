import React, { useMemo } from 'react';
import { KpiActivity as KpiActivityData } from '../types';
import { formatIST } from '../lib/time';
import { KpiConnectionStatus } from '../hooks/useKpiActivity';

interface Props {
  activity: KpiActivityData | null;
  status: KpiConnectionStatus;
}

const KPI_DEFINITIONS: {
  key: string;
  label: string;
  unit: string;
  max: number;
}[] = [
  { key: 'dlThroughputMbps', label: 'Download speed', unit: 'Mbps', max: 1000 },
  { key: 'prbUtilPct', label: 'Radio capacity in use (PRB)', unit: '%', max: 100 },
  { key: 'rrcSetupSuccessPct', label: 'Successful connection setup (RRC)', unit: '%', max: 100 },
  { key: 'dropCallRatePct', label: 'Dropped calls', unit: '%', max: 100 },
  { key: 'availabilityPct', label: 'Network availability', unit: '%', max: 100 },
];

function isStale(timestamp: string | null): boolean {
  if (!timestamp) return false;
  const sampleTime = new Date(timestamp).getTime();
  const now = Date.now();
  return now - sampleTime > 60_000; // 60 seconds
}

export const KpiActivity: React.FC<Props> = ({ activity, status }) => {
  const stale = useMemo(() => isStale(activity?.lastSampleTime ?? null), [activity]);

  const statusColor = {
    connecting: 'bg-yellow-500',
    open: 'bg-emerald-500',
    closed: 'bg-red-500',
  }[status];
  const statusLabel = {
    connecting: 'Connecting to sample stream…',
    open: 'Sample stream connected',
    closed: 'Sample stream offline',
  }[status];

  return (
    <div className="space-y-4">
      <div role="status" className="flex items-center gap-2 text-xs text-slate-600">
        <span className={`w-2 h-2 rounded-full ${statusColor}`} />
        {statusLabel}
      </div>

      {!activity ? (
        <div className="flex flex-col items-center justify-center p-5 text-center text-slate-600 border border-dashed rounded-md">
          <p className="text-sm font-medium">No data — run <code className="bg-bento-bg px-1 py-0.5 rounded">make kpis</code></p>
        </div>
      ) : (
        <>
          {/* Header tiles */}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <div className="rounded-lg bg-bento-bg p-3">
              <div className="text-xs text-slate-600">Samples per minute</div>
              <div className="text-base font-semibold">{activity.ratePerMin.toFixed(1)}</div>
            </div>
            <div className="rounded-lg bg-bento-bg p-3">
              <div className="text-xs text-slate-600">Samples received</div>
              <div className="text-base font-semibold">{activity.totalSamples}</div>
            </div>
            <div className="rounded-lg bg-bento-bg p-3">
              <div className="text-xs text-slate-600">Cells sending data</div>
              <div className="text-base font-semibold">{activity.cellsReporting}</div>
            </div>
            <div className="rounded-lg bg-bento-bg p-3">
              <div className="text-xs text-slate-600">Most recent sample</div>
              <div className="text-base font-semibold">
                {activity.lastSampleTime ? formatIST(activity.lastSampleTime, { date: false }) : '—'}
              </div>
              {stale && (
                <div className="mt-1">
                  <span
                    title="No KPI sample has arrived in the last 60 seconds."
                    className="inline-flex items-center px-1.5 py-0.5 rounded bg-amber-600 text-[10px] font-medium text-white"
                  >
                    No recent sample
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* KPI averages */}
          <div className="space-y-2">
            <h3 className="font-display text-xs font-extrabold uppercase tracking-wider text-navy/70">Network Averages</h3>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-5">
              {KPI_DEFINITIONS.map(def => {
                const value = activity.averages[def.key] ?? 0;
                const percent = Math.min((value / def.max) * 100, 100);
                return (
                  <div key={def.key} className="rounded-lg bg-bento-bg p-3">
                    <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5">
                      <span className="text-xs text-slate-600">{def.label}</span>
                      <span className="text-sm font-bold text-navy tabular-nums">{value.toFixed(1)} {def.unit}</span>
                    </div>
                    <div className="h-1 w-full rounded-full bg-slate-200">
                      <div
                        className="h-full bg-emerald-500 rounded"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
