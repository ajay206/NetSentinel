export interface Incident {
  id: string;
  rootSiteId: string;
  siteIds: string[];
  alarmIds: string[];
  alarmKeys: string[];
  alarmCount: number;
  severity: 'critical' | 'major' | 'minor' | 'warning' | 'indeterminate' | 'cleared';
  region: string | null;
  firstSeen: string;
  lastSeen: string;
  status: 'open' | 'cleared';
  version: number;
  /** Step 13b: operator workflow overlay (null until someone acts on it). */
  workflow?: import('./hooks/useWorkflow').Workflow | null;
}

export interface IncidentList {
  items: Incident[];
  total: number;
  stats: {
    alarms: number;
    incidents: number;
    compressionRatio: number;
  };
}
