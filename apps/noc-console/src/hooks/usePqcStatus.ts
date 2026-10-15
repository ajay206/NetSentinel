import { useQuery } from "@tanstack/react-query";
import type { PqcStatusResponse } from "../types.pqc";

/** Step 21: hybrid TLS per service + last model-signature verify (viewer). */
export function usePqcStatus() {
  return useQuery<PqcStatusResponse, Error>({
    queryKey: ["pqc-status"],
    queryFn: async () => {
      const resp = await fetch("/api/security/pqc");
      if (!resp.ok) throw new Error(`pqc status ${resp.status}`);
      return (await resp.json()) as PqcStatusResponse;
    },
    refetchInterval: 60_000,
  });
}
