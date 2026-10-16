import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { IncidentBoard } from './IncidentBoard';
import type { IncidentList } from '../types.incident';

const createMockData = (overrides: Partial<IncidentList> = {}): IncidentList => ({
  items: [
    {
      id: 'inc-critical',
      rootSiteId: 'site-root-1',
      siteIds: ['site-1', 'site-2'],
      alarmIds: ['alarm-1', 'alarm-2'],
      alarmKeys: ['key-1', 'key-2'],
      alarmCount: 2,
      severity: 'critical',
      region: 'us-east',
      firstSeen: '2024-01-01T10:00:00Z',
      lastSeen: '2024-01-01T10:02:05Z',
      status: 'open',
      version: 1,
    },
    {
      id: 'inc-major',
      rootSiteId: 'site-root-2',
      siteIds: ['site-3'],
      alarmIds: ['alarm-3'],
      alarmKeys: ['key-3'],
      alarmCount: 1,
      severity: 'major',
      region: 'eu-west',
      firstSeen: '2024-01-01T10:00:00Z',
      lastSeen: '2024-01-01T10:01:30Z',
      status: 'open',
      version: 1,
    },
    {
      id: 'inc-cleared',
      rootSiteId: 'site-root-3',
      siteIds: ['site-4'],
      alarmIds: ['alarm-4'],
      alarmKeys: ['key-4'],
      alarmCount: 1,
      severity: 'cleared',
      region: null,
      firstSeen: '2024-01-01T09:00:00Z',
      lastSeen: '2024-01-01T09:30:00Z',
      status: 'cleared',
      version: 1,
    },
  ],
  total: 3,
  stats: {
    alarms: 4,
    incidents: 3,
    compressionRatio: 1.3333333333333333,
  },
  ...overrides,
});

describe('IncidentBoard', () => {
  const defaultProps = {
    data: createMockData(),
    isLoading: false,
    isError: false,
    selectedId: null as string | null,
    onSelect: vi.fn(),
  };

  it('renders loading state', () => {
    render(<IncidentBoard {...defaultProps} isLoading={true} />);
    expect(screen.getByTestId('loading-state')).toHaveTextContent('Loading incidents…');
  });

  it('renders error state', () => {
    render(<IncidentBoard {...defaultProps} isError={true} />);
    expect(screen.getByTestId('error-state')).toHaveTextContent('Incident service unavailable');
  });

  it('renders empty state', () => {
    render(
      <IncidentBoard
        {...defaultProps}
        data={{ items: [], total: 0, stats: { alarms: 0, incidents: 0, compressionRatio: 0 } }}
      />,
    );
    expect(screen.getByTestId('empty-state')).toHaveTextContent(
      'No incidents yet — run a scenario (e.g. make sim)',
    );
  });

  it('renders stats line with ratio', () => {
    render(<IncidentBoard {...defaultProps} />);
    expect(screen.getByText('4 alarms → 3 incidents (1.3×)')).toBeInTheDocument();
  });

  it('renders cards in sorted order: open critical, open major, cleared', () => {
    render(<IncidentBoard {...defaultProps} />);
    const cards = screen.getAllByTestId(/^incident-inc-/);
    expect(cards[0]).toHaveAttribute('data-testid', 'incident-inc-critical');
    expect(cards[1]).toHaveAttribute('data-testid', 'incident-inc-major');
    expect(cards[2]).toHaveAttribute('data-testid', 'incident-inc-cleared');
  });

  it('clicking a card selects it', () => {
    render(<IncidentBoard {...defaultProps} />);
    const criticalCard = screen.getByTestId('incident-inc-critical');
    fireEvent.click(criticalCard);
    expect(defaultProps.onSelect).toHaveBeenCalledWith('inc-critical');
  });

  it('clicking selected card clears selection', () => {
    render(<IncidentBoard {...defaultProps} selectedId="inc-critical" />);
    const criticalCard = screen.getByTestId('incident-inc-critical');
    fireEvent.click(criticalCard);
    expect(defaultProps.onSelect).toHaveBeenCalledWith(null);
  });

  it('shows clear filter row when incident selected', () => {
    render(<IncidentBoard {...defaultProps} selectedId="inc-critical" />);
    expect(screen.getByText('Showing alarms for inc-critical')).toBeInTheDocument();
    const clearButton = screen.getByTestId('clear-filter');
    expect(clearButton).toHaveTextContent('Clear filter');
    fireEvent.click(clearButton);
    expect(defaultProps.onSelect).toHaveBeenCalledWith(null);
  });

  it('displays severity chips with correct colors', () => {
    render(<IncidentBoard {...defaultProps} />);
    // Theme chips (src/theme.ts severityChip)
    expect(screen.getByTestId('severity-inc-critical').firstChild).toHaveClass('text-red-700');
    expect(screen.getByTestId('severity-inc-major').firstChild).toHaveClass('text-orange-700');
    expect(screen.getByTestId('severity-inc-cleared').firstChild).toHaveClass('text-slate-400');
    expect(screen.getByTestId('severity-inc-critical')).toHaveTextContent('Critical');
  });

  it('displays status badges', () => {
    render(<IncidentBoard {...defaultProps} />);
    expect(screen.getByTestId('status-inc-critical')).toHaveTextContent('OPEN');
    expect(screen.getByTestId('status-inc-critical')).toHaveClass('bg-amber-500/20');
    expect(screen.getByTestId('status-inc-cleared')).toHaveTextContent('CLEARED');
    expect(screen.getByTestId('status-inc-cleared')).toHaveClass('bg-slate-700');
  });

  it('displays duration labels', () => {
    render(<IncidentBoard {...defaultProps} />);
    expect(screen.getByText('2m 05s')).toBeInTheDocument();
    expect(screen.getByText('1m 30s')).toBeInTheDocument();
    expect(screen.getByText('30m 00s')).toBeInTheDocument();
  });

  it('displays root site in mono font', () => {
    render(<IncidentBoard {...defaultProps} />);
    expect(screen.getByText('site-root-1')).toHaveClass('font-mono');
  });

  it('displays alarm count and site count', () => {
    render(<IncidentBoard {...defaultProps} />);
    expect(screen.getByText('2 alarms · 2 sites')).toBeInTheDocument();
    expect(screen.getAllByText('1 alarm · 1 site')).toHaveLength(2);
  });

  it('applies selected ring style', () => {
    render(<IncidentBoard {...defaultProps} selectedId="inc-major" />);
    const majorCard = screen.getByTestId('incident-inc-major');
    expect(majorCard).toHaveClass('ring-2');
    expect(majorCard).toHaveClass('ring-sky-400');
  });

  it('sets aria-pressed on selected card', () => {
    render(<IncidentBoard {...defaultProps} selectedId="inc-major" />);
    const majorCard = screen.getByTestId('incident-inc-major');
    expect(majorCard).toHaveAttribute('aria-pressed', 'true');
    const criticalCard = screen.getByTestId('incident-inc-critical');
    expect(criticalCard).toHaveAttribute('aria-pressed', 'false');
  });
});
