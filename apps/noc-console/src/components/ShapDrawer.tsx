import React from 'react';
import { FaultBadge } from './FaultBadge';
import { SeverityChip } from './ui/Card';
import type { EnrichedAlarm } from '../types.enriched';
import type { FaultExplanation, FaultPrediction } from '../types.fault';

interface ShapDrawerProps {
  alarm: EnrichedAlarm | null;
  prediction?: FaultPrediction;
  explanation?: FaultExplanation;
  isLoading: boolean;
  isError: boolean;
  onClose: () => void;
  /** Suggested runbooks for this alarm, rendered at the top of the drawer. */
  runbooks?: React.ReactNode;
  /** Step 13b: acknowledge / resolve controls (operators) or read-only state (viewers). */
  actions?: React.ReactNode;
  /** Render in the alarm dashboard instead of as an overlay. */
  inline?: boolean;
}

export const ShapDrawer: React.FC<ShapDrawerProps> = ({
  alarm,
  prediction,
  explanation,
  isLoading,
  isError,
  onClose,
  runbooks,
  actions,
  inline = false,
}) => {
  React.useEffect(() => {
    if (!alarm) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [alarm, onClose]);
  if (!alarm) return null;
  const contributions = explanation?.contributions ?? [];
  const maxAbs = Math.max(1e-9, ...contributions.map((c) => Math.abs(c.shap)));

  return (
    <aside
      role={inline ? 'region' : 'dialog'}
      aria-label="Alarm details"
      data-testid="alarm-drawer"
      className={inline
        ? 'ns-card h-full min-h-0 overflow-y-auto p-4 text-navy'
        : 'fixed right-0 top-0 h-full w-full sm:w-[34rem] shadow-2xl bg-white border-l border-bento-border p-5 sm:p-6 z-50 overflow-y-auto text-navy'}
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display font-extrabold text-lg text-navy">Alarm details</h2>
        <button
          aria-label="Close"
          onClick={onClose}
          className="px-2.5 py-1 rounded-lg bg-bento-bg hover:bg-slate-200 text-navy font-bold text-xs"
        >
          ✕
        </button>
      </div>

      <dl
        className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1.5 text-xs mb-5"
        data-testid="alarm-details"
      >
        <dt className="text-bento-muted font-bold">Problem</dt>
        <dd className="text-navy font-semibold">{alarm.specificProblem}</dd>
        <dt className="text-bento-muted font-bold">Site</dt>
        <dd className="font-mono font-bold text-navy">{alarm.siteId}</dd>
        <dt className="text-bento-muted font-bold">Region</dt>
        <dd className="font-medium text-navy">{alarm.enrichment.region ?? '—'}</dd>
        <dt className="text-bento-muted font-bold">Severity</dt>
        <dd>
          <SeverityChip severity={alarm.perceivedSeverity} />
        </dd>
        {alarm.probableCause && (
          <>
            <dt className="text-bento-muted font-bold">Probable cause</dt>
            <dd className="font-medium text-navy">{alarm.probableCause}</dd>
          </>
        )}
      </dl>

      {actions && (
        <section className="mb-5" aria-label="Alarm workflow">
          <h3 className="mb-2 text-sm font-bold font-display text-navy">Workflow</h3>
          {actions}
        </section>
      )}

      {runbooks && <div className="mb-5">{runbooks}</div>}

      <h3 className="font-bold font-display text-sm text-navy mb-2">Why this fault?</h3>
      <div className="flex items-center gap-2 mb-1">
        <FaultBadge
          prediction={prediction}
          isLoading={!prediction && isLoading}
          isError={!prediction && isError}
        />
      </div>
      {prediction && (
        <div className="text-[11px] text-bento-muted font-medium mb-4">model {prediction.modelVersion}</div>
      )}

      {isError ? (
        <p className="text-red-600 text-sm font-bold">ml-service unreachable — run make ml</p>
      ) : isLoading && contributions.length === 0 ? (
        <p className="text-bento-muted text-sm font-medium">Loading SHAP explanation…</p>
      ) : (
        <ul className="space-y-2.5" data-testid="shap-list">
          {contributions.map((c) => {
            const positive = c.shap >= 0;
            return (
              <li key={c.feature} className="text-xs" data-testid="shap-row">
                <div className="flex justify-between font-bold">
                  <span className="text-navy">{c.feature}</span>
                  <span className={positive ? 'text-red-600' : 'text-sky-700'}>
                    {positive ? '+' : ''}
                    {c.shap.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex-1 h-2 bg-bento-bg rounded-full overflow-hidden">
                    <div
                      data-testid="shap-bar"
                      className={`h-2 rounded-full ${positive ? 'bg-red-400' : 'bg-sky-400'}`}
                      style={{ width: `${(Math.abs(c.shap) / maxAbs) * 100}%` }}
                    />
                  </div>
                  <span className="text-bento-muted w-28 text-right font-medium">
                    value {Number(c.value.toFixed(2))} ·{' '}
                    {positive ? 'pushes towards' : 'pushes away'}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-6 text-[11px] text-bento-muted font-medium">
        SHAP values from XGBoost TreeSHAP — they explain the model, not the network.
      </p>
    </aside>
  );
};
