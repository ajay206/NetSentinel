import { render, screen } from '@testing-library/react';
import { KpiActivity } from './KpiActivity';

describe('KpiActivity', () => {
  it('distinguishes a connected stream from old sample data', () => {
    render(
      <KpiActivity
        status="open"
        activity={{
          totalSamples: 100,
          ratePerMin: 12,
          cellsReporting: 3,
          lastSampleTime: new Date(Date.now() - 61_000).toISOString(),
          lastSample: null,
          averages: {},
        }}
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent('Sample stream connected');
    expect(screen.getByText('No recent sample')).toHaveAttribute(
      'title',
      'No KPI sample has arrived in the last 60 seconds.',
    );
  });
});
