# ADR-017 – LangGraph multi-agent copilot with a human approval node
**Status:** Accepted (Step 17). Builds on ADR-009 (local-LLM copilot), ADR-010 (MCP tools), ADR-015 (Graph RAG) and ADR-016 (human approval of tickets).

## Context
The W9 copilot is one call: gather evidence, then ask the LLM once. W17 asks for a supervisor with Triage, RCA, Remediation and Report agents, a checkpointer, a human approval node, KG write-back, an `incident.created` trigger and tracing. The console should show each agent step for one incident from storm → approval → ticket draft. It has to work on a laptop with a 1.5B local model, and CI must test it with a mocked LLM.

## Decision
- **LangGraph `StateGraph`** with a supervisor node and conditional edges to five specialists, each returning to the supervisor. The routing policy is deterministic (plan-and-execute): the next agent whose output is missing. A small local model is unreliable at picking tools (ReAct), and a fixed policy makes the path testable.
- **Reuse, not rewrite:** triage calls the W9 `gather` (MCP or HTTP tools, Graph RAG). RCA calls the shared `llm_answer` (citation guard plus deterministic fallback), so a run works with `LLM=off`.
- **Human-in-the-loop:** the approval node calls LangGraph `interrupt()`, and the operator resumes it through `POST /api/copilot/runs/{id}/approval` (operator role, audited). Nothing is written before the decision. After approval the agent only opens a ticket **draft**, which a second human approval in the queue must still pass (ADR-016).
- **Checkpointer:** `InMemorySaver`, one thread per run, capped at 200 runs. A Postgres checkpointer was not adopted; it would add a package and schema for a demo that does not need runs to survive restarts.
- **Tracing:** each step records its duration and tool calls in the run state. Langfuse is optional, through its public ingestion API over httpx (no SDK); it needs a self-hosted Langfuse because the managed service may be paid.
- **KG write-back:** an approved finding becomes `(:RcaFinding)-[:ROOT_CAUSE]->(:Site)` with runbook and ticket links, through the gateway. The service token gets exactly this extra write.

## Consequences
- A full run takes triage + LLM time, then waits for a human; the console polls.
- Runs are lost on restart (documented, troubleshooting #77).
- Topology reloads drop the `ROOT_CAUSE` edge, but the finding node keeps its site id.
- **Deferred:** LLM-chosen routing, long-term memory across runs, a persistent checkpointer.
