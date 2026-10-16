import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const OUT = process.env.SHOT_DIR || path.resolve('test-results/visual');
fs.mkdirSync(OUT, { recursive: true });

const session = {
  token: 'visual-token',
  username: 'operator',
  role: 'operator',
  expiresAt: Date.now() + 86400000,
};

const now = new Date().toISOString();
const health = {
  status: 'ok',
  services: [
    { name: 'api-gateway', status: 'up' },
    { name: 'alarm-ingest', status: 'up' },
    { name: 'incident-service', status: 'up' },
    { name: 'ml-service', status: 'up' },
    { name: 'llm-gateway', status: 'degraded', detail: 'cold start' },
    { name: 'neo4j', status: 'up' },
  ],
  checkedAt: now,
};

const topology = {
  seed: 1,
  small: true,
  regions: ['North', 'South'],
  sites: [
    { siteId: 'SITE-011', name: 'Fibre Hub', region: 'North', kind: 'access', lat: 41.01, lon: 28.97, nodes: [] },
    { siteId: 'SITE-001', name: 'Core-1', region: 'North', kind: 'core', lat: 41.02, lon: 28.98, nodes: [] },
    { siteId: 'SITE-002', name: 'Agg-2', region: 'South', kind: 'agg', lat: 40.99, lon: 29.01, nodes: [] },
  ],
  links: [
    { linkId: 'LNK-012', a: 'SITE-011', b: 'SITE-001', kind: 'fibre' },
    { linkId: 'LNK-013', a: 'SITE-001', b: 'SITE-002', kind: 'fibre' },
  ],
  counts: { regions: 2, sites: 3, nodes: 0, cells: 12, links: 2 },
};

function buckets() {
  const out = [];
  const base = Date.now() - 30 * 60_000;
  for (let i = 0; i < 30; i++) {
    const t = new Date(base + i * 60_000).toISOString();
    const storm = i === 22;
    out.push({
      t,
      critical: storm ? 18 : i % 5 === 0 ? 2 : 0,
      major: storm ? 14 : i % 3 === 0 ? 3 : 1,
      minor: storm ? 8 : 2,
      warning: storm ? 2 : 1,
      cleared: 0,
      total: storm ? 42 : 4 + (i % 3),
    });
  }
  return out;
}

const incidents = {
  items: [
    {
      id: 'inc-1',
      severity: 'critical',
      status: 'open',
      rootSiteId: 'SITE-011',
      region: 'North',
      alarmCount: 38,
      siteCount: 1,
      startedAt: now,
      updatedAt: now,
      title: 'Fibre cut SITE-011',
    },
    {
      id: 'inc-2',
      severity: 'major',
      status: 'open',
      rootSiteId: 'SITE-002',
      region: 'South',
      alarmCount: 6,
      siteCount: 1,
      startedAt: now,
      updatedAt: now,
      title: 'Power dip Agg-2',
    },
  ],
  total: 2,
};

async function mockApis(page: import('@playwright/test').Page) {
  await page.route('**/api/**', async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    if (url.includes('/api/auth/')) return json({ ok: true });
    if (url.includes('/health')) return json(health);
    if (url.includes('/api/topology')) return json(topology);
    if (url.includes('/api/alarms/timeline')) return json({ buckets: buckets(), windowMinutes: 30 });
    if (url.includes('/api/incidents')) return json(incidents);
    if (url.includes('/api/alarms')) return json({ items: [], total: 0 });
    if (url.includes('/api/enriched')) return json({ items: [], total: 0 });
    if (url.includes('/api/kpi')) return json({ series: [], points: [] });
    if (url.includes('/api/anomalies')) return json({ items: [], total: 0 });
    if (url.includes('/api/security/pqc'))
      return json({
        checkedAt: now,
        tls: [{ target: 'llm-gateway:8443', mode: 'hybrid', ok: true, latencyMs: 12 }],
        model: { ok: true, version: 'fault-v1', algorithm: 'ML-DSA-65' },
        plaintext: ['api-gateway'],
      });
    if (url.includes('/api/tickets')) return json({ items: [], total: 0 });
    if (url.includes('/api/agents')) return json({ items: [], total: 0 });
    if (url.includes('/api/rag')) return json({ hits: [] });
    if (url.includes('/api/impact')) return json({ impacted: [], backend: 'neo4j', latencyMs: 4 });
    if (url.includes('alarm-workflow') || url.includes('/workflow')) return json({ items: [] });
    if (url.includes('/api/')) return json({ items: [], total: 0, buckets: [], series: [], points: [], services: health.services, status: 'ok', checkedAt: now });
    return json({ status: 'ok', services: health.services, checkedAt: now });
  });
  await page.route('**/ws**', (route) => route.abort());
  await page.route('**/health', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(health) });
  });
}

test.beforeEach(async ({ page }) => {
  await mockApis(page);
  await page.addInitScript((s) => {
    sessionStorage.setItem('ns.session', JSON.stringify(s));
    // Stub WebSocket so the feed hooks do not hang the page.
    class FakeWS {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSED = 3;
      readyState = 1;
      onopen = null;
      onclose = null;
      onmessage = null;
      onerror = null;
      constructor() {
        setTimeout(() => this.onopen && this.onopen(), 0);
      }
      send() {}
      close() {
        this.readyState = 3;
        this.onclose && this.onclose();
      }
    }
    // @ts-expect-error test stub
    window.WebSocket = FakeWS;
  }, session);
});

const viewports = [
  { width: 375, height: 812, name: '375' },
  { width: 768, height: 1024, name: '768' },
  { width: 1280, height: 800, name: '1280' },
  { width: 1920, height: 1080, name: '1920' },
];

for (const vp of viewports) {
  test(`ops dashboard ${vp.name}`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('http://127.0.0.1:5179/', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('kpi-summary')).toBeVisible({ timeout: 20000 });
    await expect(page.getByText(/NetSentinel/)).toBeVisible();
    await page.screenshot({ path: path.join(OUT, `ops-${vp.name}.png`), fullPage: true });
  });
}

test('hovered tooltip at 1280', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('http://127.0.0.1:5179/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('kpi-summary')).toBeVisible({ timeout: 20000 });
  const tip = page.locator('[data-testid="kpi-summary"] [data-testid="info-tip"]').first();
  await tip.scrollIntoViewIfNeeded();
  await tip.hover({ force: true });
  await expect(page.getByRole('tooltip')).toBeVisible({ timeout: 10000 });
  await page.screenshot({ path: path.join(OUT, 'tooltip-1280.png'), fullPage: false });
});
