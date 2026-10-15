import type { PqcModel, PqcStatusResponse, PqcTls } from "../types.pqc";

const REPO = "https://github.com/ajay206/NetSentinel/blob/main/";

const modelStyle: Record<PqcModel["status"], string> = {
  pass: "bg-emerald-900 text-emerald-200",
  fail: "bg-red-900 text-red-200",
  unsigned: "bg-amber-900 text-amber-200",
  off: "bg-slate-700 text-slate-300",
  unknown: "bg-slate-700 text-slate-300",
};

function tlsLabel(t: PqcTls): { text: string; cls: string } {
  if (!t.tls)
    return { text: "plaintext (compose network)", cls: "text-slate-500" };
  if (t.hybridOnly)
    return { text: `hybrid only · ${t.group}`, cls: "text-emerald-300" };
  if (t.hybrid)
    return { text: `hybrid · classical still accepted`, cls: "text-amber-300" };
  if (t.classical)
    return { text: "classical only · X25519", cls: "text-red-300" };
  return { text: "unreachable", cls: "text-red-300" };
}

/** Step 21: post-quantum status. Values come from real handshakes and the last verify. */
export function PqcStatus({
  data,
  error,
  isLoading,
}: {
  data?: PqcStatusResponse;
  error?: Error | null;
  isLoading?: boolean;
}) {
  const model: PqcModel = data?.model ?? {
    status: "unknown",
    reason: "no data",
  };
  const tls = data?.tls ?? [];
  return (
    <section className="ns-card space-y-3" data-testid="pqc-status">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">PQC status</h3>
        {data && (
          <span className="text-[11px] text-slate-500">
            checked {data.checkedAt}
          </span>
        )}
      </div>
      {error && <p className="text-sm text-red-400">{error.message}</p>}
      {isLoading && !data && <p className="text-sm text-slate-400">Probing…</p>}
      {data && (
        <>
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="text-slate-400">Model signature</span>
            <span
              data-testid="pqc-model"
              className={`rounded px-2 py-0.5 ${modelStyle[model.status] ?? modelStyle.unknown}`}
              title={model.reason}
            >
              {model.status}
              {model.alg ? ` · ${model.alg}` : ""}
            </span>
            {model.modelVersion && (
              <span className="text-slate-500">
                {model.modelVersion} · {model.policy}
              </span>
            )}
          </div>
          <table className="w-full text-[12px]">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="font-normal">Service</th>
                <th className="font-normal">TLS key exchange</th>
              </tr>
            </thead>
            <tbody>
              {tls.map((t) => {
                const l = tlsLabel(t);
                return (
                  <tr key={t.service} data-testid="pqc-row">
                    <td className="py-0.5 text-slate-300">{t.service}</td>
                    <td className={`py-0.5 ${l.cls}`} title={t.hybridDetail}>
                      {l.text}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <a
            className="text-[11px] text-sky-400 underline"
            href={REPO + data.report}
            target="_blank"
            rel="noreferrer"
          >
            Benchmarks: {data.report}
          </a>
        </>
      )}
    </section>
  );
}
