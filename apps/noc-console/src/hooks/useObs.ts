import { useQuery } from '@tanstack/react-query';

/** W22: p95 latency (ms) and 5xx ratio per service over the last 30 min (from Prometheus). */
export interface ServiceSpark {
  p95Ms: number[];
  errorRate: number[];
}
export interface SparklinesResponse {
  enabled: boolean;
  error?: string;
  services: Record<string, ServiceSpark>;
}
export interface ObsLinks {
  grafana: string | null;
  langfuse: string | null;
  mlflow: string | null;
  prometheus: string | null;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res || !res.ok) throw new Error(`${url} ${res?.status}`);
  return (await res.json()) as T;
}

export function useSparklines() {
  return useQuery<SparklinesResponse>({
    queryKey: ['obs-sparklines'],
    queryFn: () => getJson<SparklinesResponse>('/api/obs/sparklines'),
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useObsLinks() {
  return useQuery<ObsLinks>({
    queryKey: ['obs-links'],
    queryFn: () => getJson<ObsLinks>('/api/obs/links'),
    staleTime: 300_000,
    retry: false,
  });
}

export const last = (xs: number[]): number | undefined => (xs.length ? xs[xs.length - 1] : undefined);

/** W24: served fault-classifier version and its last eval-gate result. */
export interface ModelInfo {
  name: string;
  version: string | null;
  trainedAt?: string | null;
  metrics?: { accuracy?: number; macro_f1?: number };
  gate: { passed: boolean; reasons: string[] } | null;
  signature?: string | null;
  loaded: boolean;
}

export function useModelInfo() {
  return useQuery<ModelInfo>({
    queryKey: ['model-info'],
    queryFn: () => getJson<ModelInfo>('/api/ml/model/info'),
    refetchInterval: 60_000,
    retry: false,
  });
}
