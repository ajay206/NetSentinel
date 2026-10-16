import React from 'react';
import { TIPS } from '../lib/tooltips';
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
        info={TIPS.panelDemoPath}
      />
      <ol className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-0 sm:overflow-x-auto sm:pb-1">
        {stages.map((stage, idx) => {
          const isCurrent = idx === firstPendingIndex && !stage.done;
          const circleClasses = stage.done
            ? 'bg-emerald-500 text-white flex items-center justify-center'
            : isCurrent
              ? 'bg-deck-navy text-white flex items-center justify-center ring-2 ring-deck-cyan animate-pulse'
              : 'bg-slate-700 text-deck-navy flex items-center justify-center';

          return (
            <li
              key={stage.id}
              data-testid={`stage-${stage.id}`}
              data-done={stage.done ? 'true' : 'false'}
              className="flex min-w-0 items-center gap-3 sm:min-w-[7.5rem] sm:flex-1 sm:flex-col sm:items-center"
            >
              <div className="relative flex items-center">
                <div
                  className={circleClasses}
                  style={{ width: 32, height: 32, borderRadius: '9999px' }}
                >
                  {stage.done ? '✓' : idx + 1}
                </div>
                {idx < stages.length - 1 && (
                  <div className="mx-2 hidden h-0.5 flex-1 bg-slate-700 sm:block" />
                )}
              </div>
              <div className="min-w-0">
                <span className="block text-sm sm:mt-2 sm:text-center">{stage.label}</span>
                {stage.detail && (
                  <span className="block text-xs text-slate-400 sm:text-center">{stage.detail}</span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <div className="mt-4 text-center text-sm">
        {allDone ? (
          <span role="status" className="inline-block bg-emerald-600 text-white px-3 py-1 rounded">
            Phase 1 demo complete
          </span>
        ) : (
          <span className="italic text-slate-400">{currentHint}</span>
        )}
      </div>
    </div>
  );
};
