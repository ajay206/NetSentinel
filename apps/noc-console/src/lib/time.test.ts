import { formatIST, IST_LABEL } from './time';

describe('formatIST', () => {
  const iso = '2026-10-14T08:45:11Z'; // 14:15:11 IST
  it('formats with date by default', () => {
    const out = formatIST(iso);
    expect(out).toContain('14:15:11');
    expect(out).toContain(IST_LABEL);
    expect(out).toMatch(/^14 Oct 2026, /);
  });

  it('formats time only when date false', () => {
    const out = formatIST(iso, { date: false });
    expect(out).toBe('14:15:11 IST');
  });

  it('returns placeholder for invalid input', () => {
    expect(formatIST('invalid')).toBe('—');
    expect(formatIST(new Date('invalid'))).toBe('—');
  });
});
