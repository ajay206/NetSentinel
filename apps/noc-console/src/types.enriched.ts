import type { Alarm } from './types';

export interface Enrichment {
  siteName: string | null;
  region: string;
  siteKind: string | null;
  nodeTypes: string[];
  parentSiteId: string | null;
  known: boolean;
}

export interface DedupInfo {
  key: string;
  count: number;
  firstSeen: string;
  isDuplicate: boolean;
}

export interface Correlation {
  groupId: string | null;
  rootSiteId: string | null;
  role: 'root' | 'symptom' | 'none';
}

export interface EnrichedAlarm extends Alarm {
  ingestedAt: string;
  enrichment: Enrichment;
  dedup: DedupInfo;
  correlation: Correlation;
}

export type EnrichedWsMessage =
  | { type: 'snapshot'; alarms: EnrichedAlarm[] }
  | { type: 'enriched'; alarm: EnrichedAlarm };
