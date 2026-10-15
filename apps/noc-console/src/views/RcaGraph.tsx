import React, { useEffect, useMemo, useState } from 'react';
import { Card, StateMessage } from '../components/ui/Card';
import { useImpact } from '../hooks/useImpact';
import type { Topology } from '../types';
import type { ImpactResult, ImpactTarget, ImpactTargetType, ImpactedSite } from '../types.graph';

type Props = {
  topology?: Topology;
  /** Called with the current answer (or null) so NetworkMap can highlight the impact radius. */
  onImpact?: (target: ImpactTarget | null, result: ImpactResult | null) => void;
};

const REASON: Record<ImpactedSite['reason'], string> = {
  failed: 'Site down',
  node: 'Node down',
  isolated: 'Isolated from core',
};

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

/** Step 14: impact / RCA panel. Pick a link, site or node; see which cells lose service. */
export const RcaGraph: React.FC<Props> = ({ topology, onImpact }) => {
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
      (s.nodes ?? []).map((n) => ({ value: n.nodeId, label: `${n.nodeId} (${n.kind})` })),
    );
  }, [topology, type]);

  return (
    <Card
      title="Impact / RCA graph"
      subtitle="Pick a link, site or node to see which cells lose service."
      info="Answered by topology-service with Cypher on the Neo4j knowledge graph (Step 14). Impacted sites are highlighted on the network map."
      testId="rca-graph"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select
          aria-label="Failure type"
          value={type}
          onChange={(e) => {
            setType(e.target.value as ImpactTargetType);
            setId('');
          }}
          className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-slate-200"
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
          className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-slate-200 min-w-0 flex-1"
        >
          <option value="">— select —</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setId('')}
          disabled={!id}
          className="rounded px-2 py-1 text-xs font-medium text-sky-300 hover:text-sky-200 disabled:opacity-40"
        >
          Clear
        </button>
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
            <span
              className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300"
              data-testid="impact-latency"
            >
              {result.backend} · {result.elapsedMs.toFixed(1)} ms
            </span>
          </p>
          {result.impactedSites.length === 0 ? (
            <StateMessage kind="empty">
              No cells lose service: there is a redundant path.
            </StateMessage>
          ) : (
            <div className="min-h-0 overflow-auto">
              <table className="w-full text-left text-sm" data-testid="impact-table">
                <thead className="text-xs uppercase text-slate-400">
                  <tr>
                    <th className="py-1 pr-2">Site</th>
                    <th className="py-1 pr-2">Kind</th>
                    <th className="py-1 pr-2">Why</th>
                    <th className="py-1">Cells lost</th>
                  </tr>
                </thead>
                <tbody>
                  {result.impactedSites.map((s) => (
                    <tr key={s.siteId} className="border-t border-slate-800">
                      <td className="py-1 pr-2 font-mono">{s.siteId}</td>
                      <td className="py-1 pr-2">{s.kind}</td>
                      <td className="py-1 pr-2">{REASON[s.reason]}</td>
                      <td className="py-1 font-mono text-xs" title={s.cells.join(', ')}>
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
