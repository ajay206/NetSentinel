import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CopilotChat } from './CopilotChat';
import { TraceView } from './TraceView';
import type { AgentRun } from '../types.agents';

const waiting: AgentRun = {
  runId: 'RUN-00000000AA',
  incidentId: 'INC-0123456789',
  siteId: 'SITE-010',
  status: 'awaiting_approval',
  createdAt: '2026-10-15T08:00:00Z',
  updatedAt: '2026-10-15T08:00:01Z',
  agentPath: ['supervisor', 'triage', 'rca', 'remediation'],
  messages: [
    {
      agent: 'triage',
      text: 'Root alarm LOS at SITE-010',
      ts: '',
      sources: ['alm-root-0001'],
    },
    { agent: 'rca', text: 'Fibre cut on LNK-012', ts: '' },
  ],
  plan: {
    summary: '1 step(s) for fibre cut at SITE-010',
    steps: [
      {
        text: 'Dispatch splicing team',
        runbookId: 'RB-FIB-001',
        section: 'Remediation',
      },
    ],
    ticketDraft: {
      title: 'Fibre cut at SITE-010',
      severity: 'critical',
      description: 'x',
    },
  },
  ticketId: null,
  kgWriteBack: null,
  trace: [
    {
      seq: 1,
      agent: 'triage',
      name: 'gather evidence',
      startedAt: '',
      durationMs: 40,
      ok: true,
      toolCalls: [{ name: 'get_alarms', ok: true, durationMs: 12, transport: 'mcp' }],
      detail: '3 alarms',
    },
    {
      seq: 2,
      agent: 'rca',
      name: 'root-cause analysis',
      startedAt: '',
      durationMs: 900,
      ok: true,
      toolCalls: [{ name: 'query_topology', ok: false, durationMs: 5, transport: 'http' }],
      detail: 'llm',
    },
    {
      seq: 3,
      agent: 'remediation',
      name: 'plan remediation',
      startedAt: '',
      durationMs: 1,
      ok: true,
      toolCalls: [],
      detail: '',
    },
  ],
  report: null,
  tracing: { langfuse: false },
};
const done: AgentRun = {
  ...waiting,
  status: 'completed',
  agentPath: [...waiting.agentPath, 'approval', 'report'],
  ticketId: 'TKT-00000000AA',
  kgWriteBack: {
    ok: true,
    detail: '(:RcaFinding)-[:ROOT_CAUSE]->(:Site SITE-010)',
  },
  report: '# Copilot run RUN-00000000AA',
};

function chat(over: Partial<React.ComponentProps<typeof CopilotChat>> = {}) {
  const props = {
    incidentId: 'INC-0123456789',
    run: waiting,
    runs: [waiting],
    canOperate: true,
    onStart: vi.fn(),
    onSelectRun: vi.fn(),
    onDecide: vi.fn(),
    ...over,
  };
  render(<CopilotChat {...props} />);
  return props;
}

describe('CopilotChat (W17)', () => {
  it('starts a run on the selected incident and shows the chat', () => {
    const p = chat();
    fireEvent.click(screen.getByRole('button', { name: /Run agents on INC-0123456789/ }));
    expect(p.onStart).toHaveBeenCalledWith({ incidentId: 'INC-0123456789' });
    expect(screen.getByTestId('chat-log')).toHaveTextContent('Fibre cut on LNK-012');
    expect(screen.getByTestId('run-status')).toHaveTextContent('Awaiting approval');
  });

  it('human approval node: approve, and reject needs a note', () => {
    const p = chat();
    expect(screen.getByTestId('approval-box')).toHaveTextContent('RB-FIB-001');
    expect(screen.getByRole('button', { name: 'Reject plan' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Approval note'), {
      target: { value: ' go ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Approve plan' }));
    expect(p.onDecide).toHaveBeenCalledWith(true, 'go');
  });

  it('viewer is read-only; completed run shows ticket, KG and report', () => {
    chat({ canOperate: false, run: done, runs: [done] });
    expect(screen.getByRole('note')).toHaveTextContent('operator role');
    expect(screen.queryByTestId('approval-box')).toBeNull();
    expect(screen.getByTestId('run-ticket')).toHaveTextContent('TKT-00000000AA');
    expect(screen.getByTestId('run-report')).toHaveTextContent('Copilot run');
  });
});

describe('TraceView (W17)', () => {
  it('shows the agent path, one row per step and tool calls', () => {
    render(<TraceView run={done} />);
    expect(screen.getAllByTestId('agent-pill').map((p) => p.textContent)).toEqual([
      'supervisor',
      'triage',
      'rca',
      'remediation',
      'approval',
      'report',
    ]);
    expect(screen.getAllByTestId('trace-step')).toHaveLength(3);
    expect(screen.getAllByTestId('trace-tool').map((t) => t.textContent)).toEqual([
      'get_alarms · 12 ms',
      'query_topology · 5 ms',
    ]);
    expect(screen.getByTestId('trace-view')).toHaveTextContent('3 steps · 941 ms');
  });

  it('placeholder without a run', () => {
    render(<TraceView run={null} />);
    expect(screen.getByText('Start a run to see the agent trace.')).toBeInTheDocument();
  });
});
