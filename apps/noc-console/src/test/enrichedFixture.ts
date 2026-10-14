import type { EnrichedAlarm } from '../types.enriched';

export function makeEnriched(overrides: Partial<EnrichedAlarm> = {}): EnrichedAlarm {
  return {
    id: 'a-1',
    alarmType: 'communicationsAlarm',
    perceivedSeverity: 'major',
    probableCause: 'lossOfSignal',
    specificProblem: 'LOS',
    siteId: 'S-N-001',
    alarmRaisedTime: '2026-10-14T10:00:00Z',
    state: 'raised',
    sourceSystemId: 'netgen-simulator',
    alarmedObject: { id: 'S-N-001' },
    ingestedAt: '2026-10-14T10:00:01Z',
    enrichment: {
      siteName: 'North Hub 1',
      region: 'North',
      siteKind: 'hub',
      nodeTypes: ['gNB', 'router'],
      parentSiteId: null,
      known: true,
    },
    dedup: { key: 'S-N-001|x|lossOfSignal|LOS', count: 1, firstSeen: '2026-10-14T10:00:00Z', isDuplicate: false },
    correlation: { groupId: null, rootSiteId: null, role: 'none' },
    ...overrides,
  };
}
