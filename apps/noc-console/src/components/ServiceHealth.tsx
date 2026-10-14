import React from 'react';
import type { HealthResponse } from '../types';
import { formatIST } from '../lib/time';

interface ServiceHealthProps {
  health: HealthResponse | undefined;
  isError: boolean;
}

export const ServiceHealth: React.FC<ServiceHealthProps> = ({ health, isError }) => {
  if (isError || !health) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 h-full">
        <h2 className="text-slate-200 font-semibold mb-3">Service Health</h2>
        <div className="text-center py-8 text-slate-500">
          <p>Gateway unreachable</p>
          <p className="text-xs mt-1">Health endpoint not responding</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 h-full">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-slate-200 font-semibold">Service Health</h2>
        <span
          className={`px-2 py-0.5 text-xs rounded ${
            health.status === 'ok'
              ? 'bg-emerald-500/15 text-emerald-400'
              : 'bg-orange-500/15 text-orange-400'
          }`}
        >
          {health.status.toUpperCase()}
        </span>
      </div>
      <div className="space-y-2">
        {health.services.map((svc) => (
          <div
            key={svc.name}
            className="flex items-center justify-between p-2 bg-slate-800/50 rounded"
          >
            <div className="flex items-center space-x-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  svc.status === 'up' ? 'bg-emerald-400' : 'bg-red-400'
                }`}
              ></span>
              <span className="text-slate-300">{svc.name}</span>
            </div>
            {svc.detail && (
              <span className="text-xs text-slate-500">{svc.detail}</span>
            )}
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-600 mt-3">
        Last checked: {formatIST(health.checkedAt)}
      </p>
    </div>
  );
};
