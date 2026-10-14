/** W12: map live dashboard state to the five Phase 1 demo stages. */
export interface DemoStage {
  id: 'alarms' | 'anomaly' | 'fault' | 'runbooks' | 'copilot';
  label: string;
  done: boolean;
  detail?: string;
}

export interface DemoStagesInput {
  alarmCount: number;
  anomalyCount: number;
  faultType?: string | null;
  runbookCount: number;
  copilotSources: number;
  copilotCited: boolean;
}

export function demoStages(input: DemoStagesInput): DemoStage[] {
  const { alarmCount, anomalyCount, faultType, runbookCount, copilotSources, copilotCited } = input;

  const stages: DemoStage[] = [
    {
      id: 'alarms',
      label: 'Alarms stream',
      done: alarmCount > 0,
      detail: `${alarmCount} alarm${alarmCount === 1 ? '' : 's'}`,
    },
    {
      id: 'anomaly',
      label: 'KPI anomaly',
      done: anomalyCount > 0,
      detail: `${anomalyCount} ${anomalyCount === 1 ? 'anomaly' : 'anomalies'}`,
    },
    {
      id: 'fault',
      label: 'Fault badge',
      done: Boolean(faultType),
      detail: faultType ?? undefined,
    },
    {
      id: 'runbooks',
      label: 'Runbooks',
      done: runbookCount > 0,
      detail: `${runbookCount} runbook${runbookCount === 1 ? '' : 's'}`,
    },
    {
      id: 'copilot',
      label: 'Copilot answer',
      done: copilotSources > 0 && copilotCited,
      detail:
        copilotSources > 0
          ? `${copilotSources} source${copilotSources === 1 ? '' : 's'}${
              copilotCited ? ', cited' : ''
            }`
          : undefined,
    },
  ];

  return stages;
}
