import { describe, it, expect } from 'vitest';
import { applyMessage } from './useAlarmFeed';
import type { Alarm, WsMessage } from '../types';

function makeAlarm(
  id: string,
  raisedTime: string,
  severity: Alarm['perceivedSeverity'] = 'minor'
): Alarm {
  return {
    id,
    alarmType: 'Test Alarm',
    perceivedSeverity: severity,
    probableCause: 'Test Cause',
    specificProblem: 'Test Problem',
    siteId: 'SITE-001',
    alarmRaisedTime: raisedTime,
    state: 'active',
    sourceSystemId: 'SYS-01',
    alarmedObject: { id: 'OBJ-001' },
  };
}

describe('applyMessage', () => {
  it('handles snapshot and sorts newest-first', () => {
    const msg: WsMessage = {
      type: 'snapshot',
      alarms: [
        makeAlarm('a', '2024-01-01T10:00:00Z'),
        makeAlarm('b', '2024-01-01T12:00:00Z'),
      ],
    };
    const result = applyMessage([], msg);
    expect(result[0].id).toBe('b');
    expect(result[1].id).toBe('a');
  });

  it('dedupes by id on alarm message', () => {
    const existing = [makeAlarm('a', '2024-01-01T10:00:00Z')];
    const msg: WsMessage = {
      type: 'alarm',
      alarm: makeAlarm('a', '2024-01-01T11:00:00Z', 'critical'),
    };
    const result = applyMessage(existing, msg);
    expect(result).toHaveLength(1);
    expect(result[0].perceivedSeverity).toBe('critical');
  });

  it('caps at max', () => {
    const alarms: Alarm[] = [];
    for (let i = 0; i < 250; i++) {
      alarms.push(makeAlarm(`alarm-${i}`, `2024-01-01T10:0${(i % 10)}:00Z`));
    }
    const msg: WsMessage = { type: 'snapshot', alarms };
    const result = applyMessage([], msg, 200);
    expect(result).toHaveLength(200);
  });

  it('prepends new alarm newest-first', () => {
    const existing = [makeAlarm('a', '2024-01-01T10:00:00Z')];
    const msg: WsMessage = {
      type: 'alarm',
      alarm: makeAlarm('b', '2024-01-01T11:00:00Z'),
    };
    const result = applyMessage(existing, msg);
    expect(result[0].id).toBe('b');
    expect(result[1].id).toBe('a');
  });
});
