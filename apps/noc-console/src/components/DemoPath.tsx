import React from 'react';
import { CardHeader } from './ui/Card';
import type { DemoStage } from '../lib/demoPath';

interface DemoPathProps {
  stages: DemoStage[];
  hint?: string;
}

export const DemoPath: React.FC<DemoPathProps> = ({ stages, hint }) => {
  const firstPendingIndex = stages.findIndex((s) => !s.done);
  const allDone = firstPendingIndex === -1;

  const defaultHints: Record<DemoStage['id'], string> = {
    alarms: 'Run make demo (or make sim) to start fibre_cut',
    anomaly: 'Waiting for ml-service anomalies',
    fault: 'Click a root alarm to classify it',
    runbooks: 'Runbooks appear for the selected alarm',
    copilot: 'Press Analyze site (operator role)',
  };

  const currentHint = allDone ? undefined : (hint ?? defaultHints[stages[firstPendingIndex].id]);

  return (
    <div className="ns-card text-slate-100">
      <CardHeader
        title="Demo path (fibre_cut)"
        subtitle="The five steps of the fibre-cut walkthrough; each turns green when it is done."
        info="Start the demo stack, then follow the steps: alarms arrive, a KPI anomaly appears, click a root alarm to classify it, open a runbook, ask the copilot."
      />
      <ol className="flex items-center justify-between">
        {stages.map((stage, idx) => {
          const isCurrent = idx === firstPendingIndex && !stage.done;
          const circleClasses = stage.done
            ? 'bg-emerald-500 text-white flex items-center justify-center'
            : isCurrent
              ? 'bg-slate-700 text-white flex items-center justify-center ring-2 ring-sky-400 animate-pulse'
              : 'bg-slate-700 text-white flex items-center justify-center';

          return (
            <li
              key={stage.id}
              data-testid={`stage-${stage.id}`}
              data-done={stage.done ? 'true' : 'false'}
              className="flex-1 flex flex-col items-center"
            >
              <div className="relative flex items-center">
                <div
                  className={circleClasses}
                  style={{ width: 32, height: 32, borderRadius: '9999px' }}
                >
                  {stage.done ? '✓' : idx + 1}
                </div>
                {idx < stages.length - 1 && <div className="flex-1 h-0.5 bg-slate-700 mx-2" />}
              </div>
              <span className="mt-2 text-sm">{stage.label}</span>
              {stage.detail && <span className="text-xs text-slate-400">{stage.detail}</span>}
            </li>
          );
        })}
      </ol>
      <div className="mt-4 text-center">
        {allDone ? (
          <span role="status" className="inline-block bg-emerald-600 text-white px-3 py-1 rounded">
            Phase 1 demo complete
          </span>
        ) : (
          <span className="italic text-slate-300">{currentHint}</span>
        )}
      </div>
    </div>
  );
};
