export type TicketStatus = 'draft' | 'approved' | 'rejected';

/** W16: a ticket from ticket-service (via /api/tickets). */
export interface Ticket {
  id: string;
  status: TicketStatus;
  title: string;
  description: string;
  severity: 'critical' | 'major' | 'minor' | 'warning';
  siteId: string | null;
  incidentId: string | null;
  faultType: string | null;
  runbookIds: string[];
  sourceIds: string[];
  createdBy: string;
  createdVia: 'ui' | 'mcp' | 'api';
  createdAt: string;
  decidedBy: string | null;
  decidedAt: string | null;
  decisionNote: string | null;
  version: number;
}

export interface TicketList {
  items: Ticket[];
  counts: Record<TicketStatus, number>;
}

/** One append-only, hash-chained audit entry. */
export interface AuditEntry {
  seq: number;
  ts: string;
  ticketId: string;
  actor: string;
  role: string;
  action: 'created' | 'approved' | 'rejected';
  fromStatus: string | null;
  toStatus: string;
  detail: Record<string, unknown>;
  prevHash?: string;
  hash: string;
}
