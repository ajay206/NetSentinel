import { CardHeader } from "../components/ui/Card";
import { Tip, Tooltip } from "../components/ui/Tooltip";
import { TIPS } from "../lib/tooltips";
import type { PqcModel, PqcStatusResponse, PqcTls } from "../types.pqc";

const REPO = "https://github.com/ajay206/NetSentinel/blob/main/";

const ist = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

const MODEL: Record<PqcModel["status"], { cls: string; tip: string }> = {
  pass: { cls: "bg-emerald-900 text-emerald-200", tip: TIPS.chipModelPass },
  fail: { cls: "bg-red-900 text-red-200", tip: TIPS.chipModelFail },
  unsigned: { cls: "bg-amber-900 text-amber-200", tip: TIPS.chipModelUnsigned },
  off: {
    cls: "bg-bento-bg text-slate-600",
    tip: "Signature checking is switched off.",
  },
  unknown: { cls: "bg-bento-bg text-slate-600", tip: TIPS.chipModelUnknown },
};

function tlsLabel(t: PqcTls): { text: string; cls: string; tip: string } {
  if (!t.tls)
    return {
      text: "plaintext (compose network)",
      cls: "text-bento-muted",
      tip: TIPS.chipPlaintext,
    };
  if (t.hybridOnly)
    return {
      text: `hybrid only · ${t.group}`,
      cls: "text-emerald-700",
      tip: TIPS.chipHybrid,
    };
  if (t.hybrid)
    return {
      text: "hybrid · classical still accepted",
      cls: "text-amber-700",
      tip: TIPS.chipHybridMixed,
    };
  if (t.classical)
    return {
      text: "classical only · X25519",
      cls: "text-red-700",
      tip: TIPS.chipClassical,
    };
  return {
    text: "unreachable",
    cls: "text-red-700",
    tip: TIPS.chipUnreachable,
  };
}

function when(iso?: string): string {
  const d = iso ? new Date(iso) : null;
  return d && !Number.isNaN(d.getTime()) ? `${ist.format(d)} IST` : "—";
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
  const hybrid = tls.filter((t) => t.tls && t.hybridOnly).length;
  const m = MODEL[model.status] ?? MODEL.unknown;
  return (
    <section className="ns-card" data-testid="pqc-status">
      <CardHeader
        title="PQC status"
        subtitle="Post-quantum encryption per service and the AI model's signature check."
        info={TIPS.panelPqc}
        actions={
          data && (
            <span
              className="text-[11px] text-slate-600"
              data-testid="pqc-checked"
            >
              checked {when(data.checkedAt)}
            </span>
          )
        }
      />
      {error && <p className="text-sm text-red-400">{error.message}</p>}
      {isLoading && !data && <p className="text-sm text-bento-muted">Probing…</p>}
      {data && (
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg border border-bento-border bg-bento-bg p-2">
              <div className="text-bento-muted">
                <Tip tip="Is the AI model the ml-service serves exactly the one that was signed?">
                  Model signature
                </Tip>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <Tooltip
                  content={
                    <>
                      {m.tip}{" "}
                      {model.reason && (
                        <span className="block text-bento-muted">
                          {model.reason}
                        </span>
                      )}
                    </>
                  }
                >
                  <span
                    data-testid="pqc-model"
                    className={`rounded px-2 py-0.5 font-medium ${m.cls}`}
                  >
                    {model.status}
                    {model.alg ? ` · ${model.alg}` : ""}
                  </span>
                </Tooltip>
              </div>
              {model.modelVersion && (
                <div
                  className="mt-1 truncate font-mono text-[11px] text-slate-600"
                  title={model.modelVersion}
                >
                  {model.modelVersion} · {model.policy}
                </div>
              )}
            </div>
            <div className="rounded-lg border border-bento-border bg-bento-bg p-2">
              <div className="text-bento-muted">
                <Tip tip="How many services only accept post-quantum (hybrid) encryption. The rest are listed below.">
                  Hybrid TLS
                </Tip>
              </div>
              <div
                className="mt-1 text-lg font-semibold tabular-nums text-navy"
                data-testid="pqc-count"
              >
                {hybrid}{" "}
                <span className="text-xs font-normal text-bento-muted">
                  of {tls.length} services
                </span>
              </div>
            </div>
          </div>
          <div className="ns-table-wrap">
            <table className="w-full table-fixed text-xs">
              <thead className="ns-thead">
                <tr>
                  <th className="w-[45%] font-medium">
                    <Tip tip={TIPS.colService}>Service</Tip>
                  </th>
                  <th className="font-medium">
                    <Tip tip={TIPS.colTlsKx}>TLS key exchange</Tip>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tls.map((t) => {
                  const l = tlsLabel(t);
                  return (
                    <tr
                      key={t.service}
                      data-testid="pqc-row"
                      className="border-t border-bento-border"
                    >
                      <td className="truncate font-mono text-navy">
                        {t.service}
                      </td>
                      <td>
                        <Tooltip
                          content={
                            t.hybridDetail ? (
                              <>
                                {l.tip}{" "}
                                <span className="block text-bento-muted">
                                  {t.hybridDetail}
                                </span>
                              </>
                            ) : (
                              l.tip
                            )
                          }
                        >
                          <span className={l.cls}>{l.text}</span>
                        </Tooltip>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Tooltip content={TIPS.btnBenchmarks}>
            <a
              className="self-start text-[11px] text-sky-700 underline hover:text-sky-700"
              href={REPO + data.report}
              target="_blank"
              rel="noreferrer"
            >
              Benchmarks: {data.report}
            </a>
          </Tooltip>
        </div>
      )}
    </section>
  );
}
