import { useQuery } from '@tanstack/react-query';
import type { AnomalyList, CellAnomalies } from '../types.anomaly';

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return (await res.json()) as T;
}

/** Top anomalies across cells (GET /api/ml/anomalies via the gateway). */
export function useAnomalyList(kpi: string, hours: number) {
  return useQuery<AnomalyList, Error>({
    queryKey: ['anomalies', kpi, hours],
    queryFn: () =>
      getJson<AnomalyList>(
        `/api/ml/anomalies?kpi=${encodeURIComponent(kpi)}&hours=${hours}&limit=20`
      ),
    refetchInterval: 30000,
    retry: 1,
  });
}

/** Anomalies for one cell, used to mark points on the KPI chart. */
export function useCellAnomalies(cellId: string | null, kpi: string, hours: number) {
  return useQuery<CellAnomalies, Error>({
    queryKey: ['cellAnomalies', cellId, kpi, hours],
    queryFn: () =>
      getJson<CellAnomalies>(
        `/api/ml/anomalies/cells/${encodeURIComponent(cellId ?? '')}?kpi=${encodeURIComponent(kpi)}&hours=${hours}`
      ),
    enabled: cellId !== null,
    refetchInterval: 30000,
    retry: 1,
  });
}
