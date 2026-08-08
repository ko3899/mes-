const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const MESUI = require('../admin/static/js/ui_utils.js');

test('sortRows orders numeric values ascending and keeps nulls last', () => {
  const rows = [{id: 1, qty: null}, {id: 2, qty: 10}, {id: 3, qty: 2}];
  assert.deepEqual(MESUI.sortRows(rows, 'qty', 'ASC', 'number').map(r => r.id), [3, 2, 1]);
});

test('nextSortState cycles field ASC, DESC, then default', () => {
  assert.deepEqual(MESUI.nextSortState({field: '', order: ''}, 'name'), {field: 'name', order: 'ASC'});
  assert.deepEqual(MESUI.nextSortState({field: 'name', order: 'ASC'}, 'name'), {field: 'name', order: 'DESC'});
  assert.deepEqual(MESUI.nextSortState({field: 'name', order: 'DESC'}, 'name'), {field: '', order: ''});
});

test('sortHeaderHtml exposes an accessible button and active direction', () => {
  const html = MESUI.sortHeaderHtml('qty', '计划数', {field: 'qty', order: 'DESC'});
  assert.match(html, /data-sort-field="qty"/);
  assert.match(html, /aria-sort="descending"/);
});

test('crud source resets both sort values and renders sortable state', () => {
  const source = fs.readFileSync(path.join(__dirname, '../admin/static/js/crud.js'), 'utf8');
  assert.match(source, /sortOrder\s*=\s*'DESC'/);
  assert.match(source, /MESUI\.sortHeaderHtml/);
});
