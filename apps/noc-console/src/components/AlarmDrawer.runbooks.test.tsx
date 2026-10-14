import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { ShapDrawer } from './ShapDrawer';
import { RunbooksPanel } from '../views/RunbooksPanel';
import { makeEnriched } from '../test/enrichedFixture';
import type { RunbookHit, RunbookDoc } from '../types.runbook';

const alarm = makeEnriched({
  id: 'a1',
  siteId: 'SITE-011',
  perceivedSeverity: 'major',
  specificProblem: 'Cell unavailable',
});

const hits: RunbookHit[] = [
  {
    runbookId: 'RB-HWD-004',
    title: 'Clock oscillator drift',
    section: 'Diagnosis',
    snippet: 'Check GPS lock.',
    score: 0.812,
    faultType: 'hw_drift',
  },
  {
    runbookId: 'RB-FIB-002',
    title: 'Last-mile fibre cut',
    section: 'Triage',
    snippet: 'Single access site down.',
    score: 0.65,
    faultType: 'fibre_cut',
  },
];

const doc: RunbookDoc = {
  id: 'RB-HWD-004',
  title: 'Clock oscillator drift',
  faultType: 'hw_drift',
  tags: [],
  markdown: '# Clock oscillator drift\n\nStep 1: check GPS lock.',
};

function renderDrawer(selectedId: string | null, onSelect = vi.fn(), onClose = vi.fn()) {
  render(
    <ShapDrawer
      alarm={alarm}
      isLoading={false}
      isError={false}
      onClose={onClose}
      runbooks={
        <RunbooksPanel
          alarmLabel="Cell unavailable @ SITE-011"
          hits={hits}
          selectedId={selectedId}
          onSelect={onSelect}
          doc={selectedId ? doc : undefined}
        />
      }
    />,
  );
  return { onSelect, onClose };
}

describe('alarm detail drawer with suggested runbooks', () => {
  it('shows alarm details and clickable runbooks with title and score inside the drawer', () => {
    const { onSelect } = renderDrawer(null);
    const drawer = screen.getByTestId('alarm-drawer');
    expect(within(drawer).getByTestId('alarm-details')).toHaveTextContent('SITE-011');
    expect(within(drawer).getByRole('heading', { name: 'Suggested runbooks' })).toBeInTheDocument();
    const rows = within(drawer).getAllByTestId('runbook-hit');
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('Clock oscillator drift');
    expect(rows[0]).toHaveTextContent('0.812');
    fireEvent.click(rows[1]);
    expect(onSelect).toHaveBeenCalledWith('RB-FIB-002');
  });

  it('renders the selected runbook markdown and closes on Escape', () => {
    const { onClose } = renderDrawer('RB-HWD-004');
    expect(screen.getByText(/Step 1: check GPS lock/)).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });
});
