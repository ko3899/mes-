const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { escapeHtml, menuPage, statusHtml } =
  require('../admin/static/js/ui_utils.js');

const projectRoot = path.resolve(__dirname, '..');

function browserElement() {
  return {
    innerHTML: '',
    textContent: '',
    value: '',
    classList: {
      add() {},
      remove() {},
      contains() { return false; },
    },
  };
}

function loadBrowserScript(relativePath, globals = {}, prerequisitePaths = []) {
  const context = vm.createContext({
    console,
    Set,
    Promise,
    JSON,
    Number,
    String,
    Math,
    Object,
    Array,
    Date,
    isNaN,
    encodeURIComponent,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    ...globals,
  });
  [...prerequisitePaths, relativePath].forEach((scriptPath) => {
    const source = fs.readFileSync(path.join(projectRoot, scriptPath), 'utf8');
    vm.runInContext(source, context, { filename: scriptPath });
  });
  return context;
}

function nextTurn() {
  return new Promise((resolve) => setImmediate(resolve));
}

function createImportFlow(response) {
  const elements = {
    mTitle: browserElement(),
    mBody: browserElement(),
    importFile: {
      ...browserElement(),
      files: [{
        name: '<img src=x onerror=alert(1)>.csv',
        size: 1024,
      }],
    },
    importPreview: browserElement(),
    importResult: browserElement(),
    modal: browserElement(),
  };
  class FormDataDouble {
    constructor() {
      this.entries = [];
    }
    append(key, value) {
      this.entries.push([key, value]);
    }
  }
  const context = loadBrowserScript('admin/static/js/crud.js', {
    MESUI: {escapeHtml, statusHtml},
    localStorage: {getItem() { return null; }, setItem() {}},
    document: {getElementById(id) { return elements[id] || null; }},
    curApiBase: '/api/base/workshop',
    selectedRows: new Set(),
    FormData: FormDataDouble,
    fetch() {
      return Promise.resolve({
        json() {
          return Promise.resolve(response);
        },
      });
    },
    setTimeout() {},
    alert() {},
  });
  context.doImport();
  return {context, elements};
}

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

test('escapeHtml covers all attribute-breaking characters', () => {
  assert.equal(
    escapeHtml(`&<>"'`),
    '&amp;&lt;&gt;&quot;&#39;'
  );
});

test('crudLoad escapes row data and edits through the stored row id', async () => {
  const elements = {
    kw: {...browserElement(), value: ''},
    tb: browserElement(),
    pg: browserElement(),
  };
  const maliciousName = '<img src=x onerror=alert(1)>';
  const maliciousCreatedAt = '<svg onload=alert(2)>';
  let openedRow = null;
  const context = loadBrowserScript('admin/static/js/crud.js', {
    MESUI: {escapeHtml, statusHtml},
    localStorage: {getItem() { return null; }, setItem() {}},
    document: {getElementById(id) { return elements[id] || null; }},
    curApiBase: '/api/base/workshop',
    curFields: [{k: 'workshop_name', l: '车间名称'}],
    selectedRows: new Set(),
    openModal(title, fields, row) { openedRow = row; },
    updateBatchBar() {},
    alert() {},
    confirm() { return true; },
  }, ['admin/static/js/api.js']);
  context.api = function() {
    return Promise.resolve({
      code: 0,
      data: {
        list: [{
          id: 7,
          workshop_name: maliciousName,
          created_at: maliciousCreatedAt,
        }],
        total: 1,
      },
    });
  };

  context.crudLoad(1);
  await nextTurn();

  assert.doesNotMatch(elements.tb.innerHTML, /<img\b/i);
  assert.doesNotMatch(elements.tb.innerHTML, /<svg\b/i);
  assert.match(elements.tb.innerHTML, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(elements.tb.innerHTML, /onclick="crudEdit\(7\)"/);
  assert.doesNotMatch(elements.tb.innerHTML, /crudEdit\(\{/);

  context.crudEdit(7);
  assert.equal(openedRow.id, 7);
  assert.equal(openedRow.workshop_name, maliciousName);
});

test('openModalSync escapes labels, option text, and attribute values', () => {
  const elements = {
    mTitle: browserElement(),
    mBody: browserElement(),
    modal: browserElement(),
  };
  const maliciousValue = `"><img src=x onerror=alert(1)>`;
  const fields = [
    {k: 'name', l: '<svg onload=alert(2)>', r: true},
    {
      k: 'state',
      l: '状态',
      s: [{v: maliciousValue, t: '<img src=x onerror=alert(3)>'}],
    },
  ];
  const context = loadBrowserScript('admin/static/js/modal.js', {
    MESUI: {escapeHtml, statusHtml},
    document: {getElementById(id) { return elements[id] || null; }},
    api() { return Promise.resolve({code: 0}); },
    alert() {},
  });
  context.curFields = fields;
  context.openModalSync('编辑', fields, {
    name: maliciousValue,
    state: maliciousValue,
  });

  assert.doesNotMatch(elements.mBody.innerHTML, /<svg\b/i);
  assert.doesNotMatch(elements.mBody.innerHTML, /<img\b/i);
  assert.match(elements.mBody.innerHTML, /&lt;svg onload=alert\(2\)&gt;/);
  assert.match(
    elements.mBody.innerHTML,
    /value="&quot;&gt;&lt;img src=x onerror=alert\(1\)&gt;"/
  );
  assert.match(
    elements.mBody.innerHTML,
    /&lt;img src=x onerror=alert\(3\)&gt;/
  );
});

test('showCompareResult escapes record keys and values', () => {
  const elements = {mBody: browserElement()};
  const document = {
    documentElement: {
      getAttribute() { return 'light'; },
      setAttribute() {},
    },
    getElementById(id) { return elements[id] || browserElement(); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {},
  };
  const context = loadBrowserScript('admin/static/js/app.js', {
    MESUI: {escapeHtml, statusHtml},
    document,
    localStorage: {getItem() { return null; }, setItem() {}},
    alert() {},
    confirm() { return true; },
  });

  context.showCompareResult(
    {'<img src=x onerror=alert(1)>': '<svg onload=alert(2)>'},
    {'<img src=x onerror=alert(1)>': '安全值'},
  );

  assert.doesNotMatch(elements.mBody.innerHTML, /<img\b/i);
  assert.doesNotMatch(elements.mBody.innerHTML, /<svg\b/i);
  assert.match(elements.mBody.innerHTML, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(elements.mBody.innerHTML, /&lt;svg onload=alert\(2\)&gt;/);
});

test('doImport escapes the selected file name in its real change event', () => {
  const {elements} = createImportFlow({
    code: 0,
    message: '导入成功',
    data: {success: 1, errors: []},
  });

  elements.importFile.onchange.call(elements.importFile);

  assert.doesNotMatch(elements.importPreview.innerHTML, /<img\b/i);
  assert.match(
    elements.importPreview.innerHTML,
    /&lt;img src=x onerror=alert\(1\)&gt;\.csv/
  );
});

test('doImport escapes successful response messages and row errors', async () => {
  const {context, elements} = createImportFlow({
    code: 0,
    message: '<img src=x onerror=alert(2)>',
    data: {
      success: 0,
      errors: ['<svg onload=alert(3)>'],
    },
  });

  context.modalSaveHandler();
  await nextTurn();

  assert.doesNotMatch(elements.importResult.innerHTML, /<img\b/i);
  assert.doesNotMatch(elements.importResult.innerHTML, /<svg\b/i);
  assert.match(
    elements.importResult.innerHTML,
    /&lt;img src=x onerror=alert\(2\)&gt;/
  );
  assert.match(
    elements.importResult.innerHTML,
    /&lt;svg onload=alert\(3\)&gt;/
  );
});

test('doImport escapes failed response messages', async () => {
  const {context, elements} = createImportFlow({
    code: 400,
    message: '<img src=x onerror=alert(4)>',
  });

  context.modalSaveHandler();
  await nextTurn();

  assert.doesNotMatch(elements.importResult.innerHTML, /<img\b/i);
  assert.match(
    elements.importResult.innerHTML,
    /&lt;img src=x onerror=alert\(4\)&gt;/
  );
});
