(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.MESCollector = Object.assign(root.MESCollector || {}, api);
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>'"]/g, function (char) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[char];
    });
  }

  function classifyBarcode(value) {
    var code = String(value == null ? '' : value).trim().toUpperCase();
    if (!code) return null;
    if (code.indexOf('WO') === 0) return {kind: 'workorder', code: code};
    if (code.indexOf('TK') === 0) return {kind: 'task', code: code};
    return {kind: 'product', code: code};
  }

  function normalizeApiResponse(response, payload) {
    var status = Number(response && response.status) || 0;
    if (status === 401 || payload && payload.code === 401) {
      return {ok: false, type: 'auth', status: 401, message: payload && payload.message || '请先登录'};
    }
    if (!payload || typeof payload !== 'object') {
      return {ok: false, type: 'invalid', status: status, message: '服务器返回了无效数据'};
    }
    if (status >= 500) {
      return {ok: false, type: 'server', status: status, message: payload.message || '服务器暂时不可用'};
    }
    if (status >= 400 || payload.code && payload.code !== 0) {
      return {ok: false, type: 'business', status: status || payload.code, message: payload.message || '操作未完成'};
    }
    return {ok: true, type: 'success', status: status || 200, data: payload.data, message: payload.message || ''};
  }

  function createApiClient(fetchImpl) {
    var doFetch = fetchImpl || root.fetch;
    async function request(url, options) {
      var opts = Object.assign({headers: {'Content-Type': 'application/json'}}, options || {});
      if (opts.body && typeof opts.body !== 'string') opts.body = JSON.stringify(opts.body);
      try {
        var response = await doFetch(url, opts);
        var payload = null;
        try { payload = await response.json(); } catch (ignore) {}
        return normalizeApiResponse(response, payload);
      } catch (error) {
        return {ok: false, type: 'network', status: 0, message: '网络连接失败', error: error};
      }
    }
    return {
      request: request,
      get: function (url) { return request(url); },
      post: function (url, body) { return request(url, {method: 'POST', body: body}); },
    };
  }

  return {
    escapeHtml: escapeHtml,
    classifyBarcode: classifyBarcode,
    normalizeApiResponse: normalizeApiResponse,
    createApiClient: createApiClient,
  };
}));
