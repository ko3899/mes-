const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const baseUrl = 'http://127.0.0.1:8080/admin';
const reportsDir = path.resolve(__dirname, '../../reports/ui');
fs.mkdirSync(reportsDir, {recursive: true});
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].find((candidate) => fs.existsSync(candidate));

(async () => {
  assert.ok(executablePath, 'Chrome or Edge executable is required for browser acceptance');
  const browser = await chromium.launch({headless: true, executablePath});
  const page = await browser.newPage({viewport: {width: 1366, height: 768}});
  const consoleErrors = [];
  const pageErrors = [];
  const httpErrors = [];

  page.on('console', (message) => {
    if (message.type() === 'error') {
      const location = message.location();
      consoleErrors.push(`${message.text()} @ ${location.url || 'unknown'}`);
    }
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('response', (response) => {
    if (response.status() >= 400) {
      httpErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  try {
    await page.goto(baseUrl, {waitUntil: 'domcontentloaded'});
    await page.locator('.login-layout').waitFor({state: 'visible'});
    await page.screenshot({
      path: path.join(reportsDir, 'login-desktop.png'),
      fullPage: true,
    });

    await page.locator('#lu').fill('admin');
    await page.locator('#lp').fill('admin123');
    await page.locator('#loginBtn').click();
    await page.locator('#pageContent .dashboard-hero').waitFor({state: 'visible'});

    assert.equal(await page.locator('.metrics-grid .metric-card').count(), 6);
    assert.equal(await page.locator('.dashboard-grid .chart-card').count(), 4);
    await page.screenshot({
      path: path.join(reportsDir, 'dashboard-desktop.png'),
      fullPage: false,
    });

    await page.locator('#themeBtn').click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    assert.equal(await page.locator('#themeBtn').getAttribute('aria-label'), '切换浅色主题');

    await page.locator('#toggleBtn').click();
    await page.waitForFunction(() => (
      Math.round(document.querySelector('.sidebar-shell').getBoundingClientRect().width) === 76
    ));
    assert.equal(await page.locator('#toggleBtn').getAttribute('aria-expanded'), 'false');
    await page.locator('#toggleBtn').click();
    await page.waitForFunction(() => (
      Math.round(document.querySelector('.sidebar-shell').getBoundingClientRect().width) === 248
    ));

    await page.locator('button[data-menu="base"]').click();
    await page.locator('button[data-page="base/workshop"]').click();
    await page.locator('#pageContent .table-wrap').waitFor({state: 'visible'});
    assert.ok(await page.locator('#tb tr').count() >= 1);
    await page.locator('#addBtn').click();
    await page.locator('#modal.show').waitFor({state: 'visible'});
    assert.equal(await page.locator('#mTitle').textContent(), '新增');
    await page.locator('#modalCancelBtn').click();

    await page.setViewportSize({width: 390, height: 844});
    await page.locator('#toggleBtn').click();
    await page.waitForFunction(() => (
      document.getElementById('appPage').classList.contains('sidebar-open')
      && Math.round(document.querySelector('.sidebar-shell').getBoundingClientRect().x) === 0
    ));
    assert.equal(await page.locator('#toggleBtn').getAttribute('aria-expanded'), 'true');
    await page.screenshot({
      path: path.join(reportsDir, 'dashboard-mobile.png'),
      fullPage: false,
    });

    await page.locator('button[data-page="home"]').click();
    await page.locator('#pageContent .dashboard-hero').waitFor({state: 'visible'});
    assert.equal(
      await page.locator('#appPage').evaluate((element) => element.classList.contains('sidebar-open')),
      false
    );
    assert.equal(await page.locator('#toggleBtn').getAttribute('aria-expanded'), 'false');

    assert.deepEqual(pageErrors, []);
    assert.deepEqual(httpErrors, []);
    assert.deepEqual(consoleErrors, []);
    process.stdout.write('enterprise-blue browser acceptance passed\n');
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
