import React, { useMemo, useState } from 'react';
import { TIPS } from '../../lib/tooltips';
import { Tip, Tooltip } from '../../components/ui/Tooltip';
import { Card, StateMessage } from '../../components/ui/Card';
import { useAuditLog } from '../../hooks/useAdmin';

const fmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Kolkata',
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

/** Step 13b (admin): newest-first audit trail of security and workflow actions. */
export const AuditLog: React.FC = () => {
  const log = useAuditLog();
  const [q, setQ] = useState('');
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (log.data ?? []).filter(
      (e) => !needle || [e.actor, e.action, e.target].some((v) => v.toLowerCase().includes(needle)),
    );
  }, [log.data, q]);

  let body: React.ReactNode;
  if (log.isLoading) body = <StateMessage kind="loading">Loading audit log…</StateMessage>;
  else if (log.isError)
    body = <StateMessage kind="error">Audit log unavailable: {log.error.message}</StateMessage>;
  else if (!rows.length) body = <StateMessage kind="empty">No matching entries.</StateMessage>;
  else
    body = (
      <div className="ns-table-wrap">
        <table className="w-max min-w-full text-sm" data-testid="audit-table">
          <thead className="ns-thead">
            <tr className="text-left">
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colTime}>Time (IST)</Tip>
              </th>
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colActor}>Actor</Tip>
              </th>
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colAction}>Action</Tip>
              </th>
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colTarget}>Target</Tip>
              </th>
              <th className="px-2 py-1.5">
                <Tip tip={TIPS.colDetails}>Details</Tip>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className="border-t border-bento-border">
                <td className="whitespace-nowrap px-2 py-1.5 font-mono text-xs text-bento-muted">
                  {fmt.format(new Date(e.ts * 1000))}
                </td>
                <td className="px-2 py-1.5 text-navy">{e.actor}</td>
                <td className="px-2 py-1.5">
                  <span className="rounded bg-bento-bg px-1.5 py-0.5 font-mono text-xs text-sky-700">
                    {e.action}
                  </span>
                </td>
                <td className="max-w-[16rem] px-2 py-1.5 font-mono text-xs">
                  <Tooltip content={e.target}>
                    <span className="block truncate">{e.target}</span>
                  </Tooltip>
                </td>
                <td className="px-2 py-1.5 text-xs text-bento-muted">
                  {Object.entries(e.detail ?? {})
                    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
                    .join(' · ') || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );

  return (
    <Card
      title="Audit log"
      subtitle="Who changed what: roles, passwords, resets and incident actions."
      info={TIPS.panelAuditLog}
      testId="audit-log"
      actions={
        <input
          aria-label="Filter audit log"
          placeholder="Filter…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="w-40 rounded border border-bento-border bg-bento-bg px-2 py-0.5 text-xs text-navy"
        />
      }
    >
      {body}
    </Card>
  );
};
