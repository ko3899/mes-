(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.MESCollector = Object.assign(root.MESCollector || {}, api);
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function createCollectorApi(client) {
    return {
      login: function (body) { return client.post('/api/login', body); },
      logout: function () { return client.post('/api/logout', {}); },
      userInfo: function () { return client.get('/api/user/info'); },
      summary: function () { return client.get('/api/collector/summary'); },
      tasks: function () { return client.get('/api/prod/task/list?mine=1&size=50'); },
      reports: function () { return client.get('/api/prod/report/list?mine=1&date=today&size=20'); },
      resolveBarcode: function (code) {
        return client.get('/api/collector/barcode/' + encodeURIComponent(code));
      },
      startTask: function (id) {
        return client.post('/api/prod/task/update', {id: id, status: 1});
      },
      addReport: function (body) { return client.post('/api/prod/report/add', body); },
      inspections: function () { return client.get('/api/qm/incoming/list?status=0&size=20'); },
      addInspection: function (body) { return client.post('/api/qm/incoming/add', body); },
      inventory: function () { return client.get('/api/inv/balance/list'); },
      borrowTool: function (body) { return client.post('/api/tool/borrow/add', body); },
    };
  }

  return {createCollectorApi: createCollectorApi};
}));
