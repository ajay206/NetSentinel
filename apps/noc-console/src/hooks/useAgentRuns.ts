import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AgentRun } from '../types.agents';

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  const data: unknown = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new Error(typeof detail === 'string' ? detail : `copilot ${resp.status}`);
  }
  return data as T;
}

const post = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

/** W17: multi-agent runs (viewer). Polls so incident.created runs appear on their own. */
export function useAgentRuns() {
  return useQuery<{ items: AgentRun[] }, Error>({
    queryKey: ['agent-runs'],
    queryFn: () => call('/api/copilot/runs'),
    refetchInterval: 10_000,
  });
}

/** Start a run (operator). Runs to the human approval node, so it can take a while. */
export function useStartRun() {
  const qc = useQueryClient();
  return useMutation<AgentRun, Error, { incidentId?: string; siteId?: string }>({
    mutationFn: (target) => call('/api/copilot/runs', post(target)),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['agent-runs'] }),
  });
}

/** The human approval node: approve or reject the agents' plan (operator). */
export function useRunDecision() {
  const qc = useQueryClient();
  return useMutation<AgentRun, Error, { runId: string; approved: boolean; note: string }>({
    mutationFn: ({ runId, approved, note }) =>
      call(`/api/copilot/runs/${encodeURIComponent(runId)}/approval`, post({ approved, note })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['agent-runs'] });
      void qc.invalidateQueries({ queryKey: ['tickets'] });
    },
  });
}
