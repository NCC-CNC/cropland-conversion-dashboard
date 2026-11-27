import { readFileSync } from 'node:fs';
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// A box inside the Stettler window (ab-parkland-stettler), as a share link.
const SHARE = '#a=ab-parkland-stettler&s=-112.9,52.2;-112.7,52.2;-112.7,52.35;-112.9,52.35';

// 1x1 transparent PNG, served for basemap tiles so the checks need no outside network.
const PIXEL = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
);

const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

const VIEWPORTS = [
  { name: 'phone', width: 390, height: 800 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1024, height: 800 },
];

/** Load the app with no outside network (basemap tiles), collecting script errors. */
async function open(page: Page, hash = ''): Promise<string[]> {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    // The expected 404 probes for missing 30 m files are not app errors.
    if (m.type() === 'error' && !/Failed to load resource|net::ERR/.test(m.text())) errors.push(m.text());
  });
  await page.route(/^https?:\/\/(?!localhost)/, (r) =>
    r.fulfill({ status: 200, contentType: 'image/png', body: PIXEL }),
  );
  await page.goto(`./${hash}`);
  await page.waitForSelector('body[data-ready=true]');
  return errors;
}

const noOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test('empty state has no axe violations', async ({ page }) => {
  const errors = await open(page);
  const res = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  expect(res.violations).toEqual([]);
  expect(errors).toEqual([]);
});

test('shared polygon shows results, tabs work, no axe violations', async ({ page }) => {
  const errors = await open(page, SHARE);
  await expect(page.locator('#btn-csv')).toBeEnabled();
  await expect(page.locator('#btn-report')).toBeEnabled();

  const tabs = page.locator('#summary [role=tab]');
  expect(await tabs.count()).toBeGreaterThan(1);
  await tabs.first().focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#summary [role=tab]:focus')).toHaveCount(1);

  const res = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  expect(res.violations).toEqual([]);
  expect(errors).toEqual([]);
});

test('report downloads as a Word file', async ({ page }) => {
  await open(page, SHARE);
  await expect(page.locator('#btn-report')).toBeEnabled();
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#btn-report')]);
  expect(dl.suggestedFilename()).toMatch(/\.docx$/);
  expect(readFileSync(await dl.path()).subarray(0, 2).toString()).toBe('PK'); // a .docx is a zip
});

test('CSV downloads', async ({ page }) => {
  await open(page, SHARE);
  await expect(page.locator('#btn-csv')).toBeEnabled();
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#btn-csv')]);
  expect(dl.suggestedFilename()).toMatch(/\.csv$/);
});

for (const vp of VIEWPORTS) {
  test(`no horizontal overflow at ${vp.name} (${vp.width} px)`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await open(page, SHARE);
    await expect(page.locator('#btn-csv')).toBeEnabled();
    expect(await noOverflow(page)).toBe(true);
  });
}
