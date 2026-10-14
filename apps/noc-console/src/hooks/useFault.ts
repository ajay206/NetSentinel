import { useQuery } from '@tanstack/react-query';
import type { EnrichedAlarm } from '../types.enriched';
import type { FaultPrediction, FaultExplanation } from '../types.fault';

const fetchPrediction = async (alarm: EnrichedAlarm): Promise<FaultPrediction> => {
  const resp = await fetch('/api/ml/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alarm }),
  });
  if (!resp.ok) throw new Error('Failed to fetch prediction');
  return resp.json();
};

const fetchExplanation = async (alarm: EnrichedAlarm): Promise<FaultExplanation> => {
  const resp = await fetch('/api/ml/explain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alarm }),
  });
  if (!resp.ok) throw new Error('Failed to fetch explanation');
  return resp.json();
};

export const useFaultPrediction = (alarm: EnrichedAlarm | null) => {
  return useQuery<FaultPrediction, Error>({
    queryKey: ['fault-prediction', alarm?.id ?? 'none', alarm?.dedup.count ?? 0],
    queryFn: () => {
      if (!alarm) throw new Error('No alarm');
      return fetchPrediction(alarm);
    },
    enabled: alarm !== null,
    retry: 1,
    staleTime: 60_000,
  });
};

export const useFaultExplanation = (alarm: EnrichedAlarm | null) => {
  return useQuery<FaultExplanation, Error>({
    queryKey: ['fault-explanation', alarm?.id ?? 'none', alarm?.dedup.count ?? 0],
    queryFn: () => {
      if (!alarm) throw new Error('No alarm');
      return fetchExplanation(alarm);
    },
    enabled: alarm !== null,
    retry: 1,
    staleTime: 60_000,
  });
};
