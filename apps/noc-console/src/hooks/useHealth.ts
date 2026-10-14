import { useQuery } from '@tanstack/react-query';
import type { HealthResponse } from '../types';

export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: async () => {
      const res = await fetch('/health');
      if (!res.ok) {
        throw new Error('Health check failed');
      }
      return res.json() as Promise<HealthResponse>;
    },
    refetchInterval: 5000,
    retry: 1,
    staleTime: 4000,
  });
}
