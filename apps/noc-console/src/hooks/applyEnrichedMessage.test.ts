import { describe, expect, it } from 'vitest';
import { applyEnrichedMessage } from './useEnrichedFeed';
import { makeEnriched } from '../test/enrichedFixture';

const dedup = (key: string, count = 1) => ({
  key,
  count,
  firstSeen: '2026-10-14T10:00:00Z',
  isDuplicate: count > 1,
});

describe('applyEnrichedMessage', () => {
  it('sorts a snapshot newest first', () => {
    const older = makeEnriched({ id: 'o', alarmRaisedTime: '2026-10-14T09:00:00Z', dedup: dedup('ko') });
    const newer = makeEnriched({ id: 'n', alarmRaisedTime: '2026-10-14T11:00:00Z', dedup: dedup('kn') });
    const out = applyEnrichedMessage([], { type: 'snapshot', alarms: [older, newer] });
    expect(out.map((a) => a.id)).toEqual(['n', 'o']);
  });

  it('collapses a snapshot to the latest alarm per dedup key', () => {
    const first = makeEnriched({ id: 'x1', dedup: dedup('k1') });
    const second = makeEnriched({ id: 'x2', dedup: dedup('k1', 2) });
    const out = applyEnrichedMessage([], { type: 'snapshot', alarms: [first, second] });
    expect(out.map((a) => a.id)).toEqual(['x2']);
  });

  it('replaces an alarm with the same dedup key and moves it to the top', () => {
    const a = makeEnriched({ id: 'a', dedup: dedup('k1') });
    const b = makeEnriched({ id: 'b', dedup: dedup('k2') });
    const a2 = makeEnriched({ id: 'a2', dedup: dedup('k1', 2) });
    const out = applyEnrichedMessage([b, a], { type: 'enriched', alarm: a2 });
    expect(out.map((x) => x.id)).toEqual(['a2', 'b']);
    expect(out[0].dedup.count).toBe(2);
  });

  it('prepends new keys and truncates to max', () => {
    const prev = [makeEnriched({ id: '1', dedup: dedup('k1') }), makeEnriched({ id: '2', dedup: dedup('k2') })];
    const out = applyEnrichedMessage(prev, { type: 'enriched', alarm: makeEnriched({ id: '3', dedup: dedup('k3') }) }, 2);
    expect(out.map((x) => x.id)).toEqual(['3', '1']);
  });
});
