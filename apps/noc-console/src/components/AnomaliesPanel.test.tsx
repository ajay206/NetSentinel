import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AnomaliesPanel } from './AnomaliesPanel';
import { AnomalyList } from '../types.anomaly';

const baseProps = {
  kpi: 'dlThroughputMbps',
  onKpiChange: () => {},
};

describe('AnomaliesPanel', () => {
  it('shows empty state message', () => {
    const data: AnomalyList = { kpi: 'dlThroughputMbps', hours: 24, items: [] };
    render(<AnomaliesPanel {...baseProps} data={data} isLoading={false} isError={false} />);
    expect(screen.getByText(/No anomalies in the last 24 h/i)).toBeInTheDocument();
  });

  it('renders rows with correct badge and arrow', () => {
    const data: AnomalyList = {
      kpi: 'dlThroughputMbps',
      hours: 24,
      items: [
        {
          cellId: 'cell-1',
          region: 'R1',
          ts: '2024-01-01T12:00:00Z',
          value: 100,
          score: 6.1,
          method: 'zscore',
          direction: 'high',
        },
      ],
    };
    render(<AnomaliesPanel {...baseProps} data={data} isLoading={false} isError={false} />);
    expect(screen.getByText('cell-1')).toBeInTheDocument();
    expect(screen.getByText('R1')).toBeInTheDocument();
    expect(screen.getByText(/z 6\.1/)).toBeInTheDocument();
    expect(screen.getByText('▲')).toBeInTheDocument();
  });

  it('shows error message', () => {
    render(<AnomaliesPanel {...baseProps} data={undefined} isLoading={false} isError={true} />);
    expect(screen.getByText(/ml-service unreachable/i)).toBeInTheDocument();
  });

  it('displays count badge', () => {
    const data: AnomalyList = {
      kpi: 'dlThroughputMbps',
      hours: 24,
      items: [
        { cellId: 'c1', region: 'R', ts: '', value: 0, score: 5, method: 'zscore', direction: 'low' },
        { cellId: 'c2', region: 'R', ts: '', value: 0, score: 4, method: 'cusum', direction: 'high' },
      ],
    };
    render(<AnomaliesPanel {...baseProps} data={data} isLoading={false} isError={false} />);
    expect(screen.getByText('2')).toBeInTheDocument();
  });
});
