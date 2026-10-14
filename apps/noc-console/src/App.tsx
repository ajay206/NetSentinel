import React, { useMemo } from 'react';
import { Header } from './components/Header';
import { LiveAlarms } from './components/LiveAlarms';
import { ServiceHealth } from './components/ServiceHealth';
import { PlaceholderPanel } from './components/PlaceholderPanel';
import { NetworkMap } from './components/NetworkMap';
import { KpiActivity } from './components/KpiActivity';
import { useAlarmFeed } from './hooks/useAlarmFeed';
import { useHealth } from './hooks/useHealth';
import { useTopology } from './hooks/useTopology';
import { useKpiActivity } from './hooks/useKpiActivity';
import { worstSeverityBySite } from './lib/siteStatus';

export const App: React.FC = () => {
  const { alarms, status: wsStatus } = useAlarmFeed();
  const { data: health, isError } = useHealth();
  const { data: topology, isLoading: topoLoading, isError: topoError } = useTopology();
  const { activity: kpiActivity, status: kpiStatus } = useKpiActivity();

  const severityBySite = useMemo(() => worstSeverityBySite(alarms), [alarms]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col">
      <Header wsStatus={wsStatus} />
      <main className="flex-1 p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Row 1 */}
        <div className="lg:col-span-2">
          <LiveAlarms alarms={alarms} />
        </div>
        <div>
          <ServiceHealth health={health} isError={isError} />
        </div>

        {/* Row 2 */}
        <div className="lg:col-span-2">
          <NetworkMap
            topology={topology}
            isLoading={topoLoading}
            isError={topoError}
            severityBySite={severityBySite}
          />
        </div>
        <div className="grid grid-cols-1 gap-4">
          <section>
            <h2 className="text-xl font-semibold text-slate-200 mb-2">KPI activity</h2>
            <KpiActivity activity={kpiActivity} status={kpiStatus} />
          </section>
          <PlaceholderPanel title="KPI charts" week={5} />
          <PlaceholderPanel title="Anomalies" week={6} />
          <PlaceholderPanel title="Copilot" week={9} />
        </div>
      </main>
    </div>
  );
};

export default App;
