import React, { useState } from 'react';
import type { Workflow } from '../hooks/useWorkflow';
import { formatIST } from '../lib/time';
import { TIPS } from '../lib/tooltips';
import { Tooltip } from './ui/Tooltip';

type Action = 'ack' | 'assign' | 'resolve' | 'note';

interface WorkflowActionsProps {
  /** What is being acted on, e.g. "incident INC-…" (used in labels). */
  subject: string;
  workflow?: Workflow | null;
  canAct: boolean;
  currentUser: string;
  allowAssign?: boolean;
  isPending?: boolean;
  error?: Error | null;
  onAction: (action: Action, extra: { note?: string; assignee?: string }) => void;
}

const STATE_CHIP: Record<string, string> = {
  new: 'bg-slate-200 text-navy',
  acknowledged: 'bg-amber-500/15 text-amber-700',
  resolved: 'bg-emerald-500/15 text-emerald-300',
};

/** Step 13b: acknowledge / assign / resolve / note. Hidden controls for viewers. */
export const WorkflowActions: React.FC<WorkflowActionsProps> = ({
  subject,
  workflow,
  canAct,
  currentUser,
  allowAssign = false,
  isPending = false,
  error,
  onAction,
}) => {
  const [note, setNote] = useState('');
  const [assignee, setAssignee] = useState('');
  const state = workflow?.state ?? 'new';
  const resolved = state === 'resolved';
  const run = (action: Action, extra: { note?: string; assignee?: string } = {}) => {
    onAction(action, { note: note.trim() || undefined, ...extra });
    setNote('');
  };
  const btn =
    'rounded px-2.5 py-1 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-40';

  return (
    <div className="space-y-2 text-xs" data-testid="workflow">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded px-2 py-0.5 font-medium ${STATE_CHIP[state]}`}
          data-testid="workflow-state"
        >
          {state === 'new' ? 'New' : state === 'acknowledged' ? 'Acknowledged' : 'Resolved'}
        </span>
        {workflow?.assignee && (
          <span className="text-bento-muted">
            Assigned to <span className="text-navy">{workflow.assignee}</span>
          </span>
        )}
        {workflow?.resolvedBy && <span className="text-bento-muted">by {workflow.resolvedBy}</span>}
      </div>

      {canAct ? (
        <div className="space-y-2" data-testid="workflow-controls">
          <textarea
            aria-label={`Note for ${subject}`}
            placeholder="Note (required to resolve)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={1000}
            rows={2}
            className="w-full rounded border border-bento-border bg-bento-bg px-2 py-1 text-navy"
          />
          <div className="flex flex-wrap gap-2">
            <Tooltip content={TIPS.btnAck}>
              <span className="inline-flex">
                <button
                  type="button"
                  className={`${btn} bg-amber-600/80 text-white hover:bg-amber-500`}
                  disabled={isPending || state !== 'new'}
                  onClick={() => run('ack')}
                >
                  Acknowledge
                </button>
              </span>
            </Tooltip>
            {allowAssign && (
              <>
                <Tooltip content={TIPS.btnAssign}>
                  <span className="inline-flex">
                    <button
                      type="button"
                      className={`${btn} bg-slate-200 text-navy hover:bg-slate-300`}
                      disabled={isPending || resolved || workflow?.assignee === currentUser}
                      onClick={() => run('assign', { assignee: currentUser })}
                    >
                      Assign to me
                    </button>
                  </span>
                </Tooltip>
                <input
                  aria-label={`Assign ${subject} to`}
                  placeholder="username"
                  value={assignee}
                  onChange={(e) => setAssignee(e.target.value.toLowerCase())}
                  className="w-28 rounded border border-bento-border bg-bento-bg px-2 py-1 text-navy"
                />
                <button
                  type="button"
                  className={`${btn} bg-slate-200 text-navy hover:bg-slate-300`}
                  disabled={isPending || resolved || !assignee.trim()}
                  onClick={() => {
                    run('assign', { assignee: assignee.trim() });
                    setAssignee('');
                  }}
                >
                  Assign
                </button>
              </>
            )}
            <Tooltip content={TIPS.btnResolve}>
              <span className="inline-flex">
                <button
                  type="button"
                  className={`${btn} bg-emerald-600/80 text-white hover:bg-emerald-500`}
                  disabled={isPending || resolved || !note.trim()}
                  onClick={() => run('resolve')}
                >
                  Resolve
                </button>
              </span>
            </Tooltip>
            <Tooltip content={TIPS.btnNote}>
              <span className="inline-flex">
                <button
                  type="button"
                  className={`${btn} border border-bento-border text-slate-600 hover:bg-bento-bg`}
                  disabled={isPending || !note.trim()}
                  onClick={() => run('note')}
                >
                  Add note
                </button>
              </span>
            </Tooltip>
          </div>
          {error && (
            <p role="alert" className="text-red-700">
              {error.message}
            </p>
          )}
        </div>
      ) : (
        <p className="text-slate-600" data-testid="workflow-readonly">
          Read-only: operators can acknowledge, assign and resolve.
        </p>
      )}

      {workflow && workflow.notes.length > 0 && (
        <ol className="max-h-32 space-y-1 overflow-y-auto border-l border-bento-border pl-3">
          {[...workflow.notes].reverse().map((n, i) => (
            <li key={`${n.ts}-${i}`} className="text-bento-muted">
              <span className="text-slate-600">{formatIST(new Date(n.ts * 1000))}</span>{' '}
              <span className="text-navy">{n.by}</span> {n.action}
              {n.assignee ? ` → ${n.assignee}` : ''}
              {n.text ? `: ${n.text}` : ''}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
};
