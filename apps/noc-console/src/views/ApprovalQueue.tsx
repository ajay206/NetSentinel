import React, { useEffect, useState, type ChangeEvent } from 'react';
import { TIPS } from '../lib/tooltips';
import { CardHeader } from '../components/ui/Card';
import { Tooltip } from '../components/ui/Tooltip';
import type { Ticket, TicketStatus, AuditEntry } from '../types.ticket';

export interface ApprovalQueueProps {
  tickets?: Ticket[];
  isLoading?: boolean;
  isError?: boolean;
  status: TicketStatus | 'all';
  onStatusChange: (s: TicketStatus | 'all') => void;
  selectedId?: string | null;
  onSelect: (id: string | null) => void;
  audit?: AuditEntry[];
  auditLoading?: boolean;
  canApprove: boolean;
  onDecide: (id: string, decision: 'approve' | 'reject', note: string) => void;
  isPending?: boolean;
  error?: Error | null;
}

export const ApprovalQueue: React.FC<ApprovalQueueProps> = ({
  tickets = [],
  isLoading,
  isError,
  status,
  onStatusChange,
  selectedId,
  onSelect,
  audit = [],
  auditLoading,
  canApprove,
  onDecide,
  isPending,
  error,
}) => {
  const selectedTicket = tickets.find((t) => t.id === selectedId) ?? null;
  const [note, setNote] = useState('');
  useEffect(() => setNote(''), [selectedId]);

  const handleStatus = (e: ChangeEvent<HTMLSelectElement>) => {
    onStatusChange(e.target.value as TicketStatus | 'all');
  };

  const handleDecide = (decision: 'approve' | 'reject') => {
    if (!selectedTicket) return;
    onDecide(selectedTicket.id, decision, note.trim());
    setNote('');
  };

  const statusPill = (s: TicketStatus) => {
    const map: Record<TicketStatus, string> = {
      draft: 'bg-amber-900 text-amber-200',
      approved: 'bg-emerald-900 text-emerald-200',
      rejected: 'bg-red-900 text-red-200',
    };
    return (
      <Tooltip
        content={
          { draft: TIPS.statusDraft, approved: TIPS.statusApproved, rejected: TIPS.statusRejected }[
            s
          ]
        }
      >
        <span className={`px-2 py-0.5 rounded text-xs ${map[s]}`} data-testid="status-pill">
          {s}
        </span>
      </Tooltip>
    );
  };

  return (
    <div className="ns-card" data-testid="approval-queue">
      <CardHeader
        as="h3"
        title="Approval queue"
        subtitle="AI and operators draft tickets; only operators approve."
        info={TIPS.panelApprovals}
      />

      <div className="mb-4">
        <label className="sr-only" htmlFor="status-filter">
          Status
        </label>
        <select
          id="status-filter"
          aria-label="Status"
          value={status}
          onChange={handleStatus}
          className="ns-control w-full sm:w-48"
        >
          <option value="all">All</option>
          <option value="draft">Draft</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {isLoading && <p className="text-bento-muted text-sm">Loading tickets…</p>}
      {isError && <p className="text-red-400">ticket-service unavailable</p>}
      {!isLoading && !isError && tickets.length === 0 && (
        <p className="text-bento-muted text-sm">No tickets</p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <ul className="ns-scroll max-h-[28rem] space-y-3 pr-1">
          {tickets.map((ticket) => (
            <li key={ticket.id}>
              <button
                type="button"
                data-testid="ticket-row"
                aria-pressed={selectedId === ticket.id}
                onClick={() => onSelect(ticket.id)}
                className={`w-full rounded-xl border p-4 text-left transition-colors hover:bg-bento-bg/60 ${
                  selectedId === ticket.id ? 'border-emerald-500' : 'border-bento-border'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono font-bold">{ticket.id}</span>
                  {statusPill(ticket.status)}
                </div>
                <p className="mt-2 text-sm font-semibold leading-relaxed text-navy">{ticket.title}</p>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
                  <span>Severity: {ticket.severity}</span>
                  {ticket.siteId && <span>Site: {ticket.siteId}</span>}
                  {ticket.incidentId && <span>Inc: {ticket.incidentId}</span>}
                  {ticket.createdVia === 'mcp' && (
                    <span data-testid="via-mcp" className="rounded bg-slate-200 px-1.5 py-0.5">
                      🤖 MCP
                    </span>
                  )}
                  <span>By {ticket.createdBy}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>

        {selectedTicket && (
          <section data-testid="ticket-detail" className="min-w-0 rounded-xl border border-bento-border p-4 lg:p-5">
            <h4 className="font-medium">{selectedTicket.title}</h4>
            <p className="mt-2 whitespace-pre-wrap">{selectedTicket.description}</p>

            <div className="mt-2">
              {selectedTicket.runbookIds.map((id) => (
                <span
                  key={id}
                  className="inline-block mr-1 mb-1 px-2 py-0.5 bg-slate-200 rounded text-xs font-mono"
                >
                  {id}
                </span>
              ))}
              {selectedTicket.incidentId && (
                <span className="inline-block mr-1 mb-1 px-2 py-0.5 bg-bento-bg rounded text-xs font-mono text-slate-600">
                  {selectedTicket.incidentId}
                </span>
              )}
            </div>

            {selectedTicket.decidedAt && (
              <div className="mt-2 text-sm">
                <p>
                  Decision: {selectedTicket.decidedBy} at{' '}
                  {new Date(selectedTicket.decidedAt).toLocaleString()}
                </p>
                {selectedTicket.decisionNote && <p>Note: {selectedTicket.decisionNote}</p>}
              </div>
            )}

            {selectedTicket.status === 'draft' && (
              <div className="mt-4">
                <label className="sr-only" htmlFor="decision-note">
                  Decision note
                </label>
                <textarea
                  id="decision-note"
                  aria-label="Decision note"
                  maxLength={500}
                  placeholder="Why are you approving or rejecting? (required to reject)"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  className="w-full rounded border-bento-border bg-bento-bg p-2"
                />
                <div className="mt-2 flex gap-2">
                  <Tooltip
                    content={
                      canApprove
                        ? TIPS.btnApproveTicket
                        : `${TIPS.btnApproveTicket} Requires the operator role.`
                    }
                  >
                    <span className="inline-flex">
                      <button
                        type="button"
                        onClick={() => handleDecide('approve')}
                        disabled={!canApprove || isPending}
                        className="px-4 py-2 bg-emerald-600 rounded disabled:opacity-50"
                      >
                        Approve
                      </button>
                    </span>
                  </Tooltip>
                  <Tooltip
                    content={
                      canApprove
                        ? TIPS.btnRejectTicket
                        : `${TIPS.btnRejectTicket} Requires the operator role.`
                    }
                  >
                    <span className="inline-flex">
                      <button
                        type="button"
                        onClick={() => handleDecide('reject')}
                        disabled={!canApprove || note.trim() === '' || isPending}
                        className="px-4 py-2 bg-red-600 rounded disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </span>
                  </Tooltip>
                </div>
                {!canApprove && (
                  <p role="note" className="mt-1 text-sm text-bento-muted">
                    Read-only: approving needs the operator role.
                  </p>
                )}
                {error && <p className="mt-1 text-red-400">{error.message}</p>}
              </div>
            )}

            <div className="mt-4">
              <h5 className="font-medium">Audit trail</h5>
              {auditLoading && <p className="text-bento-muted text-sm">Loading audit…</p>}
              {!auditLoading && (
                <ol data-testid="audit-trail" className="list-decimal ml-4">
                  {audit.map((entry) => (
                    <li key={entry.seq} className="text-sm">
                      {entry.action} · {entry.actor} ({entry.role}) ·{' '}
                      {new Date(entry.ts).toLocaleString()}{' '}
                      <code className="font-mono">{entry.hash.slice(0, 8)}</code>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </section>
        )}
        {!selectedTicket && tickets.length > 0 && (
          <div className="hidden items-center justify-center rounded-xl border border-dashed border-bento-border p-6 text-center text-sm text-bento-muted lg:flex">
            Select a ticket to see its details, audit trail and approve or reject it.
          </div>
        )}
      </div>
    </div>
  );
};
