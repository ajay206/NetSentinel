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
  { key: 'dlThroughputMbps', label: 'DL Throughput', unit: 'Mbps', max: 1000 },
  { key: 'prbUtilPct', label: 'PRB Utilisation', unit: '%', max: 100 },
  { key: 'rrcSetupSuccessPct', label: 'RRC Setup Success', unit: '%', max: 100 },
  { key: 'dropCallRatePct', label: 'Drop Call Rate', unit: '%', max: 100 },
  { key: 'availabilityPct', label: 'Availability', unit: '%', max: 100 },
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

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
        <span className={`w-2 h-2 rounded-full ${statusColor}`} />
        Connection: {status}
      </div>

      {!activity ? (
        <div className="flex flex-col items-center justify-center p-8 text-center text-gray-400 border border-dashed rounded-md">
          <p className="text-lg font-medium">no data — run <code className="bg-gray-800 px-1 py-0.5 rounded">make kpis</code></p>
        </div>
      ) : (
        <>
          {/* Header tiles */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-slate-800 p-3 rounded shadow">
              <div className="text-xs text-gray-400">Samples / min</div>
              <div className="text-lg font-semibold">{activity.ratePerMin.toFixed(1)}</div>
            </div>
            <div className="bg-slate-800 p-3 rounded shadow">
              <div className="text-xs text-gray-400">Total Samples</div>
              <div className="text-lg font-semibold">{activity.totalSamples}</div>
            </div>
            <div className="bg-slate-800 p-3 rounded shadow">
              <div className="text-xs text-gray-400">Cells Reporting</div>
              <div className="text-lg font-semibold">{activity.cellsReporting}</div>
            </div>
            <div className="bg-slate-800 p-3 rounded shadow">
              <div className="text-xs text-gray-400">Last Sample</div>
              <div className="text-lg font-semibold">
                {activity.lastSampleTime ? formatIST(activity.lastSampleTime, { date: false }) : '—'}
              </div>
              {stale && (
                <div className="mt-1">
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-amber-600 text-[10px] font-medium text-white">
                    stale
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* KPI averages */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-gray-200">Network Averages</h3>
            <div className="space-y-3">
              {KPI_DEFINITIONS.map(def => {
                const value = activity.averages[def.key] ?? 0;
                const percent = Math.min((value / def.max) * 100, 100);
                return (
                  <div key={def.key} className="bg-slate-800 p-3 rounded">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-sm text-gray-400">{def.label}</span>
                      <span className="text-sm font-medium text-gray-200">{value.toFixed(1)} {def.unit}</span>
                    </div>
                    <div className="h-1 w-full bg-gray-700 rounded">
                      <div
                        className="h-full bg-emerald-500 rounded"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Charts arrive with kpi-service — Week 5
            </p>
          </div>
        </>
      )}
    </div>
  );
};
