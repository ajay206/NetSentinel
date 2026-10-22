import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ServiceHealth } from './ServiceHealth';

const health = { status: 'ok' as const, services: [{ name: 'ml-service', status: 'up' as const }], checkedAt: '2026-10-21T10:00:00Z' };

function renderWith(fetchImpl: (u: string) => unknown) {
  vi.stubGlobal('fetch', vi.fn(async (u: string) => ({ ok: true, json: async () => fetchImpl(u) })));
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><ServiceHealth health={health as never} isError={false} /></QueryClientProvider>);
}

afterEach(() => vi.unstubAllGlobals());

describe('ServiceHealth W22 sparklines', () => {
  it('shows sparklines and Grafana/Langfuse links when Prometheus answers', async () => {
    renderWith((u) =>
      u.includes('sparklines')
        ? { enabled: true, services: { 'ml-service': { p95Ms: [10, 20, 30], errorRate: [0, 0, 0.02] } } }
        : u.includes('model/info')
          ? { name: 'fault_classifier', version: 'v1', gate: { passed: false, reasons: ['macro_f1 0.2 < 0.8'] }, loaded: true }
          : { grafana: 'http://localhost:3000', langfuse: 'http://localhost:3001', mlflow: null, prometheus: null },
    );
    await waitFor(() => expect(screen.getByTestId('service-spark')).toBeInTheDocument());
    expect(screen.getByText(/p95 30 ms/)).toBeInTheDocument();
    expect(screen.getByText('2.0% 5xx')).toBeInTheDocument();
    expect(screen.getByText('Open Grafana')).toHaveAttribute('href', 'http://localhost:3000');
    expect(screen.queryByText('Open MLflow')).toBeNull();
    expect(screen.getByTestId('model-version-chip')).toHaveTextContent('gate blocked');
  });

  it('hides sparklines and links when the obs profile is off', async () => {
    renderWith((u) => (u.includes('sparklines') ? { enabled: true, error: 'prometheus unreachable', services: {} } : { grafana: 'x', langfuse: null, mlflow: null, prometheus: null }));
    await waitFor(() => expect(screen.getByText('ml-service')).toBeInTheDocument());
    expect(screen.queryByTestId('service-spark')).toBeNull();
    expect(screen.queryByTestId('obs-links')).toBeNull();
  });
});
