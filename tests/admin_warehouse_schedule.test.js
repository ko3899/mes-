const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {escapeHtml, statusHtml} =
  require('../admin/static/js/ui_utils.js');

const projectRoot = path.resolve(__dirname, '..');

function browserElement() {
  return {
    innerHTML: '',
    textContent: '',
    value: '',
    style: {},
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
    ...globals,
  });
  [...prerequisitePaths, relativePath].forEach((scriptPath) => {
    const source = fs.readFileSync(path.join(projectRoot, scriptPath), 'utf8');
    vm.runInContext(source, context, {filename: scriptPath});
  });
  return context;
}

function nextTurn() {
  return new Promise((resolve) => setImmediate(resolve));
}

const pageCases = [
  {
    fn: 'renderWarehousePage',
    path: 'warehouse/list',
    title: '仓库设置',
    apiBase: '/api/warehouse',
    dataTable: 'inv_warehouse',
    fields: ['warehouse_name', 'code', 'address', 'status'],
  },
  {
    fn: 'renderAreaPage',
    path: 'warehouse/area',
    title: '库区设置',
    apiBase: '/api/area',
    dataTable: 'inv_area',
    fields: ['warehouse_id', 'area_name', 'code', 'status'],
    relations: [
      ['warehouse_id', '/api/warehouse/list?size=1000', 'warehouse_name'],
    ],
  },
  {
    fn: 'renderLocationPage',
    path: 'warehouse/location',
    title: '库位设置',
    apiBase: '/api/location',
    dataTable: 'inv_location',
    fields: ['area_id', 'location_name', 'code', 'status'],
    relations: [
      ['area_id', '/api/area/list?size=1000', 'area_name'],
    ],
  },
  {
    fn: 'renderArrivalPage',
    path: 'warehouse/arrival',
    title: '到货通知',
    apiBase: '/api/arrival',
    dataTable: 'inv_arrival_notice',
    fields: ['notice_no', 'supplier_id', 'expected_date', 'status', 'remark'],
    relations: [
      ['supplier_id', '/api/base/supplier/list?size=1000', 'supplier_name'],
    ],
  },
  {
    fn: 'renderTransactionPage',
    path: 'warehouse/transaction',
    title: '库存事务',
    apiBase: '/api/transaction',
    dataTable: 'inv_transaction_log',
    fields: [
      'trans_type', 'product_id', 'quantity', 'warehouse_id', 'area_id',
      'location_id', 'batch_no', 'ref_no', 'remark',
    ],
    relations: [
      ['product_id', '/api/base/product/all', 'product_name'],
      ['warehouse_id', '/api/warehouse/list?size=1000', 'warehouse_name'],
      ['area_id', '/api/area/list?size=1000', 'area_name'],
      ['location_id', '/api/location/list?size=1000', 'location_name'],
    ],
  },
  {
    fn: 'renderQualityTemplatePage',
    path: 'qm/template',
    title: '质检模板',
    apiBase: '/api/qm/template',
    dataTable: 'qm_inspect_template',
    fields: ['template_name', 'inspect_type', 'items', 'status'],
  },
  {
    fn: 'renderCheckProjectPage',
    path: 'eqp/check-project',
    title: '设备点检项目',
    apiBase: '/api/eqp/check-project',
    dataTable: 'eqp_check_project',
    fields: ['project_name', 'check_type', 'standard', 'method', 'status'],
  },
  {
    fn: 'renderScheduleCalendarPage',
    path: 'sched/calendar',
    title: '排班日历',
    apiBase: '/api/sched/calendar',
    dataTable: 'sched_calendar',
    fields: ['plan_id', 'work_date', 'shift_type', 'user_ids'],
    relations: [
      ['plan_id', '/api/sched/plan/list?size=1000', 'plan_name'],
    ],
  },
];

test('the eight warehouse, quality, equipment, and schedule renderers use real route configs', () => {
  const calls = [];
  const context = loadBrowserScript(
    'admin/static/js/pages/warehouse_schedule.js',
    {
      renderCrud(el, pagePath, config) {
        calls.push({el, pagePath, config});
      },
    },
  );

  pageCases.forEach((expected, index) => {
    const el = {page: expected.path};
    assert.equal(typeof context[expected.fn], 'function');
    context[expected.fn](el);
    const actual = calls[index];
    assert.equal(actual.el, el);
    assert.equal(actual.pagePath, expected.path);
    assert.equal(actual.config.t, expected.title);
    assert.equal(actual.config.apiBase, expected.apiBase);
    assert.equal(actual.config.dataTable, expected.dataTable);
    assert.deepEqual(
      Array.from(actual.config.f, (field) => field.k),
      expected.fields,
    );
    (expected.relations || []).forEach(([key, api, textKey]) => {
      const field = actual.config.f.find((item) => item.k === key);
      assert.equal(field.type, 'select');
      assert.equal(field.api, api);
      assert.equal(field.vk, 'id');
      assert.equal(field.tk, textKey);
    });
  });

  const arrival = calls[3].config;
  assert.equal(arrival.f[0].generated, true);
  const transaction = calls[4].config;
  assert.equal(transaction.actions.edit, false);
  assert.equal(transaction.actions.delete, false);
  assert.equal(transaction.actions.import, false);
  assert.notEqual(transaction.actions.add, false);
  assert.notEqual(transaction.actions.export, false);
});

test('renderPage dispatches all eight menu keys to their page renderers', () => {
  const content = browserElement();
  const calls = [];
  const globals = {
    document: {
      documentElement: {
        getAttribute() { return 'light'; },
        setAttribute() {},
      },
      getElementById(id) { return id === 'pageContent' ? content : null; },
      querySelector() { return null; },
      querySelectorAll() { return []; },
      addEventListener() {},
    },
    localStorage: {getItem() { return null; }, setItem() {}},
    alert() {},
    confirm() { return true; },
    renderHome() {},
  };
  pageCases.forEach((item) => {
    globals[item.fn] = function(el) {
      calls.push({fn: item.fn, el});
    };
  });
  const context = loadBrowserScript('admin/static/js/app.js', globals);

  pageCases.forEach((item, index) => {
    content.innerHTML = '';
    context.renderPage(item.path);
    assert.equal(calls[index].fn, item.fn);
    assert.equal(calls[index].el, content);
    assert.doesNotMatch(content.innerHTML, /页面建设中/);
  });
});

function loadCrud(config, rows) {
  const root = browserElement();
  const ids = [
    'addBtn', 'searchBtn', 'resetBtn', 'kw', 'exportBtn', 'importBtn',
    'pageSize', 'tb', 'pg',
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, browserElement()]));
  const document = {
    getElementById(id) {
      return root.innerHTML.includes(`id="${id}"`) ? elements[id] : null;
    },
  };
  const apiCalls = [];
  const openedUrls = [];
  const context = loadBrowserScript('admin/static/js/crud.js', {
    MESUI: {escapeHtml, statusHtml},
    localStorage: {getItem() { return null; }, setItem() {}},
    document,
    selectedRows: new Set(),
    updateBatchBar() {},
    alert() {},
    confirm() { return true; },
    openModal() {},
    window: {
      open(url) { openedUrls.push(url); },
    },
    api(url) {
      apiCalls.push(url);
      return Promise.resolve({
        code: 0,
        data: {list: rows || [], total: (rows || []).length},
      });
    },
  });
  context.renderCrud(root, 'not/the-route', config);
  return {context, root, elements, apiCalls, openedUrls};
}

test('renderCrud honors an explicit apiBase and keeps all actions enabled by default', async () => {
  const loaded = loadCrud({
    t: '默认动作',
    apiBase: '/api/real-route',
    dataTable: 'real_table',
    f: [{k: 'name', l: '名称'}],
  }, [{id: 7, name: '记录'}]);

  await nextTurn();

  assert.equal(loaded.context.curApiBase, '/api/real-route');
  assert.equal(loaded.apiCalls[0], '/api/real-route/list?page=1&size=15');
  assert.match(loaded.root.innerHTML, /id="addBtn"/);
  assert.match(loaded.root.innerHTML, /id="importBtn"/);
  assert.match(loaded.root.innerHTML, /id="exportBtn"/);
  assert.match(loaded.elements.tb.innerHTML, /crudEdit\(7\)/);
  assert.match(loaded.elements.tb.innerHTML, /crudDel\(7\)/);
  loaded.context.doExport();
  assert.deepEqual(loaded.openedUrls, ['/api/export/real_table']);
});

test('renderCrud action flags remove disallowed controls and row mutations', async () => {
  const loaded = loadCrud({
    t: '只读事务',
    apiBase: '/api/transaction',
    actions: {edit: false, delete: false, import: false},
    f: [{k: 'trans_type', l: '事务类型'}],
  }, [{id: 9, trans_type: 'IN'}]);

  await nextTurn();

  assert.match(loaded.root.innerHTML, /id="addBtn"/);
  assert.match(loaded.root.innerHTML, /id="exportBtn"/);
  assert.doesNotMatch(loaded.root.innerHTML, /id="importBtn"/);
  assert.doesNotMatch(loaded.elements.tb.innerHTML, /crudEdit/);
  assert.doesNotMatch(loaded.elements.tb.innerHTML, /crudDel/);
  assert.doesNotMatch(loaded.root.innerHTML, /<th>操作<\/th>/);
});

test('batch deletion cannot bypass a disabled delete action', () => {
  const alerts = [];
  let apiCalls = 0;
  const context = loadBrowserScript('admin/static/js/app.js', {
    document: {
      documentElement: {
        getAttribute() { return 'light'; },
        setAttribute() {},
      },
      getElementById() { return null; },
      querySelector() { return null; },
      querySelectorAll() { return []; },
      addEventListener() {},
    },
    localStorage: {getItem() { return null; }, setItem() {}},
    confirm() { return true; },
    alert(message) { alerts.push(message); },
  });
  context.selectedRows = new Set(['9']);
  context.curCrudActions = {delete: false};
  context.curApiBase = '/api/transaction';
  context.api = function() {
    apiCalls += 1;
    return Promise.resolve({code: 0});
  };

  context.batchDelete();

  assert.equal(apiCalls, 0);
  assert.deepEqual(alerts, ['当前页面不允许删除']);
});

test('the batch delete control is hidden when delete is disabled', () => {
  const deleteButton = browserElement();
  const count = browserElement();
  const batchBar = {
    ...browserElement(),
    querySelector(selector) {
      if (selector === '.btn-red') return deleteButton;
      if (selector === '.count') return count;
      return null;
    },
  };
  const context = loadBrowserScript('admin/static/js/app.js', {
    document: {
      documentElement: {
        getAttribute() { return 'light'; },
        setAttribute() {},
      },
      getElementById(id) { return id === 'batchBar' ? batchBar : null; },
      querySelector() { return null; },
      querySelectorAll() { return []; },
      addEventListener() {},
    },
    localStorage: {getItem() { return null; }, setItem() {}},
    alert() {},
    confirm() { return true; },
  });
  context.selectedRows = new Set(['9']);
  context.curCrudActions = {delete: false};

  context.updateBatchBar();

  assert.equal(deleteButton.style.display, 'none');
});

test('disabled actions also guard their callable entry points', async () => {
  let modalCalls = 0;
  let apiCalls = 0;
  let exportCalls = 0;
  const alerts = [];
  const elements = {
    mTitle: browserElement(),
    mBody: browserElement(),
    importFile: browserElement(),
    modal: browserElement(),
  };
  const context = loadBrowserScript('admin/static/js/crud.js', {
    MESUI: {escapeHtml, statusHtml},
    localStorage: {getItem() { return null; }, setItem() {}},
    document: {
      getElementById(id) { return elements[id] || null; },
    },
    selectedRows: new Set(),
    updateBatchBar() {},
    alert(message) { alerts.push(message); },
    confirm() { return true; },
    openModal() { modalCalls += 1; },
    window: {open() { exportCalls += 1; }},
    api() {
      apiCalls += 1;
      return Promise.resolve({code: 0});
    },
  });
  context.curCrudActions = {
    add: false,
    edit: false,
    delete: false,
    import: false,
    export: false,
  };
  context.curFields = [{k: 'name', l: '名称'}];
  context.curApiBase = '/api/transaction';
  context.currentRowsById = {9: {id: 9, name: '事务'}};

  context.crudAdd();
  context.crudEdit(9);
  context.crudDel(9);
  context.doExport();
  context.doImport();
  await nextTurn();

  assert.equal(modalCalls, 0);
  assert.equal(apiCalls, 0);
  assert.equal(exportCalls, 0);
  assert.equal(alerts.length, 5);
});

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return {promise, resolve};
}

test('an older list response cannot overwrite a newly rendered page', async () => {
  const root = browserElement();
  const elements = Object.fromEntries(
    ['addBtn', 'searchBtn', 'resetBtn', 'kw', 'exportBtn', 'importBtn',
      'pageSize', 'tb', 'pg'].map((id) => [id, browserElement()]),
  );
  const first = deferred();
  const second = deferred();
  let apiCall = 0;
  const context = loadBrowserScript('admin/static/js/crud.js', {
    MESUI: {escapeHtml, statusHtml},
    localStorage: {getItem() { return null; }, setItem() {}},
    document: {
      getElementById(id) {
        return root.innerHTML.includes(`id="${id}"`) ? elements[id] : null;
      },
    },
    selectedRows: new Set(),
    updateBatchBar() {},
    alert() {},
    confirm() { return true; },
    openModal() {},
    api() {
      apiCall += 1;
      return apiCall === 1 ? first.promise : second.promise;
    },
  });

  context.renderCrud(root, 'page/one', {
    t: '第一页',
    apiBase: '/api/one',
    f: [{k: 'one_name', l: '一页名称'}],
  });
  context.renderCrud(root, 'page/two', {
    t: '第二页',
    apiBase: '/api/two',
    f: [{k: 'two_name', l: '二页名称'}],
  });
  second.resolve({
    code: 0,
    data: {list: [{id: 2, two_name: '新页记录'}], total: 1},
  });
  await nextTurn();
  first.resolve({
    code: 0,
    data: {list: [{id: 1, one_name: '旧页记录'}], total: 1},
  });
  await nextTurn();

  assert.match(elements.tb.innerHTML, /新页记录/);
  assert.doesNotMatch(elements.tb.innerHTML, /旧页记录/);
  assert.match(elements.tb.innerHTML, /crudEdit\(2\)/);
  assert.doesNotMatch(elements.tb.innerHTML, /crudEdit\(1\)/);
});

test('a pending delete cannot reload a page after navigation', async () => {
  const deletion = deferred();
  let reloads = 0;
  const context = loadBrowserScript('admin/static/js/crud.js', {
    MESUI: {escapeHtml, statusHtml},
    localStorage: {getItem() { return null; }, setItem() {}},
    selectedRows: new Set(),
    confirm() { return true; },
    alert() {},
    api() { return deletion.promise; },
  });
  context.curCrudActions = {delete: true};
  context.crudRenderToken = 10;
  context.curApiBase = '/api/old-page';
  context.crudLoad = function() { reloads += 1; };

  context.crudDel(7);
  context.crudRenderToken = 11;
  context.curApiBase = '/api/new-page';
  deletion.resolve({code: 0});
  await nextTurn();

  assert.equal(reloads, 0);
});

test('a pending import cannot update or close a page after navigation', async () => {
  const upload = deferred();
  const elements = {
    mTitle: browserElement(),
    mBody: browserElement(),
    modal: browserElement(),
    importFile: {
      ...browserElement(),
      files: [{name: 'rows.csv', size: 32}],
    },
    importPreview: browserElement(),
    importResult: browserElement(),
  };
  let cacheInvalidations = 0;
  let closes = 0;
  let reloads = 0;
  let delayed = null;
  class FormDataDouble {
    append() {}
  }
  const context = loadBrowserScript('admin/static/js/crud.js', {
    MESUI: {escapeHtml, statusHtml},
    localStorage: {getItem() { return null; }, setItem() {}},
    document: {
      getElementById(id) { return elements[id] || null; },
    },
    selectedRows: new Set(),
    FormData: FormDataDouble,
    fetch() { return upload.promise; },
    clearApiCache() { cacheInvalidations += 1; },
    closeModal() { closes += 1; },
    setTimeout(callback) { delayed = callback; },
    alert() {},
  });
  context.curCrudActions = {import: true};
  context.crudRenderToken = 20;
  context.curApiBase = '/api/old-page';
  context.curDataTable = 'inv_warehouse';
  context.crudLoad = function() { reloads += 1; };

  context.doImport();
  context.modalSaveHandler();
  const loadingHtml = elements.importResult.innerHTML;
  context.crudRenderToken = 21;
  context.curApiBase = '/api/new-page';
  upload.resolve({
    json() {
      return Promise.resolve({
        code: 0,
        message: '导入成功',
        data: {success: 1, errors: []},
      });
    },
  });
  await nextTurn();
  if (delayed) delayed();

  assert.equal(cacheInvalidations, 1);
  assert.equal(elements.importResult.innerHTML, loadingHtml);
  assert.equal(closes, 0);
  assert.equal(reloads, 0);
});

test('a stale select response cannot open a modal after page invalidation', async () => {
  const options = deferred();
  let modalShown = false;
  const elements = {
    mTitle: browserElement(),
    mBody: browserElement(),
    modal: {
      ...browserElement(),
      classList: {
        add() { modalShown = true; },
        remove() {},
      },
    },
  };
  const context = loadBrowserScript('admin/static/js/modal.js', {
    MESUI: {escapeHtml, statusHtml},
    document: {
      getElementById(id) { return elements[id] || null; },
    },
    api() { return options.promise; },
    alert() {},
  });
  context.crudRenderToken = 1;
  context.curApiBase = '/api/area';

  context.openModal('新增', [{
    k: 'warehouse_id',
    l: '仓库',
    type: 'select',
    api: '/api/warehouse/list',
    vk: 'id',
    tk: 'warehouse_name',
  }], {});
  context.crudRenderToken = 2;
  context.curApiBase = '/api/location';
  options.resolve({code: 0, data: []});
  await nextTurn();

  assert.equal(modalShown, false);
});

test('modal save keeps the API, fields, and edit id captured when it opened', async () => {
  const elements = {
    mTitle: browserElement(),
    mBody: browserElement(),
    modal: browserElement(),
    f_name: {...browserElement(), value: '原页面数据'},
  };
  const calls = [];
  const context = loadBrowserScript('admin/static/js/modal.js', {
    MESUI: {escapeHtml, statusHtml},
    document: {
      getElementById(id) { return elements[id] || null; },
    },
    api(url, options) {
      calls.push({url, options});
      return Promise.resolve({code: 0});
    },
    closeModal() {},
    crudLoad() {},
    alert() {},
  });
  context.crudRenderToken = 4;
  context.curApiBase = '/api/original';
  context.curFields = [{k: 'name', l: '名称'}];
  context.editId = 12;
  context.openModalSync('编辑', context.curFields, {name: '旧值'});
  context.curApiBase = '/api/new-page';
  context.curFields = [{k: 'other', l: '其他'}];
  context.editId = 99;

  context.modalSaveHandler();
  await nextTurn();

  assert.equal(calls[0].url, '/api/original/update');
  assert.equal(calls[0].options.body.id, 12);
  assert.equal(calls[0].options.body.name, '原页面数据');
});

test('a modal invalidated by navigation cannot submit its old form', () => {
  const elements = {
    mTitle: browserElement(),
    mBody: browserElement(),
    modal: browserElement(),
    f_name: {...browserElement(), value: '不应提交'},
  };
  let apiCalls = 0;
  const alerts = [];
  const context = loadBrowserScript('admin/static/js/modal.js', {
    MESUI: {escapeHtml, statusHtml},
    document: {
      getElementById(id) { return elements[id] || null; },
    },
    api() {
      apiCalls += 1;
      return Promise.resolve({code: 0});
    },
    crudLoad() {},
    alert(message) { alerts.push(message); },
  });
  context.crudRenderToken = 7;
  context.curApiBase = '/api/original';
  context.curFields = [{k: 'name', l: '名称'}];
  context.editId = null;
  context.openModalSync('新增', context.curFields, {});
  context.crudRenderToken = 8;

  context.modalSaveHandler();

  assert.equal(apiCalls, 0);
  assert.deepEqual(alerts, ['页面已切换，请重新操作']);
});

test('generated fields remain visible in the table but are excluded from forms', async () => {
  const fields = [
    {k: 'notice_no', l: '通知单号', generated: true},
    {k: 'remark', l: '备注'},
  ];
  const loaded = loadCrud({
    t: '到货通知',
    apiBase: '/api/arrival',
    f: fields,
  }, [{id: 3, notice_no: 'AN202607280001', remark: '待收货'}]);
  await nextTurn();
  assert.match(loaded.root.innerHTML, /通知单号/);
  assert.match(loaded.elements.tb.innerHTML, /AN202607280001/);

  const modalElements = {
    mTitle: browserElement(),
    mBody: browserElement(),
    modal: browserElement(),
  };
  const modal = loadBrowserScript('admin/static/js/modal.js', {
    MESUI: {escapeHtml, statusHtml},
    document: {
      getElementById(id) { return modalElements[id] || null; },
    },
    api() { return Promise.resolve({code: 0}); },
    alert() {},
  });
  modal.curFields = fields;
  modal.openModalSync('新增', fields, {});

  assert.doesNotMatch(modalElements.mBody.innerHTML, /通知单号/);
  assert.doesNotMatch(modalElements.mBody.innerHTML, /id="f_notice_no"/);
  assert.match(modalElements.mBody.innerHTML, /id="f_remark"/);
});
