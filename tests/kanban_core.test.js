const test = require('node:test');
const assert = require('node:assert/strict');
const {mapSnapshot, createKanbanController} = require('../frontend/static/js/kanban.js');

function response(status, payload) {
  return {status, ok: status >= 200 && status < 300, json: async () => payload};
}

test('kanban snapshot mapper handles zero totals and clamps progress', () => {
  const mapped = mapSnapshot({
    server_time: '2026-08-01T09:00:00',
    today_qualified: 0, today_defect: 0,
    active_order_count: 2,
    active_orders: [
      {order_no: 'WO1', product_name: '<img>', planned_qty: 10, completed_qty: 12, status: 1},
      {order_no: 'WO2', product_name: '产品B', planned_qty: 0, completed_qty: 0, status: 0},
    ],
    equipment: [{name: '运行', value: 0}, {name: '维修', value: 0}, {name: '停用', value: 0}],
    workshop_output: [], quality_alerts: {pending: 0, failed_today: 0},
  });
  assert.equal(mapped.yieldRate, '--');
  assert.equal(mapped.equipmentRate, '--');
  assert.equal(mapped.orders[0].progress, 100);
  assert.equal(mapped.orders[1].progress, 0);
  assert.equal(mapped.orders[0].productName, '<img>');
});

test('kanban snapshot mapper calculates rates from real values', () => {
  const mapped = mapSnapshot({
    today_qualified: 95, today_defect: 5, active_orders: [], active_order_count: 0,
    equipment: [{name: '运行', value: 8}, {name: '维修', value: 1}, {name: '停用', value: 1}],
    workshop_output: [], quality_alerts: {pending: 2, failed_today: 1},
  });
  assert.equal(mapped.yieldRate, '95%');
  assert.equal(mapped.equipmentRate, '80%');
  assert.equal(mapped.qualityAlerts, 3);
});

test('kanban controller reuses an in-flight refresh and renders once', async () => {
  let resolveFetch;
  const pending = new Promise(resolve => { resolveFetch = resolve; });
  const events = [];
  const controller = createKanbanController({
    fetchImpl: () => pending,
    view: {render: data => events.push(['render', data]), setOnline: time => events.push(['online', time]), showError() {}, showAuth() {}, markStale() {}},
    charts: {update: data => events.push(['charts', data])},
  });
  const first = controller.refresh();
  const second = controller.refresh();
  assert.equal(first, second);
  resolveFetch(response(200, {code: 0, data: {today_qualified: 1, today_defect: 0, active_orders: [], equipment: [], workshop_output: [], quality_alerts: {}}}));
  await first;
  assert.equal(events.filter(event => event[0] === 'render').length, 1);
  assert.equal(events.filter(event => event[0] === 'charts').length, 1);
});

test('kanban controller retains the last snapshot when refresh fails', async () => {
  const replies = [
    response(200, {code: 0, data: {server_time: '2026-08-01T09:00:00', today_qualified: 5, today_defect: 0, active_orders: [], equipment: [], workshop_output: [], quality_alerts: {}}}),
    response(503, {code: 503, message: '维护中'}),
  ];
  const events = [];
  const controller = createKanbanController({
    fetchImpl: async () => replies.shift(),
    view: {render: data => events.push(['render', data.qualified]), setOnline() {}, showError: message => events.push(['error', message]), showAuth() {}, markStale: message => events.push(['stale', message])},
    charts: {update() {}},
  });
  await controller.refresh();
  await controller.refresh();
  assert.deepEqual(events, [['render', 5], ['stale', '维护中']]);
});

test('kanban controller distinguishes initial failure and authentication', async () => {
  const replies = [response(500, {message: '启动失败'}), response(401, {message: '请登录'})];
  const events = [];
  const controller = createKanbanController({
    fetchImpl: async () => replies.shift(), charts: {update() {}},
    view: {render() {}, setOnline() {}, markStale() {}, showError: message => events.push(['error', message]), showAuth: message => events.push(['auth', message])},
  });
  await controller.refresh();
  await controller.refresh();
  assert.deepEqual(events, [['error', '启动失败'], ['auth', '请登录']]);
});
