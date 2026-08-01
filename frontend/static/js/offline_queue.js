(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.MESCollector = Object.assign(root.MESCollector || {}, api);
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function createOfflineQueue(options) {
    var storage = options.storage;
    var api = options.api;
    var now = options.now || function () { return new Date().toISOString(); };
    var makeId = options.makeId || function () {
      return 'op-' + Date.now() + '-' + Math.random().toString(16).slice(2);
    };
    var key = 'mes.collector.queue.' + String(options.userId);
    var syncing = null;

    function list() {
      try {
        var parsed = JSON.parse(storage.getItem(key) || '[]');
        return Array.isArray(parsed) ? parsed : [];
      } catch (ignore) {
        return [];
      }
    }

    function save(items) {
      storage.setItem(key, JSON.stringify(items));
    }

    function enqueue(request) {
      var items = list();
      var id = makeId();
      var body = Object.assign({}, request.body || {}, {client_operation_id: id});
      var item = {
        id: id,
        url: request.url,
        method: request.method || 'POST',
        body: body,
        createdAt: now(),
        attempts: 0,
        status: 'pending',
        lastError: '',
      };
      items.push(item);
      save(items);
      return item;
    }

    function remove(id) {
      save(list().filter(function (item) { return item.id !== id; }));
    }

    function counts() {
      var items = list();
      return {
        pending: items.filter(function (item) { return item.status === 'pending'; }).length,
        needsAttention: items.filter(function (item) { return item.status === 'needs_attention'; }).length,
        total: items.length,
      };
    }

    async function performSync() {
      var snapshot = list().filter(function (item) { return item.status === 'pending'; });
      for (var i = 0; i < snapshot.length; i += 1) {
        var item = snapshot[i];
        var result = await api(item);
        if (result && result.ok) {
          remove(item.id);
          continue;
        }
        var items = list();
        var current = items.find(function (candidate) { return candidate.id === item.id; });
        if (!current) continue;
        current.lastError = result && result.message || '同步失败';
        if (result && result.type === 'business') {
          current.status = 'needs_attention';
        } else {
          current.attempts += 1;
          current.status = 'pending';
        }
        save(items);
        break;
      }
      return counts();
    }

    function sync() {
      if (syncing) return syncing;
      syncing = performSync().finally(function () { syncing = null; });
      return syncing;
    }

    function retry(id) {
      var items = list();
      var item = items.find(function (candidate) { return candidate.id === id; });
      if (item) {
        item.status = 'pending';
        item.lastError = '';
        save(items);
      }
      return sync();
    }

    return {enqueue: enqueue, list: list, remove: remove, counts: counts, sync: sync, retry: retry};
  }

  return {createOfflineQueue: createOfflineQueue};
}));
