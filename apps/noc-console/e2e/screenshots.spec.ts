import { test } from '@playwright/test';
import path from 'path';

const viewports = [
  { width: 375, height: 812, name: '375' },
  { width: 768, height: 1024, name: '768' },
  { width: 1280, height: 800, name: '1280' },
  { width: 1920, height: 1080, name: '1920' },
];

for (const vp of viewports) {
  test(`screenshot at ${vp.name}px`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join('test-results', `responsive-${vp.name}.png`), fullPage: false });
  });
}
