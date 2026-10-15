import React from 'react';
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
  if (!run) {
    return <div className="text-slate-400 text-sm">Start a run to see the agent trace.</div>;
  }

  const totalDuration = run.trace.reduce((sum, s) => sum + s.durationMs, 0);
  const maxDuration = Math.max(...run.trace.map((s) => s.durationMs), 1);
  const stepsCount = run.trace.length;

  return (
    <section data-testid="trace-view" className="space-y-4">
      <h4 className="text-xs uppercase tracking-wide text-slate-400">Agent trace</h4>

      <div data-testid="agent-path" className="flex flex-wrap gap-1 text-sm">
        {run.agentPath.map((a, i) => (
          <React.Fragment key={`${a}-${i}`}>
            <span data-testid="agent-pill" className={`px-2 py-0.5 rounded ${agentColors[a]}`}>
              {a}
            </span>
            {i < run.agentPath.length - 1 && <span className="mx-1">→</span>}
          </React.Fragment>
        ))}
      </div>

      <div className="flex items-center text-sm text-slate-400">
        <span>
          {stepsCount} steps · {totalDuration} ms
        </span>
        {run.tracing.langfuse && (
          <span className="ml-2 px-2 py-0.5 bg-amber-600 text-xs rounded">Langfuse</span>
        )}
      </div>

      <ol className="space-y-2">
        {run.trace.map((step) => {
          const barWidth = Math.max((step.durationMs / maxDuration) * 100, 2);
          return (
            <li key={step.seq} className="flex flex-col gap-1" data-testid="trace-step">
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded ${agentColors[step.agent]}`}
                  data-testid="step-agent"
                >
                  {step.agent}
                </span>
                <span className="flex-1">{step.name}</span>
                <span className="font-mono text-right text-xs text-slate-500">
                  {step.durationMs} ms
                </span>
                {step.ok ? null : <span className="text-red-600 text-xs font-medium">failed</span>}
              </div>

              <div className="relative h-2 bg-slate-700 rounded overflow-hidden">
                <div className="h-full bg-sky-500" style={{ width: `${barWidth}%` }} />
              </div>

              <div className="flex flex-wrap gap-1">
                {step.toolCalls.map((tc, idx) => (
                  <span
                    key={idx}
                    data-testid="trace-tool"
                    className={`px-2 py-0.5 border rounded text-xs ${
                      tc.ok ? 'border-slate-500' : 'border-red-600 text-red-600'
                    }`}
                  >
                    {tc.name} · {tc.durationMs} ms
                  </span>
                ))}
              </div>

              <p className="text-xs text-slate-400">{step.detail}</p>
            </li>
          );
        })}
      </ol>
    </section>
  );
};
