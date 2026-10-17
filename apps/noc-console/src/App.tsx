import React, { useCallback, useMemo, useState } from "react";
import { TIPS } from "./lib/tooltips";
import { Header } from "./components/Header";
import { LiveAlarms } from "./components/LiveAlarms";
import { EnrichedAlarms } from "./components/EnrichedAlarms";
import { FaultBadge } from "./components/FaultBadge";
import { ShapDrawer } from "./components/ShapDrawer";
import { useFaultExplanation, useFaultPrediction } from "./hooks/useFault";
import { useRunbook, useRunbookSearch } from "./hooks/useRunbooks";
import { buildRunbookQuery } from "./lib/runbookQuery";
import { RunbooksPanel } from "./views/RunbooksPanel";
import { CopilotPanel } from "./views/CopilotPanel";
import { CopilotChat } from "./views/CopilotChat";
import { PqcStatus } from "./views/PqcStatus";
import { usePqcStatus } from "./hooks/usePqcStatus";
import { TraceView } from "./views/TraceView";
import {
  useAgentRuns,
  useRunDecision,
  useStartRun,
} from "./hooks/useAgentRuns";
import { useCopilotAnalyze } from "./hooks/useCopilot";
import type { EnrichedAlarm } from "./types.enriched";
import { useEnrichedFeed } from "./hooks/useEnrichedFeed";
import { ServiceHealth } from "./components/ServiceHealth";
import { NetworkMap } from "./components/NetworkMap";
import { KpiActivity } from "./components/KpiActivity";
import { KpiChartsContainer } from "./components/KpiChartsContainer";
import { AnomaliesContainer } from "./components/AnomaliesContainer";
import { useAlarmFeed } from "./hooks/useAlarmFeed";
import { useHealth } from "./hooks/useHealth";
import { useTopology } from "./hooks/useTopology";
import { useKpiActivity } from "./hooks/useKpiActivity";
import { worstSeverityBySite } from "./lib/siteStatus";
import { AlarmTimeline } from "./components/AlarmTimeline";
import { useTimeline } from "./hooks/useTimeline";
import { DemoPath, type ConsolePage } from "./components/DemoPath";
import { KpiSummary } from "./components/KpiSummary";
import { CardHeader } from "./components/ui/Card";
import { useAnomalyList } from "./hooks/useAnomalies";
import { IncidentBoard } from "./views/IncidentBoard";
import { useIncidents } from "./hooks/useIncidents";
import {
  useTicketAudit,
  useTicketDecision,
  useTickets,
} from "./hooks/useTickets";
import { ApprovalQueue } from "./views/ApprovalQueue";
import type { TicketStatus } from "./types.ticket";
import { alarmBelongsTo } from "./lib/incidents";
import { saveSession, type Role, type Session } from "./lib/auth";
import { can } from "./lib/rbac";
import {
  useAlarmAction,
  useAlarmWorkflow,
  useIncidentAction,
} from "./hooks/useWorkflow";
import { WorkflowActions } from "./components/WorkflowActions";
import { ChangePasswordDialog } from "./components/ChangePasswordDialog";
import { AdminDashboard } from "./views/admin/AdminDashboard";
import { RcaGraph } from "./views/RcaGraph";
import type { ImpactResult, ImpactTarget } from "./types.graph";

interface AppProps {
  /** W11: set by AuthGate; without it (tests, AUTH_DISABLED) every control is enabled. */
  session?: Session;
  onLogout?: () => void;
  /** Step 13b: a password change returns a fresh token (older ones are revoked). */
  onSessionChange?: (s: Session) => void;
}

const PageHeading: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div className="border-b border-bento-border pb-3">
    <h1 className="text-2xl font-extrabold text-navy">{title}</h1>
    <p className="mt-1 max-w-3xl text-sm leading-relaxed text-bento-muted">{description}</p>
  </div>
);

export const App: React.FC<AppProps> = ({
  session,
  onLogout,
  onSessionChange,
}) => {
  // Step 13b: role-specific dashboards. The gateway enforces the same rules (403).
  const role = session?.role ?? "admin";
  const me = session?.username ?? "anonymous";
  const canOperate = can(role, "incident.act");
  const canCopilot = can(role, "copilot.analyze");
  const isAdmin = can(role, "admin.users");
  const canApprove = can(role, "ticket.approve");
  const [view, setView] = useState<"ops" | "admin">("ops");
  const [activePage, setActivePage] = useState<ConsolePage>("overview");
  const [pwOpen, setPwOpen] = useState(false);
  const incidentAction = useIncidentAction();
  const alarmWorkflow = useAlarmWorkflow();
  const alarmAction = useAlarmAction();
  const timeline = useTimeline();
  // W12: same query key as the Anomalies panel's default, so this shares its cache
  const anomalies = useAnomalyList("dlThroughputMbps", 24);
  const { alarms, status: wsStatus } = useAlarmFeed();
  const { alarms: enrichedAlarms, status: enrichedStatus } = useEnrichedFeed();
  const { data: health, isError } = useHealth();
  const {
    data: topology,
    isLoading: topoLoading,
    isError: topoError,
  } = useTopology();
  const { activity: kpiActivity, status: kpiStatus } = useKpiActivity();

  // W13: selecting an incident filters both alarm feeds to its members
  const incidents = useIncidents();
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const incident =
    incidents.data?.items?.find((i) => i?.id === incidentId) ?? null;
  // W16: approval queue + audit trail; the incident board links to related drafts
  const [ticketStatus, setTicketStatus] = useState<TicketStatus | "all">(
    "draft",
  );
  const [ticketId, setTicketId] = useState<string | null>(null);
  const tickets = useTickets(ticketStatus);
  const allTickets = useTickets("all");
  const ticketAudit = useTicketAudit(ticketId);
  const decision = useTicketDecision();
  // W17: multi-agent copilot runs (operators start and approve; viewers read the trace)
  const agentRuns = useAgentRuns();
  const pqc = usePqcStatus();
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

  const severityBySite = useMemo(() => worstSeverityBySite(alarms), [alarms]);
  // Step 14: the RCA graph panel's answer drives the impact radius on the network map
  const [impact, setImpact] = useState<{
    target: ImpactTarget | null;
    result: ImpactResult | null;
  }>({ target: null, result: null });
  const onImpact = useCallback(
    (target: ImpactTarget | null, result: ImpactResult | null) =>
      setImpact({ target, result }),
    [],
  );
  const impactedSiteIds = useMemo(
    () => new Set(impact.result?.impactedSites.map((s) => s.siteId) ?? []),
    [impact.result],
  );

  // Bento redesign summary row
  const summary = useMemo(() => {
    const active = alarms.filter((a) => a.perceivedSeverity !== "cleared");
    const items = incidents.data?.items ?? [];
    const open = items.filter((i) => i?.status === "open");
    const biggest = [...(open.length ? open : items)].sort(
      (a, b) => (b?.alarmCount ?? 0) - (a?.alarmCount ?? 0),
    )[0];
    const services = health?.services ?? [];
    return {
      activeAlarms: active.length,
      criticalAlarms: active.filter((a) => a.perceivedSeverity === "critical")
        .length,
      openIncidents: open.length,
      compressionRatio: incidents.data?.stats?.compressionRatio ?? null,
      anomalies: anomalies.data?.items?.length ?? 0,
      servicesUp: services.filter((x) => x.status === "up").length,
      servicesTotal: services.length,
      stormRoot: biggest?.rootSiteId ?? null,
    };
  }, [alarms, incidents.data, health, anomalies.data]);

  return (
    <div className="min-h-screen bg-bento-bg text-navy flex flex-col font-sans antialiased">
      <div className="px-4 pb-6 pt-4 md:px-6 md:pb-8 md:pt-6 flex-1 flex flex-col gap-4 lg:gap-6 max-w-[1920px] mx-auto w-full">
        <Header
          wsStatus={wsStatus}
          user={session}
          onLogout={onLogout}
          onChangePassword={session ? () => setPwOpen(true) : undefined}
          views={
            isAdmin
              ? [
                  { id: "ops", label: "Operations" },
                  { id: "admin", label: "Admin" },
                ]
              : []
          }
          activeView={view}
          onSelectView={(id) => setView(id === "admin" ? "admin" : "ops")}
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
        {isAdmin && view === "admin" ? (
          <main className="flex-1">
            <AdminDashboard currentUser={me} health={health} healthError={isError} />
          </main>
        ) : (
          <>
            <DemoPath activePage={activePage} onNavigate={setActivePage} />
            <main className="flex-1 space-y-4 lg:space-y-6" aria-label={`${activePage} dashboard`}>
              {activePage === "overview" && (
                <>
                  <PageHeading title="Operations overview" description="A quick view of current network activity, incidents, and service health." />
                  <KpiSummary {...summary} />
                  <div className="grid grid-cols-1 items-start gap-4 lg:gap-6 lg:grid-cols-12">
                    <div className="lg:col-span-7 lg:min-h-[440px]">
                      <AlarmTimeline data={timeline.data} isLoading={timeline.isLoading} isError={timeline.isError} rootSiteId={summary.stormRoot} />
                    </div>
                    <div className="lg:col-span-5">
                      <IncidentBoard
                        data={incidents.data}
                        isLoading={incidents.isLoading}
                        isError={incidents.isError}
                        selectedId={incidentId}
                        onSelect={setIncidentId}
                        selectedFooter={incidentId ? (
                          <>
                            {relatedDrafts.length > 0 && (
                              <div className="mb-2 flex flex-wrap items-center gap-1 text-xs" data-testid="related-drafts">
                                <span className="text-bento-muted font-bold">Related tickets:</span>
                                {relatedDrafts.map((t) => (
                                  <button key={t.id} type="button" className="font-mono font-bold text-sky-800 hover:underline" onClick={() => { setTicketStatus("all"); setTicketId(t.id); setActivePage("alarms"); }}>
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
                              onAction={(action, extra) => incidentAction.mutate({ incidentId, action, ...extra })}
                            />
                          </>
                        ) : null}
                      />
                    </div>
                  </div>
                </>
              )}

              {activePage === "alarms" && (
                <>
                  <PageHeading title="Alarm management" description="Review incoming alarms, related network events, and ticket decisions that need attention." />
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
                  <div className="grid grid-cols-1 gap-4 lg:gap-6 lg:grid-cols-12">
                    <div className="lg:col-span-9 lg:h-[420px]"><LiveAlarms alarms={shownAlarms} /></div>
                    <div className="lg:col-span-3 lg:h-[420px]"><ServiceHealth health={health} isError={isError} /></div>
                  </div>
                  {selected ? (
                    <div className="grid grid-cols-1 items-start gap-4 lg:gap-6 lg:grid-cols-12">
                      <div className="lg:col-span-8 lg:h-[460px]">
                        <EnrichedAlarms
                          alarms={shownEnriched}
                          status={enrichedStatus}
                          selectedKey={selectedKey}
                          onSelect={(a) => selectAlarm(a.dedup.key)}
                          selectedBadge={<FaultBadge prediction={prediction.data} isLoading={prediction.isLoading} isError={prediction.isError} />}
                        />
                      </div>
                      <div className="lg:col-span-4 lg:h-[460px]">
                        <ShapDrawer
                          inline
                          alarm={selected}
                          prediction={prediction.data}
                          explanation={explanation.data}
                          isLoading={explanation.isLoading}
                          isError={explanation.isError}
                          onClose={() => selectAlarm(null)}
                          actions={(
                            <WorkflowActions
                              subject={`alarm ${selected.siteId}`}
                              workflow={alarmWorkflow.data?.[selected.dedup.key]}
                              canAct={canOperate}
                              currentUser={me}
                              isPending={alarmAction.isPending}
                              error={alarmAction.error}
                              onAction={(action, { note }) =>
                                action !== "assign" &&
                                alarmAction.mutate({ key: selected.dedup.key, action, note })
                              }
                            />
                          )}
                          runbooks={(
                            <RunbooksPanel
                              alarmLabel={`${selected.specificProblem} @ ${selected.siteId}`}
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
                          )}
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="lg:h-[460px]">
                      <EnrichedAlarms
                        alarms={shownEnriched}
                        status={enrichedStatus}
                        selectedKey={selectedKey}
                        onSelect={(a) => selectAlarm(a.dedup.key)}
                        selectedBadge={<FaultBadge prediction={prediction.data} isLoading={prediction.isLoading} isError={prediction.isError} />}
                      />
                    </div>
                  )}
                </>
              )}

              {activePage === "network" && (
                <>
                  <PageHeading title="Network map and impact" description="See how sites connect and which services or cells may be affected by a fault." />
                  <div className="grid grid-cols-1 gap-4 lg:gap-6 lg:grid-cols-12">
                    <div className="lg:col-span-7 lg:h-[500px]">
                      <NetworkMap topology={topology} isLoading={topoLoading} isError={topoError} severityBySite={severityBySite} impactedSiteIds={impactedSiteIds} failedLinkId={impact.target?.type === "link" ? impact.target.id : null} failedSiteId={impact.target?.type === "site" ? impact.target.id : null} />
                    </div>
                    <div className="lg:col-span-5 lg:h-[500px]"><RcaGraph topology={topology} onImpact={onImpact} agentRun={run} /></div>
                  </div>
                  <PqcStatus data={pqc.data} error={pqc.error} isLoading={pqc.isLoading} />
                </>
              )}

              {activePage === "performance" && (
                <>
                  <PageHeading title="Network performance" description="Track service measurements over time and review cells with unusual changes." />
                  <section className="ns-card">
                    <CardHeader title="Measurement freshness" subtitle="How recently performance samples arrived from network cells." info={TIPS.panelKpiActivity} />
                    <KpiActivity activity={kpiActivity} status={kpiStatus} />
                  </section>
                  <div className="grid grid-cols-1 gap-4 lg:gap-6 lg:grid-cols-2">
                    <KpiChartsContainer />
                    <AnomaliesContainer />
                  </div>
                </>
              )}

              {activePage === "investigation" && (
                <>
                  <PageHeading title="Investigation workspace" description="Review repair guidance and AI-assisted analysis. Operator actions still require an authorized human decision." />
                  <RunbooksPanel
                    compact
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
                  <div className="grid grid-cols-1 gap-4 lg:gap-6 lg:grid-cols-12">
                    <div className="lg:col-span-7 lg:h-[640px]">
                      <CopilotChat
                        incidentId={incidentId}
                        siteId={selected?.siteId ?? null}
                        run={run}
                        runs={runs}
                        isStarting={startRun.isPending}
                        isDeciding={runDecision.isPending}
                        error={startRun.error ?? runDecision.error}
                        canOperate={canOperate}
                        onStart={(target) => startRun.mutate(target, { onSuccess: (r) => setRunId(r.runId) })}
                        onSelectRun={setRunId}
                        onDecide={(approved, note) => run && runDecision.mutate({ runId: run.runId, approved, note })}
                      />
                    </div>
                    <div className="ns-card lg:col-span-5 lg:h-[640px]"><TraceView run={run} /></div>
                  </div>
                  <CopilotPanel
                    defaultSiteId={selected?.siteId ?? topology?.sites?.[0]?.siteId ?? null}
                    sites={topology?.sites ?? []}
                    onAnalyze={(siteId, window) => copilot.mutate({ siteId, window })}
                    result={copilot.data}
                    isPending={copilot.isPending}
                    error={copilot.error}
                    onOpenRunbook={setRunbookId}
                    canAnalyze={canCopilot}
                  />
                </>
              )}
            </main>
          </>
        )}
      </div>
    </div>
  );
};

export default App;
