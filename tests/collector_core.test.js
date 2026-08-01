const test = require('node:test');
const assert = require('node:assert/strict');

const core = require('../frontend/static/js/core.js');
const {createCollectorApi} = require('../frontend/static/js/api.js');
const {createOfflineQueue} = require('../frontend/static/js/offline_queue.js');
const {createScanner} = require('../frontend/static/js/scanner.js');

function memoryStorage() {
  const values = new Map();
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
}

test('collector API exposes semantic endpoint methods', async () => {
  const calls = [];
  const client = {
    get: async url => { calls.push(['GET', url]); return {ok: true}; },
    post: async (url, body) => { calls.push(['POST', url, body]); return {ok: true}; },
  };
  const api = createCollectorApi(client);
  await api.summary();
  await api.tasks();
  await api.resolveBarcode('WO 1');
  await api.addReport({qualified_qty: 1});
  assert.deepEqual(calls, [
    ['GET', '/api/collector/summary'],
    ['GET', '/api/prod/task/list?mine=1&size=50'],
    ['GET', '/api/collector/barcode/WO%201'],
    ['POST', '/api/prod/report/add', {qualified_qty: 1}],
  ]);
});

test('collector core escapes dynamic text and classifies scan codes', () => {
  assert.equal(
    core.escapeHtml('<img src=x onerror=alert(1)>'),
    '&lt;img src=x onerror=alert(1)&gt;'
  );
  assert.deepEqual(core.classifyBarcode(' wo0001 '), {
    kind: 'workorder', code: 'WO0001',
  });
  assert.deepEqual(core.classifyBarcode('tk0002'), {
    kind: 'task', code: 'TK0002',
  });
  assert.deepEqual(core.classifyBarcode('p-100'), {
    kind: 'product', code: 'P-100',
  });
  assert.equal(core.classifyBarcode('  '), null);
});

test('collector API response normalization distinguishes failure classes', () => {
  assert.deepEqual(
    core.normalizeApiResponse({status: 401, ok: false}, {code: 401, message: '请登录'}),
    {ok: false, type: 'auth', status: 401, message: '请登录'}
  );
  assert.deepEqual(
    core.normalizeApiResponse({status: 400, ok: false}, {code: 400, message: '余量不足'}),
    {ok: false, type: 'business', status: 400, message: '余量不足'}
  );
  assert.deepEqual(
    core.normalizeApiResponse({status: 503, ok: false}, {code: 503}),
    {ok: false, type: 'server', status: 503, message: '服务器暂时不可用'}
  );
  assert.deepEqual(
    core.normalizeApiResponse({status: 200, ok: true}, null),
    {ok: false, type: 'invalid', status: 200, message: '服务器返回了无效数据'}
  );
});

test('offline queue is isolated by user and replays in FIFO order', async () => {
  const storage = memoryStorage();
  const calls = [];
  const options = {
    storage,
    now: () => '2026-08-01T08:00:00',
    makeId: (() => { let id = 0; return () => `op-${++id}`; })(),
    api: async item => { calls.push(item.id); return {ok: true}; },
  };
  const first = createOfflineQueue({...options, userId: 1});
  const second = createOfflineQueue({...options, userId: 2});
  first.enqueue({url: '/api/prod/report/add', body: {qualified_qty: 1}});
  first.enqueue({url: '/api/prod/report/add', body: {qualified_qty: 2}});
  second.enqueue({url: '/api/prod/report/add', body: {qualified_qty: 9}});

  assert.equal(first.list().length, 2);
  assert.equal(second.list().length, 1);
  assert.equal(first.list()[0].body.client_operation_id, 'op-1');
  await first.sync();
  assert.deepEqual(calls, ['op-1', 'op-2']);
  assert.equal(first.list().length, 0);
  assert.equal(second.list().length, 1);
});

test('offline queue retains retryable errors and marks business failures', async () => {
  const storage = memoryStorage();
  const responses = [
    {ok: false, type: 'network', message: '断网'},
    {ok: false, type: 'business', message: '任务已完成'},
  ];
  const queue = createOfflineQueue({
    storage, userId: 3,
    now: () => '2026-08-01T08:00:00',
    makeId: (() => { let id = 0; return () => `retry-${++id}`; })(),
    api: async () => responses.shift(),
  });
  queue.enqueue({url: '/api/prod/report/add', body: {qualified_qty: 1}});

  await queue.sync();
  assert.equal(queue.list()[0].status, 'pending');
  assert.equal(queue.list()[0].attempts, 1);
  await queue.sync();
  assert.equal(queue.list()[0].status, 'needs_attention');
  assert.deepEqual(queue.counts(), {pending: 0, needsAttention: 1, total: 1});
});

test('scanner mounts one listener and fully releases input and camera', async () => {
  const listeners = new Map();
  const input = {
    addEventListener(type, handler) { listeners.set(type, handler); },
    removeEventListener(type, handler) {
      if (listeners.get(type) === handler) listeners.delete(type);
    },
  };
  const stopped = [];
  const stream = {getTracks: () => [{stop: () => stopped.push(1)}, {stop: () => stopped.push(2)}]};
  const scanner = createScanner({
    navigator: {mediaDevices: {getUserMedia: async () => stream}},
    BarcodeDetector: class { async detect() { return []; } },
    requestFrame: () => 1,
    cancelFrame: () => {},
  });

  scanner.mount(input, () => {});
  scanner.mount(input, () => {});
  assert.equal(listeners.size, 1);
  assert.equal((await scanner.startCamera({})).supported, true);
  scanner.unmount();
  assert.equal(listeners.size, 0);
  assert.equal(stopped.length, 2);
});

test('scanner reports unsupported camera without requesting permission', async () => {
  let requested = false;
  const scanner = createScanner({
    navigator: {mediaDevices: {getUserMedia: async () => { requested = true; }}},
    BarcodeDetector: null,
  });
  assert.deepEqual(await scanner.startCamera({}), {supported: false});
  assert.equal(requested, false);
});
