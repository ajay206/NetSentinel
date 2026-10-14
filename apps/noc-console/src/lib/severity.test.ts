import { describe, it, expect } from 'vitest';
import { severityRank, severityStyles, getSeverityStyles } from './severity';

describe('severity', () => {
  it('ranks severities correctly', () => {
    expect(severityRank.critical).toBeGreaterThan(severityRank.major);
    expect(severityRank.major).toBeGreaterThan(severityRank.minor);
    expect(severityRank.minor).toBeGreaterThan(severityRank.warning);
    expect(severityRank.warning).toBeGreaterThan(severityRank.cleared);
  });

  it('returns styles for each severity', () => {
    const severities: Array<keyof typeof severityStyles> = [
      'critical',
      'major',
      'minor',
      'warning',
      'cleared',
    ];
    severities.forEach((s) => {
      const styles = getSeverityStyles(s);
      expect(styles.badge).toBeTruthy();
      expect(styles.rowBorder).toBeTruthy();
    });
  });
});
