import { TIPS } from './tooltips';
import type { RunStatus } from '../types.agents';

/** Run status pill: friendly label, colour and tooltip (shared by chat, trace and RCA graph). */
export const RUN_STATUS: Record<RunStatus, { label: string; cls: string; tip: string }> = {
  running: {
    label: 'Running',
    cls: 'bg-sky-900 text-sky-200',
    tip: TIPS.statusRunning,
  },
  awaiting_approval: {
    label: 'Awaiting approval',
    cls: 'bg-amber-900 text-amber-200',
    tip: TIPS.statusAwaiting,
  },
  completed: {
    label: 'Completed',
    cls: 'bg-emerald-900 text-emerald-200',
    tip: TIPS.statusCompleted,
  },
  rejected: {
    label: 'Rejected',
    cls: 'bg-red-900 text-red-200',
    tip: TIPS.statusRejected,
  },
  failed: {
    label: 'Failed',
    cls: 'bg-red-900 text-red-200',
    tip: TIPS.statusFailed,
  },
};

export const AGENT_LABEL: Record<string, string> = {
  supervisor: 'Supervisor',
  triage: 'Triage',
  rca: 'RCA',
  remediation: 'Remediation',
  approval: 'Approval',
  report: 'Report',
  human: 'Operator',
};
