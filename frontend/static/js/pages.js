(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.MESCollector = Object.assign(root.MESCollector || {}, api);
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function createCollectorPages(options) {
    var doc = options.document;
    var api = options.api;
    var ui = options.ui;
    var scanner = options.scanner;
    var container = options.container;
    var generation = 0;

    function node(tag, className, text) {
      var element = doc.createElement(tag);
      if (className) element.className = className;
      if (text != null) element.textContent = String(text);
      return element;
    }
    function clear(element) { element.replaceChildren(); }
    function button(label, className, handler) {
      var element = node('button', 'button ' + (className || ''), label);
      element.type = 'button'; element.addEventListener('click', handler); return element;
    }
    function intro(kicker, title, description) {
      var box = node('div', 'page-intro');
      box.append(node('span', 'eyebrow', kicker), node('h1', '', title), node('p', '', description));
      return box;
    }
    function section(title, meta) {
      var card = node('section', 'section-card');
      var heading = node('div', 'section-heading');
      heading.append(node('h2', '', title), node('span', '', meta || ''));
      card.append(heading); return card;
    }
    function empty(title, detail) {
      var box = node('div', 'empty-state'); box.append(node('strong', '', title), node('span', '', detail)); return box;
    }
    function loading() { return node('div', 'loading', '正在读取现场数据…'); }
    function field(label, input) {
      var wrap = node('label', 'field'); wrap.append(node('span', '', label), input); return wrap;
    }
    function input(type, placeholder) {
      var element = node('input', 'form-control'); element.type = type || 'text'; element.placeholder = placeholder || ''; return element;
    }
    function taskStatus(task) {
      if (Number(task.status) === 3) return {label: '已完成', className: 'done'};
      if (Number(task.status) > 0) return {label: '进行中', className: 'running'};
      return {label: '待开始', className: ''};
    }
    function taskCard(task, showActions) {
      var card = node('article', 'task-card');
      var head = node('div', 'task-card-header');
      var status = taskStatus(task);
      head.append(node('strong', '', task.task_no || '未编号任务'), node('span', 'status-tag ' + status.className, status.label));
      var meta = node('div', 'task-meta');
      [['工单', task.workorder_no || '-'], ['工序', task.process_name || '-'], ['产品', task.product_name || '-'], ['计划', task.planned_qty || 0]].forEach(function (item) {
        var cell = node('span', '', item[0]); cell.append(node('b', '', item[1])); meta.append(cell);
      });
      var footer = node('div', 'task-card-footer');
      var progress = Math.max(0, Math.min(100, task.planned_qty ? Math.round((Number(task.completed_qty) || 0) / Number(task.planned_qty) * 100) : 0));
      var track = node('div', 'progress-track'); var fill = node('i'); fill.style.width = progress + '%'; track.append(fill);
      footer.append(track, node('span', 'progress-text', progress + '%'));
      card.append(head, meta, footer);
      if (showActions && Number(task.status) < 3) {
        var actions = node('div', 'action-row');
        if (Number(task.status) === 0) actions.append(button('开始任务', 'button-secondary', async function () {
          var result = await api.startTask(task.id); ui.toast(result.ok ? '任务已开始' : result.message); if (result.ok) render('task');
        }));
        actions.append(button('生产报工', 'button-primary', function () { ui.openReport(task, function () { render('report'); }); }));
        card.append(actions);
      }
      return card;
    }

    async function renderHome(token) {
      container.append(intro('SHIFT WORKSPACE', '现场工作台', '聚焦您今天需要完成的任务与采集操作。'));
      var metrics = node('div', 'metrics-grid');
      [['待完成任务', '—'], ['今日报工', '—'], ['待检验', '—']].forEach(function (item) {
        var card = node('div', 'metric-card'); card.append(node('span', '', item[0]), node('strong', '', item[1]), node('em', '', '实时')); metrics.append(card);
      });
      container.append(metrics);
      var quick = section('快捷操作', '常用入口'); var grid = node('div', 'quick-grid');
      [['扫码报工', '扫描工单、任务或产品码', 'scan'], ['生产报工', '选择当前任务快速上报', 'report'], ['质量检验', '提交来料检验结果', 'quality'], ['我的任务', '查看个人生产任务', 'task']].forEach(function (item) {
        var action = button('', 'quick-action', function () { ui.navigate(item[2]); }); action.append(node('strong', '', item[0]), node('span', '', item[1])); grid.append(action);
      });
      quick.append(grid); container.append(quick);
      var result = await api.summary(); if (token !== generation) return;
      if (!result.ok) { ui.toast(result.message); return; }
      var values = [result.data.pending_tasks, result.data.today_reports, result.data.pending_inspections];
      metrics.querySelectorAll('strong').forEach(function (element, index) { element.textContent = String(values[index] || 0); });
    }

    function renderScanResult(result, host) {
      clear(host);
      if (!result.ok) { host.append(empty('未识别此条码', result.message)); return; }
      var data = result.data; var card = section('识别结果', data.kind === 'product' ? '产品码' : data.kind === 'task' ? '任务码' : '工单码');
      card.append(node('div', 'list-row', data.entity.product_name || data.entity.task_no || data.entity.order_no || data.entity.code));
      if (!data.tasks.length) card.append(empty('没有可操作任务', '当前用户没有该条码关联的待完成任务。'));
      data.tasks.forEach(function (task) { card.append(taskCard(task, true)); }); host.append(card);
    }
    function renderScan() {
      container.append(intro('BARCODE STATION', '扫码采集', '支持 USB 扫码枪、手工输入和兼容设备摄像头。'));
      var stage = node('section', 'scan-stage'); var frame = node('div', 'scan-frame');
      var scanInput = node('input', 'scan-input'); scanInput.id = 'scanInput'; scanInput.placeholder = '扫描或输入条码后回车'; scanInput.autocomplete = 'off';
      frame.append(scanInput); stage.append(frame, node('p', 'scan-hint', '支持 WO 工单码、TK 任务码及产品编码'));
      var camera = button('启用摄像头扫码', 'button-secondary button-block', async function () {
        video.classList.remove('is-hidden');
        try { var state = await scanner.startCamera(video); if (!state.supported) { video.classList.add('is-hidden'); ui.toast('当前设备不支持摄像头扫码，请使用扫码枪'); } }
        catch (error) { video.classList.add('is-hidden'); ui.toast('无法打开摄像头，请检查权限'); }
      });
      var video = node('video', 'camera-view is-hidden'); video.setAttribute('playsinline', ''); video.muted = true;
      stage.append(camera, video); container.append(stage);
      var resultHost = node('div'); container.append(resultHost);
      async function handle(code) { clear(resultHost); resultHost.append(loading()); renderScanResult(await api.resolveBarcode(code), resultHost); scanInput.focus(); }
      scanner.mount(scanInput, handle); setTimeout(function () { scanInput.focus(); }, 0);
    }

    async function renderTasks(token, reportMode) {
      container.append(intro(reportMode ? 'PRODUCTION REPORT' : 'MY ASSIGNMENTS', reportMode ? '生产报工' : '我的任务', reportMode ? '选择一项待完成任务，提交本次合格与不良数量。' : '仅显示分配给当前登录用户的生产任务。'));
      var host = node('div'); host.append(loading()); container.append(host);
      var result = await api.tasks(); if (token !== generation) return; clear(host);
      if (!result.ok) { host.append(empty('任务读取失败', result.message)); return; }
      var tasks = result.data.list || [];
      if (reportMode) tasks = tasks.filter(function (task) { return Number(task.status) < 3; });
      if (!tasks.length) { host.append(empty(reportMode ? '暂无可报工任务' : '暂无个人任务', '新任务分配后会显示在这里。')); return; }
      tasks.forEach(function (task) { host.append(taskCard(task, true)); });
      if (reportMode) {
        var records = section('今日报工记录', '最近 20 条'); records.append(loading()); container.append(records);
        var reportResult = await api.reports(); if (token !== generation) return; records.lastChild.remove();
        if (!reportResult.ok || !reportResult.data.list.length) records.append(empty('今日暂无记录', '提交报工后将在这里显示。'));
        else reportResult.data.list.forEach(function (item) {
          var row = node('div', 'list-row'); var left = node('div'); left.append(node('strong', '', item.report_no), node('span', '', (item.process_name || '-') + ' · ' + (item.report_time || ''))); row.append(left, node('span', 'value-blue', '合格 ' + item.qualified_qty)); records.append(row);
        });
      }
    }

    async function renderQuality(token) {
      container.append(intro('QUALITY GATE', '来料检验', '记录检验结论，并查看当前待检批次。'));
      var formCard = section('提交检验', 'IQC'); var form = node('form', 'form-grid');
      var supplier = input('text', '供应商名称'); var resultSelect = node('select', 'form-control');
      ['合格', '不合格'].forEach(function (value) { var option = node('option', '', value); option.value = value; resultSelect.append(option); });
      var remark = node('textarea', 'form-control'); remark.placeholder = '检验说明（可选）';
      var qualitySubmit = button('提交检验', 'button-success button-large', function () {}); qualitySubmit.type = 'submit';
      form.append(field('供应商', supplier), field('检验结果', resultSelect), field('备注', remark), qualitySubmit);
      form.addEventListener('submit', async function (event) {
        event.preventDefault(); if (!supplier.value.trim()) { ui.toast('请输入供应商'); return; }
        var submit = form.querySelector('button'); submit.disabled = true;
        var response = await api.addInspection({supplier: supplier.value.trim(), result: resultSelect.value, remark: remark.value.trim(), status: 1});
        submit.disabled = false; ui.toast(response.ok ? '检验已提交' : response.message); if (response.ok) render('quality');
      });
      formCard.append(form); container.append(formCard);
      var list = section('待检批次', '状态 0'); list.append(loading()); container.append(list);
      var response = await api.inspections(); if (token !== generation) return; list.lastChild.remove();
      var rows = response.ok ? response.data.list || [] : [];
      if (!rows.length) list.append(empty('暂无待检批次', response.ok ? '当前没有等待检验的记录。' : response.message));
      rows.forEach(function (item) { var row = node('div', 'list-row'); var left = node('div'); left.append(node('strong', '', item.inspect_no), node('span', '', item.supplier || '未填写供应商')); row.append(left, node('span', 'status-tag', '待检')); list.append(row); });
    }

    async function renderMaterial(token) {
      container.append(intro('STOCK & TOOL', '库存 / 工具', '查询物料库存；工具领用将生成真实借用记录。'));
      var inventory = section('库存查询', '实时结存'); var search = input('search', '输入产品名称或编码'); inventory.append(field('产品搜索', search));
      var inventoryHost = node('div'); inventory.append(inventoryHost); container.append(inventory);
      var response = await api.inventory(); if (token !== generation) return;
      var items = response.ok && Array.isArray(response.data) ? response.data : [];
      function showInventory() {
        clear(inventoryHost); var keyword = search.value.trim().toLowerCase();
        var filtered = items.filter(function (item) { return !keyword || String(item.product_name || '').toLowerCase().includes(keyword) || String(item.code || '').toLowerCase().includes(keyword); });
        if (!filtered.length) { inventoryHost.append(empty('没有匹配库存', '请更换产品名称或编码。')); return; }
        filtered.forEach(function (item) { var row = node('div', 'list-row'); var left = node('div'); left.append(node('strong', '', item.product_name || '产品 #' + item.product_id), node('span', '', item.code || '未设置编码')); row.append(left, node('span', 'value-blue', String(item.quantity || 0) + ' ' + (item.unit || ''))); inventoryHost.append(row); });
      }
      search.addEventListener('input', showInventory); showInventory();
      var borrow = section('工具借用', '非物料出库'); var form = node('form', 'form-grid two'); var toolId = input('number', '工具 ID'); var quantity = input('number', '数量'); quantity.min = '1';
      var submit = button('确认借用', 'button-primary button-large', function () {}); submit.type = 'submit'; submit.style.gridColumn = '1 / -1'; form.append(field('工具 ID', toolId), field('借用数量', quantity), submit);
      form.addEventListener('submit', async function (event) { event.preventDefault(); if (!toolId.value || !quantity.value) { ui.toast('请填写工具 ID 和数量'); return; } submit.disabled = true; var result = await api.borrowTool({tool_id: Number(toolId.value), borrow_qty: Number(quantity.value)}); submit.disabled = false; ui.toast(result.ok ? '工具借用已登记' : result.message); if (result.ok) { toolId.value = ''; quantity.value = ''; } });
      borrow.append(form); container.append(borrow);
    }

    function render(page) {
      generation += 1; var token = generation; scanner.unmount(); clear(container);
      if (page === 'scan') renderScan();
      else if (page === 'task') renderTasks(token, false);
      else if (page === 'report') renderTasks(token, true);
      else if (page === 'quality') renderQuality(token);
      else if (page === 'material') renderMaterial(token);
      else renderHome(token);
    }
    function destroy() { generation += 1; scanner.unmount(); clear(container); }
    return {render: render, destroy: destroy};
  }
  return {createCollectorPages: createCollectorPages};
}));
