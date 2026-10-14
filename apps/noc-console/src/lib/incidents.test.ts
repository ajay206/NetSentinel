import { describe, it, expect } from 'vitest';
import { sortIncidents, alarmBelongsTo, durationLabel } from './incidents';
import type { Incident } from '../types.incident';

const createIncident = (overrides: Partial<Incident> = {}): Incident => ({
  id: 'inc-1',
  rootSiteId: 'site-root',
  siteIds: ['site-1', 'site-2'],
  alarmIds: ['alarm-1', 'alarm-2'],
  alarmKeys: ['key-1', 'key-2'],
  alarmCount: 2,
  severity: 'major',
  region: 'us-east',
  firstSeen: '2024-01-01T10:00:00Z',
  lastSeen: '2024-01-01T10:02:05Z',
  status: 'open',
  version: 1,
  ...overrides,
});

describe('sortIncidents', () => {
  it('sorts open before cleared', () => {
    const items = [
      createIncident({ id: 'cleared', status: 'cleared', severity: 'critical' }),
      createIncident({ id: 'open', status: 'open', severity: 'minor' }),
    ];
    const sorted = sortIncidents(items);
    expect(sorted[0].id).toBe('open');
    expect(sorted[1].id).toBe('cleared');
  });

  it('sorts by severity rank within same status', () => {
    const items = [
      createIncident({ id: 'minor', severity: 'minor' }),
      createIncident({ id: 'critical', severity: 'critical' }),
      createIncident({ id: 'major', severity: 'major' }),
    ];
    const sorted = sortIncidents(items);
    expect(sorted.map((i) => i.id)).toEqual(['critical', 'major', 'minor']);
  });

  it('sorts by lastSeen desc when status and severity equal', () => {
    const items = [
      createIncident({ id: 'older', lastSeen: '2024-01-01T10:00:00Z' }),
      createIncident({ id: 'newer', lastSeen: '2024-01-01T10:05:00Z' }),
    ];
    const sorted = sortIncidents(items);
    expect(sorted[0].id).toBe('newer');
    expect(sorted[1].id).toBe('older');
  });
});

describe('alarmBelongsTo', () => {
  const incident = createIncident();

  it('returns true when incident is null', () => {
    expect(alarmBelongsTo(null, { id: 'any' })).toBe(true);
  });

  it('returns true when alarm.id matches', () => {
    expect(alarmBelongsTo(incident, { id: 'alarm-1' })).toBe(true);
  });

  it('returns true when dedup.key matches', () => {
    expect(alarmBelongsTo(incident, { id: 'other', dedup: { key: 'key-1' } })).toBe(true);
  });

  it('returns false when no match', () => {
    expect(alarmBelongsTo(incident, { id: 'unknown', dedup: { key: 'unknown' } })).toBe(false);
  });
});

describe('durationLabel', () => {
  it('formats minutes and seconds', () => {
    expect(durationLabel('2024-01-01T10:00:00Z', '2024-01-01T10:02:05Z')).toBe('2m 05s');
  });

  it('formats seconds only when under a minute', () => {
    expect(durationLabel('2024-01-01T10:00:00Z', '2024-01-01T10:00:45Z')).toBe('45s');
  });

  it('pads seconds to two digits', () => {
    expect(durationLabel('2024-01-01T10:00:00Z', '2024-01-01T10:01:03Z')).toBe('1m 03s');
  });

  it('returns 0s for negative diff', () => {
    expect(durationLabel('2024-01-01T10:01:00Z', '2024-01-01T10:00:00Z')).toBe('0s');
  });
});
