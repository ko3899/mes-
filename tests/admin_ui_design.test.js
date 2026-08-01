const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

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
