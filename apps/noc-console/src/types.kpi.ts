export interface KpiCell {
  cellId: string;
  siteId: string | null;
  region: string | null;
  lastTs: string;
  sampleCount: number;
}

export interface KpiPoint {
  ts: string; // ISO string
  dlThroughputMbps: number | null;
  prbUtilPct: number | null;
  rrcSetupSuccessPct: number | null;
  dropCallRatePct: number | null;
  availabilityPct: number | null;
}

export interface KpiSeries {
  cellId: string;
  agg: string;
  from: string;
  to: string;
  points: KpiPoint[];
}

export type KpiName =
  | 'dlThroughputMbps'
  | 'prbUtilPct'
  | 'rrcSetupSuccessPct'
  | 'dropCallRatePct'
  | 'availabilityPct';

export const KPI_META: Record<
  KpiName,
  { label: string; unit: string }
> = {
  dlThroughputMbps: { label: 'DL Throughput', unit: 'Mbps' },
  prbUtilPct: { label: 'PRB Utilisation', unit: '%' },
  rrcSetupSuccessPct: { label: 'RRC Setup Success', unit: '%' },
  dropCallRatePct: { label: 'Drop Call Rate', unit: '%' },
  availabilityPct: { label: 'Availability', unit: '%' },
};
