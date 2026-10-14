export interface PathResult {
  d: string;
  min: number | null;
  max: number | null;
}

/**
 * Build an SVG path string for a series of numeric values.
 * Null values create gaps (move commands).
 * The chart is scaled to fit within width x height, leaving `pad` pixels on each side.
 */
export function buildPath(
  values: (number | null)[],
  width: number,
  height: number,
  pad = 4,
): PathResult {
  if (values.length === 0) return { d: '', min: null, max: null };

  const valid = values.filter((v): v is number => v !== null);
  const min = valid.length ? Math.min(...valid) : null;
  const max = valid.length ? Math.max(...valid) : null;

  const flat = min === null || max === null || max === min;
  const range = flat ? 1 : (max as number) - (min as number);
  const innerW = width - 2 * pad;
  const innerH = height - 2 * pad;
  const stepX = values.length > 1 ? innerW / (values.length - 1) : 0;

  const parts: string[] = [];
  let penDown = false;
  values.forEach((v, i) => {
    if (v === null) {
      penDown = false; // gap: next point starts a new subpath
      return;
    }
    const x = pad + i * stepX;
    const y = flat ? pad + innerH / 2 : pad + innerH - ((v - (min as number)) / range) * innerH;
    parts.push(`${penDown ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`);
    penDown = true;
  });

  return { d: parts.join(' '), min, max };
}

/** x/y of point i using the same scaling as buildPath (null when the value is missing). */
export function pointPosition(
  values: (number | null)[],
  i: number,
  width: number,
  height: number,
  pad = 4,
): { x: number; y: number } | null {
  const v = values[i];
  if (v === null || v === undefined) return null;
  const valid = values.filter((x): x is number => x !== null);
  const min = Math.min(...valid);
  const max = Math.max(...valid);
  const innerW = width - 2 * pad;
  const innerH = height - 2 * pad;
  const stepX = values.length > 1 ? innerW / (values.length - 1) : 0;
  const y = max === min ? pad + innerH / 2 : pad + innerH - ((v - min) / (max - min)) * innerH;
  return { x: pad + i * stepX, y };
}

/**
 * Map anomaly timestamps onto chart point indices: an anomaly belongs to the last point
 * whose bucket start is at or before it (works for 15m, 1h and 1d aggregation).
 */
export function anomalyIndices(pointTs: string[], anomalyTs: string[]): number[] {
  const starts = pointTs.map((t) => new Date(t).getTime());
  const out = new Set<number>();
  anomalyTs.forEach((t) => {
    const a = new Date(t).getTime();
    let idx = -1;
    for (let i = 0; i < starts.length && starts[i] <= a; i += 1) idx = i;
    if (idx >= 0) out.add(idx);
  });
  return [...out].sort((x, y) => x - y);
}
