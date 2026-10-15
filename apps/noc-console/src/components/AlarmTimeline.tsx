import React, { useMemo, useState } from 'react';
import { TIPS } from '../lib/tooltips';
import { Card, StateMessage } from './ui/Card';
import {
  bucketAt,
  formatHHMM,
  isBurst,
  niceTicks,
  peakBucket,
  stormAnnotation,
  type Severity,
  type TimelineResponse,
} from '../lib/timeline';
import { severityHex, severityLabel } from '../theme';

interface AlarmTimelineProps {
  data?: TimelineResponse;
  isLoading: boolean;
  isError: boolean;
  /** Root site of the largest open incident (incident-service), used in the peak annotation. */
  rootSiteId?: string | null;
}

const TITLE = 'Alarm storm timeline';
const SUBTITLE = 'Alarms raised per minute, stacked by severity. A tall bar means an alarm storm.';
const INFO = TIPS.panelTimeline;

// Bottom-up stacking order (most severe at the bottom, where the eye starts)
const STACK: Severity[] = ['critical', 'major', 'minor', 'warning', 'cleared'];

// Chart geometry (SVG user units; the SVG scales to the card width)
const W = 720;
const H = 230;
const M = { left: 44, right: 16, top: 30, bottom: 36 };
const PLOT_W = W - M.left - M.right;
const PLOT_H = H - M.top - M.bottom;
// At least this many slots, so 1-3 buckets don't become one huge bar (data is right-aligned)
const MIN_SLOTS = 30;

export function AlarmTimeline({ data, isLoading, isError, rootSiteId }: AlarmTimelineProps) {
  // null = follow the peak
  const [picked, setPicked] = useState<number | null>(null);

  const buckets = data?.buckets ?? [];
  const n = buckets.length;
  const peak = useMemo(() => peakBucket(data), [data]);
  const annotation = useMemo(() => stormAnnotation(data, rootSiteId), [data, rootSiteId]);

  if (isLoading) {
    return (
      <Card title={TITLE} subtitle={SUBTITLE} info={INFO} testId="timeline-card">
        <StateMessage kind="loading">Loading timeline…</StateMessage>
      </Card>
    );
  }
  if (isError) {
    return (
      <Card title={TITLE} subtitle={SUBTITLE} info={INFO} testId="timeline-card">
        <StateMessage kind="error">
          Timeline unavailable — the gateway could not load alarm history.
        </StateMessage>
      </Card>
    );
  }
  if (!data || n === 0 || !peak) {
    return (
      <Card title={TITLE} subtitle={SUBTITLE} info={INFO} testId="timeline-card">
        <StateMessage kind="empty">No alarms yet — run a scenario (e.g. make sim).</StateMessage>
      </Card>
    );
  }

  const selectedIndex = picked === null ? peak.index : Math.min(picked, n - 1);
  const selected = bucketAt(data, selectedIndex);
  const ticks = niceTicks(peak.bucket.total);
  const yMax = ticks[ticks.length - 1] || 1;
  const slots = Math.max(n, MIN_SLOTS);
  const slotW = PLOT_W / slots;
  const barW = Math.max(2, slotW * 0.7);
  const x0 = M.left + (slots - n) * slotW; // right-align: newest minute at the right edge
  const y = (v: number) => M.top + PLOT_H - (v / yMax) * PLOT_H;
  const labelEvery = Math.max(1, Math.ceil(n / 6));
  const peakX = x0 + peak.index * slotW + slotW / 2;
  const calloutAnchor = peakX > W - 160 ? 'end' : peakX < M.left + 160 ? 'start' : 'middle';

  return (
    <Card title={TITLE} subtitle={SUBTITLE} info={INFO} testId="timeline-card">
      {annotation && (
        <p
          data-testid="storm-annotation"
          className="mb-2 inline-flex items-center gap-2 rounded-md bg-red-500/10 px-2.5 py-1 text-sm font-medium text-red-300 ring-1 ring-red-500/30"
        >
          <span className="h-2 w-2 rounded-full bg-red-400" aria-hidden />
          {annotation}
        </p>
      )}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label="Alarm storm timeline chart"
        className="block"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="#1e293b" />
            <text x={M.left - 6} y={y(t) + 3} fill="#94a3b8" fontSize={10} textAnchor="end">
              {t}
            </text>
          </g>
        ))}
        <text
          transform={`translate(12 ${M.top + PLOT_H / 2}) rotate(-90)`}
          fill="#94a3b8"
          fontSize={10}
          textAnchor="middle"
        >
          Alarms per minute
        </text>
        <line
          x1={M.left}
          x2={W - M.right}
          y1={M.top + PLOT_H}
          y2={M.top + PLOT_H}
          stroke="#475569"
        />

        {buckets.map((b, i) => {
          const cx = x0 + i * slotW + slotW / 2;
          let acc = 0;
          const isPeak = i === peak.index;
          const isSel = i === selectedIndex;
          return (
            <g
              key={b.start}
              data-testid="timeline-bar"
              data-peak={isPeak ? 'true' : undefined}
              onClick={() => setPicked(i)}
              style={{ cursor: 'pointer' }}
            >
              <title>{`${formatHHMM(b.start)} IST — ${b.total} alarms`}</title>
              {/* full-height hit area */}
              <rect x={cx - slotW / 2} y={M.top} width={slotW} height={PLOT_H} fill="transparent" />
              {STACK.map((sev) => {
                const c = b.bySeverity[sev] ?? 0;
                if (!c) return null;
                const top = y(acc + c);
                const h = y(acc) - top;
                acc += c;
                return (
                  <rect
                    key={sev}
                    x={cx - barW / 2}
                    y={top}
                    width={barW}
                    height={h}
                    fill={severityHex[sev]}
                  />
                );
              })}
              {(isPeak || isSel) && (
                <rect
                  x={cx - barW / 2 - 2}
                  y={y(b.total) - 2}
                  width={barW + 4}
                  height={y(0) - y(b.total) + 2}
                  fill="none"
                  stroke={isPeak ? '#f8fafc' : '#38bdf8'}
                  strokeWidth={1.5}
                  strokeDasharray={isPeak ? undefined : '3 2'}
                />
              )}
              {i % labelEvery === 0 || i === n - 1 ? (
                <text
                  x={cx}
                  y={M.top + PLOT_H + 14}
                  fill="#94a3b8"
                  fontSize={10}
                  textAnchor="middle"
                >
                  {formatHHMM(b.start)}
                </text>
              ) : null}
            </g>
          );
        })}

        {/* Peak callout above the bar */}
        <text
          data-testid="storm-callout"
          x={peakX}
          y={Math.max(12, y(peak.bucket.total) - 8)}
          fill="#fca5a5"
          fontSize={11}
          fontWeight={600}
          textAnchor={calloutAnchor}
        >
          {`Peak ${peak.bucket.total} @ ${formatHHMM(peak.bucket.start)}`}
        </text>
        <text x={M.left + PLOT_W / 2} y={H - 4} fill="#94a3b8" fontSize={10} textAnchor="middle">
          Time (IST)
        </text>
      </svg>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-300">
        <div className="flex flex-wrap items-center gap-3" data-testid="timeline-legend">
          {STACK.map((sev) => (
            <span key={sev} className="inline-flex items-center gap-1.5">
              <span
                className="h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: severityHex[sev] }}
              />
              {severityLabel(sev)}
            </span>
          ))}
        </div>
      </div>

      {n > 1 && (
        <input
          type="range"
          aria-label="Scrub timeline"
          min={0}
          max={n - 1}
          value={selectedIndex}
          onChange={(e) => setPicked(Number(e.target.value))}
          className="mt-3 w-full accent-sky-500"
        />
      )}

      {selected && (
        <div
          className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg bg-slate-800/60 px-3 py-2 text-xs"
          data-testid="timeline-selected"
        >
          <span className="font-medium text-slate-100">
            {formatHHMM(selected.start)} IST · {selected.total} alarms
          </span>
          {STACK.map((sev) => (
            <span key={sev} className="inline-flex items-center gap-1 text-slate-300">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: severityHex[sev] }}
              />
              {severityLabel(sev)}{' '}
              <span className="tabular-nums">{selected.bySeverity[sev] ?? 0}</span>
            </span>
          ))}
          {isBurst(selected, data.peak) && (
            <span className="rounded bg-red-500/15 px-2 py-0.5 font-medium text-red-300 ring-1 ring-red-500/30">
              Burst
            </span>
          )}
        </div>
      )}
    </Card>
  );
}
