import { describe, it, expect } from 'vitest';
import { anomalyIndices, buildPath, pointPosition } from './chart';

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

describe('anomalyIndices / pointPosition', () => {
  it('maps anomaly times onto the bucket that contains them', () => {
    const pts = ['2026-10-14T00:00:00Z', '2026-10-14T01:00:00Z', '2026-10-14T02:00:00Z'];
    const idx = anomalyIndices(pts, [
      '2026-10-14T01:15:00Z',
      '2026-10-14T01:45:00Z',
      '2026-10-14T02:30:00Z',
      '2026-10-13T23:00:00Z',
    ]);
    expect(idx).toEqual([1, 2]);
  });

  it('positions points with the same scale as buildPath', () => {
    expect(pointPosition([0, 10], 1, 100, 50, 0)).toEqual({ x: 100, y: 0 });
    expect(pointPosition([0, null], 1, 100, 50, 0)).toBeNull();
  });
});
