import React, { useMemo, useState } from 'react';
import type { Alarm, PerceivedSeverity } from '../types';
import { getSeverityStyles, severityRank } from '../lib/severity';

interface LiveAlarmsProps {
  alarms: Alarm[];
}

const severityFilters: PerceivedSeverity[] = [
  'critical',
  'major',
  'minor',
  'warning',
  'cleared',
];

export const LiveAlarms: React.FC<LiveAlarmsProps> = ({ alarms }) => {
  const [activeFilter, setActiveFilter] = useState<PerceivedSeverity | 'all'>('all');

  const filtered = useMemo(() => {
    if (activeFilter === 'all') return alarms;
    return alarms.filter((a) => a.perceivedSeverity === activeFilter);
  }, [alarms, activeFilter]);

  const counts = useMemo(() => {
    const counts: Record<string, number> = { all: alarms.length };
    severityFilters.forEach((s) => {
      counts[s] = alarms.filter((a) => a.perceivedSeverity === s).length;
    });
    return counts;
  }, [alarms]);

  const sortedSeverities = [...severityFilters].sort(
    (a, b) => severityRank[b] - severityRank[a]
  );

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-slate-200 font-semibold">Live Alarms</h2>
        <div className="flex flex-wrap gap-1">
          <button
            onClick={() => setActiveFilter('all')}
            className={`px-2 py-0.5 text-xs rounded ${
              activeFilter === 'all'
                ? 'bg-sky-500 text-slate-900'
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
          >
            All ({counts.all})
          </button>
          {sortedSeverities.map((s) => {
            const styles = getSeverityStyles(s);
            return (
              <button
                key={s}
                onClick={() => setActiveFilter(s)}
                className={`px-2 py-0.5 text-xs rounded capitalize ${
                  activeFilter === s
                    ? `${styles.badge} ring-2`
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {s} ({counts[s]})
              </button>
            );
          })}
        </div>
      </div>

      {alarms.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-500">
          <p>Waiting for alarms — run `make sim`</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-500">
          <p>No {activeFilter} alarms</p>
        </div>
      ) : (
        <div className="overflow-y-auto flex-1">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-700">
                <th className="text-left py-1.5">Time</th>
                <th className="text-left py-1.5">Severity</th>
                <th className="text-left py-1.5">Site</th>
                <th className="text-left py-1.5">Alarm Type</th>
                <th className="text-left py-1.5">Probable Cause</th>
                <th className="text-left py-1.5">Specific Problem</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((alarm) => {
                const styles = getSeverityStyles(alarm.perceivedSeverity);
                return (
                  <tr
                    key={alarm.id}
                    className={`border-b border-slate-800 ${styles.rowBorder} hover:bg-slate-800/50`}
                  >
                    <td className="py-1.5 text-slate-400 font-mono">
                      {new Date(alarm.alarmRaisedTime).toISOString().replace('T', ' ').slice(0, 19)}
                    </td>
                    <td className="py-1.5">
                      <span
                        className={`inline-flex px-1.5 py-0.25 rounded text-xs ${styles.badge}`}
                      >
                        {alarm.perceivedSeverity}
                      </span>
                    </td>
                    <td className="py-1.5 text-slate-300">{alarm.siteId}</td>
                    <td className="py-1.5 text-slate-300">{alarm.alarmType}</td>
                    <td className="py-1.5 text-slate-400">{alarm.probableCause}</td>
                    <td className="py-1.5 text-slate-400">{alarm.specificProblem}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
