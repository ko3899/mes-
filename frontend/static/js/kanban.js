(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.MESKanban = Object.assign(root.MESKanban || {}, api);
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function number(value) { var parsed = Number(value); return Number.isFinite(parsed) ? parsed : 0; }
  function percent(part, total) { return total > 0 ? Math.round(part / total * 100) + '%' : '--'; }
  function mapSnapshot(data) {
    data = data || {};
    var qualified = number(data.today_qualified); var defect = number(data.today_defect);
    var equipment = Array.isArray(data.equipment) ? data.equipment : Array.isArray(data.eqp_stats) ? data.eqp_stats : [];
    var equipmentTotal = equipment.reduce(function (sum, item) { return sum + number(item.value); }, 0);
    var equipmentRunning = equipment.reduce(function (sum, item) { return sum + (item.name === '运行' ? number(item.value) : 0); }, 0);
    var alerts = data.quality_alerts || {};
    var orders = (Array.isArray(data.active_orders) ? data.active_orders : []).map(function (order) {
      var planned = number(order.planned_qty); var completed = number(order.completed_qty);
      return {orderNo: order.order_no || '-', productName: order.product_name || '-', workshopName: order.workshop_name || '-', planned: planned, completed: completed, status: number(order.status), progress: Math.max(0, Math.min(100, planned > 0 ? Math.round(completed / planned * 100) : 0))};
    });
    return {
      serverTime: data.server_time || '', qualified: qualified, defect: defect,
      yieldRate: percent(qualified, qualified + defect), activeOrderCount: number(data.active_order_count != null ? data.active_order_count : orders.length),
      equipment: equipment, equipmentRate: percent(equipmentRunning, equipmentTotal),
      workshopOutput: Array.isArray(data.workshop_output) ? data.workshop_output : [],
      qualityPending: number(alerts.pending), qualityFailed: number(alerts.failed_today), qualityAlerts: number(alerts.pending) + number(alerts.failed_today), orders: orders,
    };
  }

  function createKanbanController(options) {
    var fetchImpl = options.fetchImpl; var view = options.view; var charts = options.charts;
    var setTimer = options.setTimer || setInterval; var clearTimer = options.clearTimer || clearInterval;
    var doc = options.document; var win = options.window; var inFlight = null; var lastSnapshot = null; var timer = null; var started = false;
    function refresh() {
      if (inFlight) return inFlight;
      inFlight = (async function () {
        try {
          var response = await fetchImpl('/api/kanban/realtime'); var payload = null;
          try { payload = await response.json(); } catch (ignore) {}
          if (response.status === 401 || payload && payload.code === 401) { view.showAuth(payload && payload.message || '请登录后查看生产数据'); return; }
          if (!response.ok || !payload || payload.code !== 0) throw new Error(payload && payload.message || '实时数据读取失败');
          var mapped = mapSnapshot(payload.data); lastSnapshot = mapped; view.render(mapped); charts.update(mapped); view.setOnline(mapped.serverTime);
        } catch (error) {
          if (lastSnapshot) view.markStale(error.message || '刷新失败'); else view.showError(error.message || '实时数据读取失败');
        }
      }()).finally(function () { inFlight = null; });
      return inFlight;
    }
    function onVisible() { if (!doc || doc.visibilityState === 'visible') refresh(); }
    function resize() { if (charts.resize) charts.resize(); }
    function start() { if (started) return; started = true; refresh(); timer = setTimer(refresh, 30000); if (doc) doc.addEventListener('visibilitychange', onVisible); if (win) win.addEventListener('resize', resize); }
    function stop() { if (!started) return; started = false; if (timer) clearTimer(timer); timer = null; if (doc) doc.removeEventListener('visibilitychange', onVisible); if (win) win.removeEventListener('resize', resize); }
    return {refresh: refresh, start: start, stop: stop, resize: resize};
  }

  function createDomView(doc) {
    function byId(id) { return doc.getElementById(id); }
    function set(id, value) { byId(id).textContent = String(value); }
    function render(data) {
      byId('errorState').classList.add('is-hidden'); set('metricQualified', data.qualified.toLocaleString()); set('metricDefect', data.defect.toLocaleString()); set('metricYield', data.yieldRate); set('metricOrders', data.activeOrderCount); set('metricEquipment', data.equipmentRate); set('orderCount', data.orders.length + ' 条'); set('qualitySummary', data.qualityAlerts + ' 项');
      var body = byId('orderTableBody'); body.replaceChildren(); byId('orderEmpty').classList.toggle('is-hidden', data.orders.length > 0);
      data.orders.forEach(function (order) {
        var row = doc.createElement('tr'); var identity = doc.createElement('td'); var strong = doc.createElement('strong'); strong.textContent = order.orderNo; var small = doc.createElement('small'); small.textContent = order.productName; identity.append(strong, small);
        var workshop = doc.createElement('td'); workshop.textContent = order.workshopName; var planned = doc.createElement('td'); planned.textContent = order.planned.toLocaleString(); var completed = doc.createElement('td'); completed.textContent = order.completed.toLocaleString();
        var progressCell = doc.createElement('td'); var progress = doc.createElement('div'); progress.className = 'progress-cell'; var track = doc.createElement('div'); track.className = 'progress-bar'; var fill = doc.createElement('i'); fill.style.width = order.progress + '%'; track.append(fill); var progressText = doc.createElement('span'); progressText.textContent = order.progress + '%'; progress.append(track, progressText); progressCell.append(progress);
        var statusCell = doc.createElement('td'); var status = doc.createElement('span'); status.className = 'order-status ' + (order.status ? '' : 'waiting'); status.textContent = order.status ? '进行中' : '待开始'; statusCell.append(status); row.append(identity, workshop, planned, completed, progressCell, statusCell); body.append(row);
      });
    }
    function setOnline(serverTime) { byId('staleState').classList.add('is-hidden'); set('connectionLabel', '数据在线'); var date = serverTime ? new Date(serverTime) : new Date(); set('lastUpdated', Number.isNaN(date.getTime()) ? '--:--' : date.toLocaleTimeString('zh-CN', {hour12: false, hour: '2-digit', minute: '2-digit'})); }
    function markStale(message) { byId('staleState').classList.remove('is-hidden'); set('connectionLabel', '数据已过期'); byId('staleState').querySelector('span').textContent = message || '正在保留最近一次成功快照'; }
    function showFailure(message, auth) { byId('errorState').classList.remove('is-hidden'); set('errorMessage', message); byId('errorState').querySelector('strong').textContent = auth ? '登录后查看生产数据' : '看板暂时无法读取数据'; }
    return {render: render, setOnline: setOnline, markStale: markStale, showError: function (message) { showFailure(message, false); }, showAuth: function (message) { showFailure(message, true); }};
  }

  function createCharts(echarts, doc) {
    var instances = null;
    function ensure() { if (!instances && echarts) instances = {output: echarts.init(doc.getElementById('outputChart')), equipment: echarts.init(doc.getElementById('equipmentChart')), quality: echarts.init(doc.getElementById('qualityChart'))}; return instances; }
    var textStyle = {color: '#87a4c2', fontSize: 9}; var splitLine = {lineStyle: {color: 'rgba(111,158,204,.12)'}};
    function update(data) { var charts = ensure(); if (!charts) return;
      charts.output.setOption({animationDuration: 280, grid: {left: 8, right: 18, top: 14, bottom: 5, containLabel: true}, xAxis: {type: 'value', axisLabel: textStyle, splitLine: splitLine}, yAxis: {type: 'category', data: data.workshopOutput.map(function (item) { return item.workshop_name || '-'; }), axisLabel: textStyle, axisLine: {show: false}, axisTick: {show: false}}, series: [{type: 'bar', barWidth: 9, data: data.workshopOutput.map(function (item) { return number(item.qty); }), itemStyle: {color: '#3b82f6', borderRadius: [0,4,4,0]}}]});
      charts.equipment.setOption({animationDuration: 280, color: ['#2dd4a3','#f4b740','#526f8d'], tooltip: {trigger: 'item'}, series: [{type: 'pie', radius: ['53%','74%'], center: ['50%','52%'], label: {color: '#9bb6cf', fontSize: 9, formatter: '{b}  {c}'}, data: data.equipment}]});
      charts.quality.setOption({animationDuration: 280, grid: {left: 14, right: 14, top: 18, bottom: 8, containLabel: true}, xAxis: {type: 'value', axisLabel: textStyle, splitLine: splitLine}, yAxis: {type: 'category', data: ['待检验','今日不合格'], axisLabel: textStyle, axisLine: {show: false}, axisTick: {show: false}}, series: [{type: 'bar', barWidth: 12, data: [{value: data.qualityPending, itemStyle: {color: '#f4b740'}}, {value: data.qualityFailed, itemStyle: {color: '#ef6b67'}}], itemStyle: {borderRadius: [0,5,5,0]}, label: {show: true, position: 'right', color: '#bdd8f1'}}]});
    }
    function resize() { if (instances) Object.keys(instances).forEach(function (key) { instances[key].resize(); }); }
    return {update: update, resize: resize};
  }

  function boot(rootObject) {
    var doc = rootObject.document; var view = createDomView(doc); var charts = createCharts(rootObject.echarts, doc);
    var controller = createKanbanController({fetchImpl: rootObject.fetch.bind(rootObject), view: view, charts: charts, document: doc, window: rootObject});
    doc.getElementById('refreshButton').addEventListener('click', controller.refresh);
    async function toggleFullscreen() { try { if (!doc.fullscreenElement) await doc.documentElement.requestFullscreen(); else await doc.exitFullscreen(); } catch (ignore) {} }
    doc.getElementById('fullscreenButton').addEventListener('click', toggleFullscreen); doc.addEventListener('keydown', function (event) { if (event.key === 'F11') { event.preventDefault(); toggleFullscreen(); } });
    function updateClock() { var now = new Date(); doc.getElementById('currentClock').textContent = now.toLocaleTimeString('zh-CN', {hour12: false}); doc.getElementById('currentDate').textContent = now.toLocaleDateString('zh-CN', {year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short'}); }
    updateClock(); rootObject.setInterval(updateClock, 1000); controller.start(); return controller;
  }

  if (typeof window !== 'undefined' && window.document) window.document.addEventListener('DOMContentLoaded', function () { boot(window); });
  return {mapSnapshot: mapSnapshot, createKanbanController: createKanbanController, createDomView: createDomView, createCharts: createCharts, boot: boot};
}));
