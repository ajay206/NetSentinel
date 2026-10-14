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

/* New utilities */

export function peakBucket(
  data: TimelineResponse | undefined,
): { index: number; bucket: TimelineBucket } | null {
  if (!data?.buckets?.length) return null;
  let maxTotal = -1;
  let peakIdx = -1;
  data.buckets.forEach((b, i) => {
    if (b.total > maxTotal) {
      maxTotal = b.total;
      peakIdx = i;
    }
  });
  if (maxTotal <= 0) return null;
  return { index: peakIdx, bucket: data.buckets[peakIdx] };
}

export function formatHHMM(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const fmt = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Kolkata',
  });
  return fmt.format(d);
}

export function stormAnnotation(
  data: TimelineResponse | undefined,
  rootSiteId?: string | null,
): string | null {
  const peakInfo = peakBucket(data);
  if (!peakInfo) return null;
  const { bucket } = peakInfo;
  const total = bucket.total;
  const start = formatHHMM(bucket.start);
  let txt = `Storm: ${total} alarms at ${start} IST`;
  if (rootSiteId) txt += `, root ${rootSiteId}`;
  return txt;
}

export function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0, 1];
  const rawStep = max / count;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const candidates = [1, 2, 5, 10].map((n) => n * magnitude);
  // integer counts: never step below 1
  const step = Math.max(1, candidates.find((s) => s >= rawStep) ?? candidates[3]);
  const niceMax = step * Math.ceil(max / step);
  const ticks: number[] = [];
  for (let v = 0; v <= niceMax; v += step) {
    ticks.push(v);
  }
  return ticks;
}
