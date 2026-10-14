import { describe, expect, test } from 'vitest';
import { worstSeverityBySite } from './siteStatus';
import type { Alarm, PerceivedSeverity } from '../types';

function mkAlarm(partial: Partial<Alarm>): Alarm {
  return {
    id: '',
    href: '',
    alarmType: '',
    perceivedSeverity: 'warning',
    probableCause: '',
    specificProblem: '',
    siteId: '',
    alarmRaisedTime: '',
    state: '',
    sourceSystemId: '',
    alarmedObject: { id: '' },
    ...partial,
  };
}

describe('worstSeverityBySite', () => {
  test('cleared alarm removes previous active alarms', () => {
    const alarms: Alarm[] = [
      mkAlarm({
        siteId: 'siteA',
        perceivedSeverity: 'critical',
        alarmRaisedTime: '2023-01-01T10:00:00Z',
        alarmType: 'type1',
        probableCause: 'cause1',
      }),
      mkAlarm({
        siteId: 'siteA',
        perceivedSeverity: 'cleared',
        alarmRaisedTime: '2023-01-01T11:00:00Z',
        alarmType: 'type1',
        probableCause: 'cause1',
      }),
    ]; // newest first (cleared is newest)

    const result = worstSeverityBySite(alarms);
    expect(result).toEqual({});
  });

  test('multiple severities keep the highest', () => {
    const alarms: Alarm[] = [
      mkAlarm({
        siteId: 'siteB',
        perceivedSeverity: 'major',
        alarmRaisedTime: '2023-01-01T09:00:00Z',
        alarmType: 'type2',
        probableCause: 'cause2',
      }),
      mkAlarm({
        siteId: 'siteB',
        perceivedSeverity: 'critical',
        alarmRaisedTime: '2023-01-01T10:00:00Z',
        alarmType: 'type3',
        probableCause: 'cause3',
      }),
    ]; // newest first (critical newest)

    const result = worstSeverityBySite(alarms);
    expect(result).toEqual({ siteB: 'critical' });
  });

  test('independent sites are handled separately', () => {
    const alarms: Alarm[] = [
      mkAlarm({
        siteId: 'siteX',
        perceivedSeverity: 'minor',
        alarmRaisedTime: '2023-01-01T08:00:00Z',
        alarmType: 't1',
        probableCause: 'c1',
      }),
      mkAlarm({
        siteId: 'siteY',
        perceivedSeverity: 'warning',
        alarmRaisedTime: '2023-01-01T09:00:00Z',
        alarmType: 't2',
        probableCause: 'c2',
      }),
      mkAlarm({
        siteId: 'siteX',
        perceivedSeverity: 'major',
        alarmRaisedTime: '2023-01-01T10:00:00Z',
        alarmType: 't3',
        probableCause: 'c3',
      }),
    ]; // newest first (major for X newest)

    const result = worstSeverityBySite(alarms);
    const expected: Record<string, PerceivedSeverity> = {
      siteX: 'major',
      siteY: 'warning',
    };
    expect(result).toEqual(expected);
  });
});
