/** Step 14: topology-service impact analysis (GET /api/graph/impact via the gateway). */
export type ImpactTargetType = 'link' | 'site' | 'node';

export interface ImpactTarget {
  type: ImpactTargetType;
  id: string;
}

export interface ImpactedSite {
  siteId: string;
  kind: string;
  /** failed = the site itself is down, node = one node down, isolated = no path to a core */
  reason: 'failed' | 'node' | 'isolated';
  cells: string[];
}

export interface ImpactResult {
  target: ImpactTarget;
  impactedSites: ImpactedSite[];
  cellsLost: number;
  sitesIsolated: number;
  backend: 'neo4j' | 'memory';
  elapsedMs: number;
}
