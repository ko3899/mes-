const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const MESUI = require('../admin/static/js/ui_utils.js');

test('manual order registry covers core and generic record pages', () => {
  assert.equal(MESUI.manualOrderRegistry['prod/workorder'].tableKey, 'prod/workorder');
  assert.equal(MESUI.manualOrderRegistry['inv/balance'].tableKey, 'inv/balance');
  assert.equal(MESUI.manualOrderRegistry['sys/user'].tableKey, 'sys/user');
  assert.equal(MESUI.manualOrderRegistry['prod/serial'].tableKey, 'prod/serial');
  assert.equal(MESUI.manualOrderRegistry['qm/8d'].tableKey, 'qm/8d');
  assert.equal(MESUI.manualOrderRegistry['svc/complaint'].tableKey, 'svc/complaint');
  assert.equal(typeof MESUI.enableManualTableOrder, 'function');
});

test('field sorting disables manual movement', () => {
  assert.equal(MESUI.canAdjustManualOrder({field: 'planned_qty', order: 'ASC'}), false);
  assert.equal(MESUI.canAdjustManualOrder({field: '', order: ''}), true);
});

test('display ID comes from position while the hidden record key stays separate', () => {
  assert.equal(MESUI.displayPosition({'42': 7}, 42), 7);
  assert.equal(MESUI.displayPosition({}, 42), null);
});

test('custom record tables are arranged by their persisted positions', () => {
  const rows = [{id: 7}, {id: 9}, {id: 8}];
  const ordered = MESUI.orderRecordsByPosition(rows, {'7': 2, '8': 1, '9': 3});
  assert.deepEqual(ordered.map(item => item.id), [8, 7, 9]);
});

test('manual ordering reuses the ID and operation columns instead of adding a sequence column', () => {
  const source = fs.readFileSync(path.join(__dirname, '../admin/static/js/ui_utils.js'), 'utf8');
  assert.doesNotMatch(source, /manual-order-heading/);
  assert.doesNotMatch(source, /th\.textContent\s*=\s*'顺序'/);
  assert.match(source, /display-id-cell/);
});

test('application exposes move and one-step table ordering actions', () => {
  const source = fs.readFileSync(path.join(__dirname, '../admin/static/js/app.js'), 'utf8');
  assert.match(source, /function moveTableRecord/);
  assert.match(source, /function stepTableRecord/);
  assert.match(source, /target_position/);
});

test('manual explains global position and field-sort interaction', () => {
  const manual = fs.readFileSync(path.join(__dirname, '../docs/MES工厂管家_使用手册.md'), 'utf8');
  assert.match(manual, /目标排列 ID/);
  assert.match(manual, /真实主键.*隐藏/);
  assert.match(manual, /恢复默认顺序/);
});
