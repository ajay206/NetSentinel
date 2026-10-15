import React from 'react';
import { CardHeader } from '../components/ui/Card';
import { Tip, Tooltip } from '../components/ui/Tooltip';
import { AGENT_LABEL } from '../lib/statusTips';
import { TIPS } from '../lib/tooltips';
import type { AgentRun, AgentName } from '../types.agents';

const agentColors: Record<AgentName, string> = {
  supervisor: 'bg-slate-600 text-slate-100',
  triage: 'bg-sky-900 text-sky-200',
  rca: 'bg-violet-900 text-violet-200',
  remediation: 'bg-amber-900 text-amber-200',
  approval: 'bg-emerald-900 text-emerald-200',
  report: 'bg-teal-900 text-teal-200',
};

export const TraceView: React.FC<{ run?: AgentRun | null }> = ({ run }) => {
  const header = (
    <CardHeader
      title="Agent trace"
      subtitle="Each agent step, the tools it called and how long it took."
      info={TIPS.panelTrace}
    />
  );
  if (!run) {
    return (
      <section data-testid="trace-view" className="flex h-full min-h-0 flex-col">
        {header}
        <div className="text-sm text-slate-400">Start a run to see the agent trace.</div>
      </section>
    );
  }

  const totalDuration = run.trace.reduce((sum, s) => sum + s.durationMs, 0);
  const maxDuration = Math.max(...run.trace.map((s) => s.durationMs), 1);
  const stepsCount = run.trace.length;

  return (
    <section data-testid="trace-view" className="flex h-full min-h-0 flex-col">
      {header}
      <div data-testid="agent-path" className="flex flex-wrap items-center gap-1 text-xs">
        {run.agentPath.map((a, i) => (
          <React.Fragment key={`${a}-${i}`}>
            <Tooltip content={TIPS.chipAgent}>
              <span data-testid="agent-pill" className={`rounded px-2 py-0.5 ${agentColors[a]}`}>
                {a}
              </span>
            </Tooltip>
            {i < run.agentPath.length - 1 && (
              <span aria-hidden className="text-slate-500">
                →
              </span>
            )}
          </React.Fragment>
        ))}
      </div>

      <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
        <Tip tip="Number of agent steps so far and their total time, in milliseconds.">
          {stepsCount} steps · {totalDuration} ms
        </Tip>
        {run.tracing.langfuse && (
          <Tooltip content={TIPS.chipLangfuse}>
            <span className="rounded bg-amber-900 px-2 py-0.5 text-[11px] text-amber-200">
              Langfuse
            </span>
          </Tooltip>
        )}
      </div>

      <ol className="ns-scroll mt-3 space-y-3 pr-1">
        {run.trace.map((step) => {
          const barWidth = Math.max((step.durationMs / maxDuration) * 100, 2);
          return (
            <li key={step.seq} className="flex flex-col gap-1" data-testid="trace-step">
              <div className="flex items-center gap-2 text-sm">
                <Tooltip content={TIPS.chipAgent}>
                  <span
                    className={`w-24 shrink-0 rounded px-2 py-0.5 text-center text-xs ${agentColors[step.agent]}`}
                    data-testid="step-agent"
                  >
                    {step.agent}
                  </span>
                </Tooltip>
                <span className="min-w-0 flex-1 truncate text-slate-200" title={step.name}>
                  {step.name}
                </span>
                {!step.ok && <span className="text-xs font-medium text-red-400">failed</span>}
                <span className="w-20 shrink-0 text-right font-mono text-xs tabular-nums text-slate-400">
                  {step.durationMs} ms
                </span>
              </div>

              <div
                className="h-1.5 overflow-hidden rounded bg-slate-800"
                aria-label={`${AGENT_LABEL[step.agent] ?? step.agent}: ${step.durationMs} ms`}
              >
                <div className="h-full rounded bg-sky-500" style={{ width: `${barWidth}%` }} />
              </div>

              {step.toolCalls.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {step.toolCalls.map((tc, idx) => (
                    <Tooltip key={idx} content={TIPS.chipToolCall}>
                      <span
                        data-testid="trace-tool"
                        className={`max-w-full truncate rounded border px-1.5 py-0.5 font-mono text-[11px] ${
                          tc.ok ? 'border-slate-700 text-slate-300' : 'border-red-700 text-red-300'
                        }`}
                      >
                        {tc.name} · {tc.durationMs} ms
                      </span>
                    </Tooltip>
                  ))}
                </div>
              )}

              {step.detail && <p className="text-xs text-slate-400">{step.detail}</p>}
            </li>
          );
        })}
      </ol>
    </section>
  );
};
