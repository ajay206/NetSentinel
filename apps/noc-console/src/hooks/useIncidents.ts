import { useQuery } from '@tanstack/react-query';
import type { IncidentList } from '../types.incident';

/** W13: incidents from incident-service (GET /api/incidents via the gateway). */
export function useIncidents(limit = 50) {
  return useQuery<IncidentList, Error>({
    queryKey: ['incidents', limit],
    queryFn: async () => {
      const res = await fetch(`/api/incidents?limit=${limit}`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`/api/incidents -> ${res.status}`);
      return (await res.json()) as IncidentList;
    },
    refetchInterval: 5000,
    retry: 1,
  });
}
