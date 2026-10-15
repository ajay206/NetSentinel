import { useQuery } from '@tanstack/react-query';
import type { ImpactResult, ImpactTarget } from '../types.graph';

/** Step 14: which cells lose service if `target` fails (viewer role; graph profile). */
export function useImpact(target: ImpactTarget | null) {
  return useQuery<ImpactResult, Error>({
    queryKey: ['graph', 'impact', target?.type, target?.id],
    enabled: target !== null,
    staleTime: 30_000,
    retry: false,
    queryFn: async () => {
      if (!target) throw new Error('no target');
      const qs = new URLSearchParams({ [`${target.type}Id`]: target.id });
      const res = await fetch(`/api/graph/impact?${qs}`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) {
        let detail = `/api/graph/impact -> ${res.status}`;
        try {
          const body = (await res.json()) as { detail?: unknown };
          if (typeof body.detail === 'string') detail = body.detail;
        } catch {
          // keep the status line
        }
        throw new Error(detail);
      }
      return (await res.json()) as ImpactResult;
    },
  });
}
