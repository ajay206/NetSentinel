export const SEVERITIES = ['critical', 'major', 'minor', 'warning'] as const;
export type Sev = (typeof SEVERITIES)[number];

export const severityHex: Record<Sev | 'cleared', string> = {
  critical: '#EF4444',
  major: '#F97316',
  minor: '#F59E0B',
  warning: '#6DCFF6', // deck cyan
  cleared: '#6B7280', // muted grey
};

export const severityChip: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-700 ring-1 ring-red-500/40 font-bold',
  major: 'bg-orange-500/15 text-orange-700 ring-1 ring-orange-500/40 font-bold',
  minor: 'bg-amber-500/15 text-amber-700 ring-1 ring-amber-500/40 font-bold',
  warning: 'bg-sky-500/15 text-sky-800 ring-1 ring-sky-500/40 font-bold',
  indeterminate: 'bg-slate-500/15 text-slate-700 ring-1 ring-slate-500/40 font-bold',
  cleared: 'bg-slate-700/15 text-slate-600 ring-1 ring-slate-700/40 font-bold',
};

export function severityLabel(sev: string): string {
  if (!sev) return '';
  return sev.charAt(0).toUpperCase() + sev.slice(1);
}

export const space = {
  gutter: 'gap-3.5', // 14px grid gap matching mockup
  pad: 'p-4',
};

export const card = 'bg-white rounded-[20px] shadow-sm shadow-navy/5 p-4.5 border border-bento-border';
