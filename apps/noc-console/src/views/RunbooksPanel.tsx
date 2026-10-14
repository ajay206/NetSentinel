import React from 'react';
import type { RunbookDoc, RunbookHit } from '../types.runbook';
import { MarkdownPreview } from '../components/MarkdownPreview';

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
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-4" data-testid="runbooks-panel">
      <div className="flex items-baseline justify-between mb-3 gap-2">
        <h3 className="text-slate-200 font-semibold">Suggested runbooks</h3>
        <span className="text-xs text-slate-500 truncate">{alarmLabel ?? 'select an alarm'}</span>
      </div>
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
