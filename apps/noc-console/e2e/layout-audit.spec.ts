import { test, expect, type Page } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { mockApis } from './mocks';

/**
 * Layout audit: full screenshots of every view at 4 widths plus an overflow check.
 * Fails if any element escapes its card (spill), if the page scrolls sideways,
 * or if text is truncated without a title attribute.
 */
const OUT = process.env.SHOT_DIR || path.resolve('test-results/layout');
const BASE = process.env.CONSOLE_URL || 'http://127.0.0.1:5179/';
fs.mkdirSync(OUT, { recursive: true });

const widths = [375, 768, 1280, 1440];

type Problem = { kind: string; card: string; el: string; detail: string };

async function findProblems(page: Page): Promise<Problem[]> {
  return page.evaluate(() => {
    const out: { kind: string; card: string; el: string; detail: string }[] = [];
    const describe = (el: Element) => {
      const id = (el as HTMLElement).dataset?.testid;
      const cls = typeof el.className === 'string' ? el.className.split(' ').slice(0, 4).join('.') : '';
      return `${el.tagName.toLowerCase()}${id ? `[${id}]` : ''}${cls ? `.${cls}` : ''} "${(el.textContent || '').trim().slice(0, 40)}"`;
    };
    const visible = (el: Element) => {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return s.visibility !== 'hidden' && s.display !== 'none' && r.width > 0 && r.height > 0;
    };
    if (document.documentElement.scrollWidth > window.innerWidth + 1)
      out.push({ kind: 'page-x-scroll', card: 'document', el: 'html', detail: `${document.documentElement.scrollWidth} > ${window.innerWidth}` });
    const cards = Array.from(document.querySelectorAll('.ns-card, [data-card]'));
    for (const card of cards) {
      if (!visible(card)) continue;
      const cr = card.getBoundingClientRect();
      const title = (card.querySelector('h2,h3')?.textContent || describe(card)).trim().slice(0, 40);
      for (const el of Array.from(card.querySelectorAll('*'))) {
        if (!visible(el) || el.closest('[role="tooltip"]') || el.closest('[data-overflow-ok]')) continue;
        // skip anything inside a clipping/scrolling ancestor below the card: that is intended scrolling
        let clipped = false;
        for (let a = el.parentElement; a && a !== card; a = a.parentElement) {
          const s = getComputedStyle(a);
          if (s.overflowX !== 'visible' || s.overflowY !== 'visible') { clipped = true; break; }
        }
        if (clipped) continue;
        const r = el.getBoundingClientRect();
        const tol = 2;
        if (r.right > cr.right + tol || r.left < cr.left - tol || r.bottom > cr.bottom + tol || r.top < cr.top - tol)
          out.push({ kind: 'spill', card: title, el: describe(el), detail: `el ${Math.round(r.left)},${Math.round(r.top)}-${Math.round(r.right)},${Math.round(r.bottom)} card ${Math.round(cr.left)},${Math.round(cr.top)}-${Math.round(cr.right)},${Math.round(cr.bottom)}` });
      }
    }
    for (const el of Array.from(document.querySelectorAll('.truncate, .text-ellipsis, [class*="line-clamp"]'))) {
      const h = el as HTMLElement;
      if (!visible(el)) continue;
      if ((h.scrollWidth > h.clientWidth + 1 || h.scrollHeight > h.clientHeight + 1) && !h.title && !h.closest('[title]'))
        out.push({ kind: 'truncated-no-title', card: '', el: describe(el), detail: `${h.scrollWidth}>${h.clientWidth}` });
    }
    return out;
  });
}

async function open(page: Page, w: number, role: 'admin' | 'operator' = 'admin') {
  page.on('pageerror', (e) => { throw e; });
  await mockApis(page, role);
  await page.setViewportSize({ width: w, height: w < 500 ? 812 : w < 1000 ? 1024 : 900 });
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('kpi-summary')).toBeVisible({ timeout: 20000 });
  await page.waitForTimeout(1500);
}

function record(name: string, problems: Problem[]) {
  fs.writeFileSync(path.join(OUT, `problems-${name}.json`), JSON.stringify(problems, null, 1));
  if (process.env.LAYOUT_STRICT) expect(problems, JSON.stringify(problems, null, 1).slice(0, 4000)).toEqual([]);
}

for (const w of widths) {
  test(`operations ${w}`, async ({ page }) => {
    await open(page, w);
    await page.screenshot({ path: path.join(OUT, `ops-${w}.png`), fullPage: true });
    // every select: focus it and shoot the card it lives in
    const selects = page.locator('select');
    const n = await selects.count();
    for (let i = 0; i < n; i++) {
      const s = selects.nth(i);
      if (!(await s.isVisible())) continue;
      await s.scrollIntoViewIfNeeded();
      await s.focus();
      const card = s.locator('xpath=ancestor::section[1]');
      const target = (await card.count()) ? card : s;
      await target.screenshot({ path: path.join(OUT, `select-${i}-${w}.png`) }).catch(() => {});
    }
    // every scroll container: scroll to the bottom and shoot its card
    const scrollers = await page.locator('.ns-scroll, [data-scroll]').all();
    let k = 0;
    for (const sc of scrollers) {
      if (!(await sc.isVisible())) continue;
      await sc.evaluate((e) => (e.scrollTop = e.scrollHeight));
      const card = sc.locator('xpath=ancestor::section[1]');
      if (await card.count()) await card.screenshot({ path: path.join(OUT, `scrolled-${k++}-${w}.png`) }).catch(() => {});
    }
    const opsProblems = await findProblems(page);
    // selections: a ticket (detail + audit trail) and an incident (filter + workflow actions)
    const ticket = page.getByTestId('ticket-row').first();
    if (await ticket.count()) {
      await ticket.scrollIntoViewIfNeeded();
      await ticket.click();
      await page.waitForTimeout(500);
      await page.getByTestId('approval-queue').screenshot({ path: path.join(OUT, `ticket-selected-${w}.png`) });
    }
    const inc = page.locator('[data-testid^="incident-INC-"]').first();
    if (await inc.count()) {
      await inc.scrollIntoViewIfNeeded();
      await inc.click();
      await page.waitForTimeout(500);
      await page.getByTestId('incident-board').screenshot({ path: path.join(OUT, `incident-selected-${w}.png`) });
    }
    opsProblems.push(...(await findProblems(page)));
    // drawer: open the first enriched alarm row
    const row = page.locator('.ns-card', { has: page.getByRole('heading', { name: /enriched/i }) }).locator('tbody tr').first();
    if (await row.count()) {
      await row.scrollIntoViewIfNeeded();
      await row.click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: path.join(OUT, `drawer-${w}.png`) });
      const rb = page.getByRole('dialog').getByRole('button', { name: /RB-0/ }).first();
      if (await rb.count()) { await rb.click(); await page.waitForTimeout(500); await page.screenshot({ path: path.join(OUT, `drawer-runbook-${w}.png`) }); }
    }
    await page.keyboard.press('Escape');
    // user menu + change-password modal
    const menu = page.getByRole('button', { name: /admin/i }).last();
    await menu.click().catch(() => {});
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(OUT, `usermenu-${w}.png`) });
    const pw = page.getByRole('menuitem', { name: /password/i }).or(page.getByRole('button', { name: /change password/i })).first();
    if (await pw.count()) {
      await pw.click();
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(OUT, `password-modal-${w}.png`) });
    }
    record(`ops-${w}`, opsProblems);
  });

  test(`admin ${w}`, async ({ page }) => {
    await open(page, w);
    const btn = page.getByRole('button', { name: /^admin/i }).first();
    await btn.click();
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(OUT, `admin-${w}.png`), fullPage: true });
    record(`admin-${w}`, await findProblems(page));
  });
}

