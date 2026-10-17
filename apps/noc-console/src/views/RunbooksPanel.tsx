import React from 'react';
import { TIPS } from '../lib/tooltips';
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
  /** Use denser result rows when the panel is part of a multi-section workspace. */
  compact?: boolean;
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
  compact = false,
}) => {
  let body: React.ReactNode;
  if (!alarmLabel) {
    body = <p className="text-bento-muted text-sm">Click an enriched alarm to see runbooks.</p>;
  } else if (isLoading) {
    body = <p className="text-bento-muted text-sm">Searching runbooks…</p>;
  } else if (isError) {
    body = <p className="text-red-400 text-sm">rag-service unavailable</p>;
  } else if (hits.length === 0) {
    body = <p className="text-bento-muted text-sm">No matching runbooks</p>;
  } else {
    body = (
      <ol className={compact ? 'space-y-1.5' : 'space-y-2'}>
        {hits.slice(0, 3).map((hit) => {
          const selected = selectedId === hit.runbookId;
          return (
            <li key={hit.runbookId}>
              <button
                type="button"
                data-testid="runbook-hit"
                onClick={() => onSelect?.(hit.runbookId)}
                aria-pressed={selected}
                className={`w-full text-left ${compact ? 'p-2' : 'p-3'} rounded-lg border transition-colors ${
                  selected
                    ? 'bg-slate-200 border-sky-500'
                    : 'bg-bento-bg border-bento-border hover:bg-slate-200'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-navy truncate">{hit.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      <span className="font-mono">{hit.runbookId}</span> · {hit.section}
                    </div>
                    <div className={`text-sm text-bento-muted ${compact ? 'line-clamp-1 mt-0.5' : 'line-clamp-2 mt-1'}`}>{hit.snippet}</div>
                    {!compact && <NodeChips ids={hit.nodeIds} />}
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span className="text-xs font-mono text-slate-600 bg-slate-200 px-2 py-0.5 rounded">
                      {hit.score.toFixed(3)}
                    </span>
                    <span className="text-xs text-bento-muted bg-slate-200 px-2 py-0.5 rounded">
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
    <div className={`ns-card ${compact ? 'p-3 sm:p-4 lg:p-4' : ''}`} data-testid="runbooks-panel">
      <CardHeader
        as="h3"
        title="Suggested runbooks"
        subtitle={compact ? undefined : 'Repair procedures that match the selected alarm.'}
        info={TIPS.panelRunbooks}
        actions={
          <span className="flex min-w-0 flex-wrap items-center gap-2">
            {alarmLabel && hits.length > 0 && <RetrievalModeBadge mode={mode} />}
            <span className="max-w-[16rem] truncate text-xs text-slate-500" title={alarmLabel ?? undefined}>
              {alarmLabel ?? 'select an alarm'}
            </span>
          </span>
        }
      />
      {body}
      {alarmLabel && selectedId && (
        <div className="border-t border-bento-border mt-4 pt-3">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-navy font-medium">{doc?.title ?? selectedId}</h4>
            <button
              type="button"
              onClick={onClosePreview}
              aria-label="Close preview"
              className="text-bento-muted hover:text-navy px-2"
            >
              ×
            </button>
          </div>
          {docLoading || !doc ? (
            <p className="text-bento-muted text-sm">Loading runbook…</p>
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
