import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';

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
  beforeEach(() => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            status: 'ok',
            services: [
              { name: 'Core Router', status: 'up', detail: 'Primary' },
              { name: 'Edge Switch', status: 'down', detail: 'Link down' },
            ],
            checkedAt: new Date().toISOString(),
          }),
      })
    ) as unknown as typeof fetch;

    (globalThis as unknown as { WebSocket: unknown }).WebSocket = FakeWebSocket;
  });

  it('renders heading and placeholders', async () => {
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    );

    expect(screen.getByText('NetSentinel')).toBeInTheDocument();
    expect(screen.getByText('NOC Console')).toBeInTheDocument();
    expect(screen.getByText(/LOCAL · SYNTHETIC DATA/)).toBeInTheDocument();
    expect(screen.getByText('Network map')).toBeInTheDocument();
    expect(screen.getByText('KPI charts')).toBeInTheDocument();
    expect(screen.getByText('Anomalies')).toBeInTheDocument();
    expect(screen.getByText('Copilot')).toBeInTheDocument();
  });
});
