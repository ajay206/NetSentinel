import { useQuery } from '@tanstack/react-query';
import { KpiCell, KpiSeries } from '../types.kpi';

const API_BASE = '/api/kpi';

export const useKpiCells = () => {
  return useQuery<KpiCell[]>({
    queryKey: ['kpi', 'cells'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/cells`);
      if (!res.ok) throw new Error('Failed to fetch KPI cells');
      return res.json();
    },
    refetchInterval: 30_000,
    staleTime: 0,
  });
};

type Agg = '15m' | '1h' | '1d';

export const useKpiSeries = (
  cellId: string | null,
  agg: Agg,
  hours: number,
) => {
  return useQuery<KpiSeries>({
    queryKey: ['kpi', 'series', cellId, agg, hours],
    enabled: !!cellId,
    queryFn: async () => {
      // Recompute the window on every (re)fetch so the chart slides forward with time
      const now = Date.now();
      const params = new URLSearchParams({
        agg,
        from: new Date(now - hours * 60 * 60 * 1000).toISOString(),
        to: new Date(now).toISOString(),
      });
      const res = await fetch(`${API_BASE}/cells/${encodeURIComponent(cellId ?? '')}?${params}`);
      if (!res.ok) throw new Error('Failed to fetch KPI series');
      return res.json();
    },
    refetchInterval: 15_000,
    staleTime: 0,
  });
};
