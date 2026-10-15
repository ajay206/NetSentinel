import React, { useState } from 'react';
import type { AgentRun, RunStatus } from '../types.agents';

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
  const statusColors: Record<RunStatus, string> = {
    awaiting_approval: 'bg-amber-500 text-white',
    completed: 'bg-emerald-500 text-white',
    rejected: 'bg-red-600 text-white',
    running: 'bg-sky-500 text-white',
    failed: 'bg-red-600 text-white',
  };

  const startLabel = isStarting ? 'Running…' : `Run agents on ${incidentId ?? siteId}`;
  const startDisabled = (!incidentId && !siteId) || !canOperate || isStarting;

  const handleStart = () => {
    if (incidentId) onStart({ incidentId });
    else if (siteId) onStart({ siteId });
  };

  const handleDecide = (approved: boolean) => {
    onDecide(approved, note.trim());
    setNote('');
  };

  return (
    <div className="ns-card" data-testid="copilot-chat">
      <h3 className="text-xl font-bold">Copilot chat (multi-agent)</h3>
      <p className="text-sm text-slate-400">
        Supervisor + triage, RCA, remediation and report agents; a human approves before any ticket
        draft.
      </p>

      <button
        className={`mt-2 px-4 py-2 rounded ${
          startDisabled ? 'bg-slate-600 cursor-not-allowed' : 'bg-sky-600'
        } text-white`}
        disabled={startDisabled}
        onClick={handleStart}
        title={!canOperate ? 'Requires the operator role' : undefined}
      >
        {startLabel}
      </button>

      {!canOperate && (
        <p className="mt-1 text-xs text-slate-500" role="note">
          Read-only: running agents needs the operator role.
        </p>
      )}

      {runs.length > 1 && (
        <select
          aria-label="Run"
          className="mt-2 p-1 border rounded bg-slate-800 text-white"
          value={run?.runId ?? ''}
          onChange={(e) => onSelectRun(e.target.value)}
        >
          {runs.map((r) => (
            <option key={r.runId} value={r.runId}>
              {r.runId} · {r.status}
            </option>
          ))}
        </select>
      )}

      {run && (
        <>
          <span
            data-testid="run-status"
            className={`inline-block mt-2 px-2 py-0.5 rounded ${statusColors[run.status]}`}
          >
            {run.status}
          </span>

          <div data-testid="chat-log" className="mt-4 space-y-3">
            {run.messages.map((msg, i) => {
              const isHuman = msg.agent === 'human';
              const align = isHuman ? 'items-end' : 'items-start';
              const bg = isHuman ? 'bg-sky-600' : 'bg-slate-700';
              const label = isHuman
                ? 'Human'
                : (msg.agent as string).charAt(0).toUpperCase() + (msg.agent as string).slice(1);
              return (
                <div key={i} className={`flex ${align}`}>
                  <div
                    className={`max-w-xs px-3 py-2 rounded ${bg} text-white whitespace-pre-wrap`}
                  >
                    <strong className="block mb-1">{label}</strong>
                    {msg.text}
                    {msg.sources && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {msg.sources.map((src, idx) => (
                          <span
                            key={idx}
                            className="px-1 py-0.5 border border-slate-500 rounded text-xs font-mono"
                          >
                            {src}
                          </span>
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
              className="mt-4 p-3 border border-amber-500 rounded bg-slate-800"
            >
              <p className="font-medium">{run.plan.summary}</p>
              <ol className="list-decimal list-inside mt-2 space-y-1">
                {run.plan.steps.map((st, idx) => (
                  <li key={idx} className="text-sm">
                    {st.text} ({st.runbookId} §{st.section})
                  </li>
                ))}
              </ol>
              <p className="mt-2">
                Ticket: {run.plan.ticketDraft.title} – {run.plan.ticketDraft.severity}
              </p>
              <textarea
                aria-label="Approval note"
                className="w-full mt-2 p-1 border rounded bg-slate-700 text-white"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <div className="mt-2 flex gap-2">
                <button
                  className={`px-3 py-1 rounded ${
                    canOperate && !isDeciding ? 'bg-emerald-600' : 'bg-slate-600 cursor-not-allowed'
                  } text-white`}
                  disabled={!canOperate || isDeciding}
                  onClick={() => handleDecide(true)}
                >
                  Approve plan
                </button>
                <button
                  className={`px-3 py-1 rounded ${
                    canOperate && !isDeciding && note.trim()
                      ? 'bg-red-600'
                      : 'bg-slate-600 cursor-not-allowed'
                  } text-white`}
                  disabled={!canOperate || isDeciding || !note.trim()}
                  onClick={() => handleDecide(false)}
                >
                  Reject plan
                </button>
              </div>
            </div>
          )}

          {run.ticketId && (
            <p data-testid="run-ticket" className="mt-2 text-sm">
              Ticket draft {run.ticketId} is waiting in the Approval queue.
            </p>
          )}

          {run.kgWriteBack && (
            <p className="mt-2 text-sm">
              Knowledge graph:{' '}
              <span className={run.kgWriteBack.ok ? 'text-emerald-400' : 'text-red-600'}>
                {run.kgWriteBack.detail}
              </span>
            </p>
          )}

          {run.report && (
            <pre
              data-testid="run-report"
              className="mt-2 whitespace-pre-wrap text-xs bg-slate-800 p-2 rounded"
            >
              {run.report}
            </pre>
          )}
        </>
      )}

      {error && <p className="mt-2 text-red-600">{error.message}</p>}
    </div>
  );
};
