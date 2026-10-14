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

export interface AnalyzeResponse {
  siteId: string;
  window: string;
  answer: CopilotAnswer;
  generatedBy: 'llm' | 'fallback';
  model: string | null;
  attempts: number;
  errors: string[];
  sourceIds: string[];
  warnings: string[];
  durationMs: number;
}
