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
