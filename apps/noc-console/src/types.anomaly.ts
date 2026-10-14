export interface AnomalyItem {
  cellId: string;
  region: string;
  ts: string; // ISO timestamp
  value: number;
  score: number;
  method: 'zscore' | 'cusum' | 'both';
  direction: 'high' | 'low';
}

export interface AnomalyList {
  kpi: string;
  hours: number;
  items: AnomalyItem[];
}

export interface CellAnomalyPoint {
  ts: string;
  value: number;
  score: number;
  method: 'zscore' | 'cusum' | 'both';
  direction: 'high' | 'low';
}

export interface CellAnomalies {
  cellId: string;
  kpi: string;
  from: string;
  to: string;
  threshold: number;
  points: number;
  anomalies: CellAnomalyPoint[];
}
