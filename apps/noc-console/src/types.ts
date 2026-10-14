export type PerceivedSeverity =
  | 'critical'
  | 'major'
  | 'minor'
  | 'warning'
  | 'cleared';

export interface AlarmedObject {
  id: string;
}

export interface Alarm {
  id: string;
  href?: string;
  alarmType: string;
  perceivedSeverity: PerceivedSeverity;
  probableCause: string;
  specificProblem: string;
  siteId: string;
  alarmRaisedTime: string;
  state: string;
  sourceSystemId: string;
  alarmedObject: AlarmedObject;
}

export interface ServiceStatus {
  name: string;
  status: 'up' | 'down';
  detail?: string;
}

export interface HealthResponse {
  status: 'ok' | 'degraded';
  services: ServiceStatus[];
  checkedAt: string;
}

export type WsMessage =
  | { type: 'snapshot'; alarms: Alarm[] }
  | { type: 'alarm'; alarm: Alarm };

//
// Topology types (GET /api/topology)
//
export interface TopoNode {
  nodeId: string;
  kind: string;
  cells: string[];
}

export interface TopoSite {
  siteId: string;
  name: string;
  region: string;
  kind: 'core' | 'hub' | 'access';
  lat: number;
  lon: number;
  nodes: TopoNode[];
}

export interface TopoLink {
  linkId: string;
  a: string; // siteId of endpoint A
  b: string; // siteId of endpoint B
  kind: 'fibre' | 'microwave';
  role: 'core' | 'ring' | 'access';
}

export interface TopologyCounts {
  regions: number;
  sites: number;
  nodes: number;
  cells: number;
  links: number;
}

export interface Topology {
  seed: number;
  small: boolean;
  regions: string[];
  sites: TopoSite[];
  links: TopoLink[];
  counts: TopologyCounts;
}

//
// KPI Activity types (GET /api/kpis/activity & WS /ws/kpis)
//
export interface KpiSample {
  sampleId: string;
  siteId: string;
  nodeId: string;
  cellId: string;
  region: string;
  timestamp: string;
  granularitySec: number;
  kpis: Record<string, number>;
}

export interface KpiActivity {
  totalSamples: number;
  ratePerMin: number;
  lastSampleTime: string | null;
  lastSample: KpiSample | null;
  averages: Record<string, number>;
  cellsReporting: number;
}

/** /ws/kpis sends the activity snapshot flat: {type: 'kpiActivity', totalSamples, ...}. */
export type KpiWsMessage = { type: 'kpiActivity' } & KpiActivity;
