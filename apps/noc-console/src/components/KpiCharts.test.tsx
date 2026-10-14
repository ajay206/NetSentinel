import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { KpiCharts } from './KpiCharts';
import type { KpiCell, KpiSeries } from '../types.kpi';

const cells: KpiCell[] = [
  { cellId: 'SITE-001-N1-C1', siteId: 'SITE-001', region: 'North', lastTs: '2026-10-14T09:00:00Z', sampleCount: 4 },
];
const series: KpiSeries = {
  cellId: 'SITE-001-N1-C1',
  agg: '1h',
  from: '2026-10-14T06:00:00Z',
  to: '2026-10-14T09:00:00Z',
  points: [
    { ts: '2026-10-14T06:00:00Z', dlThroughputMbps: 100, prbUtilPct: 40, rrcSetupSuccessPct: 99, dropCallRatePct: 0.5, availabilityPct: 99.9 },
    { ts: '2026-10-14T07:00:00Z', dlThroughputMbps: 300, prbUtilPct: 60, rrcSetupSuccessPct: 98, dropCallRatePct: 0.7, availabilityPct: 99.8 },
  ],
};

function renderCharts(overrides: Partial<Parameters<typeof KpiCharts>[0]> = {}) {
  return render(
    <KpiCharts
      cells={cells}
      series={series}
      isLoading={false}
      isError={false}
      cellId="SITE-001-N1-C1"
      onCellChange={vi.fn()}
      kpi="dlThroughputMbps"
      onKpiChange={vi.fn()}
      agg="1h"
      onAggChange={vi.fn()}
      hours={24}
      onHoursChange={vi.fn()}
      {...overrides}
    />
  );
}

describe('KpiCharts', () => {
  it('marks anomalies with red dots and a badge (W6)', () => {
    renderCharts({ anomalyTs: ['2026-10-14T07:30:00Z'] });
    expect(screen.getAllByTestId('anomaly-mark')).toHaveLength(1);
    expect(screen.getByTestId('anomaly-badge')).toHaveTextContent('1 anomaly');
  });

  it('shows no badge without anomalies', () => {
    renderCharts();
    expect(screen.queryByTestId('anomaly-badge')).toBeNull();
  });

  it('draws the series with min/max/last and cell options', () => {
    const { container } = renderCharts();
    expect(screen.getByText('KPI charts')).toBeInTheDocument();
    expect(container.querySelector('path')?.getAttribute('d')).toMatch(/^M/);
    expect(screen.getByTestId('kpi-stats')).toHaveTextContent('max 300.00');
    expect(screen.getByTestId('kpi-stats')).toHaveTextContent('last 300.00');
    expect(screen.getByRole('option', { name: 'SITE-001-N1-C1 · North' })).toBeInTheDocument();
  });

  it('shows the empty state', () => {
    renderCharts({ series: { ...series, points: [] } });
    expect(screen.getByText(/No KPI data yet/)).toBeInTheDocument();
  });

  it('shows the error state', () => {
    renderCharts({ isError: true });
    expect(screen.getByText('kpi-service unreachable')).toBeInTheDocument();
  });
});
