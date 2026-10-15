import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RcaGraph } from './RcaGraph';
import { NetworkMap } from '../components/NetworkMap';
import type { Topology } from '../types';
import type { ImpactResult } from '../types.graph';

const site = (siteId: string, kind: string, lat: number, lon: number) => ({
  siteId,
  name: `Site ${siteId}`,
  region: 'north',
  kind,
  lat,
  lon,
  nodes: [{ nodeId: `${siteId}-N1`, kind: 'gnb', cells: [`${siteId}-N1-C1`, `${siteId}-N1-C2`] }],
});

const topology = {
  seed: 42,
  small: true,
  regions: ['north'],
  sites: [
    site('SITE-001', 'core', 50, 10),
    site('SITE-004', 'hub', 51, 11),
    site('SITE-010', 'access', 52, 12),
  ],
  links: [
    { linkId: 'LNK-003', a: 'SITE-001', b: 'SITE-004', kind: 'fibre', role: 'core' },
    { linkId: 'LNK-012', a: 'SITE-004', b: 'SITE-010', kind: 'fibre', role: 'access' },
  ],
  counts: { regions: 1, sites: 3, nodes: 3, cells: 6, links: 2 },
} as unknown as Topology;

const answer: ImpactResult = {
  target: { type: 'link', id: 'LNK-012' },
  impactedSites: [
    {
      siteId: 'SITE-010',
      kind: 'access',
      reason: 'isolated',
      cells: ['SITE-010-N1-C1', 'SITE-010-N1-C2'],
    },
  ],
  cellsLost: 2,
  sitesIsolated: 1,
  backend: 'neo4j',
  elapsedMs: 6.4,
};

function renderPanel(fetchImpl: typeof fetch, onImpact = vi.fn()) {
  vi.stubGlobal('fetch', fetchImpl);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <RcaGraph topology={topology} onImpact={onImpact} />
    </QueryClientProvider>,
  );
  return onImpact;
}

afterEach(() => vi.unstubAllGlobals());

describe('RcaGraph (Step 14)', () => {
  it('asks the gateway which cells lose service when LNK-012 fails', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(answer), { status: 200 }));
    const onImpact = renderPanel(fetchMock as unknown as typeof fetch);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Failed element'), { target: { value: 'LNK-012' } });

    expect(await screen.findByTestId('impact-summary')).toHaveTextContent(
      'LNK-012 fails → 1 site isolated, 2 cells lose service',
    );
    expect(screen.getByTestId('impact-latency')).toHaveTextContent('neo4j · 6.4 ms');
    const table = screen.getByTestId('impact-table');
    expect(table).toHaveTextContent('SITE-010');
    expect(table).toHaveTextContent('Isolated from core');
    expect(table).toHaveTextContent('SITE-010-N1-C1, SITE-010-N1-C2');
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toBe(
      '/api/graph/impact?linkId=LNK-012',
    );
    await waitFor(() =>
      expect(onImpact).toHaveBeenLastCalledWith({ type: 'link', id: 'LNK-012' }, answer),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    await waitFor(() => expect(onImpact).toHaveBeenLastCalledWith(null, null));
  });

  it('switches to sites and nodes and sends the right parameter', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            ...answer,
            target: { type: 'node', id: 'SITE-004-N1' },
            impactedSites: [],
            cellsLost: 0,
            sitesIsolated: 0,
          }),
          { status: 200 },
        ),
    );
    renderPanel(fetchMock as unknown as typeof fetch);
    fireEvent.change(screen.getByLabelText('Failure type'), { target: { value: 'node' } });
    fireEvent.change(screen.getByLabelText('Failed element'), { target: { value: 'SITE-004-N1' } });
    expect(await screen.findByText(/redundant path/)).toBeInTheDocument();
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toBe(
      '/api/graph/impact?nodeId=SITE-004-N1',
    );
  });

  it('shows the gateway error when the graph profile is off', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            detail: 'topology-service unreachable (start the `graph` compose profile)',
          }),
          {
            status: 503,
          },
        ),
    );
    renderPanel(fetchMock as unknown as typeof fetch);
    fireEvent.change(screen.getByLabelText('Failed element'), { target: { value: 'LNK-003' } });
    expect(await screen.findByText(/start the `graph` compose profile/)).toBeInTheDocument();
  });
});

describe('NetworkMap impact radius (Step 14)', () => {
  it('rings impacted sites and draws the failed link red', () => {
    const { container } = render(
      <NetworkMap
        topology={topology}
        isLoading={false}
        isError={false}
        severityBySite={{}}
        impactedSiteIds={new Set(['SITE-010'])}
        failedLinkId="LNK-012"
      />,
    );
    const rings = container.querySelectorAll('[data-impacted]');
    expect([...rings].map((r) => r.getAttribute('data-impacted'))).toEqual(['SITE-010']);
    const failed = container.querySelectorAll('line[data-failed]');
    expect([...failed].map((l) => l.getAttribute('data-link-id'))).toEqual(['LNK-012']);
  });

  it('has no highlight without an impact', () => {
    const { container } = render(
      <NetworkMap topology={topology} isLoading={false} isError={false} severityBySite={{}} />,
    );
    expect(container.querySelectorAll('[data-impacted], line[data-failed]')).toHaveLength(0);
  });
});
