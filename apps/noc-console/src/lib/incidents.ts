import type { Incident } from '../types.incident';

const severityRank: Record<Incident['severity'], number> = {
  critical: 0,
  major: 1,
  minor: 2,
  warning: 3,
  indeterminate: 4,
  cleared: 5,
};

export function sortIncidents(items: Incident[]): Incident[] {
  return [...items].sort((a, b) => {
    if (a.status !== b.status) {
      return a.status === 'open' ? -1 : 1;
    }
    const rankDiff = severityRank[a.severity] - severityRank[b.severity];
    if (rankDiff !== 0) return rankDiff;
    return new Date(b.lastSeen).getTime() - new Date(a.lastSeen).getTime();
  });
}

export function alarmBelongsTo(
  incident: Incident | null,
  alarm: { id: string; dedup?: { key: string } },
): boolean {
  if (incident === null) return true;
  if (incident.alarmIds.includes(alarm.id)) return true;
  if (alarm.dedup?.key && incident.alarmKeys.includes(alarm.dedup.key)) return true;
  return false;
}

export function durationLabel(firstSeen: string, lastSeen: string): string {
  const start = new Date(firstSeen).getTime();
  const end = new Date(lastSeen).getTime();
  const diffMs = end - start;
  if (diffMs < 0) return '0s';
  const totalSeconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes > 0) {
    return `${minutes}m ${seconds.toString().padStart(2, '0')}s`;
  }
  return `${seconds}s`;
}
