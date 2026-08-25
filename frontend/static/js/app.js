(function () {
  'use strict';
  var kit = window.MESCollector;
  var doc = document;
  var apiClient = kit.createApiClient(window.fetch.bind(window));
  var api = kit.createCollectorApi(apiClient);
  var scanner = kit.createScanner({
    navigator: navigator,
    BarcodeDetector: window.BarcodeDetector,
    requestFrame: window.requestAnimationFrame.bind(window),
    cancelFrame: window.cancelAnimationFrame.bind(window),
  });
  var currentUser = null;
  var queue = null;
  var pages = null;
  var currentPage = 'home';
  var toastTimer = null;

  function byId(id) { return doc.getElementById(id); }
  function setAuthenticatedView(authenticated) {
    byId('loginView').classList.toggle('is-hidden', authenticated);
    byId('appView').classList.toggle('is-hidden', !authenticated);
  }
  function toast(message) {
    var target = byId('toastRoot'); target.textContent = message || '操作未完成'; target.classList.add('is-visible');
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { target.classList.remove('is-visible'); }, 2400);
  }
  function setNetworkState() {
    var online = navigator.onLine !== false; var state = byId('networkState');
    state.classList.toggle('is-offline', !online); state.querySelector('span').textContent = online ? '在线' : '离线';
    byId('offlineBanner').classList.toggle('is-hidden', online);
    updateSyncCount();
  }
  function updateSyncCount() {
    var counts = queue ? queue.counts() : {total: 0}; byId('syncCount').textContent = String(counts.total || 0);
  }
  async function syncOfflineQueue() {
    if (!queue) return; if (navigator.onLine === false) { toast('网络尚未恢复'); return; }
    var counts = await queue.sync(); updateSyncCount();
    if (counts.needsAttention) toast('有 ' + counts.needsAttention + ' 条记录需要处理');
    else if (!counts.total) toast('离线记录已同步');
  }
  function closeModal() { byId('modalRoot').classList.add('is-hidden'); byId('modalRoot').replaceChildren(); }
  function formField(label, input) { var wrap = doc.createElement('label'); wrap.className = 'field'; var span = doc.createElement('span'); span.textContent = label; wrap.append(span, input); return wrap; }
  function makeInput(type, placeholder) { var input = doc.createElement('input'); input.className = 'form-control'; input.type = type; input.placeholder = placeholder; return input; }
  function clientOperationId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    return 'mobile-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  }
  function openReport(task, onSuccess) {
    var root = byId('modalRoot'); root.replaceChildren(); root.classList.remove('is-hidden');
    var card = doc.createElement('form'); card.className = 'modal-card';
    var title = doc.createElement('h2'); title.textContent = '生产报工'; var detail = doc.createElement('p'); detail.textContent = (task.task_no || '') + ' · ' + (task.process_name || '未命名工序');
    var qualified = makeInput('number', '本次合格数量'); qualified.min = '0.000001'; qualified.step = 'any';
    var defect = makeInput('number', '本次不良数量'); defect.min = '0'; defect.step = 'any'; defect.value = '0';
    var remark = doc.createElement('textarea'); remark.className = 'form-control'; remark.placeholder = '备注（可选）';
    var actions = doc.createElement('div'); actions.className = 'action-row';
    var cancel = doc.createElement('button'); cancel.type = 'button'; cancel.className = 'button button-secondary'; cancel.textContent = '取消'; cancel.addEventListener('click', closeModal);
    var submit = doc.createElement('button'); submit.type = 'submit'; submit.className = 'button button-primary'; submit.textContent = '确认报工'; actions.append(cancel, submit);
    card.append(title, detail, formField('合格数量', qualified), formField('不良数量', defect), formField('备注', remark), actions); root.append(card);
    card.addEventListener('submit', async function (event) {
      event.preventDefault(); var good = Number(qualified.value); var bad = Number(defect.value || 0);
      if (!(good > 0) || bad < 0) { toast('请输入正确的报工数量'); return; }
      var body = {task_id: task.id, workorder_id: task.workorder_id, process_id: task.process_id, qualified_qty: good, defect_qty: bad, controlled: true, client_operation_id: clientOperationId(), remark: remark.value.trim()};
      submit.disabled = true;
      if (navigator.onLine === false) {
        queue.enqueue({url: '/api/prod/report/add', body: body}); updateSyncCount(); closeModal(); toast('已离线暂存，联网后自动同步'); return;
      }
      var result = await api.addReport(body); submit.disabled = false;
      if (!result.ok && (result.type === 'network' || result.type === 'server')) { queue.enqueue({url: '/api/prod/report/add', body: body}); updateSyncCount(); closeModal(); toast('网络异常，报工已暂存'); return; }
      if (!result.ok) { toast(result.message); return; }
      closeModal(); toast('报工成功'); if (onSuccess) onSuccess();
    });
  }
  var titles = {home: '现场工作台', scan: '扫码采集', task: '我的任务', report: '生产报工', quality: '来料检验', material: '库存 / 工具'};
  function navigate(page) {
    currentPage = titles[page] ? page : 'home'; localStorage.setItem('mes.collector.page', currentPage); byId('pageTitle').textContent = titles[currentPage];
    doc.querySelectorAll('.nav-item').forEach(function (item) { var active = item.dataset.page === currentPage; item.classList.toggle('is-active', active); if (active) item.setAttribute('aria-current', 'page'); else item.removeAttribute('aria-current'); });
    pages.render(currentPage);
  }
  function activate(user) {
    currentUser = user; byId('userName').textContent = user.real_name || user.username; byId('userAvatar').textContent = (user.real_name || user.username || '操').charAt(0);
    queue = kit.createOfflineQueue({storage: localStorage, userId: user.id, api: function (item) { return apiClient.request(item.url, {method: item.method, body: item.body}); }});
    pages = kit.createCollectorPages({document: doc, api: api, scanner: scanner, container: byId('pageContent'), ui: {toast: toast, navigate: navigate, openReport: openReport}});
    setAuthenticatedView(true); setNetworkState(); navigate(localStorage.getItem('mes.collector.page') || 'home'); if (navigator.onLine !== false) syncOfflineQueue();
  }
    var captchaKey = window._captchaKey || '';
    async function login(event) {
      event.preventDefault(); var username = byId('usernameInput').value.trim(); var password = byId('passwordInput').value; var error = byId('loginError');
      if (!username || !password) { error.textContent = '请输入工号和密码'; return; }
      var body = {username: username, password: password};
      if (captchaKey) { body.captcha_key = captchaKey; body.captcha_code = byId('captchaInput').value; }
      var button = byId('loginButton'); button.disabled = true; button.textContent = '正在验证…'; error.textContent = '';
      var result = await api.login(body); button.disabled = false; button.textContent = '进入工作台';
      if (!result.ok) {
        error.textContent = result.message;
        if (result.status === 429) showCaptcha();
        return;
      }
      byId('passwordInput').value = ''; captchaKey = ''; byId('captchaField').classList.add('is-hidden'); activate(result.data);
    }
    function loadCaptcha() {
      return apiClient.request('/api/captcha', {method:'GET'}).then(function(r) {
        if (r && r.ok && r.data && r.data.key) {
          captchaKey = r.data.key;
          byId('captchaImage').src = '/api/captcha/image/' + encodeURIComponent(captchaKey) + '?t=' + Date.now();
        }
      });
    }
    function showCaptcha() {
      byId('captchaField').classList.remove('is-hidden');
      loadCaptcha();
      byId('captchaInput').focus();
    }
  async function logout() { if (pages) pages.destroy(); await api.logout(); currentUser = null; queue = null; pages = null; closeModal(); setAuthenticatedView(false); byId('passwordInput').value = ''; }

  doc.addEventListener('DOMContentLoaded', async function () {
    setAuthenticatedView(false); byId('loginForm').addEventListener('submit', login); byId('userButton').addEventListener('click', logout); byId('networkState').addEventListener('click', syncOfflineQueue); byId('syncButton').addEventListener('click', syncOfflineQueue); byId('captchaImage').addEventListener('click', loadCaptcha);
    byId('bottomNav').addEventListener('click', function (event) { var item = event.target.closest('[data-page]'); if (item) navigate(item.dataset.page); });
    window.addEventListener('online', function () { setNetworkState(); syncOfflineQueue(); }); window.addEventListener('offline', setNetworkState);
    var session = await api.userInfo(); if (session.ok) activate(session.data);
  });
}());
