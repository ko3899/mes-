const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

test('all production chain renderers exist', () => {
  const source = read('admin/static/js/pages/production_chain.js');
  ['renderSales', 'renderPlan', 'renderRoute', 'renderTask', 'renderReport2']
    .forEach((name) => {
      assert.match(source, new RegExp(`function\\s+${name}\\s*\\(`));
    });
});

test('production chain script loads before the application dispatcher', () => {
  const html = read('admin/index.html');
  const chainIndex = html.indexOf('/admin/static/js/pages/production_chain.js');
  const appIndex = html.indexOf('/admin/static/js/app.js');
  assert.ok(chainIndex >= 0, 'production chain script must be included');
  assert.ok(appIndex >= 0, 'application dispatcher must be included');
  assert.ok(chainIndex < appIndex, 'production chain script must load first');
});

test('module dispatch clears stale content and catches renderer failures', () => {
  const source = read('admin/static/js/app.js');
  assert.match(source, /el\.replaceChildren\(\)/);
  assert.match(source, /try\s*\{/);
  assert.match(source, /renderModuleError\(el,/);
});

test('missing production pages expose their own business titles', () => {
  const source = read('admin/static/js/pages/production_chain.js');
  ['销售订单', '生产计划', '工艺路线', '任务管理', '报工管理']
    .forEach((title) => assert.match(source, new RegExp(title)));
});

test('process and route editors enforce workshop-scoped choices', () => {
  const processSource = read('admin/static/js/pages/extensions.js');
  const routeSource = read('admin/static/js/pages/production_chain.js');
  assert.match(processSource, /所属车间.*必填/);
  assert.match(processSource, /processWorkshopFilter/);
  assert.match(routeSource, /\/api\/base\/route\/save/);
  assert.match(routeSource, /routeStepRows/);
  assert.match(routeSource, /is_inspection_point/);
});

test('sales plans and production batches expose line-based save flows', () => {
  const source = read('admin/static/js/pages/production_chain.js');
  const menu = read('admin/static/js/menu.js');
  const app = read('admin/static/js/app.js');
  assert.match(source, /\/api\/prod\/sales\/save/);
  assert.match(source, /\/api\/prod\/plan\/save/);
  assert.match(source, /\/api\/prod\/batch\/save/);
  assert.match(source, /salesLineItems/);
  assert.match(source, /planLineItems/);
  assert.match(menu, /prod\/batch/);
  assert.match(app, /renderProductionBatch/);
});

test('workorder UI releases snapshots and generates tasks', () => {
  const source = read('admin/static/js/pages/business.js');
  assert.match(source, /\/api\/prod\/workorder\/save/);
  assert.match(source, /\/release/);
  assert.match(source, /\/generate-tasks/);
  assert.match(source, /production_batch_id/);
  assert.match(source, /route_version/);
});

test('material UI uses frozen BOM and controlled inventory actions', () => {
  const workorder = read('admin/static/js/pages/business.js');
  const material = read('admin/static/js/pages/prod_ext.js');
  assert.match(workorder, /generate-materials/);
  assert.match(material, /requested_qty/);
  assert.match(material, /issued_qty/);
  assert.match(material, /returned_qty/);
  assert.match(material, /materialAction/);
});
