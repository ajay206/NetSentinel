export type RunStatus = 'running' | 'awaiting_approval' | 'completed' | 'rejected' | 'failed';
export type AgentName = 'supervisor' | 'triage' | 'rca' | 'remediation' | 'approval' | 'report';
export interface AgentToolCall {
  name: string;
  ok: boolean;
  durationMs: number;
  transport: string;
}
export interface TraceStep {
  seq: number;
  agent: AgentName;
  name: string;
  startedAt: string;
  durationMs: number;
  ok: boolean;
  toolCalls: AgentToolCall[];
  detail: string;
}
export interface ChatMessage {
  agent: AgentName | 'human';
  text: string;
  ts: string;
  sources?: string[];
}
export interface PlanStep {
  text: string;
  runbookId: string;
  section: string;
}
export interface RemediationPlan {
  summary: string;
  steps: PlanStep[];
  ticketDraft: {
    title: string;
    severity: string;
    description: string;
  };
}
export interface AgentRun {
  runId: string;
  incidentId: string | null;
  siteId: string;
  status: RunStatus;
  createdAt: string;
  updatedAt: string;
  agentPath: AgentName[];
  messages: ChatMessage[];
  plan: RemediationPlan | null;
  ticketId: string | null;
  kgWriteBack: { ok: boolean; detail: string } | null;
  trace: TraceStep[];
  report: string | null;
  tracing: { langfuse: boolean };
  trigger?: 'api' | 'incident.created';
  generatedBy?: 'llm' | 'fallback' | null;
  decision?: { approved: boolean; by: string; note: string; at: string } | null;
}
