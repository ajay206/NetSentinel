import React from 'react';
import { CardHeader } from '../components/ui/Card';
import type { RunbookDoc, RunbookHit } from '../types.runbook';
import { MarkdownPreview } from '../components/MarkdownPreview';
import { NodeChips, RetrievalModeBadge } from '../components/NodeChips';

interface RunbooksPanelProps {
  alarmLabel?: string | null;
  hits?: RunbookHit[];
  isLoading?: boolean;
  isError?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  doc?: RunbookDoc;
  docLoading?: boolean;
  onClosePreview?: () => void;
  /** Step 15: retrieval mode reported by rag-service ("graph" = Graph RAG). */
  mode?: string | null;
}

/** W8: top-3 runbooks for the selected alarm (hybrid BM25 + vector search in rag-service). */
export const RunbooksPanel: React.FC<RunbooksPanelProps> = ({
  alarmLabel,
  hits = [],
  isLoading = false,
  isError = false,
  selectedId = null,
  onSelect,
  doc,
  docLoading = false,
  onClosePreview,
  mode = null,
}) => {
  let body: React.ReactNode;
  if (!alarmLabel) {
    body = <p className="text-slate-400 text-sm">Click an enriched alarm to see runbooks.</p>;
  } else if (isLoading) {
    body = <p className="text-slate-400 text-sm">Searching runbooks…</p>;
  } else if (isError) {
    body = <p className="text-red-400 text-sm">rag-service unavailable</p>;
  } else if (hits.length === 0) {
    body = <p className="text-slate-400 text-sm">No matching runbooks</p>;
  } else {
    body = (
      <ol className="space-y-2">
        {hits.slice(0, 3).map((hit) => {
          const selected = selectedId === hit.runbookId;
          return (
            <li key={hit.runbookId}>
              <button
                type="button"
                data-testid="runbook-hit"
                onClick={() => onSelect?.(hit.runbookId)}
                aria-pressed={selected}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selected
                    ? 'bg-slate-700 border-sky-500'
                    : 'bg-slate-800 border-slate-700 hover:bg-slate-700/60'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-slate-100 truncate">{hit.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      <span className="font-mono">{hit.runbookId}</span> · {hit.section}
                    </div>
                    <div className="text-sm text-slate-400 line-clamp-2 mt-1">{hit.snippet}</div>
                    <NodeChips ids={hit.nodeIds} />
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span className="text-xs font-mono text-slate-300 bg-slate-700 px-2 py-0.5 rounded">
                      {hit.score.toFixed(3)}
                    </span>
                    <span className="text-xs text-slate-400 bg-slate-700 px-2 py-0.5 rounded">
                      {hit.faultType.replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>
              </button>
            </li>
          );
        })}
      </ol>
    );
  }

  return (
    <div className="ns-card" data-testid="runbooks-panel">
      <CardHeader
        as="h3"
        title="Suggested runbooks"
        subtitle="Repair procedures that match the selected alarm."
        info="Graph RAG: hybrid keyword + vector search, expanded with the alarm's topology neighbourhood (site, links, parent hub) and reranked. Chips show the graph nodes behind each hit."
        actions={
          <span className="flex items-center gap-2">
            {alarmLabel && hits.length > 0 && <RetrievalModeBadge mode={mode} />}
            <span className="text-xs text-slate-500 truncate max-w-[12rem]">
              {alarmLabel ?? 'select an alarm'}
            </span>
          </span>
        }
      />
      {body}
      {alarmLabel && selectedId && (
        <div className="border-t border-slate-700 mt-4 pt-3">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-slate-100 font-medium">{doc?.title ?? selectedId}</h4>
            <button
              type="button"
              onClick={onClosePreview}
              aria-label="Close preview"
              className="text-slate-400 hover:text-slate-200 px-2"
            >
              ×
            </button>
          </div>
          {docLoading || !doc ? (
            <p className="text-slate-400 text-sm">Loading runbook…</p>
          ) : (
            <div className="max-h-80 overflow-y-auto">
              <MarkdownPreview markdown={doc.markdown} />
            </div>
          )}
        </div>
      )}
    </div>
  );
};
