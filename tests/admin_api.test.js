const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const apiSource = fs.readFileSync(
  path.resolve(__dirname, '../admin/static/js/api.js'),
  'utf8'
);

class HeadersDouble {
  constructor(values = {}) {
    this._values = new Map(
      Object.entries(values).map(([key, value]) => [key.toLowerCase(), String(value)])
    );
  }

  append(name, value) {
    const key = String(name).toLowerCase();
    const next = String(value);
    const current = this._values.get(key);
    this._values.set(key, current ? `${current}, ${next}` : next);
  }

  delete(name) {
    this._values.delete(String(name).toLowerCase());
  }

  get(name) {
    return this._values.get(String(name).toLowerCase()) || null;
  }

  has(name) {
    return this._values.has(String(name).toLowerCase());
  }

  set(name, value) {
    this._values.set(String(name).toLowerCase(), String(value));
  }

  forEach(callback) {
    this._values.forEach((value, key) => callback(value, key, this));
  }

  entries() {
    return this._values.entries();
  }

  keys() {
    return this._values.keys();
  }

  values() {
    return this._values.values();
  }

  getSetCookie() {
    return [];
  }

  [Symbol.iterator]() {
    return this.entries();
  }
}

class ResponseDouble {
  constructor(body, options = {}) {
    this._body = body;
    this.status = options.status === undefined ? 200 : options.status;
    this.statusText = options.statusText || '';
    this.headers = new HeadersDouble(options.headers || {
      'content-type': 'application/json; charset=utf-8',
    });
    this.url = options.url || 'http://localhost.test/api';
    this.redirected = Boolean(options.redirected);
    this.type = options.type || 'basic';
    this.body = null;
    this.bodyUsed = false;
    this.ok = this.status >= 200 && this.status < 300;
  }

  async json() {
    this.bodyUsed = true;
    if (typeof this._body === 'string') return JSON.parse(this._body);
    return this._body;
  }

  async text() {
    this.bodyUsed = true;
    return typeof this._body === 'string' ? this._body : JSON.stringify(this._body);
  }

  async arrayBuffer() {
    this.bodyUsed = true;
    return new TextEncoder().encode(await this.text()).buffer;
  }

  async blob() {
    this.bodyUsed = true;
    return new Blob([await this.text()], {
      type: this.headers.get('content-type') || '',
    });
  }

  async formData() {
    throw new TypeError('Response body is not form data');
  }

  clone() {
    return new ResponseDouble(this._body, {
      status: this.status,
      statusText: this.statusText,
      headers: Object.fromEntries(this.headers),
      url: this.url,
      redirected: this.redirected,
      type: this.type,
    });
  }
}

function jsonResponse(body, status = 200) {
  return new ResponseDouble(body, {
    status,
    headers: {'content-type': 'application/json; charset=utf-8'},
  });
}

function loadApi(sequence, options = {}) {
  let calls = 0;
  let logoutCalls = 0;
  const context = vm.createContext({
    console: {error() {}, log() {}, warn() {}},
    Date,
    JSON,
    Promise,
    Object,
    String,
    doLogout() {
      logoutCalls += 1;
      if (options.logoutError) throw options.logoutError;
    },
    fetch: async () => {
      const next = sequence[Math.min(calls, sequence.length - 1)];
      calls += 1;
      if (next instanceof Error) throw next;
      return next;
    },
  });
  vm.runInContext(apiSource, context, {filename: 'admin/static/js/api.js'});
  return {
    api: context.api,
    calls: () => calls,
    logoutCalls: () => logoutCalls,
  };
}

test('GET responses are cached during the cache TTL', async () => {
  const loaded = loadApi([
    jsonResponse({code: 0, data: ['cached']}),
    jsonResponse({code: 0, data: ['unexpected']}),
  ]);

  const first = await loaded.api('/api/items');
  const second = await loaded.api('/api/items');

  assert.equal(first.data[0], 'cached');
  assert.equal(second.data[0], 'cached');
  assert.equal(loaded.calls(), 1);
});

test('failed GET responses are not cached', async () => {
  const loaded = loadApi([
    jsonResponse({code: 503, message: '服务暂时不可用'}),
    jsonResponse({code: 0, data: ['recovered']}),
  ]);

  const failed = await loaded.api('/api/items');
  const retried = await loaded.api('/api/items');

  assert.equal(failed.code, 503);
  assert.equal(retried.data[0], 'recovered');
  assert.equal(loaded.calls(), 2);
});

test('successful write invalidates cached GET data', async () => {
  const loaded = loadApi([
    jsonResponse({code: 0, data: ['old']}),
    jsonResponse({code: 0}),
    jsonResponse({code: 0, data: ['new']}),
  ]);

  await loaded.api('/api/items');
  await loaded.api('/api/items', {method: 'POST', body: {id: 1}});
  const refreshed = await loaded.api('/api/items');

  assert.equal(refreshed.data[0], 'new');
  assert.equal(loaded.calls(), 3);
});

test('failed write remains an error and does not masquerade as success', async () => {
  const loaded = loadApi([
    jsonResponse({code: 503, message: '保存失败'}, 503),
  ]);

  const result = await loaded.api('/api/items', {
    method: 'POST',
    body: {id: 1},
  });

  assert.equal(result.code, 503);
  assert.equal(result.message, '保存失败');
  assert.notEqual(result.code, 0);
});

test('non-JSON HTTP 404 is normalized to an error object', async () => {
  const loaded = loadApi([
    new ResponseDouble('<!doctype html><h1>Not Found</h1>', {
      status: 404,
      headers: {'content-type': 'text/html; charset=utf-8'},
    }),
  ]);

  const result = await loaded.api('/missing');

  assert.equal(result.code, 404);
  assert.match(result.message, /HTTP 404/);
});

test('JSON HTTP errors preserve the service code and message', async () => {
  const loaded = loadApi([
    jsonResponse({code: 422, message: '字段校验失败'}, 400),
  ]);

  const result = await loaded.api('/api/items');

  assert.equal(result.code, 422);
  assert.equal(result.message, '字段校验失败');
});

test('network failures return a consistent error object', async () => {
  const loaded = loadApi([new TypeError('connection refused')]);

  const result = await loaded.api('/api/items');

  assert.equal(result.code, -1);
  assert.equal(result.message, '网络请求失败');
});

test('401 responses still trigger logout and remain inspectable', async () => {
  const loaded = loadApi([
    jsonResponse({code: 401, message: '登录已失效'}, 401),
  ]);

  const result = await loaded.api('/api/items');

  assert.equal(loaded.logoutCalls(), 1);
  assert.equal(result.code, 401);
  assert.equal(result.message, '登录已失效');
});

test('non-JSON 401 responses also trigger logout', async () => {
  const loaded = loadApi([
    new ResponseDouble('<!doctype html><h1>Unauthorized</h1>', {
      status: 401,
      headers: {'content-type': 'text/html; charset=utf-8'},
    }),
  ]);

  const result = await loaded.api('/api/items');

  assert.equal(loaded.logoutCalls(), 1);
  assert.equal(result.code, 401);
  assert.match(result.message, /HTTP 401/);
});

test('programming errors during response handling are not mislabeled as network failures', async () => {
  const programmingError = new Error('logout implementation bug');
  const loaded = loadApi([
    jsonResponse({code: 401, message: '登录已失效'}, 401),
  ], {logoutError: programmingError});

  await assert.rejects(
    loaded.api('/api/items'),
    /logout implementation bug/
  );
});
