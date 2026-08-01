const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

test('collector document exposes an accessible local application shell', () => {
  const html = read('frontend/index.html');
  for (const id of [
    'loginView', 'appView', 'networkState', 'syncCount', 'pageTitle',
    'pageContent', 'bottomNav', 'modalRoot', 'toastRoot',
  ]) assert.match(html, new RegExp(`id="${id}"`));

  for (const page of ['home', 'scan', 'task', 'report', 'quality', 'material']) {
    assert.match(html, new RegExp(`data-page="${page}"`));
  }
  assert.doesNotMatch(html, /type="password"[^>]+value=/);
  assert.doesNotMatch(html, /https?:\/\//);
  assert.match(html, /aria-live="polite"/);
  assert.match(html, /static\/css\/collector\.css/);
  assert.match(html, /static\/js\/app\.js/);
});

test('collector stylesheet defines industrial handheld geometry and states', () => {
  const css = read('frontend/static/css/collector.css');
  for (const token of [
    '--navy-950', '--primary-600', '--workspace', '--surface',
    '--success', '--warning', '--danger',
  ]) assert.ok(css.includes(token), `missing ${token}`);
  for (const selector of [
    '.collector-shell', '.terminal-header', '.bottom-nav', '.network-pill',
    '.scan-stage', '.task-card', '.metric-card', '.offline-banner',
  ]) assert.ok(css.includes(selector), `missing ${selector}`);
  assert.match(css, /env\(safe-area-inset-bottom/);
  assert.match(css, /:focus-visible/);
  assert.match(css, /@media\s*\(max-height:\s*680px\)/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.doesNotMatch(css, /font-family:\s*(Arial|Inter|Roboto)/i);
});

test('collector page and application renderers avoid unsafe legacy patterns', () => {
  const pages = read('frontend/static/js/pages.js');
  const app = read('frontend/static/js/app.js');
  assert.doesNotMatch(pages, /\.innerHTML\s*=/);
  assert.doesNotMatch(app, /\.innerHTML\s*=/);
  assert.doesNotMatch(pages, /\balert\s*\(/);
  assert.doesNotMatch(app, /\balert\s*\(/);
  assert.match(pages, /function createCollectorPages/);
  assert.match(app, /function setNetworkState/);
  assert.match(app, /function syncOfflineQueue/);
  assert.match(app, /classList\.toggle\('is-hidden'/);
});

test('collector business forms expose real submit controls', () => {
  const pages = read('frontend/static/js/pages.js');
  const submitAssignments = pages.match(/\.type\s*=\s*'submit'/g) || [];
  assert.ok(submitAssignments.length >= 2, 'quality and tool forms need submit buttons');
});

test('collector manifest uses the enterprise-blue terminal identity', () => {
  const manifest = JSON.parse(read('frontend/manifest.json'));
  assert.equal(manifest.name, 'MES采集终端');
  assert.equal(manifest.short_name, 'MES采集');
  assert.equal(manifest.theme_color, '#0B1F3A');
  assert.equal(manifest.display, 'standalone');
});
