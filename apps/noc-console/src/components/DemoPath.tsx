import React from 'react';
import { TIPS } from '../lib/tooltips';
import { InfoTip } from './ui/Card';
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
    <div className="rounded-[20px] bg-white p-3.5 px-5 shadow-sm border border-transparent flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2 mr-2">
        <span className="text-[11px] font-extrabold uppercase tracking-wider text-bento-muted whitespace-nowrap">
          Demo path
        </span>
        <InfoTip text={TIPS.panelDemoPath} label="Demo path (fibre_cut)" />
      </div>

      <div className="flex-1 flex flex-wrap items-center gap-2 min-w-[280px]">
        {stages.map((stage, idx) => {
          return (
            <div
              key={stage.id}
              data-testid={`stage-${stage.id}`}
              data-done={stage.done ? 'true' : 'false'}
              className={`flex-1 flex items-center gap-2 text-xs font-bold px-3 py-2 rounded-xl transition-colors min-w-[110px] ${
                stage.done ? 'bg-cyan/28 text-navy' : 'bg-bento-bg text-navy'
              }`}
            >
              <span className="w-5 h-5 rounded-lg bg-navy text-white text-[11px] font-extrabold flex items-center justify-center shrink-0">
                {idx + 1}
              </span>
              <span className="truncate">{stage.label}</span>
            </div>
          );
        })}
      </div>

      {allDone ? (
        <span role="status" className="text-xs font-bold text-emerald-700 bg-emerald-100 px-3 py-1 rounded-full ml-auto">
          Phase 1 demo complete
        </span>
      ) : currentHint ? (
        <span className="text-xs italic text-bento-muted ml-auto hidden lg:inline-block">
          {currentHint}
        </span>
      ) : null}
    </div>
  );
};
