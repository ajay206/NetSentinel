import type { Alarm, PerceivedSeverity } from '../types';

const severityRank: Record<PerceivedSeverity, number> = {
  critical: 5,
  major: 4,
  minor: 3,
  warning: 2,
  cleared: 1,
};

/**
 * Returns a map of siteId to the worst (highest) active perceived severity.
 * Only active (non-cleared) alarms are considered. A cleared alarm for a site
 * removes all previously active alarms for that site.
 *
 * @param alarms Array of alarms ordered newest-first (most recent first).
 */
export function worstSeverityBySite(alarms: Alarm[]): Record<string, PerceivedSeverity> {
  // Process from oldest to newest
  // Stable sort by raise time; ties keep feed order (reversed newest-first input)
  const ordered = [...alarms]
    .reverse()
    .sort((a, b) => Date.parse(a.alarmRaisedTime) - Date.parse(b.alarmRaisedTime));

  // Track active alarms per site: key -> alarm identifier, value -> severity
  const activeBySite: Record<string, Map<string, PerceivedSeverity>> = {};

  for (const alarm of ordered) {
    const { siteId, perceivedSeverity, alarmType, probableCause } = alarm;

    // Ensure map exists for the site
    if (!activeBySite[siteId]) {
      activeBySite[siteId] = new Map();
    }

    const siteMap = activeBySite[siteId];
    const alarmKey = `${alarmType}|${probableCause}`;

    if (perceivedSeverity === 'cleared') {
      // A cleared alarm clears ALL earlier active alarms for the site
      siteMap.clear();
    } else {
      // Record/overwrite the active alarm
      siteMap.set(alarmKey, perceivedSeverity);
    }
  }

  // Determine worst severity per site
  const result: Record<string, PerceivedSeverity> = {};

  for (const [siteId, alarmsMap] of Object.entries(activeBySite)) {
    if (alarmsMap.size === 0) {
      continue; // no active alarms for this site
    }

    let worst: PerceivedSeverity = 'cleared';
    for (const sev of alarmsMap.values()) {
      if (severityRank[sev] > severityRank[worst]) {
        worst = sev;
      }
    }
    result[siteId] = worst;
  }

  return result;
}
