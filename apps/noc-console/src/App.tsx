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
import { CopilotPanel } from './views/CopilotPanel';
import { useCopilotAnalyze } from './hooks/useCopilot';
import type { EnrichedAlarm } from './types.enriched';
import { useEnrichedFeed } from './hooks/useEnrichedFeed';
import { ServiceHealth } from './components/ServiceHealth';
import { NetworkMap } from './components/NetworkMap';
import { KpiActivity } from './components/KpiActivity';
import { KpiChartsContainer } from './components/KpiChartsContainer';
import { AnomaliesContainer } from './components/AnomaliesContainer';
import { useAlarmFeed } from './hooks/useAlarmFeed';
import { useHealth } from './hooks/useHealth';
import { useTopology } from './hooks/useTopology';
import { useKpiActivity } from './hooks/useKpiActivity';
import { worstSeverityBySite } from './lib/siteStatus';
import { AlarmTimeline } from './components/AlarmTimeline';
import { useTimeline } from './hooks/useTimeline';
import { DemoPath } from './components/DemoPath';
import { KpiSummary } from './components/KpiSummary';
import { CardHeader } from './components/ui/Card';
import { demoStages } from './lib/demoPath';
import { useAnomalyList } from './hooks/useAnomalies';
import { IncidentBoard } from './views/IncidentBoard';
import { useIncidents } from './hooks/useIncidents';
import { alarmBelongsTo } from './lib/incidents';
import { roleAtLeast, type Session } from './lib/auth';

interface AppProps {
  /** W11: set by AuthGate; without it (tests, AUTH_DISABLED) every control is enabled. */
  session?: Session;
  onLogout?: () => void;
}

export const App: React.FC<AppProps> = ({ session, onLogout }) => {
  const canOperate = !session || roleAtLeast(session.role, 'operator');
  const timeline = useTimeline();
  // W12: same query key as the Anomalies panel's default, so this shares its cache
  const anomalies = useAnomalyList('dlThroughputMbps', 24);
  const { alarms, status: wsStatus } = useAlarmFeed();
  const { alarms: enrichedAlarms, status: enrichedStatus } = useEnrichedFeed();
  const { data: health, isError } = useHealth();
  const { data: topology, isLoading: topoLoading, isError: topoError } = useTopology();
  const { activity: kpiActivity, status: kpiStatus } = useKpiActivity();

  // W13: selecting an incident filters both alarm feeds to its members
  const incidents = useIncidents();
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const incident = incidents.data?.items?.find((i) => i?.id === incidentId) ?? null;
  const shownAlarms = useMemo(
    () => alarms.filter((a) => alarmBelongsTo(incident, a)),
    [alarms, incident],
  );
  const shownEnriched = useMemo(
    () => enrichedAlarms.filter((a) => alarmBelongsTo(incident, a)),
    [enrichedAlarms, incident],
  );

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
    selected && (!prediction.isLoading || prediction.isError)
      ? buildRunbookQuery(selected, predictedFault)
      : null;
  const runbookSearch = useRunbookSearch(runbookQuery, predictedFault);
  const [runbookId, setRunbookId] = useState<string | null>(null);
  const runbookDoc = useRunbook(runbookId);
  const copilot = useCopilotAnalyze();
  const selectAlarm = (key: string | null) => {
    setSelectedKey(key);
    setRunbookId(null);
  };

  const copilotSources = copilot.data?.sourceIds ?? [];
  const stages = demoStages({
    alarmCount: enrichedAlarms.length,
    anomalyCount: anomalies.data?.items?.length ?? 0,
    faultType: predictedFault,
    runbookCount: runbookSearch.data?.results?.length ?? 0,
    copilotSources: copilotSources.length,
    copilotCited: (copilot.data?.answer?.steps ?? []).some((s) =>
      copilotSources.includes(s.runbookId),
    ),
  });

  const severityBySite = useMemo(() => worstSeverityBySite(alarms), [alarms]);

  // Fix 1 redesign: headline numbers for the KPI summary row
  const summary = useMemo(() => {
    const active = alarms.filter((a) => a.perceivedSeverity !== 'cleared');
    const items = incidents.data?.items ?? [];
    const open = items.filter((i) => i?.status === 'open');
    // Root of the biggest incident (open first) for the storm annotation
    const biggest = [...(open.length ? open : items)].sort(
      (a, b) => (b?.alarmCount ?? 0) - (a?.alarmCount ?? 0),
    )[0];
    const services = health?.services ?? [];
    return {
      activeAlarms: active.length,
      criticalAlarms: active.filter((a) => a.perceivedSeverity === 'critical').length,
      openIncidents: open.length,
      compressionRatio: incidents.data?.stats?.compressionRatio ?? null,
      anomalies: anomalies.data?.items?.length ?? 0,
      servicesUp: services.filter((x) => x.status === 'up').length,
      servicesTotal: services.length,
      stormRoot: biggest?.rootSiteId ?? null,
    };
  }, [alarms, incidents.data, health, anomalies.data]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col">
      <Header wsStatus={wsStatus} user={session} onLogout={onLogout} />
      {/* 12-column grid, 16px gutters; rows share a fixed height so neighbouring panels align */}
      <main className="mx-auto w-full max-w-[1600px] flex-1 space-y-4 px-6 py-5">
        <KpiSummary {...summary} />

        <DemoPath stages={stages} />

        {/* Row: what is happening now */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="lg:col-span-6 2xl:col-span-7">
            <AlarmTimeline
              data={timeline.data}
              isLoading={timeline.isLoading}
              isError={timeline.isError}
              rootSiteId={summary.stormRoot}
            />
          </div>
          <div className="lg:col-span-6 2xl:col-span-5">
            <IncidentBoard
              data={incidents.data}
              isLoading={incidents.isLoading}
              isError={incidents.isError}
              selectedId={incidentId}
              onSelect={setIncidentId}
            />
          </div>
        </div>

        {/* Row: alarm tables (filtered by the selected incident) + service health */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="lg:col-span-9 lg:h-[420px]">
            <LiveAlarms alarms={shownAlarms} />
          </div>
          <div className="lg:col-span-3 lg:h-[420px]">
            <ServiceHealth health={health} isError={isError} />
          </div>
        </div>

        <div className="lg:h-[460px]">
          <EnrichedAlarms
            alarms={shownEnriched}
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

        {/* Row: network + KPIs */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <NetworkMap
              topology={topology}
              isLoading={topoLoading}
              isError={topoError}
              severityBySite={severityBySite}
            />
          </div>
          <div className="lg:col-span-5">
            <section className="ns-card">
              <CardHeader
                title="KPI activity"
                subtitle="Live KPI samples streaming from the cells."
                info="Counts and network-wide averages of the KPI samples the simulator publishes every 15 minutes (synthetic)."
              />
              <KpiActivity activity={kpiActivity} status={kpiStatus} />
            </section>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <KpiChartsContainer />
          <AnomaliesContainer />
        </div>

        {/* Row: diagnosis (runbooks live in the alarm drawer) */}
        <div>
          <CopilotPanel
            defaultSiteId={selected?.siteId ?? null}
            onAnalyze={(siteId, window) => copilot.mutate({ siteId, window })}
            result={copilot.data}
            isPending={copilot.isPending}
            error={copilot.error}
            onOpenRunbook={setRunbookId}
            canAnalyze={canOperate}
          />
        </div>
      </main>
      <ShapDrawer
        alarm={selected}
        prediction={prediction.data}
        explanation={explanation.data}
        isLoading={prediction.isLoading || explanation.isLoading}
        isError={prediction.isError || explanation.isError}
        onClose={() => selectAlarm(null)}
        runbooks={
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
        }
      />
    </div>
  );
};

export default App;
