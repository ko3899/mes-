const test = require('node:test');
const assert = require('node:assert/strict');
const MESUI = require('../admin/static/js/ui_utils.js');

test('enableTableSorting is available for custom record tables', () => {
  assert.equal(typeof MESUI.enableTableSorting, 'function');
});

test('custom table sorting helper is wired from the application shell', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const source = fs.readFileSync(path.join(__dirname, '../admin/static/js/app.js'), 'utf8');
  assert.match(source, /enableTableSorting/);
});
