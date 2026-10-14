import { useQuery } from '@tanstack/react-query';
import type { Topology } from '../types';

/**
 * Fetches the network topology from the backend.
 * The result is cached indefinitely (staleTime: Infinity) because the topology
 * rarely changes and is refreshed only when the user manually refetches.
 */
export function useTopology() {
  return useQuery<Topology, Error>({
    queryKey: ['topology'],
    queryFn: async () => {
      const response = await fetch('/api/topology', {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch topology: ${response.status}`);
      }

      const data: Topology = await response.json();
      return data;
    },
    staleTime: Infinity,
    // The query should not retry on 404 etc.; let React Query handle generic retries.
    retry: true,
  });
}
