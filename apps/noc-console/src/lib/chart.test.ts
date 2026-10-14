import { describe, it, expect } from 'vitest';
import { buildPath } from './chart';

describe('buildPath', () => {
  it('handles empty array', () => {
    expect(buildPath([], 100, 50)).toEqual({ d: '', min: null, max: null });
  });

  it('creates flat line when all values equal', () => {
    const res = buildPath([5, 5, 5], 100, 50);
    expect(res.min).toBe(5);
    expect(res.max).toBe(5);
    expect(res.d).toContain('M'); // start
    expect(res.d).toContain('L'); // line
  });

  it('creates gaps for nulls', () => {
    const res = buildPath([1, null, 3], 100, 50);
    // should contain two move commands (one at start, one after null)
    const moves = (res.d.match(/M/g) || []).length;
    expect(moves).toBe(2);
  });
});
