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
}

/** W7: why the model picked this fault type (XGBoost TreeSHAP, top features). */
export const ShapDrawer: React.FC<ShapDrawerProps> = ({
  alarm,
  prediction,
  explanation,
  isLoading,
  isError,
  onClose,
  runbooks,
  actions,
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
      role="dialog"
      aria-label="Alarm details"
      data-testid="alarm-drawer"
      className="fixed right-0 top-0 h-full w-full sm:w-[30rem] shadow-2xl bg-slate-900 border-l border-slate-700 p-4 z-50 overflow-y-auto text-slate-200"
    >
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">Alarm details</h2>
        <button
          aria-label="Close"
          onClick={onClose}
          className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
        >
          ✕
        </button>
      </div>

      <dl
        className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 text-xs mb-4"
        data-testid="alarm-details"
      >
        <dt className="text-slate-500">Problem</dt>
        <dd className="text-slate-100">{alarm.specificProblem}</dd>
        <dt className="text-slate-500">Site</dt>
        <dd className="font-mono">{alarm.siteId}</dd>
        <dt className="text-slate-500">Region</dt>
        <dd>{alarm.enrichment.region ?? '—'}</dd>
        <dt className="text-slate-500">Severity</dt>
        <dd>
          <SeverityChip severity={alarm.perceivedSeverity} />
        </dd>
        {alarm.probableCause && (
          <>
            <dt className="text-slate-500">Probable cause</dt>
            <dd>{alarm.probableCause}</dd>
          </>
        )}
      </dl>

      {actions && (
        <section className="mb-5" aria-label="Alarm workflow">
          <h3 className="mb-2 text-sm font-semibold">Workflow</h3>
          {actions}
        </section>
      )}

      {runbooks && <div className="mb-5">{runbooks}</div>}

      <h3 className="font-semibold text-sm mb-2">Why this fault?</h3>
      <div className="flex items-center gap-2 mb-1">
        {/* Prediction and SHAP are separate API calls; don't hide a successful
            classification when the explanation is still loading or failed. */}
        <FaultBadge
          prediction={prediction}
          isLoading={!prediction && isLoading}
          isError={!prediction && isError}
        />
      </div>
      {prediction && (
        <div className="text-[11px] text-slate-500 mb-4">model {prediction.modelVersion}</div>
      )}

      {isError ? (
        <p className="text-red-400 text-sm">ml-service unreachable — run make ml</p>
      ) : isLoading && contributions.length === 0 ? (
        <p className="text-slate-400 text-sm">Loading SHAP explanation…</p>
      ) : (
        <ul className="space-y-2" data-testid="shap-list">
          {contributions.map((c) => {
            const positive = c.shap >= 0;
            return (
              <li key={c.feature} className="text-xs" data-testid="shap-row">
                <div className="flex justify-between">
                  <span className="text-slate-300">{c.feature}</span>
                  <span className={positive ? 'text-red-400' : 'text-sky-400'}>
                    {positive ? '+' : ''}
                    {c.shap.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-slate-800 rounded">
                    <div
                      data-testid="shap-bar"
                      className={`h-1.5 rounded ${positive ? 'bg-red-400' : 'bg-sky-400'}`}
                      style={{ width: `${(Math.abs(c.shap) / maxAbs) * 100}%` }}
                    />
                  </div>
                  <span className="text-slate-500 w-28 text-right">
                    value {Number(c.value.toFixed(2))} ·{' '}
                    {positive ? 'pushes towards' : 'pushes away'}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-6 text-[11px] text-slate-500">
        SHAP values from XGBoost TreeSHAP — they explain the model, not the network.
      </p>
    </aside>
  );
};
