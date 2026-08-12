const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

test('equipment menu and dispatcher expose machine communication center', () => {
  assert.match(read('admin/static/js/menu.js'), /eqp\/machine-iot.*机台通讯/);
  assert.match(read('admin/static/js/app.js'), /'eqp\/machine-iot'.*renderMachineIot/);
  const html = read('admin/index.html');
  assert.ok(html.indexOf('pages/machine_iot.js') < html.indexOf('/admin/static/js/app.js'));
});

test('machine communication page uses the complete API set and escapes values', () => {
  const source = read('admin/static/js/pages/machine_iot.js');
  ['endpoints', 'sessions', 'requests', 'reports', 'health'].forEach((part) => {
    assert.match(source, new RegExp(`/api/iot/machine/${part}`));
  });
  assert.match(source, /endpoints\/save/);
  assert.match(source, /reports\/upload/);
  assert.match(source, /MESUI\.escapeHtml/);
  assert.match(source, /准入日志/);
  assert.match(source, /检测报告/);
  assert.match(source, /L1/);
  assert.match(source, /L3/);
  assert.doesNotMatch(source, /onclick="machineEndpointEditJson/);
  assert.match(source, /machine-endpoint-edit/);
});
