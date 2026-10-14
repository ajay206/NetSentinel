import { describe, it, expect } from 'vitest';
import { buildRunbookQuery } from './runbookQuery';

describe('buildRunbookQuery', () => {
  it('joins non-empty parts and splits camelCase', () => {
    const alarm = {
      specificProblem: 'Loss of signal',
      probableCause: 'lossOfSignal',
      alarmType: 'communicationAlarm',
      enrichment: {
        nodeTypes: ['router', 'switch'],
        siteKind: 'core',
      },
    };
    const faultType = 'link_failure';

    const query = buildRunbookQuery(alarm, faultType);

    expect(query).toContain('loss of signal');
    expect(query).toContain('loss of signal');
    expect(query).toContain('communication alarm');
    expect(query).toContain('link failure');
    expect(query).toContain('router switch');
    expect(query).toContain('core');
  });

  it('handles missing optional fields', () => {
    const alarm = {
      specificProblem: null,
      probableCause: 'powerSupplyFailure',
      alarmType: null,
      enrichment: {
        nodeTypes: [],
        siteKind: null,
      },
    };

    const query = buildRunbookQuery(alarm, null);

    expect(query).toBe('power supply failure');
  });

  it('collapses whitespace and truncates to 300 chars', () => {
    const longText = 'a'.repeat(200);
    const alarm = {
      specificProblem: longText,
      probableCause: '  multiple   spaces  ',
      alarmType: 'testAlarm',
      enrichment: {
        nodeTypes: ['type1', 'type2'],
        siteKind: 'edge',
      },
    };

    const query = buildRunbookQuery(alarm, 'fault_type');

    expect(query.length).toBeLessThanOrEqual(300);
    expect(query).not.toMatch(/\s{2,}/);
  });
});
