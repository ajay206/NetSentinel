import React, { useMemo, useState } from 'react';
import { Tip } from './ui/Tooltip';
import { TIPS } from '../lib/tooltips';
import { CardHeader, SeverityChip } from './ui/Card';
import type { Alarm, PerceivedSeverity } from '../types';
import { getSeverityStyles, severityRank } from '../lib/severity';
import { formatIST } from '../lib/time';

interface LiveAlarmsProps {
  alarms: Alarm[];
}

const severityFilters: PerceivedSeverity[] = ['critical', 'major', 'minor', 'warning', 'cleared'];

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

  const sortedSeverities = [...severityFilters].sort((a, b) => severityRank[b] - severityRank[a]);

  return (
    <div className="ns-card">
      <CardHeader
        title="Live Alarms"
        subtitle="Raw alarms as they arrive from the network, newest first."
        info={TIPS.panelLiveAlarms}
        actions={
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
        }
      />

      {alarms.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-500">
          <p>Waiting for alarms — run `make sim`</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-500">
          <p>No {activeFilter} alarms</p>
        </div>
      ) : (
        <div className="ns-table-wrap">
          <table className="w-full text-xs">
            <thead>
              <tr className="ns-thead">
                <th className="py-2 pl-2 pr-3 font-medium">
                  <Tip tip={TIPS.colTime}>Time (IST)</Tip>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <Tip tip={TIPS.colSeverity}>Severity</Tip>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <Tip tip={TIPS.colSite}>Site</Tip>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <Tip tip={TIPS.colAlarmType}>Alarm Type</Tip>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <Tip tip={TIPS.colProbableCause}>Probable Cause</Tip>
                </th>
                <th className="py-2 pr-3 font-medium">
                  <Tip tip={TIPS.colSpecificProblem}>Specific Problem</Tip>
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((alarm) => {
                return (
                  <tr key={alarm.id} className={`border-b border-slate-800 hover:bg-slate-800/50`}>
                    <td className="py-2 pl-2 pr-3 whitespace-nowrap text-slate-400 font-mono">
                      {formatIST(alarm.alarmRaisedTime)}
                    </td>
                    <td className="py-2 pr-3">
                      <SeverityChip severity={alarm.perceivedSeverity} />
                    </td>
                    <td className="py-2 pr-3 text-slate-300">{alarm.siteId}</td>
                    <td className="py-2 pr-3 text-slate-300">{alarm.alarmType}</td>
                    <td className="py-2 pr-3 text-slate-400">{alarm.probableCause}</td>
                    <td className="py-2 pr-3 text-slate-400">{alarm.specificProblem}</td>
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
