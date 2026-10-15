import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import type { Role, Session } from './lib/auth';

class FakeWebSocket {
  static OPEN = 1;
  readyState = 1;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  constructor(public url: string) {}
  send() {}
  close() {}
}

const INC = {
  id: 'INC-0123456789',
  rootSiteId: 'SITE-011',
  siteIds: ['SITE-011'],
  alarmIds: ['a1'],
  alarmKeys: [],
  alarmCount: 3,
  severity: 'critical',
  region: 'South',
  firstSeen: '2026-01-01T00:00:00Z',
  lastSeen: '2026-01-01T00:05:00Z',
  status: 'open',
  version: 1,
  workflow: null,
};

const TKT = {
  id: 'TKT-00000000AA',
  status: 'draft',
  title: 'Fibre cut at SITE-011',
  description: 'drafted by the copilot',
  severity: 'critical',
  siteId: 'SITE-011',
  incidentId: 'INC-0123456789',
  faultType: 'fibre_cut',
  runbookIds: ['RB-FIB-001'],
  sourceIds: [],
  createdBy: 'service:mcp',
  createdVia: 'mcp',
  createdAt: '2026-01-01T00:06:00Z',
  decidedBy: null,
  decidedAt: null,
  decisionNote: null,
  version: 1,
};

const RUN = {
  runId: 'RUN-00000000AA',
  incidentId: 'INC-0123456789',
  siteId: 'SITE-011',
  status: 'awaiting_approval',
  createdAt: '2026-01-01T00:06:00Z',
  updatedAt: '2026-01-01T00:06:01Z',
  agentPath: ['supervisor', 'triage', 'rca', 'remediation'],
  messages: [{ agent: 'rca', text: 'Fibre cut', ts: '' }],
  plan: {
    summary: '1 step',
    steps: [{ text: 'Splice', runbookId: 'RB-FIB-001', section: 'Remediation' }],
    ticketDraft: { title: 'Fibre cut', severity: 'critical', description: '' },
  },
  ticketId: null,
  kgWriteBack: null,
  trace: [],
  report: null,
  tracing: { langfuse: false },
};

const json = (body: unknown, ok = true) =>
  Promise.resolve({ ok, json: () => Promise.resolve(body) });

beforeEach(() => {
  globalThis.fetch = vi.fn((input: RequestInfo) => {
    const url = typeof input === 'string' ? input : input.url;
    if (url.endsWith('/health'))
      return json({ status: 'ok', services: [], checkedAt: new Date().toISOString() });
    if (url.startsWith('/api/incidents'))
      return json({
        items: [INC],
        total: 1,
        stats: { alarms: 3, incidents: 1, compressionRatio: 3 },
      });
    if (url.startsWith('/api/admin/users'))
      return json({
        items: [
          {
            username: 'admin1',
            role: 'admin',
            disabled: false,
            locked: false,
            failedLogins: 0,
            createdAt: 0,
            passwordChangedAt: null,
          },
          {
            username: 'ops1',
            role: 'operator',
            disabled: false,
            locked: true,
            failedLogins: 0,
            createdAt: 0,
            passwordChangedAt: null,
          },
        ],
      });
    if (url.startsWith('/api/admin/audit')) return json({ items: [] });
    if (url.endsWith('/audit') && url.startsWith('/api/tickets/'))
      return json({ ticketId: TKT.id, entries: [] });
    if (url.startsWith('/api/copilot/runs')) return json({ items: [RUN] });
    if (url.startsWith('/api/tickets'))
      return json({ items: [TKT], counts: { draft: 1, approved: 0, rejected: 0 } });
    if (url.startsWith('/api/admin/settings'))
      return json({
        userStore: 'postgres',
        tokenTtlSeconds: 28800,
        rateLimitPerMin: 600,
        loginRateLimitPerMin: 10,
        lockoutThreshold: 5,
        lockoutSeconds: 900,
        demoUsersSeeded: true,
        authDisabled: false,
      });
    return json({});
  }) as unknown as typeof fetch;
  (globalThis as unknown as { WebSocket: unknown }).WebSocket = FakeWebSocket;
});

function renderAs(role: Role) {
  const session: Session = { token: 't', username: `${role}1`, role, expiresAt: Date.now() + 1e6 };
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <App session={session} />
    </QueryClientProvider>,
  );
}

async function selectIncident() {
  fireEvent.click(await screen.findByTestId(`incident-${INC.id}`));
}

describe('role-specific dashboards (Step 13b)', () => {
  it('viewer: read-only, no copilot, no admin tab, no action buttons', async () => {
    renderAs('viewer');
    expect(screen.getByTestId('role-badge')).toHaveTextContent('viewer');
    expect(screen.queryByRole('heading', { name: 'Copilot analyze' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Admin' })).toBeNull();
    await selectIncident();
    expect(screen.getByTestId('workflow-readonly')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Resolve' })).toBeNull();
  });

  it('operator: copilot and incident actions, still no admin tab', async () => {
    renderAs('operator');
    expect(screen.getByRole('heading', { name: 'Copilot analyze' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Admin' })).toBeNull();
    await selectIncident();
    expect(screen.getByTestId('workflow-controls')).toBeInTheDocument();
    const resolve = screen.getByRole('button', { name: 'Resolve' });
    expect(resolve).toBeDisabled(); // a note is required
    fireEvent.change(screen.getByLabelText(`Note for incident ${INC.id}`), {
      target: { value: 'fibre spliced' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }));
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        `/api/incidents/${INC.id}/actions`,
        expect.objectContaining({ method: 'POST' }),
      ),
    );
  });

  it('admin: Admin dashboard with users, audit log and settings', async () => {
    renderAs('admin');
    fireEvent.click(screen.getByRole('button', { name: 'Admin' }));
    expect(await screen.findByTestId('users-table')).toHaveTextContent('ops1');
    expect(screen.getByText('Locked')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Unlock' })).toBeInTheDocument();
    // an admin cannot change their own role from the table
    expect(screen.getByLabelText('Role for admin1')).toBeDisabled();
    expect(await screen.findByTestId('settings-list')).toHaveTextContent('after 5 failed logins');
    expect(screen.getByTestId('audit-log')).toBeInTheDocument();
  });
});

describe('approval queue (Step 16)', () => {
  it('operator opens a related draft from the incident board and approves it', async () => {
    renderAs('operator');
    await selectIncident();
    const related = await screen.findByTestId('related-drafts');
    fireEvent.click(within(related).getByRole('button', { name: `${TKT.id} (draft)` }));
    expect(await screen.findByTestId('ticket-detail')).toHaveTextContent(TKT.title);
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        `/api/tickets/${TKT.id}/approve`,
        expect.objectContaining({ method: 'POST' }),
      ),
    );
  });

  it('viewer sees the queue read-only', async () => {
    renderAs('viewer');
    fireEvent.click(await screen.findByTestId('ticket-row'));
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled();
  });
});

describe('multi-agent copilot (Step 17)', () => {
  it('operator approves the agents plan; RCA graph shows the agent path', async () => {
    renderAs('operator');
    const box = await screen.findByTestId('approval-box');
    expect(screen.getByTestId('rca-agent-path')).toHaveTextContent('triage');
    fireEvent.click(within(box).getByRole('button', { name: 'Approve plan' }));
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        `/api/copilot/runs/${RUN.runId}/approval`,
        expect.objectContaining({ method: 'POST' }),
      ),
    );
  });

  it('viewer reads the trace but cannot approve', async () => {
    renderAs('viewer');
    await screen.findByTestId('approval-box');
    expect(screen.getByRole('button', { name: 'Approve plan' })).toBeDisabled();
  });
});
