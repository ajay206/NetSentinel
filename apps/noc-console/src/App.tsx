import React, { useMemo, useState } from 'react';
import { Header } from './components/Header';
import { LiveAlarms } from './components/LiveAlarms';
import { EnrichedAlarms } from './components/EnrichedAlarms';
import { FaultBadge } from './components/FaultBadge';
import { ShapDrawer } from './components/ShapDrawer';
import { useFaultExplanation, useFaultPrediction } from './hooks/useFault';
import type { EnrichedAlarm } from './types.enriched';
import { useEnrichedFeed } from './hooks/useEnrichedFeed';
import { ServiceHealth } from './components/ServiceHealth';
import { PlaceholderPanel } from './components/PlaceholderPanel';
import { NetworkMap } from './components/NetworkMap';
import { KpiActivity } from './components/KpiActivity';
import { KpiChartsContainer } from './components/KpiChartsContainer';
import { AnomaliesContainer } from './components/AnomaliesContainer';
import { useAlarmFeed } from './hooks/useAlarmFeed';
import { useHealth } from './hooks/useHealth';
import { useTopology } from './hooks/useTopology';
import { useKpiActivity } from './hooks/useKpiActivity';
import { worstSeverityBySite } from './lib/siteStatus';

export const App: React.FC = () => {
  const { alarms, status: wsStatus } = useAlarmFeed();
  const { alarms: enrichedAlarms, status: enrichedStatus } = useEnrichedFeed();
  const { data: health, isError } = useHealth();
  const { data: topology, isLoading: topoLoading, isError: topoError } = useTopology();
  const { activity: kpiActivity, status: kpiStatus } = useKpiActivity();

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  // Follow the latest version of the selected alarm (dedup count can grow)
  const selected: EnrichedAlarm | null =
    enrichedAlarms.find((a) => a.dedup.key === selectedKey) ?? null;
  const prediction = useFaultPrediction(selected);
  const explanation = useFaultExplanation(selected);

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

        {/* Row 1b: enriched feed from alarm-ingest (W4) */}
        <div className="lg:col-span-3">
          <EnrichedAlarms
            alarms={enrichedAlarms}
            status={enrichedStatus}
            selectedKey={selectedKey}
            onSelect={(a) => setSelectedKey(a.dedup.key)}
            selectedBadge={
              <FaultBadge
                prediction={prediction.data}
                isLoading={prediction.isLoading}
                isError={prediction.isError}
              />
            }
          />
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
          <KpiChartsContainer />
          <AnomaliesContainer />
          <PlaceholderPanel title="Copilot" week={9} />
        </div>
      </main>
      <ShapDrawer
        alarm={selected}
        prediction={prediction.data}
        explanation={explanation.data}
        isLoading={prediction.isLoading || explanation.isLoading}
        isError={prediction.isError || explanation.isError}
        onClose={() => setSelectedKey(null)}
      />
    </div>
  );
};

export default App;
