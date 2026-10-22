import type { Page } from '@playwright/test';

/** Rich synthetic data so every list, table and dropdown is full enough to show spill or cramping. */
const now = Date.now();
const iso = (msAgo: number) => new Date(now - msAgo).toISOString();
const sevs = ['critical', 'major', 'minor', 'warning'] as const;
const problems = ['LOS on fibre interface ge-0/0/1 towards aggregation ring', 'Cell down', 'High PRB utilisation', 'Power supply voltage low on rectifier module B', 'S1 link failure', 'VSWR high'];

export const health = {
  status: 'degraded',
  services: ['api-gateway', 'alarm-ingest', 'alarm-enricher', 'incident-service', 'ml-service', 'rag-service', 'copilot-agents', 'llm-gateway', 'ticket-service', 'kpi-ingest', 'graph-service', 'neo4j', 'kafka'].map((name, i) => ({ name, status: i === 7 ? 'down' : 'up', detail: i === 7 ? 'cold start: model still loading on the local runtime' : undefined })),
  checkedAt: iso(0),
};

const sites = Array.from({ length: 14 }, (_, i) => ({
  siteId: `SITE-${String(i + 1).padStart(3, '0')}`,
  name: ['Core-1', 'Fibre Hub North', 'Agg-2', 'Harbour Access', 'University Campus', 'Old Town'][i % 6] + (i > 5 ? ` ${i}` : ''),
  region: ['North', 'South', 'East'][i % 3],
  kind: i < 2 ? 'core' : i < 5 ? 'hub' : 'access',
  lat: 41 + (i % 4) * 0.02,
  lon: 28.9 + Math.floor(i / 4) * 0.03,
  nodes: [{ nodeId: `NODE-${i}`, kind: 'gNB', cells: [`CELL-${i}-1`, `CELL-${i}-2`, `CELL-${i}-3`] }],
}));
export const topology = {
  seed: 1, small: true, regions: ['North', 'South', 'East'], sites,
  links: sites.slice(1).map((s, i) => ({ linkId: `LNK-${String(i + 1).padStart(3, '0')}`, a: sites[i < 2 ? 0 : i % 5].siteId, b: s.siteId, kind: i % 3 ? 'fibre' : 'microwave', role: i < 2 ? 'core' : 'ring' })),
  counts: { regions: 3, sites: 14, nodes: 14, cells: 42, links: 13 },
};

const alarm = (i: number) => ({
  id: `ALM-${10000 + i}`,
  alarmType: 'communicationsAlarm',
  perceivedSeverity: sevs[i % 4],
  probableCause: 'lossOfSignal',
  specificProblem: problems[i % problems.length],
  siteId: sites[i % sites.length].siteId,
  alarmRaisedTime: iso(i * 20_000),
  state: 'raised',
  sourceSystemId: 'netsim-ems-north-01',
  alarmedObject: { id: `${sites[i % sites.length].siteId}/NODE-${i % 14}/CELL-${i % 3}` },
});
export const alarms = Array.from({ length: 45 }, (_, i) => alarm(i));
export const enriched = alarms.map((a, i) => ({
  ...a,
  ingestedAt: a.alarmRaisedTime,
  enrichment: { siteName: sites[i % sites.length].name, region: sites[i % sites.length].region, siteKind: 'access', nodeTypes: ['gNB', 'router'], parentSiteId: 'SITE-001', known: true },
  dedup: { key: `k-${i}`, count: (i % 7) + 1, firstSeen: a.alarmRaisedTime, isDuplicate: i % 7 > 0 },
  correlation: { groupId: i % 3 ? 'grp-1' : null, rootSiteId: 'SITE-002', role: i === 0 ? 'root' : i % 3 ? 'symptom' : 'none' },
}));

const buckets = Array.from({ length: 30 }, (_, i) => ({ start: iso((30 - i) * 60_000), total: i === 22 ? 42 : 4, bySeverity: { critical: i === 22 ? 18 : 0, major: i === 22 ? 14 : 1, minor: i === 22 ? 8 : 2, warning: 1, cleared: 0, indeterminate: 0 } }));

export const incidents = {
  items: Array.from({ length: 12 }, (_, i) => ({
    id: `INC-${2026100 + i}`, rootSiteId: sites[i].siteId, siteIds: [sites[i].siteId, sites[(i + 1) % 14].siteId],
    alarmIds: [], alarmKeys: ['k-1', 'k-2'], alarmCount: 40 - i * 3, severity: sevs[i % 4], region: sites[i].region,
    firstSeen: iso(i * 300_000 + 600_000), lastSeen: iso(i * 300_000), status: i > 9 ? 'cleared' : 'open', version: 1,
    workflow: { state: i % 3 === 0 ? 'acknowledged' : 'new', assignee: i % 3 === 0 ? 'operator' : null, notes: [] },
  })),
  total: 12,
  stats: { alarms: 312, incidents: 12, compressionRatio: 26 },
};

const tickets = Array.from({ length: 10 }, (_, i) => ({
  id: `TCK-${4000 + i}`, status: (['draft', 'approved', 'rejected'] as const)[i % 3],
  title: `Dispatch field team to ${sites[i].name}: replace damaged fibre segment and verify ring protection switch`,
  description: 'Root cause is a fibre cut on the aggregation ring. Follow RB-012 section 3 then confirm alarms clear.',
  severity: sevs[i % 4], siteId: sites[i].siteId, incidentId: `INC-${2026100 + i}`, faultType: 'fibre_cut',
  runbookIds: ['RB-012', 'RB-003'], sourceIds: ['RB-012#3'], createdBy: 'copilot-agents', createdVia: 'mcp',
  createdAt: iso(i * 600_000), decidedBy: i % 3 ? 'admin' : null, decidedAt: i % 3 ? iso(i * 500_000) : null,
  decisionNote: i % 3 ? 'Looks right, approved after checking the topology.' : null, version: 1,
}));
const ticketAudit = Array.from({ length: 6 }, (_, i) => ({ seq: i + 1, ts: iso(i * 60_000), ticketId: 'TCK-4000', actor: i ? 'admin' : 'copilot-agents', role: i ? 'admin' : 'service', action: i ? 'approved' : 'created', fromStatus: i ? 'draft' : null, toStatus: i ? 'approved' : 'draft', detail: {}, prevHash: 'a'.repeat(64), hash: 'f3c9e2b1d4a5'.repeat(5) }));

const agentNames = ['supervisor', 'triage', 'rca', 'remediation', 'approval', 'report'] as const;
const run = {
  runId: 'run-7f3a9c', incidentId: 'INC-2026100', siteId: 'SITE-002', status: 'awaiting_approval', createdAt: iso(300_000), updatedAt: iso(10_000),
  agentPath: [...agentNames],
  messages: Array.from({ length: 10 }, (_, i) => ({ agent: i === 9 ? 'human' : agentNames[i % 6], text: `Step ${i + 1}: ${problems[i % problems.length]}. Checked topology, 12 cells downstream of LNK-002 lose service; recommend rerouting via the east ring before dispatch.`, ts: iso((10 - i) * 20_000), sources: i % 2 ? ['RB-012#3', 'RB-003#1'] : undefined })),
  plan: { summary: 'Reroute traffic over the east ring, then dispatch a field team to splice the cut fibre.', steps: Array.from({ length: 5 }, (_, i) => ({ text: `Do remediation step ${i + 1} carefully and confirm the KPI recovers`, runbookId: 'RB-012', section: `${i + 1}` })), ticketDraft: { title: 'Fibre cut SITE-002', severity: 'critical', description: 'Splice fibre' } },
  ticketId: null, kgWriteBack: { ok: true, detail: 'wrote 3 edges' },
  trace: Array.from({ length: 14 }, (_, i) => ({ seq: i + 1, agent: agentNames[i % 6], name: `${agentNames[i % 6]}.step_${i}`, startedAt: iso((14 - i) * 10_000), durationMs: 120 + i * 37, ok: i !== 6, toolCalls: [{ name: 'graph.impact', ok: true, durationMs: 4, transport: 'mcp' }, { name: 'rag.search', ok: true, durationMs: 31, transport: 'http' }], detail: 'Queried topology and runbooks; found 12 impacted cells.' })),
  report: null, tracing: { langfuse: false }, trigger: 'incident.created', generatedBy: 'llm', decision: null,
};
const runs = [run, { ...run, runId: 'run-55b1e0', status: 'completed' }, { ...run, runId: 'run-12aa90', status: 'rejected' }];

const kpiCells = Array.from({ length: 20 }, (_, i) => ({ cellId: `CELL-${i}-1`, siteId: sites[i % 14].siteId, region: 'North', lastTs: iso(0), sampleCount: 200 + i }));
const kpiSeries = (cellId: string) => ({ cellId, agg: '5m', from: iso(86_400_000), to: iso(0), points: Array.from({ length: 48 }, (_, i) => ({ ts: iso((48 - i) * 1_800_000), dlThroughputMbps: 120 + Math.sin(i / 3) * 40, prbUtilPct: 55 + Math.cos(i / 4) * 20, rrcSetupSuccessPct: 98.5, dropCallRatePct: 0.4 + (i === 40 ? 3 : 0), availabilityPct: 99.9 })) });
const anomalies = { kpi: 'dlThroughputMbps', hours: 24, items: Array.from({ length: 25 }, (_, i) => ({ cellId: `CELL-${i % 14}-${(i % 3) + 1}`, region: ['North', 'South', 'East'][i % 3], ts: iso(i * 900_000), value: 12.34 + i, score: 4.2 + i / 10, method: (['zscore', 'cusum', 'both'] as const)[i % 3], direction: i % 2 ? 'high' : 'low' })) };

const pqc = {
  checkedAt: iso(0),
  tls: ['llm-gateway', 'rag-service', 'ml-service', 'ticket-service', 'copilot-agents'].map((s, i) => ({ service: s, tls: true, hybrid: i < 4, hybridOnly: i < 2, group: i < 4 ? 'X25519MLKEM768' : 'x25519', target: `${s}:8443`, hybridDetail: 'TLS 1.3 hybrid key exchange negotiated' })),
  model: { status: 'pass', reason: 'Signature verified with ML-DSA-65 against the pinned public key', alg: 'ML-DSA-65', keyId: 'ns-model-signing-2026-01', policy: 'enforce', modelVersion: 'fault-xgb-v3.2.1', verifiedAt: iso(0) },
  report: 'docs/benchmarks/pqc-tls.md',
};

const rag = { query: 'fibre cut', mode: 'graph', embedder: 'bge-small', results: Array.from({ length: 6 }, (_, i) => ({ runbookId: `RB-0${10 + i}`, title: `Fibre cut on aggregation ring, procedure ${i + 1}`, section: `${i + 1}. Isolate and reroute`, snippet: 'Confirm LOS on both ends, check the OTDR trace to locate the cut, then reroute traffic via the protection path before dispatch.', score: 0.91 - i * 0.07, faultType: 'fibre_cut', matchedFacets: ['fibre', 'ring'] })), graph: null };
const runbookDoc = { id: 'RB-010', title: 'Fibre cut on aggregation ring', faultType: 'fibre_cut', tags: ['fibre', 'ring'], markdown: '# Fibre cut\n\n' + Array.from({ length: 30 }, (_, i) => `${i + 1}. Step ${i + 1}: verify and record the result in the ticket.`).join('\n') };

const users = ['admin', 'operator', 'viewer', 'noc-shift-lead-north', 'field.engineer.long-username', 'auditor'].map((u, i) => ({ username: u, role: (['admin', 'operator', 'viewer'] as const)[i % 3], disabled: i === 4, locked: i === 5, failedLogins: i, createdAt: now / 1000 - i * 86400, passwordChangedAt: i % 2 ? now / 1000 : null }));
const audit = Array.from({ length: 40 }, (_, i) => ({ id: i + 1, ts: now / 1000 - i * 300, actor: users[i % 6].username, action: ['login.ok', 'user.create', 'role.change', 'login.fail', 'password.change'][i % 5], target: users[(i + 1) % 6].username, detail: { ip: '127.0.0.1', note: 'changed via console' } }));
const settings = { userStore: 'postgres', tokenTtlSeconds: 3600, rateLimitPerMin: 120, loginRateLimitPerMin: 10, lockoutThreshold: 5, lockoutSeconds: 900, demoUsersSeeded: true, authDisabled: false };

const workflowItems = Object.fromEntries(enriched.slice(0, 5).map((a) => [a.dedup.key, { state: 'acknowledged', assignee: 'operator', notes: [{ ts: now / 1000, by: 'operator', action: 'ack', text: 'On it' }] }]));

export async function mockApis(page: Page, role: 'admin' | 'operator' = 'admin') {
  await page.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    const p = u.pathname;
    if (!p.startsWith('/api') && p !== '/health') return route.continue();
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/health') return json(health);
    if (p === '/api/obs/sparklines') return json({ enabled: true, windowMinutes: 30, stepSeconds: 60, services: Object.fromEntries(health.services.map((s, i) => [s.name, { p95Ms: Array.from({ length: 30 }, (_, k) => 20 + ((k * (i + 3)) % 17) * 9.5), errorRate: Array.from({ length: 30 }, (_, k) => (k % (i + 4) ? 0 : 0.031)) }])) });
    if (p === '/api/obs/links') return json({ grafana: 'http://localhost:3000', langfuse: 'http://localhost:3001', mlflow: 'http://localhost:5000', prometheus: 'http://localhost:9090' });
    if (p.startsWith('/api/topology')) return json(topology);
    if (p.startsWith('/api/alarms/timeline')) return json({ buckets, bucketSeconds: 60, total: 158, peak: 42 });
    if (p.startsWith('/api/alarms/workflow')) return json({ items: workflowItems });
    if (p.startsWith('/api/alarms')) return json({ items: alarms, total: alarms.length });
    if (p.startsWith('/api/incidents')) return json(incidents);
    if (p.match(/^\/api\/tickets\/[^/]+\/audit/)) return json({ entries: ticketAudit, valid: true });
    if (p.match(/^\/api\/tickets\/[^/]+$/)) return json({ ticket: tickets[0], audit: ticketAudit, entries: ticketAudit });
    if (p.startsWith('/api/tickets')) return json({ items: tickets, counts: { draft: 4, approved: 3, rejected: 3 } });
    if (p.startsWith('/api/copilot/runs')) return json({ items: runs });
    if (p.startsWith('/api/copilot/analyze')) return json({ answer: { summary: 'Fibre cut', steps: [] }, sourceIds: [] });
    if (p.match(/^\/api\/kpi\/cells\/.+/)) return json(p.includes('anomal') ? { cellId: 'CELL-0-1', kpi: 'dlThroughputMbps', from: iso(86_400_000), to: iso(0), threshold: 3, points: 48, anomalies: anomalies.items.slice(0, 4) } : kpiSeries(decodeURIComponent(p.split('/')[4])));
    if (p.startsWith('/api/kpi/cells')) return json(kpiCells);
    if (p.startsWith('/api/kpi/anomalies') || p.startsWith('/api/anomalies')) return json(anomalies);
    if (p.startsWith('/api/security/pqc')) return json(pqc);
    if (p.startsWith('/api/rag/runbooks')) return json(runbookDoc);
    if (p.startsWith('/api/rag')) return json(rag);
    if (p.startsWith('/api/ml/anomalies/cells')) return json({ cellId: 'CELL-0-1', kpi: 'dlThroughputMbps', from: iso(86_400_000), to: iso(0), threshold: 3, points: 48, anomalies: anomalies.items.slice(0, 4) });
    if (p.startsWith('/api/ml/anomalies')) return json(anomalies);
    if (p.startsWith('/api/ml/predict')) return json({ faultType: 'fibre_cut', confidence: 0.93, probabilities: { fibre_cut: 0.93, power_failure: 0.04 }, modelVersion: 'fault-xgb-v3' });
    if (p.startsWith('/api/ml/explain')) return json({ faultType: 'fibre_cut', confidence: 0.93, modelVersion: 'fault-xgb-v3', baseValue: 0.1, contributions: ['los_count', 'neighbour_down', 'prb_util', 'power_v', 'temp_c', 'link_flaps'].map((f, i) => ({ feature: f, value: i * 3.2, shap: 0.4 - i * 0.09 })) });
    if (p.startsWith('/api/graph/impact')) return json({ target: { type: 'link', id: 'LNK-002' }, impactedSites: sites.slice(2, 8).map((s) => s.siteId), impactedCells: Array.from({ length: 12 }, (_, i) => `CELL-${i}-1`), impacted: [], backend: 'neo4j', latencyMs: 4, elapsedMs: 4 });
    if (p.startsWith('/api/admin/users')) return json({ items: users });
    if (p.startsWith('/api/admin/audit')) return json({ items: audit, valid: true });
    if (p.startsWith('/api/admin/settings')) return json(settings);
    if (p.startsWith('/api/auth')) return json({ ok: true });
    return json({ items: [], total: 0 });
  });
  await page.addInitScript(
    ({ role, alarms, enriched, now }) => {
      sessionStorage.setItem('ns.session', JSON.stringify({ token: 't', username: role, role, expiresAt: Date.now() + 86400000 }));
      class FakeWS {
        static CONNECTING = 0; static OPEN = 1; static CLOSING = 2; static CLOSED = 3;
        readyState = 1; url: string;
        onopen: null | (() => void) = null; onclose: null | (() => void) = null;
        onmessage: null | ((e: { data: string }) => void) = null; onerror = null;
        constructor(url: string) {
          this.url = url;
          setTimeout(() => {
            this.onopen?.();
            let msg: unknown = null;
            if (url.includes('/ws/enriched')) msg = { type: 'snapshot', alarms: enriched };
            else if (url.includes('/ws/alarms')) msg = { type: 'snapshot', alarms };
            else if (url.includes('/ws/kpis'))
              msg = { type: 'kpiActivity', totalSamples: 182344, ratePerMin: 1260, lastSampleTime: new Date(now).toISOString(), cellsReporting: 42,
                averages: { dlThroughputMbps: 132.4, prbUtilPct: 61.2, rrcSetupSuccessPct: 98.7, dropCallRatePct: 0.42, availabilityPct: 99.93 },
                lastSample: { sampleId: 's1', siteId: 'SITE-002', nodeId: 'NODE-2', cellId: 'CELL-2-1', region: 'North', timestamp: new Date(now).toISOString(), granularitySec: 60, kpis: { dlThroughputMbps: 120.2, prbUtilPct: 63.1 } } };
            if (msg) this.onmessage?.({ data: JSON.stringify(msg) });
          }, 10);
        }
        send() {}
        close() { this.readyState = 3; }
        addEventListener() {}
        removeEventListener() {}
      }
      // @ts-expect-error test stub
      window.WebSocket = FakeWS;
    },
    { role, alarms, enriched, now },
  );
}
