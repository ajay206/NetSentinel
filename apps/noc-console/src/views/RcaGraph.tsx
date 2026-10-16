import React, { useEffect, useMemo, useState } from 'react';
import { Tip, Tooltip } from '../components/ui/Tooltip';
import { TIPS } from '../lib/tooltips';
import { Card, StateMessage } from '../components/ui/Card';
import { useImpact } from '../hooks/useImpact';
import type { Topology } from '../types';
import type { AgentRun } from '../types.agents';
import type { ImpactResult, ImpactTarget, ImpactTargetType, ImpactedSite } from '../types.graph';

type Props = {
  topology?: Topology;
  /** Called with the current answer (or null) so NetworkMap can highlight the impact radius. */
  onImpact?: (target: ImpactTarget | null, result: ImpactResult | null) => void;
  /** Step 17: the selected multi-agent run; shows its agent path and its root site. */
  agentRun?: Pick<AgentRun, 'runId' | 'siteId' | 'agentPath' | 'status'> | null;
};

const REASON: Record<ImpactedSite['reason'], string> = {
  failed: 'Site down',
  node: 'Node down',
  isolated: 'Isolated from core',
};

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

/** Step 14: impact / RCA panel. Pick a link, site or node; see which cells lose service. */
export const RcaGraph: React.FC<Props> = ({ topology, onImpact, agentRun = null }) => {
  const [type, setType] = useState<ImpactTargetType>('link');
  const [id, setId] = useState('');
  const target = useMemo<ImpactTarget | null>(() => (id ? { type, id } : null), [type, id]);
  const { data, error, isFetching } = useImpact(target);
  const result = target && data && data.target.id === target.id ? data : null;

  useEffect(() => {
    onImpact?.(target, result);
  }, [target, result, onImpact]);

  const options = useMemo(() => {
    if (!topology) return [];
    if (type === 'link')
      return (topology.links ?? []).map((l) => ({
        value: l.linkId,
        label: `${l.linkId} · ${l.a} ↔ ${l.b} (${l.role})`,
      }));
    if (type === 'site')
      return (topology.sites ?? []).map((s) => ({
        value: s.siteId,
        label: `${s.siteId} · ${s.name} (${s.kind})`,
      }));
    return (topology.sites ?? []).flatMap((s) =>
      (s.nodes ?? []).map((n) => ({
        value: n.nodeId,
        label: `${n.nodeId} (${n.kind})`,
      })),
    );
  }, [topology, type]);

  return (
    <Card
      title="Impact / RCA graph"
      subtitle="Pick a link, site or node to see which cells lose service."
      info={TIPS.panelRca}
      testId="rca-graph"
    >
      {agentRun && agentRun.agentPath.length > 0 && (
        <div
          className="mb-3 flex flex-wrap items-center gap-1 rounded bg-bento-bg p-2 text-xs"
          data-testid="rca-agent-path"
        >
          <span className="text-bento-muted">
            Agents ({agentRun.runId}, {agentRun.status.replace('_', ' ')}):
          </span>
          {agentRun.agentPath.map((a, i) => (
            <span key={`${a}-${i}`} className="text-navy">
              {i > 0 && <span className="mx-1 text-slate-500">→</span>}
              {a}
            </span>
          ))}
          <Tooltip content={TIPS.btnImpact}>
            <button
              type="button"
              className="ml-auto font-mono text-sky-700 hover:underline"
              onClick={() => {
                setType('site');
                setId(agentRun.siteId);
              }}
            >
              impact of {agentRun.siteId}
            </button>
          </Tooltip>
        </div>
      )}
      <div className="ns-controls mb-4">
        <select
          aria-label="Failure type"
          value={type}
          onChange={(e) => {
            setType(e.target.value as ImpactTargetType);
            setId('');
          }}
          className="ns-control w-full sm:w-28"
        >
          <option value="link">Link</option>
          <option value="site">Site</option>
          <option value="node">Node</option>
        </select>
        <select
          aria-label="Failed element"
          value={id}
          onChange={(e) => setId(e.target.value)}
          disabled={options.length === 0}
          className="ns-control w-full min-w-0 sm:w-auto sm:flex-1"
        >
          <option value="">— select —</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <Tooltip content="Clear the selection and the highlight on the network map.">
          <button
            type="button"
            onClick={() => setId('')}
            disabled={!id}
            className="rounded px-2 py-1 text-xs font-medium text-sky-700 hover:text-sky-200 disabled:opacity-40"
          >
            Clear
          </button>
        </Tooltip>
      </div>

      {!topology && <StateMessage kind="loading">Loading topology…</StateMessage>}
      {topology && !target && (
        <StateMessage kind="empty">Choose an element to simulate its failure.</StateMessage>
      )}
      {target && isFetching && !result && (
        <StateMessage kind="loading">Querying the graph…</StateMessage>
      )}
      {target && error && <StateMessage kind="error">{error.message}</StateMessage>}

      {result && (
        <>
          <p
            className="mb-2 flex flex-wrap items-center gap-2 text-sm"
            data-testid="impact-summary"
          >
            <span>
              <strong>{result.target.id}</strong> fails → {plural(result.sitesIsolated, 'site')}{' '}
              isolated, {plural(result.cellsLost, 'cell')} lose service
            </span>
            <Tooltip content="Where the answer came from (Neo4j graph or in-memory copy) and how long the query took.">
              <span
                className="rounded bg-bento-bg px-2 py-0.5 text-xs text-slate-600"
                data-testid="impact-latency"
              >
                {result.backend} · {result.elapsedMs.toFixed(1)} ms
              </span>
            </Tooltip>
          </p>
          {result.impactedSites.length === 0 ? (
            <StateMessage kind="empty">
              No cells lose service: there is a redundant path.
            </StateMessage>
          ) : (
            <div className="ns-table-wrap">
              <table className="w-full text-left text-sm" data-testid="impact-table">
                <thead className="ns-thead">
                  <tr>
                    <th className="font-medium">
                      <Tip tip={TIPS.colSite}>Site</Tip>
                    </th>
                    <th className="font-medium">
                      <Tip tip="Core, hub or access site.">Kind</Tip>
                    </th>
                    <th className="font-medium">
                      <Tip tip="Why the site loses service: it failed itself, or every path to the core is cut.">
                        Why
                      </Tip>
                    </th>
                    <th className="font-medium">
                      <Tip tip="How many radio cells at this site go down, and their ids.">
                        Cells lost
                      </Tip>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {result.impactedSites.map((s) => (
                    <tr key={s.siteId} className="border-t border-bento-border">
                      <td className="font-mono">{s.siteId}</td>
                      <td>{s.kind}</td>
                      <td>{REASON[s.reason]}</td>
                      <td
                        className="max-w-[14rem] truncate font-mono text-xs"
                        title={s.cells.join(', ')}
                      >
                        {s.cells.length}: {s.cells.join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Card>
  );
};

export default RcaGraph;
