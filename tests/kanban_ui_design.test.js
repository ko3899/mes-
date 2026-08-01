const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

test('kanban page uses a semantic local-resource command screen', () => {
  const html = read('frontend/kanban.html');
  for (const id of [
    'kanbanHeader', 'refreshButton', 'fullscreenButton', 'lastUpdated',
    'staleState', 'metricQualified', 'metricDefect', 'metricYield',
    'metricOrders', 'metricEquipment', 'orderTableBody', 'outputChart',
    'equipmentChart', 'qualityChart', 'errorState',
  ]) assert.match(html, new RegExp(`id="${id}"`));
  assert.match(html, /frontend\/static\/vendor\/echarts\.min\.js/);
  assert.match(html, /frontend\/static\/css\/kanban\.css/);
  assert.match(html, /frontend\/static\/js\/kanban\.js/);
  assert.doesNotMatch(html, /http-equiv="refresh"/i);
  assert.doesNotMatch(html, /https?:\/\//);
});

test('kanban stylesheet defines readable 1080p and 1366 layouts', () => {
  const css = read('frontend/static/css/kanban.css');
  for (const token of ['--screen-bg', '--panel-bg', '--panel-border', '--accent', '--success', '--warning', '--danger']) {
    assert.ok(css.includes(token), `missing ${token}`);
  }
  for (const selector of ['.kanban-shell', '.metric-strip', '.command-grid', '.order-panel', '.stale-banner', '.progress-bar']) {
    assert.ok(css.includes(selector), `missing ${selector}`);
  }
  assert.match(css, /@media\s*\(max-width:\s*1500px\)/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /font-variant-numeric:\s*tabular-nums/);
});

test('kanban grid keeps the command area full-height when stale state is hidden', () => {
  const css = read('frontend/static/css/kanban.css');
  assert.match(css, /grid-template-rows:\s*78px\s+142px\s+1fr\s+28px/);
  assert.match(css, /\.stale-banner\s*\{[^}]*position:\s*absolute/s);
  assert.match(css, /\.command-grid\s*\{[^}]*grid-template-rows:\s*repeat\(3,\s*1fr\)/s);
  assert.match(css, /\.order-panel\s*\{[^}]*grid-row:\s*1\s*\/\s*4/s);
});

test('kanban renderer builds API text safely and avoids fake refresh behavior', () => {
  const source = read('frontend/static/js/kanban.js');
  assert.doesNotMatch(source, /\.innerHTML\s*=/);
  assert.doesNotMatch(source, /location\.reload/);
  assert.doesNotMatch(source, /carousel/i);
  assert.match(source, /textContent/);
  assert.match(source, /30000/);
  assert.match(source, /visibilitychange/);
});

test('kanban chart runtime is vendored locally', () => {
  const vendor = read('frontend/static/vendor/echarts.min.js');
  assert.ok(vendor.length > 500000, 'expected complete minified ECharts distribution');
});
