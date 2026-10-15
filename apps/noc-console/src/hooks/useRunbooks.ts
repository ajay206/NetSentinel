import { useQuery } from '@tanstack/react-query';
import type { RunbookSearchResponse, RunbookDoc } from '../types.runbook';

export function useRunbookSearch(query: string | null, faultType?: string | null) {
  return useQuery<RunbookSearchResponse, Error>({
    queryKey: ['runbooks', query, faultType ?? null],
    queryFn: async () => {
      const response = await fetch('/api/rag/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          top_k: 3,
          // Step 15: Graph RAG (site id in the query is linked to the topology)
          mode: 'graph',
          faultType: faultType ?? null,
        }),
      });

      if (!response.ok) {
        throw new Error('Runbook search failed');
      }

      return response.json();
    },
    enabled: Boolean(query && query.trim().length > 0),
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });
}

export function useRunbook(id: string | null) {
  return useQuery<RunbookDoc, Error>({
    queryKey: ['runbook', id],
    queryFn: async () => {
      const response = await fetch(`/api/rag/runbooks/${encodeURIComponent(id!)}`);

      if (!response.ok) {
        throw new Error('Runbook fetch failed');
      }

      return response.json();
    },
    enabled: Boolean(id),
  });
}
