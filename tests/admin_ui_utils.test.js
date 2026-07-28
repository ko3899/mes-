const test = require('node:test');
const assert = require('node:assert/strict');
const { escapeHtml, menuPage, statusHtml } =
  require('../admin/static/js/ui_utils.js');

test('escapeHtml renders business input as text', () => {
  assert.equal(
    escapeHtml('<img src=x onerror=alert(1)>'),
    '&lt;img src=x onerror=alert(1)&gt;'
  );
});

test('menuPage preserves each top-level destination', () => {
  assert.equal(menuPage({k: 'analytics/dashboard', home: true}), 'analytics/dashboard');
  assert.equal(menuPage({k: 'notifications', home: true}), 'notifications');
});

test('statusHtml prefers configured business labels', () => {
  const field = {k: 'status', s: [{v: 0, t: '待检'}, {v: 1, t: '已检'}]};
  assert.match(statusHtml(field, 0), /待检/);
  assert.doesNotMatch(statusHtml(field, 0), /禁用/);
});
