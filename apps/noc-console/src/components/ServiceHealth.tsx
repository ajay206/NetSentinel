import React from 'react';
import { TIPS } from '../lib/tooltips';
import { CardHeader } from './ui/Card';
import type { HealthResponse } from '../types';
import { formatIST } from '../lib/time';

interface ServiceHealthProps {
  health: HealthResponse | undefined;
  isError: boolean;
}

export const ServiceHealth: React.FC<ServiceHealthProps> = ({ health, isError }) => {
  if (isError || !health) {
    return (
      <div className="ns-card">
        <CardHeader
          title="Service Health"
          subtitle="Is every backend service up?"
          info={TIPS.panelServiceHealth}
        />
        <div className="text-center py-8 text-slate-600">
          <p>Gateway unreachable</p>
          <p className="text-xs mt-1">Health endpoint not responding</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ns-card">
      <CardHeader
        title="Service Health"
        subtitle="Is every backend service up?"
        info={TIPS.panelServiceHealth}
        actions={
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
              health.status === 'ok'
                ? 'bg-emerald-500/15 text-emerald-700'
                : 'bg-orange-500/15 text-orange-700'
            }`}
          >
            {health.status.toUpperCase()}
          </span>
        }
      />
      <div className="ns-scroll grid grid-cols-1 content-start gap-2 pr-1">
        {health.services.map((svc) => (
          <div
            key={svc.name}
            className="flex flex-col gap-1 rounded-xl bg-bento-bg/60 px-3 py-2.5 text-sm"
          >
            <div className="flex min-w-0 items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  svc.status === 'up' ? 'bg-emerald-400' : 'bg-red-400'
                }`}
              ></span>
              <span className="truncate font-semibold text-navy" title={svc.name}>{svc.name}</span>
            </div>
            {svc.detail && <span className="pl-4 text-xs leading-snug text-slate-600">{svc.detail}</span>}
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-600">Last checked: {formatIST(health.checkedAt)}</p>
    </div>
  );
};
