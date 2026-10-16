export const SEVERITIES = ['critical', 'major', 'minor', 'warning'] as const;
export type Sev = (typeof SEVERITIES)[number];

export const severityHex: Record<Sev | 'cleared', string> = {
  critical: '#ef4444',
  major: '#f97316',
  minor: '#eab308',
  warning: '#6DCFF6', // deck cyan
  cleared: '#7A748A', // deck mauve
};

export const severityChip: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-700 ring-1 ring-red-500/40',
  major: 'bg-orange-500/15 text-orange-700 ring-1 ring-orange-500/40',
  minor: 'bg-amber-500/15 text-amber-700 ring-1 ring-amber-500/40',
  warning: 'bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/40',
  indeterminate: 'bg-slate-800 text-slate-400 ring-1 ring-slate-700',
  cleared: 'bg-slate-800 text-slate-400 ring-1 ring-slate-700',
};

export function severityLabel(sev: string): string {
  if (!sev) return '';
  return sev.charAt(0).toUpperCase() + sev.slice(1);
}

export const space = {
  gutter: 'gap-4',
  pad: 'p-4',
};

export const card =
  'bg-slate-900 border border-slate-700 rounded-xl shadow-card';
