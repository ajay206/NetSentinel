export interface Claim {
  text: string;
  sources: string[];
}

export interface CopilotStep {
  text: string;
  runbookId: string;
  section: string;
}

export interface CopilotAnswer {
  suspectedCause: string;
  faultType: string;
  confidence: number;
  evidence: Claim[];
  steps: CopilotStep[];
}

export interface ToolCall {
  name: string;
  ok: boolean;
  durationMs: number;
  transport: "mcp" | "http";
}

export interface LlmRoute {
  route: string | null;
  latencyMs: number;
  redactions: number;
  blocked: string[];
}

export interface AnalyzeResponse {
  siteId: string;
  window: string;
  answer: CopilotAnswer;
  generatedBy: "llm" | "fallback";
  model: string | null;
  /** Step 18: what llm-gateway did (model route chip, latency, PII redactions, guard). */
  llm?: LlmRoute | null;
  attempts: number;
  errors: string[];
  sourceIds: string[];
  warnings: string[];
  /** Step 15: how runbooks were retrieved and which graph nodes are citable. */
  context?: { retrievalMode?: "graph" | "hybrid"; graphNodes?: string[] };
  /** W10: evidence calls (MCP tools, or direct HTTP when TOOLS=http). */
  toolCalls?: ToolCall[];
  durationMs: number;
}
