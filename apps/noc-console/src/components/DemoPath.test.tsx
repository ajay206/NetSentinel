import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DemoPath } from './DemoPath';
import { demoStages, type DemoStage, type DemoStagesInput } from '../lib/demoPath';

describe('DemoPath component', () => {
  const baseInput = {
    alarmCount: 0,
    anomalyCount: 0,
    faultType: null,
    runbookCount: 0,
    copilotSources: 0,
    copilotCited: false,
  };

  const makeStages = (overrides: Partial<DemoStagesInput> = {}): DemoStage[] => {
    return demoStages({ ...baseInput, ...overrides });
  };

  it('renders all stages with correct hints when none are done', () => {
    const stages = makeStages();
    render(<DemoPath stages={stages} />);

    // all stages should be present
    const ids: DemoStage['id'][] = ['alarms', 'anomaly', 'fault', 'runbooks', 'copilot'];
    ids.forEach((id) => {
      const li = screen.getByTestId(`stage-${id}`);
      expect(li).toBeInTheDocument();
      expect(li).toHaveAttribute('data-done', 'false');
    });

    // first pending hint should be for alarms
    expect(screen.getByText('Run make demo (or make sim) to start fibre_cut')).toBeInTheDocument();
    // no completion badge
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('shows correct hint for the current pending stage', () => {
    const stages = makeStages({ alarmCount: 5, anomalyCount: 0 });
    render(<DemoPath stages={stages} />);

    // alarms done, anomaly pending
    expect(screen.getByTestId('stage-alarms')).toHaveAttribute('data-done', 'true');
    expect(screen.getByTestId('stage-anomaly')).toHaveAttribute('data-done', 'false');

    expect(screen.getByText('Waiting for ml-service anomalies')).toBeInTheDocument();
  });

  it('displays completion badge when all stages are done', () => {
    const stages = makeStages({
      alarmCount: 2,
      anomalyCount: 1,
      faultType: 'critical',
      runbookCount: 3,
      copilotSources: 4,
      copilotCited: true,
    });
    render(<DemoPath stages={stages} />);

    expect(screen.getByRole('status')).toHaveTextContent('Phase 1 demo complete');
    // no hint displayed
    expect(screen.queryByText(/Run make demo/)).not.toBeInTheDocument();
  });

  it('does not mark copilot as done when sources exist but not cited', () => {
    const stages = makeStages({
      alarmCount: 1,
      anomalyCount: 1,
      faultType: 'minor',
      runbookCount: 1,
      copilotSources: 2,
      copilotCited: false,
    });
    render(<DemoPath stages={stages} />);

    // copilot should be pending
    expect(screen.getByTestId('stage-copilot')).toHaveAttribute('data-done', 'false');
    // hint should be for copilot stage
    expect(screen.getByText('Press Analyze site (operator role)')).toBeInTheDocument();
  });
});
