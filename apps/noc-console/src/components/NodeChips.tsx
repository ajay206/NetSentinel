import React from 'react';

/** Step 15: node-ID citation chips (sites / links / cells) from Graph RAG. */
export const NodeChips: React.FC<{ ids?: string[]; label?: string }> = ({
  ids = [],
  label = 'Graph nodes',
}) =>
  ids.length === 0 ? null : (
    <div className="flex flex-wrap gap-1 mt-1" aria-label={label} data-testid="node-chips">
      {ids.map((id) => (
        <span
          key={id}
          data-testid="node-chip"
          title={`topology node ${id}`}
          className="font-mono text-[10px] px-1.5 py-0.5 rounded border bg-teal-950 border-teal-700 text-teal-200"
        >
          ◆ {id}
        </span>
      ))}
    </div>
  );

/** Step 15: "retrieval mode: graph" indicator. */
export const RetrievalModeBadge: React.FC<{ mode?: string | null }> = ({ mode }) =>
  mode ? (
    <span
      data-testid="retrieval-mode"
      className={`text-[11px] px-2 py-0.5 rounded ${
        mode === 'graph' ? 'bg-teal-900 text-teal-200' : 'bg-slate-800 text-slate-400'
      }`}
    >
      retrieval mode: {mode}
    </span>
  ) : null;
