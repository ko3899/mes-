const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {escapeHtml} = require('../admin/static/js/ui_utils.js');

const source = fs.readFileSync(
  path.resolve(__dirname, '../admin/static/js/pages/sys_ext.js'),
  'utf8'
);

function element() {
  return {
    innerHTML: '',
    textContent: '',
    value: '',
    placeholder: '',
    classList: {add() {}, remove() {}},
    querySelectorAll() { return []; },
  };
}

function nextTurn() {
  return new Promise((resolve) => setImmediate(resolve));
}

function loadContext(elements, apiImpl) {
  const context = vm.createContext({
    console,
    Promise,
    JSON,
    String,
    Number,
    Object,
    Array,
    Date,
    MESUI: {escapeHtml},
    escapeJson(value) {
      return JSON.stringify(value).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    },
    document: {
      getElementById(id) {
        return elements[id] || null;
      },
    },
    api: apiImpl,
    closeModal() {},
    alert() {},
  });
  vm.runInContext(source, context, {filename: 'sys_ext.js'});
  return context;
}

test('configLoad escapes every dynamic field and shows only configured state for secrets', async () => {
  const elements = {tb: element()};
  const context = loadContext(elements, () => Promise.resolve({
    code: 0,
    data: {
      list: [{
        id: 7,
        config_key: '<img src=x onerror=alert(1)>_api_key',
        config_type: '<svg onload=alert(2)>',
        description: '<img src=x onerror=alert(3)>',
        value_configured: true,
      }],
    },
  }));

  context.configLoad();
  await nextTurn();

  assert.doesNotMatch(elements.tb.innerHTML, /<(?:img|svg)\b/i);
  assert.match(elements.tb.innerHTML, /&lt;img src=x onerror=alert\(1\)&gt;_api_key/);
  assert.match(elements.tb.innerHTML, /&lt;svg onload=alert\(2\)&gt;/);
  assert.match(elements.tb.innerHTML, /&lt;img src=x onerror=alert\(3\)&gt;/);
  assert.match(elements.tb.innerHTML, /已配置/);
});

test('editing a configured secret escapes attributes and omits a blank replacement', async () => {
  const elements = {
    mTitle: element(),
    mBody: element(),
    modal: element(),
    tb: element(),
    f_value: element(),
    f_desc: {...element(), value: '更新后的说明'},
  };
  let savedBody = null;
  const context = loadContext(elements, (url, options) => {
    if (options) {
      savedBody = options.body;
      return Promise.resolve({code: 0});
    }
    return Promise.resolve({code: 0, data: {list: []}});
  });

  context.configEdit({
    config_key: 'danger"><img src=x onerror=alert(1)>_api_key',
    description: 'desc"><svg onload=alert(2)>',
    value_configured: true,
  });

  assert.doesNotMatch(elements.mBody.innerHTML, /<(?:img|svg)\b/i);
  assert.match(elements.mBody.innerHTML, /留空则保留现有值/);
  context.modalSaveHandler();
  await nextTurn();

  assert.equal(savedBody.config_key, 'danger"><img src=x onerror=alert(1)>_api_key');
  assert.equal(savedBody.description, '更新后的说明');
  assert.equal(Object.hasOwn(savedBody, 'config_value'), false);
});

test('announcement list escapes stored dynamic fields before rendering', async () => {
  const elements = {tb: element()};
  const context = loadContext(elements, () => Promise.resolve({
    code: 0,
    data: {
      list: [{
        id: 9,
        title: '<img src=x onerror=alert(1)>',
        notice_type: '<svg onload=alert(2)>',
        priority: '<img src=x onerror=alert(3)>',
        status: 1,
        publish_time: '<svg onload=alert(4)>',
      }],
    },
  }));

  context.annLoad();
  await nextTurn();

  assert.doesNotMatch(elements.tb.innerHTML, /<(?:img|svg)\b/i);
  assert.match(elements.tb.innerHTML, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(elements.tb.innerHTML, /&lt;svg onload=alert\(2\)&gt;/);
  assert.match(elements.tb.innerHTML, /&lt;img src=x onerror=alert\(3\)&gt;/);
  assert.match(elements.tb.innerHTML, /&lt;svg onload=alert\(4\)&gt;/);
});

test('system management lists escape all attacker-controlled stored fields', async () => {
  const cases = [
    {
      loader: 'loginLogLoad',
      row: {
        id: 1,
        username: '<img src=x onerror=alert(1)>',
        login_ip: '<svg onload=alert(2)>',
        status: 0,
        login_time: '<img src=x onerror=alert(3)>',
      },
    },
    {
      loader: 'ipLoad',
      row: {
        id: 2,
        ip_address: '<img src=x onerror=alert(1)>',
        description: '<svg onload=alert(2)>',
        status: 1,
      },
    },
    {
      loader: 'ptLoad',
      row: {
        id: 3,
        template_name: '<img src=x onerror=alert(1)>',
        biz_type: '<svg onload=alert(2)>',
        status: 1,
      },
    },
    {
      loader: 'ncLoad',
      row: {
        id: 4,
        channel_name: '<img src=x onerror=alert(1)>',
        channel_type: '<svg onload=alert(2)>',
        enabled: 1,
      },
    },
  ];

  for (const testCase of cases) {
    const elements = {tb: element()};
    const context = loadContext(elements, () => Promise.resolve({
      code: 0,
      data: {list: [testCase.row]},
    }));
    context[testCase.loader](1);
    await nextTurn();
    assert.doesNotMatch(
      elements.tb.innerHTML,
      /<(?:img|svg)\b/i,
      testCase.loader
    );
  }
});

test('online-user control is labeled as list removal, not forced logout', async () => {
  const elements = {tb: element()};
  const context = loadContext(elements, () => Promise.resolve({
    code: 0,
    data: [{
      user_id: 8,
      username: 'operator',
      login_ip: '127.0.0.1',
      login_time: '2026-07-28',
      last_active: '2026-07-28',
    }],
  }));

  context.onlineLoad();
  await nextTurn();

  assert.doesNotMatch(elements.tb.innerHTML, /强制下线/);
  assert.match(elements.tb.innerHTML, /移出在线列表/);
});
