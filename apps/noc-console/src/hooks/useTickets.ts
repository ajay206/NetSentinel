import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AuditEntry, Ticket, TicketList, TicketStatus } from '../types.ticket';

async function getJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`ticket-service ${resp.status}`);
  return (await resp.json()) as T;
}

/** W16: the approval queue (viewer role). Polls so MCP drafts show up on their own. */
export function useTickets(status: TicketStatus | 'all') {
  return useQuery<TicketList, Error>({
    queryKey: ['tickets', status],
    queryFn: () => getJson(`/api/tickets${status === 'all' ? '' : `?status=${status}`}`),
    refetchInterval: 10_000,
  });
}

export function useTicketAudit(ticketId: string | null) {
  return useQuery<{ ticketId: string; entries: AuditEntry[] }, Error>({
    queryKey: ['ticket-audit', ticketId],
    queryFn: () => getJson(`/api/tickets/${encodeURIComponent(ticketId ?? '')}/audit`),
    enabled: ticketId !== null,
  });
}

export type DecisionInput = { id: string; decision: 'approve' | 'reject'; note: string };

/** Approve or reject a draft (operator role; the gateway answers 403 otherwise). */
export function useTicketDecision() {
  const qc = useQueryClient();
  return useMutation<Ticket, Error, DecisionInput>({
    mutationFn: async ({ id, decision, note }) => {
      const resp = await fetch(`/api/tickets/${encodeURIComponent(id)}/${decision}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note }),
      });
      const data: unknown = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const detail = (data as { detail?: unknown }).detail;
        throw new Error(typeof detail === 'string' ? detail : `Decision failed (${resp.status})`);
      }
      return data as Ticket;
    },
    onSuccess: (_t, { id }) => {
      void qc.invalidateQueries({ queryKey: ['tickets'] });
      void qc.invalidateQueries({ queryKey: ['ticket-audit', id] });
    },
  });
}
