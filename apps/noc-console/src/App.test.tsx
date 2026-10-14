import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import type { Topology } from './types';

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;
  readyState = FakeWebSocket.OPEN;
  url: string;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    setTimeout(() => this.onopen?.(), 0);
  }

  send() {}
  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
  }

  _emit(data: string) {
    this.onmessage?.(new MessageEvent('message', { data }));
  }
}

describe('App', () => {
  const queryClient = new QueryClient();

  beforeEach(() => {
    // mock health endpoint
    globalThis.fetch = vi.fn((input: RequestInfo) => {
      const url = typeof input === 'string' ? input : input.url;
      if (url.endsWith('/health')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: 'ok',
              services: [],
              checkedAt: new Date().toISOString(),
            }),
        });
      }
      if (url.endsWith('/api/topology')) {
        const topology: Topology = {
          seed: 1,
          small: true,
          regions: ['North'],
          sites: [
            {
              siteId: 'SITE-001',
              name: 'Core-1',
              region: 'North',
              kind: 'core',
              lat: 41.0082,
              lon: 28.9784,
              nodes: [],
            },
          ],
          links: [],
          counts: {
            regions: 1,
            sites: 1,
            nodes: 0,
            cells: 0,
            links: 0,
          },
        };
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(topology),
        });
      }
      // default fallback
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as unknown as typeof fetch;

    // mock WebSocket
    (globalThis as unknown as { WebSocket: unknown }).WebSocket = FakeWebSocket;
  });

  it('renders headings, map and KPI activity with site label', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    );

    // static headings
    expect(screen.getByText('NetSentinel')).toBeInTheDocument();
    expect(screen.getByText('NOC Console')).toBeInTheDocument();

    // wait for network map heading
    expect(await screen.findByRole('heading', { name: /Network map/i })).toBeInTheDocument();

    // KPI activity heading
    expect(screen.getByRole('heading', { name: /KPI activity/i })).toBeInTheDocument();

    // Header clock and other timestamps carry the IST label
    await waitFor(() => expect(screen.getAllByText(/IST/).length).toBeGreaterThan(0));
    // Network map renders the fixture site
    expect(document.querySelector('[data-site-id="SITE-001"]')).toBeInTheDocument();
    // W8: runbooks panel is mounted and waits for an alarm selection
    expect(screen.getByRole('heading', { name: 'Suggested runbooks' })).toBeInTheDocument();
    expect(screen.getByText('Click an enriched alarm to see runbooks.')).toBeInTheDocument();
    // W9: copilot panel replaces the placeholder
    expect(screen.getByRole('heading', { name: 'Copilot analyze' })).toBeInTheDocument();
  });
});
