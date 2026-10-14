import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
