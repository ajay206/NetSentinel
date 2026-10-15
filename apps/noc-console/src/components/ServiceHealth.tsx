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
        <div className="text-center py-8 text-slate-500">
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
            className={`px-2 py-0.5 text-xs rounded ${
              health.status === 'ok'
                ? 'bg-emerald-500/15 text-emerald-400'
                : 'bg-orange-500/15 text-orange-400'
            }`}
          >
            {health.status.toUpperCase()}
          </span>
        }
      />
      <div className="ns-scroll grid grid-cols-1 gap-1.5 content-start">
        {health.services.map((svc) => (
          <div
            key={svc.name}
            className="flex items-center justify-between px-2.5 py-1.5 bg-slate-800/50 rounded text-sm"
          >
            <div className="flex items-center space-x-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  svc.status === 'up' ? 'bg-emerald-400' : 'bg-red-400'
                }`}
              ></span>
              <span className="text-slate-300">{svc.name}</span>
            </div>
            {svc.detail && <span className="text-xs text-slate-500">{svc.detail}</span>}
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-600 mt-3">Last checked: {formatIST(health.checkedAt)}</p>
    </div>
  );
};
