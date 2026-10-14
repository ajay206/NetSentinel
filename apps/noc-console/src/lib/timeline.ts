export type Severity = 'critical' | 'major' | 'minor' | 'warning' | 'cleared';

export interface TimelineBucket {
  start: string;
  total: number;
  bySeverity: Record<Severity, number>;
}

export interface TimelineResponse {
  bucketSeconds: number;
  buckets: TimelineBucket[];
  total: number;
  peak: number;
}

export function bucketAt(
  response: TimelineResponse | undefined,
  index: number,
): TimelineBucket | null {
  if (!response?.buckets?.length) return null;
  const clamped = Math.max(0, Math.min(index, response.buckets.length - 1));
  return response.buckets[clamped];
}

export function isBurst(bucket: TimelineBucket | null, peak: number): boolean {
  if (!bucket) return false;
  const threshold = Math.max(5, 0.5 * peak);
  return bucket.total >= threshold;
}
