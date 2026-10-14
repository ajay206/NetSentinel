import { bucketAt, isBurst, type Severity, type TimelineResponse } from '../lib/timeline';
import { useState, useMemo } from 'react';

interface AlarmTimelineProps {
  data?: TimelineResponse;
  isLoading: boolean;
  isError: boolean;
}

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'bg-red-500',
  major: 'bg-orange-500',
  minor: 'bg-yellow-400',
  warning: 'bg-sky-400',
  cleared: 'bg-slate-500',
};

const SEVERITY_ORDER: Severity[] = ['critical', 'major', 'minor', 'warning', 'cleared'];

export function AlarmTimeline({ data, isLoading, isError }: AlarmTimelineProps) {
  // null = follow the newest bucket as the storm grows
  const [picked, setPicked] = useState<number | null>(null);

  const bucketCount = data?.buckets?.length ?? 0;
  const selectedIndex =
    picked === null ? Math.max(0, bucketCount - 1) : Math.min(picked, bucketCount - 1);
  const setSelectedIndex = setPicked;
  const selectedBucket = useMemo(() => bucketAt(data, selectedIndex), [data, selectedIndex]);
  const peak = data?.peak ?? 0;
  const burst = selectedBucket ? isBurst(selectedBucket, peak) : false;

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toISOString().slice(11, 19);
    } catch {
      return iso;
    }
  };

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
        <h2 className="text-lg font-medium text-slate-100 mb-4">Alarm storm timeline</h2>
        <p className="text-slate-400 text-center py-8">Loading timeline…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
        <h2 className="text-lg font-medium text-slate-100 mb-4">Alarm storm timeline</h2>
        <p className="text-red-400 text-center py-8">Timeline unavailable</p>
      </div>
    );
  }

  if (!data || !bucketCount) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
        <h2 className="text-lg font-medium text-slate-100 mb-4">Alarm storm timeline</h2>
        <p className="text-slate-400 text-center py-8">
          No alarms yet — run a scenario (e.g. fibre_cut)
        </p>
      </div>
    );
  }

  const maxHeight = 120;

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
      <h2 className="text-lg font-medium text-slate-100 mb-4">Alarm storm timeline</h2>
      <div className="relative h-[140px] mb-4">
        <div
          className="flex items-end h-full gap-1 overflow-x-auto px-2 pb-2"
          role="img"
          aria-label="Alarm timeline bars"
        >
          {data.buckets.map((bucket, idx) => {
            const height = peak > 0 ? Math.max(4, (bucket.total / peak) * maxHeight) : 4;
            const isSelected = idx === selectedIndex;
            const burstBar = isBurst(bucket, peak);
            return (
              <div
                key={bucket.start}
                data-testid="timeline-bar"
                className={`relative flex flex-col items-center cursor-pointer transition-all ${isSelected ? 'ring-2 ring-sky-400' : burstBar ? 'ring-1 ring-red-500/60' : ''}`}
                onClick={() => setSelectedIndex(idx)}
                style={{ width: '28px', height: `${maxHeight + 20}px` }}
              >
                <div
                  className="flex flex-col-reverse w-full h-full"
                  style={{ height: `${height}px` }}
                >
                  {SEVERITY_ORDER.map((sev) => {
                    const count = bucket.bySeverity[sev];
                    if (!count) return null;
                    const sevHeight = peak > 0 ? (count / peak) * maxHeight : 0;
                    return (
                      <div
                        key={sev}
                        className={`${SEVERITY_COLORS[sev]} w-full`}
                        style={{ height: `${sevHeight}px` }}
                      />
                    );
                  })}
                </div>
                <span className="text-xs text-slate-500 mt-1 hidden sm:block">
                  {formatTime(bucket.start).slice(0, 5)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <div className="mb-4">
        <label htmlFor="timeline-scrub" className="sr-only">
          Scrub timeline
        </label>
        <input
          id="timeline-scrub"
          type="range"
          min={0}
          max={bucketCount - 1}
          value={selectedIndex}
          onChange={(e) => setSelectedIndex(Number(e.target.value))}
          aria-label="Scrub timeline"
          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
      </div>
      <div className="space-y-2">
        <div className="flex items-center gap-3 text-sm">
          <span className="font-medium text-slate-200">
            {formatTime(selectedBucket?.start ?? '')} UTC
          </span>
          {burst && (
            <span className="px-2 py-0.5 bg-red-900/50 border border-red-700 text-red-300 rounded text-xs font-medium">
              Burst
            </span>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-1 text-sm text-slate-300">
          {SEVERITY_ORDER.map((sev) => (
            <div key={sev} className="flex justify-between">
              <dt className="capitalize">{sev}</dt>
              <dd className="font-mono text-slate-100">{selectedBucket?.bySeverity[sev] ?? 0}</dd>
            </div>
          ))}
          <div className="col-span-2 border-t border-slate-700 pt-1 flex justify-between font-medium">
            <dt>Total</dt>
            <dd className="text-slate-100">{selectedBucket?.total ?? 0}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
