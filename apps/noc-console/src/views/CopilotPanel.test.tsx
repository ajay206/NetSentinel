import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CopilotPanel } from "./CopilotPanel";
import type { AnalyzeResponse } from "../types.copilot";

const result: AnalyzeResponse = {
  siteId: "SITE-010",
  window: "30m",
  answer: {
    suspectedCause: "Fibre cut on the SITE-010 uplink",
    faultType: "fibre_cut",
    confidence: 0.85,
    evidence: [
      { text: "Critical LOS at SITE-010", sources: ["alm-root-0001"] },
    ],
    steps: [
      {
        text: "Dispatch splicing team",
        runbookId: "RB-FIB-001",
        section: "Remediation",
      },
    ],
  },
  generatedBy: "llm",
  model: "ollama:qwen2.5:1.5b",
  attempts: 1,
  errors: [],
  sourceIds: ["alm-root-0001", "RB-FIB-001"],
  warnings: [],
  durationMs: 1234,
};

describe("CopilotPanel", () => {
  it("validates the site id and calls onAnalyze", () => {
    const onAnalyze = vi.fn();
    render(<CopilotPanel onAnalyze={onAnalyze} />);
    const button = screen.getByRole("button", { name: "Analyze site" });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Site id"), {
      target: { value: "site-010" },
    });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onAnalyze).toHaveBeenCalledWith("SITE-010", "30m");
  });

  it("prefills from the selected alarm site", () => {
    render(<CopilotPanel onAnalyze={vi.fn()} defaultSiteId="SITE-042" />);
    expect(screen.getByLabelText("Site id")).toHaveValue("SITE-042");
  });

  it("renders cause, cited evidence and runbook steps", () => {
    const onOpen = vi.fn();
    render(
      <CopilotPanel
        onAnalyze={vi.fn()}
        result={result}
        onOpenRunbook={onOpen}
      />,
    );
    expect(
      screen.getByText("Fibre cut on the SITE-010 uplink"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("fibre cut · 85%", { exact: false }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("source-chip")).toHaveTextContent(
      "alm-root-0001",
    );
    expect(screen.getByText("LLM · ollama:qwen2.5:1.5b")).toBeInTheDocument();
    fireEvent.click(screen.getByText("RB-FIB-001 §Remediation"));
    expect(onOpen).toHaveBeenCalledWith("RB-FIB-001");
  });

  it("shows fallback badge, pending and error states", () => {
    const { rerender } = render(
      <CopilotPanel
        onAnalyze={vi.fn()}
        result={{ ...result, generatedBy: "fallback", model: null }}
      />,
    );
    expect(screen.getByText("fallback (no LLM)")).toBeInTheDocument();
    rerender(<CopilotPanel onAnalyze={vi.fn()} isPending />);
    expect(screen.getByRole("button", { name: "Analyzing…" })).toBeDisabled();
    rerender(
      <CopilotPanel
        onAnalyze={vi.fn()}
        error={new Error("Copilot unavailable")}
      />,
    );
    expect(screen.getByText("Copilot unavailable")).toBeInTheDocument();
  });

  it("shows MCP tool-call chips, failed ones in red (W10)", () => {
    render(
      <CopilotPanel
        onAnalyze={vi.fn()}
        result={{
          ...result,
          toolCalls: [
            { name: "get_alarms", ok: true, durationMs: 12, transport: "mcp" },
            {
              name: "kpi_anomalies",
              ok: false,
              durationMs: 30,
              transport: "mcp",
            },
            {
              name: "search_runbooks",
              ok: true,
              durationMs: 8,
              transport: "mcp",
            },
          ],
        }}
      />,
    );
    const chips = screen.getAllByTestId("tool-call-chip");
    expect(chips.map((c) => c.textContent)).toEqual([
      "⚙ get_alarms",
      "⚙ kpi_anomalies",
      "⚙ search_runbooks",
    ]);
    expect(chips[1]).toHaveClass("bg-red-950");
    expect(chips[0]).toHaveAttribute("title", "MCP · 12 ms");
  });

  it("hides chips when the response has no tool calls (W9 server)", () => {
    render(<CopilotPanel onAnalyze={vi.fn()} result={result} />);
    expect(screen.queryByTestId("tool-call-chips")).toBeNull();
  });
});
