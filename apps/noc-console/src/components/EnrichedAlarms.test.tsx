import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EnrichedAlarms } from './EnrichedAlarms';
import { makeEnriched } from '../test/enrichedFixture';

describe('EnrichedAlarms', () => {
  it('shows the empty state', () => {
    render(<EnrichedAlarms alarms={[]} />);
    expect(screen.getByText('Enriched alarm feed')).toBeInTheDocument();
    expect(screen.getByText(/Waiting for enriched alarms/)).toBeInTheDocument();
  });

  it('renders region, dedup badge, root and symptom', () => {
    const root = makeEnriched({
      id: 'r',
      perceivedSeverity: 'critical',
      dedup: { key: 'k1', count: 3, firstSeen: '2026-10-14T10:00:00Z', isDuplicate: true },
      correlation: { groupId: 'corr-1', rootSiteId: 'S-N-001', role: 'root' },
    });
    const symptom = makeEnriched({
      id: 's',
      siteId: 'S-N-007',
      enrichment: { ...root.enrichment, region: 'Central', siteName: null },
      dedup: { key: 'k2', count: 1, firstSeen: '2026-10-14T10:00:00Z', isDuplicate: false },
      correlation: { groupId: 'corr-1', rootSiteId: 'S-N-001', role: 'symptom' },
    });
    render(<EnrichedAlarms alarms={[root, symptom]} />);
    expect(screen.getByText('×3')).toBeInTheDocument();
    expect(screen.getByText('Central')).toBeInTheDocument();
    expect(screen.getByText('root')).toBeInTheDocument();
    expect(screen.getByText('↳ S-N-001')).toBeInTheDocument();
    const summary = screen.getByTestId('enriched-summary');
    expect(summary).toHaveTextContent('Alarms 2');
    expect(summary).toHaveTextContent('Deduped 2');
    expect(summary).toHaveTextContent('Groups 1');
  });

  it('selects a row on click and shows the fault badge slot (W7)', () => {
    const alarm = makeEnriched({
      id: 'sel',
      dedup: { key: 'k-sel', count: 1, firstSeen: '2026-10-14T10:00:00Z', isDuplicate: false },
    });
    const onSelect = vi.fn();
    const { rerender } = render(<EnrichedAlarms alarms={[alarm]} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('LOS'));
    expect(onSelect).toHaveBeenCalledWith(alarm);
    rerender(
      <EnrichedAlarms
        alarms={[alarm]}
        onSelect={onSelect}
        selectedKey="k-sel"
        selectedBadge={<span data-testid="fault-badge">Fibre cut 91%</span>}
      />,
    );
    expect(screen.getByTestId('fault-badge')).toHaveTextContent('Fibre cut 91%');
  });
});
