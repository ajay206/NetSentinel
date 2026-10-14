import React, { useMemo, useState } from 'react';
import { Header } from './components/Header';
import { LiveAlarms } from './components/LiveAlarms';
import { EnrichedAlarms } from './components/EnrichedAlarms';
import { FaultBadge } from './components/FaultBadge';
import { ShapDrawer } from './components/ShapDrawer';
import { useFaultExplanation, useFaultPrediction } from './hooks/useFault';
import { useRunbook, useRunbookSearch } from './hooks/useRunbooks';
import { buildRunbookQuery } from './lib/runbookQuery';
import { RunbooksPanel } from './views/RunbooksPanel';
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

  // W8: runbooks for the selected alarm. Wait for the fault prediction so we search once,
  // using the predicted fault type as a soft boost (search still works if ml-service is down).
  const predictedFault = prediction.data?.faultType ?? null;
  const runbookQuery =
    selected && !prediction.isLoading ? buildRunbookQuery(selected, predictedFault) : null;
  const runbookSearch = useRunbookSearch(runbookQuery, predictedFault);
  const [runbookId, setRunbookId] = useState<string | null>(null);
  const runbookDoc = useRunbook(runbookId);
  const selectAlarm = (key: string | null) => {
    setSelectedKey(key);
    setRunbookId(null);
  };

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
            onSelect={(a) => selectAlarm(a.dedup.key)}
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
          <RunbooksPanel
            alarmLabel={selected ? `${selected.specificProblem} @ ${selected.siteId}` : null}
            hits={runbookSearch.data?.results}
            isLoading={runbookQuery !== null && runbookSearch.isLoading}
            isError={runbookSearch.isError}
            selectedId={runbookId}
            onSelect={setRunbookId}
            doc={runbookDoc.data}
            docLoading={runbookDoc.isLoading}
            onClosePreview={() => setRunbookId(null)}
          />
          <PlaceholderPanel title="Copilot" week={9} />
        </div>
      </main>
      <ShapDrawer
        alarm={selected}
        prediction={prediction.data}
        explanation={explanation.data}
        isLoading={prediction.isLoading || explanation.isLoading}
        isError={prediction.isError || explanation.isError}
        onClose={() => selectAlarm(null)}
      />
    </div>
  );
};

export default App;
