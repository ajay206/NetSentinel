import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AlarmTimeline } from './AlarmTimeline';
import { stormAnnotation, niceTicks, peakBucket } from '../lib/timeline';
import type { TimelineResponse, TimelineBucket } from '../lib/timeline';

const createBucket = (overrides: Partial<TimelineBucket> = {}): TimelineBucket => ({
  start: '2024-01-01T00:00:00Z',
  total: 10,
  bySeverity: { critical: 2, major: 3, minor: 3, warning: 2, cleared: 0 },
  ...overrides,
});

const createData = (overrides: Partial<TimelineResponse> = {}): TimelineResponse => ({
  bucketSeconds: 60,
  buckets: [
    createBucket({ start: '2024-01-01T00:00:00Z', total: 5 }),
    createBucket({ start: '2024-01-01T00:01:00Z', total: 15 }),
    createBucket({ start: '2024-01-01T00:02:00Z', total: 8 }),
  ],
  total: 28,
  peak: 15,
  ...overrides,
});

describe('components/AlarmTimeline', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders loading state', () => {
    render(<AlarmTimeline isLoading={true} isError={false} />);
    expect(screen.getByText('Loading timeline…')).toBeInTheDocument();
  });

  it('renders error state', () => {
    render(<AlarmTimeline isLoading={false} isError={true} />);
    expect(screen.getByText(/Timeline unavailable/)).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(<AlarmTimeline data={undefined} isLoading={false} isError={false} />);
    expect(screen.getByText('No alarms yet — run a scenario (e.g. make sim).')).toBeInTheDocument();
  });

  it('renders bars for each bucket', () => {
    const data = createData();
    render(<AlarmTimeline data={data} isLoading={false} isError={false} />);
    const bars = screen.getAllByRole('img');
    expect(bars.length).toBeGreaterThan(0);
  });

  it('shows selected bucket details and updates on scrub', () => {
    const data = createData();
    render(<AlarmTimeline data={data} isLoading={false} isError={false} />);
    const slider = screen.getByLabelText('Scrub timeline');
    // follows the newest bucket by default; scrub back to the first one
    fireEvent.change(slider, { target: { value: '0' } });

    // 00:00Z is 05:30 IST
    expect(screen.getByTestId('timeline-selected')).toHaveTextContent('05:30 IST · 5 alarms');

    fireEvent.change(slider, { target: { value: '1' } });
    expect(screen.getByTestId('timeline-selected')).toHaveTextContent('05:31 IST · 15 alarms');
  });

  it('shows burst badge when bucket is burst', () => {
    const data = createData({
      peak: 10,
      buckets: [createBucket({ total: 10 })],
    });
    render(<AlarmTimeline data={data} isLoading={false} isError={false} />);
    expect(screen.getByText('Burst')).toBeInTheDocument();
  });

  it('does not show burst badge when not burst', () => {
    const data = createData({
      peak: 100,
      buckets: [createBucket({ total: 10 })],
    });
    render(<AlarmTimeline data={data} isLoading={false} isError={false} />);
    expect(screen.queryByText('Burst')).not.toBeInTheDocument();
  });

  it('annotates the storm peak with count, time and root site', () => {
    render(
      <AlarmTimeline data={createData()} isLoading={false} isError={false} rootSiteId="SITE-042" />,
    );
    expect(screen.getByTestId('storm-annotation')).toHaveTextContent(
      'Storm: 15 alarms at 05:31 IST, root SITE-042',
    );
    expect(screen.getByTestId('timeline-legend')).toHaveTextContent(/Critical/);
  });

  it('timeline helpers pick the peak and nice ticks', () => {
    const data = createData();
    expect(peakBucket(data)?.bucket.total).toBe(15);
    expect(peakBucket(data)?.index).toBe(1);
    expect(stormAnnotation(data, null)).toMatch(/^Storm: 15 alarms at 05:31 IST/);
    const ticks = niceTicks(15);
    expect(ticks[0]).toBe(0);
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(15);
  });
});
