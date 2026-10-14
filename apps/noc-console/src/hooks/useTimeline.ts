import { useQuery } from '@tanstack/react-query';
import type { TimelineResponse } from '../lib/timeline';

/** W11: alarm-storm timeline from the gateway (viewer role and up). */
export function useTimeline(bucketSeconds = 60) {
  return useQuery<TimelineResponse>({
    queryKey: ['timeline', bucketSeconds],
    queryFn: async () => {
      const res = await fetch(`/api/alarms/timeline?bucketSeconds=${bucketSeconds}`);
      if (!res.ok) throw new Error(`Timeline failed (${res.status})`);
      return res.json() as Promise<TimelineResponse>;
    },
    refetchInterval: 5000,
    staleTime: 4000,
  });
}
