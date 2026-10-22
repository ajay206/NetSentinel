import React from 'react';
import { TIPS } from '../lib/tooltips';
import { CardHeader } from './ui/Card';
import type { HealthResponse } from '../types';
import { formatIST } from '../lib/time';
import { last, useObsLinks, useSparklines } from '../hooks/useObs';
import { Sparkline } from './Sparkline';

interface ServiceHealthProps {
  health: HealthResponse | undefined;
  isError: boolean;
}

export const ServiceHealth: React.FC<ServiceHealthProps> = ({ health, isError }) => {
  const spark = useSparklines().data;
  const links = useObsLinks().data;
  const sparkOn = Boolean(spark?.enabled && !spark.error);
  if (isError || !health) {
    return (
      <div className="ns-card">
        <CardHeader
          title="Service Health"
          subtitle="Is every backend service up?"
          info={TIPS.panelServiceHealth}
        />
        <div className="text-center py-5 text-slate-600">
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
            className="flex flex-col gap-1 rounded-xl bg-bento-bg/60 px-3 py-2 text-sm"
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
            {sparkOn && spark?.services[svc.name] && (
              <div data-testid="service-spark" className="flex flex-wrap items-center gap-x-3 gap-y-1 pl-4 text-[11px] text-slate-600">
                <span className="flex items-center gap-1">
                  <Sparkline values={spark.services[svc.name].p95Ms} label={`${svc.name} p95 latency, last 30 min`} />
                  p95 {last(spark.services[svc.name].p95Ms) ?? '–'} ms
                </span>
                <span className="flex items-center gap-1">
                  <Sparkline values={spark.services[svc.name].errorRate} label={`${svc.name} error rate, last 30 min`} stroke="#E4572E" />
                  {(((last(spark.services[svc.name].errorRate) ?? 0) * 100)).toFixed(1)}% 5xx
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
        <p>Last checked: {formatIST(health.checkedAt)}</p>
        {sparkOn && links && (
          <div data-testid="obs-links" className="flex flex-wrap gap-2">
            {links.grafana && <a className="font-semibold text-navy underline" href={links.grafana} target="_blank" rel="noreferrer">Open Grafana</a>}
            {links.langfuse && <a className="font-semibold text-navy underline" href={links.langfuse} target="_blank" rel="noreferrer">Open Langfuse</a>}
            {links.mlflow && <a className="font-semibold text-navy underline" href={links.mlflow} target="_blank" rel="noreferrer">Open MLflow</a>}
          </div>
        )}
      </div>
    </div>
  );
};
