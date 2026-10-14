import { useMutation } from '@tanstack/react-query';
import type { AnalyzeResponse } from '../types.copilot';

export interface AnalyzeVars {
  siteId: string;
  window: string;
}

/** POST /api/copilot/analyze. A mutation, not a query: it is user-triggered and can be slow. */
export const useCopilotAnalyze = () =>
  useMutation<AnalyzeResponse, Error, AnalyzeVars>({
    mutationFn: async ({ siteId, window }) => {
      const resp = await fetch('/api/copilot/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ siteId, window }),
      });
      if (resp.status === 404) throw new Error('No alarms for this site in the window');
      if (!resp.ok) throw new Error('Copilot unavailable');
      return resp.json();
    },
  });
