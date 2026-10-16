import type { PerceivedSeverity } from '../types';

export const severityRank: Record<PerceivedSeverity, number> = {
  critical: 5,
  major: 4,
  minor: 3,
  warning: 2,
  cleared: 1,
};

export const severityStyles: Record<
  PerceivedSeverity,
  { badge: string; rowBorder: string }
> = {
  critical: {
    badge: 'bg-red-500/15 text-red-700 ring-red-500/30',
    rowBorder: 'border-l-4 border-red-500',
  },
  major: {
    badge: 'bg-orange-500/15 text-orange-700 ring-orange-500/30',
    rowBorder: 'border-l-4 border-orange-500',
  },
  minor: {
    badge: 'bg-amber-500/15 text-amber-700 ring-amber-500/30',
    rowBorder: 'border-l-4 border-amber-500',
  },
  warning: {
    badge: 'bg-sky-500/15 text-sky-400 ring-sky-500/30',
    rowBorder: 'border-l-4 border-sky-500',
  },
  cleared: {
    badge: 'bg-emerald-500/15 text-emerald-700 ring-emerald-500/30',
    rowBorder: 'border-l-4 border-emerald-500',
  },
};

export function getSeverityStyles(severity: PerceivedSeverity) {
  return severityStyles[severity];
}
