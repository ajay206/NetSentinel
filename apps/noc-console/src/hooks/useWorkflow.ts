import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type WorkflowState = 'new' | 'acknowledged' | 'resolved';

export interface WorkflowNote {
  ts: number;
  by: string;
  action: string;
  text: string;
  assignee?: string;
}

export interface Workflow {
  state: WorkflowState;
  assignee: string | null;
  ackedBy: string | null;
  ackedAt: number | null;
  resolvedBy: string | null;
  resolvedAt: number | null;
  notes: WorkflowNote[];
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data: unknown = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new Error(typeof detail === 'string' ? detail : `Action failed (${resp.status})`);
  }
  return data as T;
}

export type IncidentActionInput = {
  incidentId: string;
  action: 'ack' | 'assign' | 'resolve' | 'note';
  assignee?: string;
  note?: string;
};

export function useIncidentAction() {
  const qc = useQueryClient();
  return useMutation<unknown, Error, IncidentActionInput>({
    mutationFn: ({ incidentId, ...body }) =>
      post(`/api/incidents/${encodeURIComponent(incidentId)}/actions`, body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['incidents'] }),
  });
}

export function useAlarmWorkflow() {
  return useQuery<Record<string, Workflow>, Error>({
    queryKey: ['alarm-workflow'],
    queryFn: async () => {
      const resp = await fetch('/api/alarms/workflow');
      if (!resp.ok) throw new Error('Alarm workflow unavailable');
      return ((await resp.json()) as { items: Record<string, Workflow> }).items;
    },
    refetchInterval: 10_000,
  });
}

export type AlarmActionInput = { key: string; action: 'ack' | 'resolve' | 'note'; note?: string };

export function useAlarmAction() {
  const qc = useQueryClient();
  return useMutation<unknown, Error, AlarmActionInput>({
    mutationFn: (body) => post('/api/alarms/actions', body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['alarm-workflow'] }),
  });
}
