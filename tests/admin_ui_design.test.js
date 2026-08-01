const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {escapeHtml} = require('../admin/static/js/ui_utils.js');

const projectRoot = path.resolve(__dirname, '..');

function read(relativePath) {
  return fs.readFileSync(path.join(projectRoot, relativePath), 'utf8');
}

test('login and app shell expose the enterprise-blue semantic structure', () => {
  const html = read('admin/index.html');

  assert.match(html, /class="login-layout"/);
  assert.match(html, /class="login-brand"/);
  assert.match(html, /class="login-panel"/);
  assert.match(html, /class="sidebar-shell"/);
  assert.match(html, /class="topbar"/);
  assert.match(html, /aria-label="切换侧栏"/);
  assert.doesNotMatch(html, /id="globalSearch"[^>]+style=/);
  assert.doesNotMatch(html, /id="notifBadge"[^>]+style=/);
});

test('the stylesheet defines application geometry and semantic tokens', () => {
  const css = read('admin/static/css/style.css');

  for (const token of [
    '--navy-950',
    '--primary-600',
    '--surface',
    '--workspace',
    '--border-subtle',
  ]) {
    assert.ok(css.includes(token), `missing design token ${token}`);
  }

  for (const selector of [
    '.app-shell',
    '.sidebar-shell',
    '.main-shell',
    '.topbar',
    '.content',
  ]) {
    assert.ok(css.includes(selector), `missing shell selector ${selector}`);
  }
});

test('authentication view changes are expressed through a state class', () => {
  const source = read('admin/static/js/app.js');

  assert.match(source, /function setAuthenticatedView\(authenticated\)/);
  assert.match(source, /classList\.toggle\('is-hidden'/);
  assert.doesNotMatch(source, /appPage'\)\.style\.display/);
});

test('menu output exposes group, parent, item, and label hooks', () => {
  const source = read('admin/static/js/menu.js');

  for (const hook of ['menu-group', 'menu-parent', 'menu-item', 'menu-label']) {
    assert.ok(source.includes(hook), `missing navigation hook ${hook}`);
  }
  assert.match(source, /aria-expanded/);
});

test('shared component styles cover data-heavy business screens', () => {
  const css = read('admin/static/css/style.css');

  for (const selector of [
    '.card',
    '.toolbar',
    '.table-wrap',
    '.page',
    '.btn',
    '.tag',
    '.form-item',
    '.modal-mask',
    '.batch-bar',
  ]) {
    assert.ok(css.includes(selector), `missing shared selector ${selector}`);
  }
  assert.match(css, /:focus-visible/);
});

test('shared renderers use semantic classes instead of core inline presentation', () => {
  const crud = read('admin/static/js/crud.js');
  const modal = read('admin/static/js/modal.js');

  assert.match(crud, /class="table-wrap"/);
  assert.match(crud, /class="toolbar-actions"/);
  assert.match(modal, /class="required-mark"/);
  assert.doesNotMatch(crud, /id="pageSize"[^>]+style=/);
});

test('home renderer uses production command-center sections', () => {
  const source = read('admin/static/js/pages/home.js');

  for (const hook of [
    'dashboard-hero',
    'metrics-grid',
    'metric-card',
    'dashboard-grid',
    'alert-grid',
    'quick-actions',
  ]) {
    assert.ok(source.includes(hook), `missing dashboard hook ${hook}`);
  }
  assert.doesNotMatch(source, /style="display:grid/);
});

test('dashboard text helper escapes API-provided warning values', () => {
  const context = vm.createContext({MESUI: {escapeHtml}});
  vm.runInContext(read('admin/static/js/pages/home.js'), context, {
    filename: 'admin/static/js/pages/home.js',
  });

  assert.equal(
    context.dashboardText('<img src=x onerror=alert(1)>'),
    '&lt;img src=x onerror=alert(1)&gt;'
  );
});

test('dark and responsive contracts cover desktop, tablet, and mobile', () => {
  const css = read('admin/static/css/style.css');

  assert.match(css, /\[data-theme="dark"\]/);
  assert.match(css, /@media\s*\(max-width:\s*1199px\)/);
  assert.match(css, /@media\s*\(max-width:\s*767px\)/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /sidebar-open/);
});

test('theme and sidebar controls expose their state to assistive technology', () => {
  const source = read('admin/static/js/app.js');

  assert.match(source, /setAttribute\('aria-label',\s*isDark/);
  assert.match(source, /setAttribute\('aria-expanded'/);
  assert.match(source, /classList\.toggle\(className\)/);
});
