import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ApprovalQueue } from './ApprovalQueue';
import type { AuditEntry, Ticket } from '../types.ticket';

const draft: Ticket = {
  id: 'TKT-0000000001',
  status: 'draft',
  title: 'Fibre cut isolates SITE-010',
  description: 'LOS on SITE-010',
  severity: 'critical',
  siteId: 'SITE-010',
  incidentId: 'INC-0123456789',
  faultType: 'fibre_cut',
  runbookIds: ['RB-FIB-001'],
  sourceIds: [],
  createdBy: 'service:mcp',
  createdVia: 'mcp',
  createdAt: '2026-10-15T07:00:00Z',
  decidedBy: null,
  decidedAt: null,
  decisionNote: null,
  version: 1,
};
const approved: Ticket = {
  ...draft,
  id: 'TKT-0000000002',
  status: 'approved',
  createdVia: 'ui',
  createdBy: 'operator',
  decidedBy: 'operator',
  decidedAt: '2026-10-15T07:05:00Z',
};
const audit: AuditEntry[] = [
  {
    seq: 1,
    ts: '2026-10-15T07:00:00Z',
    ticketId: draft.id,
    actor: 'service:mcp',
    role: 'service',
    action: 'created',
    fromStatus: null,
    toStatus: 'draft',
    detail: {},
    hash: 'abcdef0123456789',
  },
];

function setup(over: Partial<React.ComponentProps<typeof ApprovalQueue>> = {}) {
  const props = {
    tickets: [draft, approved],
    status: 'all' as const,
    onStatusChange: vi.fn(),
    selectedId: draft.id,
    onSelect: vi.fn(),
    audit,
    canApprove: true,
    onDecide: vi.fn(),
    ...over,
  };
  render(<ApprovalQueue {...props} />);
  return props;
}

describe('ApprovalQueue (W16)', () => {
  it('lists tickets with the MCP badge and the audit trail', () => {
    setup();
    expect(screen.getAllByTestId('ticket-row')).toHaveLength(2);
    expect(screen.getAllByTestId('via-mcp')).toHaveLength(1);
    expect(screen.getByTestId('audit-trail')).toHaveTextContent('created · service:mcp (service)');
    expect(screen.getByTestId('audit-trail')).toHaveTextContent('abcdef01');
  });

  it('operator approves; reject needs a note', () => {
    const p = setup();
    const reject = screen.getByRole('button', { name: 'Reject' });
    expect(reject).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Decision note'), { target: { value: ' ok ' } });
    expect(reject).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    expect(p.onDecide).toHaveBeenCalledWith('TKT-0000000001', 'approve', 'ok');
  });

  it('viewer is read-only', () => {
    setup({ canApprove: false });
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled();
    expect(screen.getByRole('note')).toHaveTextContent('approving needs the operator role');
  });

  it('decided tickets have no decision buttons; filter and errors', () => {
    const p = setup({ selectedId: approved.id, error: new Error('boom') });
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'approved' } });
    expect(p.onStatusChange).toHaveBeenCalledWith('approved');
  });

  it('shows empty and error states', () => {
    setup({ tickets: [], isError: true, selectedId: null });
    expect(screen.getByText('ticket-service unavailable')).toBeInTheDocument();
  });
});
