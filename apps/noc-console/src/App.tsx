import React, { useCallback, useMemo, useState } from 'react';
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
import { CopilotChat } from './views/CopilotChat';
import { TraceView } from './views/TraceView';
import { useAgentRuns, useRunDecision, useStartRun } from './hooks/useAgentRuns';
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
import { useTicketAudit, useTicketDecision, useTickets } from './hooks/useTickets';
import { ApprovalQueue } from './views/ApprovalQueue';
import type { TicketStatus } from './types.ticket';
import { alarmBelongsTo } from './lib/incidents';
import { saveSession, type Role, type Session } from './lib/auth';
import { can } from './lib/rbac';
import { useAlarmAction, useAlarmWorkflow, useIncidentAction } from './hooks/useWorkflow';
import { WorkflowActions } from './components/WorkflowActions';
import { ChangePasswordDialog } from './components/ChangePasswordDialog';
import { AdminDashboard } from './views/admin/AdminDashboard';
import { RcaGraph } from './views/RcaGraph';
import type { ImpactResult, ImpactTarget } from './types.graph';

interface AppProps {
  /** W11: set by AuthGate; without it (tests, AUTH_DISABLED) every control is enabled. */
  session?: Session;
  onLogout?: () => void;
  /** Step 13b: a password change returns a fresh token (older ones are revoked). */
  onSessionChange?: (s: Session) => void;
}

export const App: React.FC<AppProps> = ({ session, onLogout, onSessionChange }) => {
  // Step 13b: role-specific dashboards. The gateway enforces the same rules (403).
  const role = session?.role ?? 'admin';
  const me = session?.username ?? 'anonymous';
  const canOperate = can(role, 'incident.act');
  const canCopilot = can(role, 'copilot.analyze');
  const isAdmin = can(role, 'admin.users');
  const canApprove = can(role, 'ticket.approve');
  const [view, setView] = useState<'ops' | 'admin'>('ops');
  const [pwOpen, setPwOpen] = useState(false);
  const incidentAction = useIncidentAction();
  const alarmWorkflow = useAlarmWorkflow();
  const alarmAction = useAlarmAction();
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
  // W16: approval queue + audit trail; the incident board links to related drafts
  const [ticketStatus, setTicketStatus] = useState<TicketStatus | 'all'>('draft');
  const [ticketId, setTicketId] = useState<string | null>(null);
  const tickets = useTickets(ticketStatus);
  const allTickets = useTickets('all');
  const ticketAudit = useTicketAudit(ticketId);
  const decision = useTicketDecision();
  // W17: multi-agent copilot runs (operators start and approve; viewers read the trace)
  const agentRuns = useAgentRuns();
  const startRun = useStartRun();
  const runDecision = useRunDecision();
  const [runId, setRunId] = useState<string | null>(null);
  const runs = agentRuns.data?.items ?? [];
  const run =
    runs.find((r) => r.runId === runId) ??
    (startRun.data && startRun.data.runId === runId ? startRun.data : null) ??
    runs[0] ??
    null;
  const relatedDrafts = (allTickets.data?.items ?? []).filter(
    (t) => incidentId !== null && t.incidentId === incidentId,
  );
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
  // Resolve against the visible (incident-filtered) feed so the drawer cannot
  // stay open on an alarm the tables are no longer showing.
  const selected: EnrichedAlarm | null =
    shownEnriched.find((a) => a.dedup.key === selectedKey) ?? null;
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
  // Step 14: the RCA graph panel's answer drives the impact radius on the network map
  const [impact, setImpact] = useState<{
    target: ImpactTarget | null;
    result: ImpactResult | null;
  }>({ target: null, result: null });
  const onImpact = useCallback(
    (target: ImpactTarget | null, result: ImpactResult | null) => setImpact({ target, result }),
    [],
  );
  const impactedSiteIds = useMemo(
    () => new Set(impact.result?.impactedSites.map((s) => s.siteId) ?? []),
    [impact.result],
  );

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
      <Header
        wsStatus={wsStatus}
        user={session}
        onLogout={onLogout}
        onChangePassword={session ? () => setPwOpen(true) : undefined}
        views={
          isAdmin
            ? [
                { id: 'ops', label: 'Operations' },
                { id: 'admin', label: 'Admin' },
              ]
            : []
        }
        activeView={view}
        onSelectView={(id) => setView(id === 'admin' ? 'admin' : 'ops')}
      />
      {session && (
        <ChangePasswordDialog
          open={pwOpen}
          username={session.username}
          onClose={() => setPwOpen(false)}
          onChanged={(r) => {
            const next: Session = {
              token: r.accessToken,
              username: r.username,
              role: r.role as Role,
              expiresAt: Date.now() + r.expiresIn * 1000,
            };
            saveSession(next);
            onSessionChange?.(next);
          }}
        />
      )}
      {isAdmin && view === 'admin' ? (
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-6 py-5">
          <AdminDashboard currentUser={me} health={health} healthError={isError} />
        </main>
      ) : (
        /* 12-column grid, 16px gutters; rows share a fixed height so neighbouring panels align */
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
                selectedFooter={
                  incidentId ? (
                    <>
                      {relatedDrafts.length > 0 && (
                        <div
                          className="mb-2 flex flex-wrap items-center gap-1 text-xs"
                          data-testid="related-drafts"
                        >
                          <span className="text-slate-400">Related tickets:</span>
                          {relatedDrafts.map((t) => (
                            <button
                              key={t.id}
                              type="button"
                              className="font-mono text-sky-300 hover:underline"
                              onClick={() => {
                                setTicketStatus('all');
                                setTicketId(t.id);
                              }}
                            >
                              {t.id} ({t.status})
                            </button>
                          ))}
                        </div>
                      )}
                      <WorkflowActions
                        subject={`incident ${incidentId}`}
                        workflow={incidents.data?.items.find((i) => i.id === incidentId)?.workflow}
                        canAct={canOperate}
                        currentUser={me}
                        allowAssign
                        isPending={incidentAction.isPending}
                        error={incidentAction.error}
                        onAction={(action, extra) =>
                          incidentAction.mutate({ incidentId, action, ...extra })
                        }
                      />
                    </>
                  ) : null
                }
              />
            </div>
          </div>

          {/* Row: W16 approval queue (operators decide; viewers read) */}
          <ApprovalQueue
            tickets={tickets.data?.items}
            isLoading={tickets.isLoading}
            isError={tickets.isError}
            status={ticketStatus}
            onStatusChange={setTicketStatus}
            selectedId={ticketId}
            onSelect={setTicketId}
            audit={ticketAudit.data?.entries}
            auditLoading={ticketId !== null && ticketAudit.isLoading}
            canApprove={canApprove}
            onDecide={(id, d, note) => decision.mutate({ id, decision: d, note })}
            isPending={decision.isPending}
            error={decision.error}
          />

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
                impactedSiteIds={impactedSiteIds}
                failedLinkId={impact.target?.type === 'link' ? impact.target.id : null}
                failedSiteId={impact.target?.type === 'site' ? impact.target.id : null}
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

          {/* Step 14: impact / RCA on the knowledge graph (highlights the map above) */}
          <div className="lg:max-h-[420px]">
            <RcaGraph topology={topology} onImpact={onImpact} agentRun={run} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <KpiChartsContainer />
            <AnomaliesContainer />
          </div>

          {/* Row: W17 multi-agent copilot chat + per-agent trace */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <CopilotChat
                incidentId={incidentId}
                siteId={selected?.siteId ?? null}
                run={run}
                runs={runs}
                isStarting={startRun.isPending}
                isDeciding={runDecision.isPending}
                error={startRun.error ?? runDecision.error}
                canOperate={canCopilot}
                onStart={(target) =>
                  startRun.mutate(target, { onSuccess: (r) => setRunId(r.runId) })
                }
                onSelectRun={setRunId}
                onDecide={(approved, note) =>
                  run && runDecision.mutate({ runId: run.runId, approved, note })
                }
              />
            </div>
            <div className="ns-card lg:col-span-5">
              <TraceView run={run} />
            </div>
          </div>

          {/* Row: diagnosis (runbooks live in the alarm drawer). Viewers have no copilot. */}
          {canCopilot && (
            <div>
              <CopilotPanel
                defaultSiteId={selected?.siteId ?? null}
                onAnalyze={(siteId, window) => copilot.mutate({ siteId, window })}
                result={copilot.data}
                isPending={copilot.isPending}
                error={copilot.error}
                onOpenRunbook={setRunbookId}
                canAnalyze={canCopilot}
              />
            </div>
          )}
        </main>
      )}
      <ShapDrawer
        alarm={selected}
        prediction={prediction.data}
        explanation={explanation.data}
        isLoading={explanation.isLoading}
        isError={explanation.isError}
        onClose={() => selectAlarm(null)}
        actions={
          selected ? (
            <WorkflowActions
              subject={`alarm ${selected.siteId}`}
              workflow={alarmWorkflow.data?.[selected.dedup.key]}
              canAct={canOperate}
              currentUser={me}
              isPending={alarmAction.isPending}
              error={alarmAction.error}
              onAction={(action, { note }) =>
                action !== 'assign' && alarmAction.mutate({ key: selected.dedup.key, action, note })
              }
            />
          ) : null
        }
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
            mode={runbookSearch.data?.mode ?? null}
          />
        }
      />
    </div>
  );
};

export default App;
