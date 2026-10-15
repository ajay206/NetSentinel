import React, { useState } from 'react';
import { CardHeader } from '../components/ui/Card';
import { Tooltip } from '../components/ui/Tooltip';
import { AGENT_LABEL, RUN_STATUS } from '../lib/statusTips';
import { TIPS } from '../lib/tooltips';
import type { AgentRun } from '../types.agents';

export const CopilotChat: React.FC<{
  incidentId?: string | null;
  siteId?: string | null;
  run?: AgentRun | null;
  runs?: AgentRun[];
  isStarting?: boolean;
  isDeciding?: boolean;
  error?: Error | null;
  canOperate: boolean;
  onStart: (target: { incidentId?: string; siteId?: string }) => void;
  onSelectRun: (runId: string) => void;
  onDecide: (approved: boolean, note: string) => void;
}> = ({
  incidentId,
  siteId,
  run,
  runs = [],
  isStarting = false,
  isDeciding = false,
  error,
  canOperate,
  onStart,
  onSelectRun,
  onDecide,
}) => {
  const [note, setNote] = useState('');

  const startLabel = isStarting ? 'Running…' : `Run agents on ${incidentId ?? siteId ?? '…'}`;
  const startDisabled = (!incidentId && !siteId) || !canOperate || isStarting;

  const handleStart = () => {
    if (incidentId) onStart({ incidentId });
    else if (siteId) onStart({ siteId });
  };

  const handleDecide = (approved: boolean) => {
    onDecide(approved, note.trim());
    setNote('');
  };

  const status = run ? RUN_STATUS[run.status] : null;
  const btn =
    'rounded px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400';

  return (
    <section className="ns-card" data-testid="copilot-chat">
      <CardHeader
        title="Copilot chat (multi-agent)"
        subtitle="Agents investigate; a human approves before any ticket draft."
        info={TIPS.panelCopilotChat}
        actions={
          status && (
            <Tooltip content={status.tip}>
              <span
                data-testid="run-status"
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${status.cls}`}
              >
                {status.label}
              </span>
            </Tooltip>
          )
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Tooltip content={canOperate ? TIPS.btnRunAgents : 'Needs the operator role.'}>
          <button
            type="button"
            className={`${btn} bg-sky-600 hover:bg-sky-500`}
            disabled={startDisabled}
            onClick={handleStart}
          >
            {startLabel}
          </button>
        </Tooltip>
        {runs.length > 1 && (
          <select
            aria-label="Run"
            className="min-w-0 max-w-full flex-1 truncate rounded border border-slate-700 bg-slate-950 px-2 py-1.5 font-mono text-xs text-slate-200"
            value={run?.runId ?? ''}
            onChange={(e) => onSelectRun(e.target.value)}
          >
            {runs.map((r) => (
              <option key={r.runId} value={r.runId}>
                {r.runId} · {RUN_STATUS[r.status]?.label ?? r.status}
              </option>
            ))}
          </select>
        )}
      </div>
      {!canOperate && (
        <p className="mt-1 text-xs text-slate-500" role="note">
          Read-only: running agents needs the operator role.
        </p>
      )}
      {error && <p className="mt-2 text-sm text-red-400">{error.message}</p>}

      <div className="ns-scroll mt-3 pr-1">
        {!run && (
          <p className="text-sm text-slate-400">
            Select an incident and press Run agents. Messages from each agent appear here.
          </p>
        )}
        {run && (
          <>
            <div data-testid="chat-log" className="space-y-2">
              {run.messages.map((msg, i) => {
                const isHuman = msg.agent === 'human';
                return (
                  <div key={i} className={`flex ${isHuman ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[85%] whitespace-pre-wrap rounded-lg border px-3 py-2 text-sm leading-relaxed ${
                        isHuman
                          ? 'border-sky-800 bg-sky-950 text-sky-100'
                          : 'border-slate-700 bg-slate-800/70 text-slate-200'
                      }`}
                    >
                      <Tooltip content={TIPS.chipAgent}>
                        <strong className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-400">
                          {AGENT_LABEL[msg.agent as string] ?? String(msg.agent)}
                        </strong>
                      </Tooltip>
                      {msg.text}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {msg.sources.map((src, idx) => (
                            <Tooltip key={idx} content={TIPS.chipCitation}>
                              <span className="max-w-full truncate rounded border border-slate-600 px-1 py-0.5 font-mono text-[11px] text-slate-300">
                                {src}
                              </span>
                            </Tooltip>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {run.status === 'awaiting_approval' && run.plan && (
              <div
                data-testid="approval-box"
                className="mt-3 rounded-lg border border-slate-700 border-l-4 border-l-amber-500 bg-slate-800/60 p-3"
              >
                <p className="text-sm font-medium text-slate-100">{run.plan.summary}</p>
                <ol className="mt-2 list-inside list-decimal space-y-1 text-sm text-slate-300">
                  {run.plan.steps.map((st, idx) => (
                    <li key={idx}>
                      {st.text}{' '}
                      <span className="font-mono text-xs text-slate-400">
                        ({st.runbookId} §{st.section})
                      </span>
                    </li>
                  ))}
                </ol>
                <p className="mt-2 text-sm text-slate-300">
                  Ticket: {run.plan.ticketDraft.title} – {run.plan.ticketDraft.severity}
                </p>
                <label className="mt-3 block text-xs text-slate-400" htmlFor="approval-note">
                  Note (optional to approve, required to reject)
                </label>
                <textarea
                  id="approval-note"
                  aria-label="Approval note"
                  placeholder="Why you approve or reject this plan…"
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm text-slate-100 placeholder:text-slate-500"
                  rows={2}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                <div className="mt-2 flex gap-2">
                  <Tooltip content={TIPS.btnApprovePlan}>
                    <button
                      type="button"
                      className={`${btn} bg-emerald-600 hover:bg-emerald-500`}
                      disabled={!canOperate || isDeciding}
                      onClick={() => handleDecide(true)}
                    >
                      Approve plan
                    </button>
                  </Tooltip>
                  <Tooltip content={TIPS.btnRejectPlan}>
                    <button
                      type="button"
                      className={`${btn} bg-red-700 hover:bg-red-600`}
                      disabled={!canOperate || isDeciding || !note.trim()}
                      onClick={() => handleDecide(false)}
                    >
                      Reject plan
                    </button>
                  </Tooltip>
                </div>
              </div>
            )}

            {run.ticketId && (
              <p data-testid="run-ticket" className="mt-3 text-sm text-slate-300">
                Ticket draft <span className="font-mono">{run.ticketId}</span> is waiting in the
                Approval queue.
              </p>
            )}

            {run.kgWriteBack && (
              <p className="mt-2 text-sm text-slate-300">
                Knowledge graph:{' '}
                <span className={run.kgWriteBack.ok ? 'text-emerald-400' : 'text-red-400'}>
                  {run.kgWriteBack.detail}
                </span>
              </p>
            )}

            {run.report && (
              <pre
                data-testid="run-report"
                className="mt-2 whitespace-pre-wrap rounded bg-slate-950 p-2 text-xs text-slate-300"
              >
                {run.report}
              </pre>
            )}
          </>
        )}
      </div>
    </section>
  );
};
