import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ShapDrawer } from './ShapDrawer';
import type { EnrichedAlarm } from '../types.enriched';
import type { FaultPrediction, FaultExplanation } from '../types.fault';

import { makeEnriched } from '../test/enrichedFixture';

const alarm: EnrichedAlarm = makeEnriched({
  id: 'a1',
  siteId: 'site-123',
  perceivedSeverity: 'major',
  specificProblem: 'Link down',
  enrichment: {
    siteName: null,
    region: 'EU',
    siteKind: 'hub',
    nodeTypes: [],
    parentSiteId: null,
    known: true,
  },
});

const prediction: FaultPrediction = {
  faultType: 'fibre_cut',
  confidence: 0.72,
  probabilities: {},
  modelVersion: 'v1.2',
};

const explanation: FaultExplanation = {
  faultType: 'fibre_cut',
  confidence: 0.72,
  modelVersion: 'v1.2',
  baseValue: 0.1,
  contributions: [
    { feature: 'latency', value: 10, shap: 0.3 },
    { feature: 'packetLoss', value: 0.05, shap: -0.2 },
  ],
};

describe('ShapDrawer', () => {
  it('renders nothing when alarm is null', () => {
    const { container } = render(
      <ShapDrawer alarm={null} isLoading={false} isError={false} onClose={() => {}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('displays alarm summary and badge', () => {
    render(
      <ShapDrawer
        alarm={alarm}
        prediction={prediction}
        explanation={explanation}
        isLoading={false}
        isError={false}
        onClose={() => {}}
      />
    );
    expect(screen.getByText(/site-123/)).toBeInTheDocument();
    expect(screen.getByText(/EU/)).toBeInTheDocument();
    expect(screen.getByTestId('fault-badge')).toHaveTextContent('Fibre cut 72%');
  });

  it('renders contributions with correct colors and widths', () => {
    render(
      <ShapDrawer
        alarm={alarm}
        prediction={prediction}
        explanation={explanation}
        isLoading={false}
        isError={false}
        onClose={() => {}}
      />
    );
    const bars = screen.getAllByTestId('shap-bar');
    expect(bars[0]).toHaveClass('bg-red-400');
    expect(bars[0]).toHaveStyle({ width: '100%' });
    expect(bars[1]).toHaveClass('bg-sky-400');
    expect(screen.getByText('latency')).toBeInTheDocument();
    expect(screen.getByText('-0.20')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    render(
      <ShapDrawer alarm={alarm} isLoading={false} isError={false} onClose={onClose} />
    );
    fireEvent.click(screen.getByLabelText('Close'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('shows error message when isError true', () => {
    render(
      <ShapDrawer alarm={alarm} isLoading={false} isError={true} onClose={() => {}} />
    );
    expect(screen.getByText(/ml-service unreachable/)).toBeInTheDocument();
  });

  it('keeps the fault badge when SHAP explanation fails', () => {
    render(
      <ShapDrawer
        alarm={alarm}
        prediction={prediction}
        isLoading={false}
        isError={true}
        onClose={() => {}}
      />,
    );
    expect(screen.getByTestId('fault-badge')).toHaveTextContent('Fibre cut 72%');
    expect(screen.getByText(/ml-service unreachable/)).toBeInTheDocument();
  });

  it('shows a SHAP loading state without hiding a ready prediction', () => {
    render(
      <ShapDrawer
        alarm={alarm}
        prediction={prediction}
        isLoading={true}
        isError={false}
        onClose={() => {}}
      />,
    );
    expect(screen.getByTestId('fault-badge')).toHaveTextContent('Fibre cut 72%');
    expect(screen.getByText('Loading SHAP explanation…')).toBeInTheDocument();
  });
});
