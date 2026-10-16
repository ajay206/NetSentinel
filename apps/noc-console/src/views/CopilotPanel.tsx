import React, { useEffect, useState } from "react";
import { TIPS } from "../lib/tooltips";
import { CardHeader } from "../components/ui/Card";
import { Tooltip } from "../components/ui/Tooltip";
import type { AnalyzeResponse, ToolCall } from "../types.copilot";
import { RetrievalModeBadge } from "../components/NodeChips";

const NODE_RE = /^(SITE-\d{3}(-N\d{1,2}(-C\d{1,2})?)?|LNK-\d{3})$/;

const SITE_RE = /^SITE-\d{3}$/;
const WINDOWS = ["15m", "30m", "60m", "120m"];

interface CopilotPanelProps {
  /** Pre-fills the site from the selected alarm. */
  defaultSiteId?: string | null;
  onAnalyze: (siteId: string, window: string) => void;
  result?: AnalyzeResponse;
  isPending?: boolean;
  error?: Error | null;
  /** Click a cited runbook to open it in the runbooks panel. */
  onOpenRunbook?: (runbookId: string) => void;
  /** W11 RBAC: analyze is operator-only at the gateway; viewers see a read-only panel. */
  canAnalyze?: boolean;
}

/** Step 15: a cited graph node (site / link / cell) gets a teal node chip. */
const SourceChip: React.FC<{ id: string; graphNodes: Set<string> }> = ({
  id,
  graphNodes,
}) =>
  graphNodes.has(id) && NODE_RE.test(id) ? (
    <span
      className="inline-block font-mono text-[10px] border bg-teal-950 border-teal-700 text-teal-200 px-1.5 py-0.5 rounded mr-1 mb-1"
      title={`topology node ${id}`}
      data-testid="node-chip"
    >
      ◆ {id}
    </span>
  ) : (
    <span
      className="inline-block font-mono text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded mr-1 mb-1"
      title={id}
      data-testid="source-chip"
    >
      {id.length > 28 ? `${id.slice(0, 26)}…` : id}
    </span>
  );

/** W10: one chip per evidence call; red when the tool failed. */
export const ToolCallChips: React.FC<{ calls: ToolCall[] }> = ({ calls }) => (
  <div
    className="flex flex-wrap gap-1"
    data-testid="tool-call-chips"
    aria-label="Tool calls"
  >
    {calls.map((c, i) => (
      <span
        key={`${c.name}-${i}`}
        data-testid="tool-call-chip"
        title={`${c.transport.toUpperCase()} · ${c.durationMs} ms${c.ok ? "" : " · failed"}`}
        className={`font-mono text-[11px] px-2 py-0.5 rounded border ${
          c.ok
            ? "bg-violet-950 border-violet-700 text-violet-200"
            : "bg-red-950 border-red-700 text-red-200"
        }`}
      >
        {c.transport === "mcp" ? "⚙ " : ""}
        {c.name}
      </span>
    ))}
  </div>
);

/** W9: "Analyze site" -> cause / evidence / steps cards with cited alarm, anomaly and runbook ids. */
export const CopilotPanel: React.FC<CopilotPanelProps> = ({
  defaultSiteId,
  onAnalyze,
  result,
  isPending = false,
  error,
  onOpenRunbook,
  canAnalyze = true,
}) => {
  const [siteId, setSiteId] = useState(defaultSiteId ?? "");
  const [window, setWindow] = useState("30m");
  useEffect(() => {
    if (defaultSiteId) setSiteId(defaultSiteId.toUpperCase());
  }, [defaultSiteId]);
  const valid = SITE_RE.test(siteId.trim());
  const graphNodes = new Set(result?.context?.graphNodes ?? []);

  return (
    <div className="ns-card" data-testid="copilot-panel">
      <CardHeader
        as="h3"
        title="Copilot analyze"
        subtitle="A cited root-cause summary and next steps for one site."
        info={TIPS.panelCopilot}
      />
      <form
        className="flex flex-wrap gap-2 items-center mb-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid && !isPending && canAnalyze)
            onAnalyze(siteId.trim(), window);
        }}
      >
        <input
          aria-label="Site id"
          value={siteId}
          onChange={(e) => setSiteId(e.target.value.toUpperCase())}
          placeholder="SITE-012"
          className="bg-bento-bg border border-bento-border rounded px-2 py-1 text-sm text-navy w-28 font-mono"
        />
        <select
          aria-label="Window"
          value={window}
          onChange={(e) => setWindow(e.target.value)}
          className="bg-bento-bg border border-bento-border rounded px-2 py-1 text-sm text-navy"
        >
          {WINDOWS.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
        <Tooltip
          content={
            canAnalyze
              ? TIPS.btnAnalyze
              : `${TIPS.btnAnalyze} Requires the operator role.`
          }
        >
          <span className="inline-flex">
            <button
              type="submit"
              disabled={!valid || isPending || !canAnalyze}
              className="bg-sky-600 hover:bg-sky-500 disabled:bg-slate-200 disabled:text-slate-500 text-white text-sm px-3 py-1 rounded"
            >
              {isPending ? "Analyzing…" : "Analyze site"}
            </button>
          </span>
        </Tooltip>
      </form>

      {!canAnalyze && (
        <p className="text-amber-700 text-xs mb-2" role="note">
          Read-only: analyze needs the operator role.
        </p>
      )}
      {error && <p className="text-red-400 text-sm">{error.message}</p>}
      {!error && !result && !isPending && (
        <p className="text-bento-muted text-sm">
          Pick a site (or click an alarm) and press Analyze. Model calls go
          through llm-gateway (local SLM first).
        </p>
      )}

      {result && !isPending && (
        <div className="space-y-3" data-testid="copilot-answer">
          <div className="flex flex-wrap gap-2 text-[11px]">
            <Tooltip
              content={
                result.generatedBy === "llm" ? TIPS.chipLlm : TIPS.chipFallback
              }
            >
              <span
                className={`px-2 py-0.5 rounded ${
                  result.generatedBy === "llm"
                    ? "bg-emerald-900 text-emerald-200"
                    : "bg-amber-900 text-amber-200"
                }`}
              >
                {result.generatedBy === "llm"
                  ? `LLM · ${result.model}`
                  : "fallback (no LLM)"}
              </span>
            </Tooltip>
            {result.llm && (
              <Tooltip content={TIPS.chipRoute}>
                <span
                  data-testid="model-route"
                  className="px-2 py-0.5 rounded bg-indigo-900 text-indigo-200"
                >
                  route · {result.llm.route ?? "none"} · gateway{" "}
                  {Math.round(result.llm.latencyMs)} ms
                </span>
              </Tooltip>
            )}
            {result.llm && result.llm.redactions > 0 && (
              <Tooltip content={TIPS.chipPii}>
                <span
                  data-testid="pii-redacted"
                  className="px-2 py-0.5 rounded bg-fuchsia-900 text-fuchsia-200"
                >
                  PII redacted · {result.llm.redactions}
                </span>
              </Tooltip>
            )}
            {result.llm && result.llm.blocked.length > 0 && (
              <Tooltip content={TIPS.chipGuard}>
                <span
                  data-testid="guard-blocked"
                  className="px-2 py-0.5 rounded bg-red-900 text-red-200"
                >
                  guard blocked · {result.llm.blocked.join(", ")}
                </span>
              </Tooltip>
            )}
            <Tooltip content={TIPS.chipAttempts}>
              <span className="px-2 py-0.5 rounded bg-bento-bg text-bento-muted">
                {result.attempts} attempt{result.attempts === 1 ? "" : "s"} ·{" "}
                {result.durationMs} ms
              </span>
            </Tooltip>
            {result.warnings.length > 0 && (
              <Tooltip
                content={`${TIPS.chipWarnings} ${result.warnings.join("; ")}`}
              >
                <span className="px-2 py-0.5 rounded bg-bento-bg text-amber-700">
                  {result.warnings.length} upstream warning
                  {result.warnings.length === 1 ? "" : "s"}
                </span>
              </Tooltip>
            )}
          </div>

          {result.context?.retrievalMode && (
            <div
              className="flex flex-wrap items-center gap-1"
              data-testid="copilot-graph"
            >
              <RetrievalModeBadge mode={result.context.retrievalMode} />
              {[...graphNodes].map((n) => (
                <SourceChip key={n} id={n} graphNodes={graphNodes} />
              ))}
            </div>
          )}

          {result.toolCalls && result.toolCalls.length > 0 && (
            <ToolCallChips calls={result.toolCalls} />
          )}

          <section className="bg-bento-bg rounded p-3">
            <h4 className="text-xs uppercase tracking-wide text-bento-muted mb-1">
              Suspected cause
            </h4>
            <p className="text-navy">{result.answer.suspectedCause}</p>
            <p className="text-xs text-bento-muted mt-1">
              {result.answer.faultType.replace(/_/g, " ")} ·{" "}
              {Math.round(result.answer.confidence * 100)}%
            </p>
          </section>

          <section className="bg-bento-bg rounded p-3">
            <h4 className="text-xs uppercase tracking-wide text-bento-muted mb-1">
              Evidence
            </h4>
            <ul className="space-y-2">
              {result.answer.evidence.map((c, i) => (
                <li key={i} className="text-sm text-navy">
                  <div>{c.text}</div>
                  <div className="mt-1">
                    {c.sources.map((s) => (
                      <SourceChip key={s} id={s} graphNodes={graphNodes} />
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="bg-bento-bg rounded p-3">
            <h4 className="text-xs uppercase tracking-wide text-bento-muted mb-1">
              Runbook steps
            </h4>
            {result.answer.steps.length === 0 ? (
              <p className="text-sm text-bento-muted">
                No runbook matched; escalate per procedure.
              </p>
            ) : (
              <ol className="list-decimal list-inside space-y-1">
                {result.answer.steps.map((s, i) => (
                  <li key={i} className="text-sm text-navy">
                    {s.text}{" "}
                    <button
                      type="button"
                      className="font-mono text-xs text-sky-700 hover:underline"
                      onClick={() => onOpenRunbook?.(s.runbookId)}
                    >
                      {s.runbookId} §{s.section}
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      )}
    </div>
  );
};
