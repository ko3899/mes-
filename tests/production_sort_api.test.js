const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('production paginated lists validate sort fields and direction', () => {
  const source = fs.readFileSync(path.join(__dirname, '../backend/blueprints/production.py'), 'utf8');
  assert.match(source, /_safe_sort/);
  assert.match(source, /workorder_sort_fields/);
  assert.match(source, /task_sort_fields/);
  assert.match(source, /report_sort_fields/);
});
