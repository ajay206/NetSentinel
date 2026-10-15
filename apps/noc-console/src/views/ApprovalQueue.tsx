import React, { useEffect, useState, type ChangeEvent } from 'react';
import { CardHeader } from '../components/ui/Card';
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
      <span className={`px-2 py-0.5 rounded text-xs ${map[s]}`} data-testid="status-pill">
        {s}
      </span>
    );
  };

  return (
    <div className="ns-card" data-testid="approval-queue">
      <CardHeader
        as="h3"
        title="Approval queue"
        subtitle="AI and operators draft tickets; only operators approve."
        info="Drafts come from operators or the copilot (MCP open_ticket_draft). Every create, approve and reject is written to an append-only, hash-chained audit log."
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
          className="rounded border-slate-600 bg-slate-800 p-1"
        >
          <option value="all">All</option>
          <option value="draft">Draft</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {isLoading && <p className="text-slate-400 text-sm">Loading tickets…</p>}
      {isError && <p className="text-red-400">ticket-service unavailable</p>}
      {!isLoading && !isError && tickets.length === 0 && (
        <p className="text-slate-400 text-sm">No tickets</p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <ul className="space-y-2">
          {tickets.map((ticket) => (
            <li key={ticket.id}>
              <button
                type="button"
                data-testid="ticket-row"
                aria-pressed={selectedId === ticket.id}
                onClick={() => onSelect(ticket.id)}
                className={`w-full text-left p-2 rounded border ${
                  selectedId === ticket.id ? 'border-emerald-500' : 'border-slate-600'
                }`}
              >
                <div className="flex justify-between items-center">
                  <span className="font-mono">{ticket.id}</span>
                  {statusPill(ticket.status)}
                </div>
                <div className="mt-1 text-sm">
                  <span>{ticket.title}</span>
                  <span className="ml-2">Severity: {ticket.severity}</span>
                  {ticket.siteId && <span className="ml-2">Site: {ticket.siteId}</span>}
                  {ticket.incidentId && <span className="ml-2">Inc: {ticket.incidentId}</span>}
                  {ticket.createdVia === 'mcp' && (
                    <span data-testid="via-mcp" className="ml-2 text-xs bg-slate-700 rounded px-1">
                      🤖 MCP
                    </span>
                  )}
                </div>
                <div className="mt-1 text-xs text-slate-500">By {ticket.createdBy}</div>
              </button>
            </li>
          ))}
        </ul>

        {selectedTicket && (
          <section data-testid="ticket-detail" className="border-l border-slate-600 pl-4">
            <h4 className="font-medium">{selectedTicket.title}</h4>
            <p className="mt-2 whitespace-pre-wrap">{selectedTicket.description}</p>

            <div className="mt-2">
              {selectedTicket.runbookIds.map((id) => (
                <span
                  key={id}
                  className="inline-block mr-1 mb-1 px-2 py-0.5 bg-slate-700 rounded text-xs font-mono"
                >
                  {id}
                </span>
              ))}
              {selectedTicket.incidentId && (
                <span className="inline-block mr-1 mb-1 px-2 py-0.5 bg-slate-800 rounded text-xs font-mono text-slate-300">
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
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  className="w-full rounded border-slate-600 bg-slate-800 p-2"
                />
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleDecide('approve')}
                    disabled={!canApprove || isPending}
                    title={!canApprove ? 'Requires the operator role' : undefined}
                    className="px-4 py-2 bg-emerald-600 rounded disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDecide('reject')}
                    disabled={!canApprove || note.trim() === '' || isPending}
                    title={!canApprove ? 'Requires the operator role' : undefined}
                    className="px-4 py-2 bg-red-600 rounded disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
                {!canApprove && (
                  <p role="note" className="mt-1 text-sm text-slate-400">
                    Read-only: approving needs the operator role.
                  </p>
                )}
                {error && <p className="mt-1 text-red-400">{error.message}</p>}
              </div>
            )}

            <div className="mt-4">
              <h5 className="font-medium">Audit trail</h5>
              {auditLoading && <p className="text-slate-400 text-sm">Loading audit…</p>}
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
      </div>
    </div>
  );
};
