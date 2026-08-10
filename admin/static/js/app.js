/* 主应用模块 */
var curUser = null;
var curPage = '';
var selectedRows = new Set();

function setAuthenticatedView(authenticated) {
    document.getElementById('loginPage').classList.toggle('is-hidden', authenticated);
    document.getElementById('appPage').classList.toggle('is-hidden', !authenticated);
}

function toggleSidebar() {
    var appPage = document.getElementById('appPage');
    var toggleBtn = document.getElementById('toggleBtn');
    var mobile = window.innerWidth < 768;
    var className = mobile ? 'sidebar-open' : 'sidebar-collapsed';
    appPage.classList.toggle(className);
    if(!mobile) appPage.classList.remove('sidebar-open');
    var expanded = mobile
        ? appPage.classList.contains('sidebar-open')
        : !appPage.classList.contains('sidebar-collapsed');
    toggleBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
}

function closeMobileSidebar() {
    var appPage = document.getElementById('appPage');
    var toggleBtn = document.getElementById('toggleBtn');
    appPage.classList.remove('sidebar-open');
    if(window.innerWidth < 768) toggleBtn.setAttribute('aria-expanded', 'false');
}

// 主题切换
function toggleTheme() {
    var current = document.documentElement.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeIcon();
    if(curPage === 'home' && typeof renderHome === 'function') {
        renderHome(document.getElementById('pageContent'));
    }
}

function updateThemeIcon() {
    var btn = document.getElementById('themeBtn');
    if(btn) {
        var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        btn.textContent = isDark ? '☀️' : '🌙';
        btn.setAttribute('aria-label', isDark ? '切换浅色主题' : '切换深色主题');
    }
}

function loadTheme() {
    var saved = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
}

// 批量操作
function toggleSelectAll(checked) {
    var checkboxes = document.querySelectorAll('#tb input[type="checkbox"][data-id]');
    checkboxes.forEach(function(cb) {
        cb.checked = checked;
        var id = cb.getAttribute('data-id');
        if(checked) selectedRows.add(id);
        else selectedRows.delete(id);
    });
    updateBatchBar();
}

function toggleSelectRow(id, checked) {
    if(checked) selectedRows.add(String(id));
    else selectedRows.delete(String(id));
    updateBatchBar();
}

function updateBatchBar() {
    var bar = document.getElementById('batchBar');
    if(!bar) return;
    var deleteBtn = bar.querySelector('.btn-red');
    if(deleteBtn) {
        var canDelete = typeof curCrudActions === 'undefined'
            || curCrudActions.delete !== false;
        deleteBtn.style.display = canDelete ? '' : 'none';
    }
    if(selectedRows.size > 0) {
        bar.classList.add('show');
        var countEl = bar.querySelector('.count');
        if(countEl) countEl.textContent = selectedRows.size + ' 项已选';
    } else {
        bar.classList.remove('show');
    }
}

function batchDelete() {
    if(!selectedRows.size) return;
    if(typeof curCrudActions !== 'undefined' && curCrudActions.delete === false) {
        alert('当前页面不允许删除');
        return;
    }
    if(!confirm('确定删除选中的 ' + selectedRows.size + ' 项？')) return;
    var count = 0;
    selectedRows.forEach(function(id) {
        api(curApiBase + '/delete', {method:'POST', body:{id:Number(id)}}).then(function(r) {
            count++;
            if(count === selectedRows.size) {
                selectedRows.clear();
                updateBatchBar();
                crudLoad(1);
            }
        });
    });
}

// 记录对比
function compareRecords() {
    if(selectedRows.size !== 2) { alert('请选择2条记录进行对比'); return; }
    var ids = Array.from(selectedRows);
    var first = currentRowsById[String(ids[0])];
    var second = currentRowsById[String(ids[1])];
    if(!first || !second) {
        alert('记录不存在或已刷新，请重新加载');
        return;
    }

    document.getElementById('mTitle').textContent = '记录对比';
    modalSaveHandler = function() { closeModal(); };
    document.getElementById('modal').classList.add('show');
    showCompareResult(first, second);
}

function showCompareResult(r1, r2) {
    var h = '<table style="width:100%"><thead><tr><th>字段</th><th>记录1</th><th>记录2</th><th>差异</th></tr></thead><tbody>';
    var allKeys = new Set([...Object.keys(r1), ...Object.keys(r2)]);
    allKeys.forEach(function(key) {
        var v1 = String(r1[key] == null ? '' : r1[key]);
        var v2 = String(r2[key] == null ? '' : r2[key]);
        var diff = v1 !== v2 ? '<span style="color:#f5222d">✗ 不同</span>' : '<span style="color:#52c41a">✓ 相同</span>';
        h += '<tr><td style="font-weight:bold">' + MESUI.escapeHtml(key) + '</td><td>'
            + MESUI.escapeHtml(v1) + '</td><td>' + MESUI.escapeHtml(v2) + '</td><td>'
            + diff + '</td></tr>';
    });
    h += '</tbody></table>';
    document.getElementById('mBody').innerHTML = h;
}

// 表格排序
function sortTable(key) {
    var th = document.querySelector('[data-sort-field="'+key+'"]');
    if(!th) return;
    var state = MESUI.nextSortState({field: sortField, order: sortOrder}, key);
    sortField = state.field;
    sortOrder = state.order || 'DESC';
    document.querySelectorAll('th.sortable').forEach(function(cell) {
        var button = cell.querySelector('.table-sort-button');
        if(!button) return;
        var field = button.getAttribute('data-sort-field');
        var active = state.field === field;
        var order = active ? state.order : '';
        cell.setAttribute('aria-sort', order === 'ASC' ? 'ascending' : (order === 'DESC' ? 'descending' : 'none'));
        button.classList.toggle('is-active', active);
        var label = button.textContent.replace(/\s*[↑↓↕]$/, '');
        button.textContent = label + (order === 'ASC' ? ' ↑' : (order === 'DESC' ? ' ↓' : ' ↕'));
    });
    crudLoad(1);
}

function refreshCurrentRecordPage() {
    if(curPage) renderPage(curPage);
}

function stepTableRecord(tableKey, recordId, direction) {
    api('/api/table-order/step', {
        method: 'POST',
        body: {table_key: tableKey, record_id: recordId, direction: direction}
    }).then(function(response) {
        if(response && response.code === 0) refreshCurrentRecordPage();
        else alert(response ? response.message : '顺序调整失败');
    });
}

function moveTableRecord(tableKey, recordId, currentPosition, total) {
    var target = prompt('目标排列 ID（1-' + total + '）', String(currentPosition || 1));
    if(target == null) return;
    if(!/^\d+$/.test(String(target).trim()) || Number(target) < 1) {
        alert('请输入有效的排列 ID');
        return;
    }
    api('/api/table-order/move', {
        method: 'POST',
        body: {table_key: tableKey, record_id: recordId, target_position: Number(target)}
    }).then(function(response) {
        if(response && response.code === 0) refreshCurrentRecordPage();
        else alert(response ? response.message : '顺序调整失败');
    });
}

// 数据校验
function validateField(el, rules) {
    var val = el.value.trim();
    var errors = [];
    
    if(rules.required && !val) errors.push('此字段必填');
    if(rules.min && Number(val) < rules.min) errors.push('最小值: ' + rules.min);
    if(rules.max && Number(val) > rules.max) errors.push('最大值: ' + rules.max);
    if(rules.minLength && val.length < rules.minLength) errors.push('最少' + rules.minLength + '个字符');
    if(rules.pattern && !rules.pattern.test(val)) errors.push(rules.message || '格式不正确');
    
    var errEl = el.parentNode.querySelector('.error-msg');
    if(errors.length) {
        el.classList.add('invalid');
        if(errEl) { errEl.textContent = errors[0]; errEl.classList.add('show'); }
        return false;
    } else {
        el.classList.remove('invalid');
        if(errEl) { errEl.classList.remove('show'); }
        return true;
    }
}

// 密码强度校验
function checkPasswordStrength(pwd) {
    var score = 0;
    if(pwd.length >= 8) score++;
    if(pwd.length >= 12) score++;
    if(/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++;
    if(/\d/.test(pwd)) score++;
    if(/[^a-zA-Z0-9]/.test(pwd)) score++;
    return score;
}

// 操作确认
function confirmAction(message, callback) {
    document.getElementById('mTitle').textContent = '操作确认';
    document.getElementById('mBody').innerHTML = '<div style="text-align:center;padding:20px">'
        + '<div style="font-size:36px;margin-bottom:12px">⚠️</div>'
        + '<p style="font-size:16px">' + message + '</p></div>';
    modalSaveHandler = function() { closeModal(); callback(); };
    document.getElementById('modal').classList.add('show');
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    loadTheme();
    updateThemeIcon();
    var pageContent = document.getElementById('pageContent');
    if(pageContent && typeof MutationObserver !== 'undefined') {
        var tableObserver = new MutationObserver(function() {
            MESUI.enableTableSorting(pageContent);
            MESUI.enableManualTableOrder(pageContent, curPage, {
                field: typeof sortField === 'undefined' ? '' : sortField,
                order: typeof sortOrder === 'undefined' ? '' : sortOrder
            });
        });
        tableObserver.observe(pageContent, {childList: true, subtree: true});
    }
    if(pageContent) {
        MESUI.enableTableSorting(pageContent);
        MESUI.enableManualTableOrder(pageContent, curPage, {field: '', order: ''});
    }

    document.getElementById('loginBtn').onclick = doLogin;
    document.getElementById('lu').onkeydown = function(e) { if(e.key === 'Enter') document.getElementById('lp').focus(); };
    document.getElementById('lp').onkeydown = function(e) { if(e.key === 'Enter') doLogin(); };
    document.getElementById('globalSearch').onkeydown = function(e) { if(e.key === 'Enter') doGlobalSearch(); };
    document.getElementById('logoutBtn').onclick = doLogout;
    document.getElementById('toggleBtn').onclick = toggleSidebar;
    document.getElementById('sidebarOverlay').onclick = closeMobileSidebar;
    document.getElementById('modalCloseBtn').onclick = closeModal;
    document.getElementById('modalCancelBtn').onclick = closeModal;
    document.getElementById('mSave').onclick = function() {
        if(modalSaveHandler) modalSaveHandler();
    };
    document.getElementById('modal').onclick = function(e) {
        if(e.target === this) closeModal();
    };

    // 全局搜索快捷键
    document.addEventListener('keydown', function(e) {
        if(e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            document.getElementById('globalSearch').focus();
        }
        if(e.key === 'Escape') {
            closeModal();
            document.getElementById('globalSearch').blur();
        }
        if(e.ctrlKey && e.key === 's') {
            e.preventDefault();
            if(modalSaveHandler) modalSaveHandler();
        }
    });

    // 会话超时检测（30分钟无操作自动登出）
    var lastActivity = Date.now();
    var sessionTimeout = 30 * 60 * 1000; // 30分钟
    
    function resetActivity() { lastActivity = Date.now(); }
    document.addEventListener('click', resetActivity);
    document.addEventListener('keypress', resetActivity);
    document.addEventListener('scroll', resetActivity);
    window.addEventListener('resize', function() {
        if(window.innerWidth >= 768) {
            document.getElementById('appPage').classList.remove('sidebar-open');
            document.getElementById('toggleBtn').setAttribute(
                'aria-expanded',
                document.getElementById('appPage').classList.contains('sidebar-collapsed') ? 'false' : 'true'
            );
        }
    });
    
    setInterval(function() {
        if(curUser && (Date.now() - lastActivity > sessionTimeout)) {
            alert('会话已超时，请重新登录');
            doLogout();
        }
    }, 60000);
});

function doGlobalSearch() {
    var kw = document.getElementById('globalSearch').value.trim();
    if(!kw) return;
    api('/api/search/global?q=' + encodeURIComponent(kw)).then(function(r) {
        if(!r||r.code!==0) return;
        var results = r.data || [];
        if(!results.length) { alert('未找到"' + kw + '"'); return; }
        var typeMap = {product:'产品',workorder:'工单',task:'任务',customer:'客户',supplier:'供应商',equipment:'设备',user:'员工'};
        var menuMap = {product:'base/product',workorder:'prod/workorder',task:'prod/task',customer:'base/customer',supplier:'base/supplier',equipment:'eqp/ledger',user:'sys/user'};
        var h = '找到 ' + results.length + ' 条结果:\n\n';
        results.forEach(function(r) {
            h += '[' + (typeMap[r.type]||r.type) + '] ' + r.name + (r.code ? ' (' + r.code + ')' : '') + '\n';
        });
        alert(h);
    });
}

function doLogin() {
    var u = document.getElementById('lu').value;
    var p = document.getElementById('lp').value;
    if(!u || !p) { document.getElementById('lerr').textContent = '请输入用户名和密码'; return; }
    document.getElementById('lerr').textContent = '登录中...';
    api('/api/login', {method:'POST', body:{username:u, password:p}}).then(function(r) {
        if(!r) { document.getElementById('lerr').textContent = '网络错误'; return; }
        if(r.code !== 0) { document.getElementById('lerr').textContent = r.message; return; }
        curUser = r.data;
        setAuthenticatedView(true);
        document.getElementById('uname').textContent = curUser.real_name || curUser.username;
        document.getElementById('uav').textContent = (curUser.real_name || curUser.username).charAt(0);
        buildMenu();
        goPage('home');
        loadNotifications();
    });
}

function doLogout() {
    api('/api/logout', {method:'POST'});
    curUser = null;
    setAuthenticatedView(false);
}

function renderPage(key) {
    if(typeof crudRenderToken !== 'undefined') crudRenderToken += 1;
    var el = document.getElementById('pageContent');
    el.replaceChildren();
    if(key === 'home') {
        try { renderHome(el); }
        catch(error) { renderModuleError(el, key, error); }
        return;
    }

    var configs = {
        'base/workshop': {t:'车间设置', f:[{k:'workshop_name',l:'车间名称',r:1},{k:'code',l:'编码',r:1},{k:'description',l:'描述'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'base/process': {t:'工序管理', f:[{k:'process_name',l:'工序名称',r:1},{k:'code',l:'编码',r:1},{k:'workshop_id',l:'车间',type:'select',api:'/api/base/workshop/list?size=1000',vk:'id',tk:'workshop_name'},{k:'standard_time',l:'标准工时(分钟)',type:'number'},{k:'description',l:'描述'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'base/product': {t:'产品定义', f:[{k:'product_name',l:'产品名称',r:1},{k:'code',l:'编码',r:1},{k:'specification',l:'规格型号'},{k:'unit',l:'单位'},{k:'product_type',l:'类型',s:[{v:'成品',t:'成品'},{v:'半成品',t:'半成品'},{v:'原材料',t:'原材料'}]},{k:'description',l:'描述'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'base/defect': {t:'不良品项', f:[{k:'defect_name',l:'缺陷名称',r:1},{k:'code',l:'编码',r:1},{k:'defect_type',l:'类型',s:[{v:'外观',t:'外观'},{v:'尺寸',t:'尺寸'},{v:'功能',t:'功能'},{v:'其他',t:'其他'}]},{k:'description',l:'描述'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'base/unit': {t:'单位管理', f:[{k:'unit_name',l:'单位名称',r:1},{k:'unit_symbol',l:'符号',r:1},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'qm/incoming': {t:'来料检验', f:[{k:'supplier',l:'供应商',r:1},{k:'result',l:'结果',s:[{v:'合格',t:'合格'},{v:'不合格',t:'不合格'}]},{k:'remark',l:'备注'},{k:'status',l:'状态',s:[{v:0,t:'待检'},{v:1,t:'已检'}]}]},
        'qm/outgoing': {t:'出货检验', f:[{k:'customer',l:'客户',r:1},{k:'result',l:'结果',s:[{v:'合格',t:'合格'},{v:'不合格',t:'不合格'}]},{k:'remark',l:'备注'},{k:'status',l:'状态',s:[{v:0,t:'待检'},{v:1,t:'已检'}]}]},
        'base/supplier': {t:'供应商管理', f:[{k:'supplier_name',l:'供应商名称',r:1},{k:'code',l:'编码',r:1},{k:'contact',l:'联系人'},{k:'phone',l:'电话'},{k:'email',l:'邮箱'},{k:'address',l:'地址'},{k:'rating',l:'评分',type:'number'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'base/customer': {t:'客户管理', f:[{k:'customer_name',l:'客户名称',r:1},{k:'code',l:'编码',r:1},{k:'contact',l:'联系人'},{k:'phone',l:'电话'},{k:'email',l:'邮箱'},{k:'address',l:'地址'},{k:'credit_limit',l:'信用额度',type:'number'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'sched/team': {t:'班组管理', f:[{k:'team_name',l:'班组名称',r:1},{k:'code',l:'编码',r:1},{k:'leader',l:'班组长'},{k:'member_count',l:'人数',type:'number'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'sched/plan': {t:'排班计划', f:[{k:'plan_name',l:'计划名称',r:1},{k:'team_id',l:'班组',r:1,type:'select',api:'/api/sched/team/list?size=1000',vk:'id',tk:'team_name'},{k:'start_date',l:'开始日期',type:'date',r:1},{k:'end_date',l:'结束日期',type:'date',r:1},{k:'shift_type',l:'班次',s:[{v:'白班',t:'白班'},{v:'夜班',t:'夜班'},{v:'两班倒',t:'两班倒'}]},{k:'status',l:'状态',s:[{v:0,t:'草稿'},{v:1,t:'已发布'}]}]},
        'tool/ledger': {t:'工具台账', f:[{k:'tool_name',l:'工具名称',r:1},{k:'code',l:'编码',r:1},{k:'specification',l:'规格'},{k:'quantity',l:'数量',type:'number'},{k:'location',l:'位置'},{k:'status',l:'状态',s:[{v:1,t:'正常'},{v:0,t:'报废'}]}]},
        'sys/role': {t:'角色管理', f:[{k:'role_name',l:'角色名称',r:1},{k:'role_key',l:'标识',r:1},{k:'description',l:'描述'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'sys/dept': {t:'部门管理', f:[{k:'dept_name',l:'部门名称',r:1},{k:'leader',l:'负责人'},{k:'phone',l:'电话'},{k:'sort_order',l:'排序',type:'number'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]},
        'sys/dict': {t:'数据字典', f:[{k:'dict_type',l:'类型',r:1},{k:'dict_label',l:'标签',r:1},{k:'dict_value',l:'值',r:1},{k:'sort_order',l:'排序',type:'number'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}]}
    };

    var special = {
        'base/bom': function(e){renderBom(e)},
        'base/route': function(e){renderRoute(e)},
        'base/process': function(e){renderProcess(e)},
        'base/supplier': function(e){renderSupplier(e)},
        'base/customer': function(e){renderCustomer(e)},
        'inv/inbound': function(e){renderInv(e,'in')},
        'inv/outbound': function(e){renderInv(e,'out')},
        'inv/balance': function(e){renderBalance(e)},
        'prod/sales': function(e){renderSales(e)},
        'prod/plan': function(e){renderPlan(e)},
        'prod/workorder': function(e){renderWO(e)},
        'prod/task': function(e){renderTask(e)},
        'prod/report': function(e){renderReport2(e)},
        'eqp/ledger': function(e){renderEqp(e)},
        'eqp/repair': function(e){renderRepair(e)},
        'eqp/maintenance': function(e){renderMaintenance(e)},
        'eqp/check': function(e){renderCheckList(e)},
        'trace/batch': function(e){renderBatch(e)},
        'trace/query': function(e){renderTraceQuery(e)},
        'flow/def': function(e){renderFlowDef(e)},
        'flow/instance': function(e){renderFlowInstance(e)},
        'flow/pending': function(e){renderFlowPending(e)},
        'report/production': function(e){renderProdReport(e)},
        'report/spc': function(e){renderSPC(e)},
        'report/cost': function(e){renderCostReport(e)},
        'doc/list': function(e){renderDocList(e)},
        'sys/user': function(e){renderUser(e)},
        'sys/log': function(e){renderLog(e)},
        'sys/backup': function(e){renderBackup(e)},
        'sys/security': function(e){renderSecurity(e)},
        'sys/login-log': function(e){renderLoginLog(e)},
        'sys/config': function(e){renderSysConfig(e)},
        'sys/announcement': function(e){renderAnnouncement(e)},
        'sys/online': function(e){renderOnlineUsers(e)},
        'sys/monitor': function(e){renderSysMonitor(e)},
        'sys/ip-whitelist': function(e){renderIPWhitelist(e)},
        'sys/print-template': function(e){renderPrintTemplate(e)},
        'sys/notify-channel': function(e){renderNotifyChannel(e)},
        'site/workstation': function(e){renderWorkstation(e)},
        'site/andon': function(e){renderAndon(e)},
        'site/rework': function(e){renderRework(e)},
        'qm/capa': function(e){renderCAPA(e)},
        'qm/control-plan': function(e){renderControlPlan(e)},
        'qm/eco': function(e){renderECO(e)},
        'eqp/mold': function(e){renderMold(e)},
        'eqp/fixture': function(e){renderFixture(e)},
        'util/energy': function(e){renderEnergy(e)},
        'util/environment': function(e){renderEnvironment(e)},
        'hr/training': function(e){renderTraining(e)},
        'hr/skill-matrix': function(e){renderSkillMatrix(e)},
        '5s/audit': function(e){render5SAudit(e)},
        'svc/complaint': function(e){renderComplaint(e)},
        'svc/return': function(e){renderReturn(e)},
        'stage/code': function(e){renderStageCode(e)},
        'stage/record': function(e){renderStageRecord(e)},
        'stage/statistics': function(e){renderStageStatistics(e)},
        'query/production': function(e){renderQueryProduction(e)},
        'query/inventory': function(e){renderQueryInventory(e)},
        'query/quality': function(e){renderQueryQuality(e)},
        'query/equipment': function(e){renderQueryEquipment(e)},
        'query/employee': function(e){renderQueryEmployee(e)},
        'query/statistics': function(e){renderQueryStatistics(e)},
        'process/flow': function(e){renderProcessFlow(e)},
        'process/record': function(e){renderProcessRecord(e)},
        'process/box': function(e){renderBoxManage(e)},
        'process/lock': function(e){renderLockManage(e)},
        'process/defect': function(e){renderDefectReceive(e)},
        'process/material': function(e){renderMaterialManage(e)},
        'process/exception': function(e){renderExceptionManage(e)},
        'process/statistics': function(e){renderProcessStats(e)},
        'process/station-config': function(e){renderStationConfig(e)},
        'qm/first': function(e){renderFirstInspect(e)},
        'qm/defect': function(e){renderDefectProcess(e)},
        'qm/8d': function(e){render8DReport(e)},
        'qm/supplier-eval': function(e){renderSupplierEval(e)},
        'qm/statistics': function(e){renderQMStatistics(e)},
        'prod/transfer': function(e){renderTransfer(e)},
        'prod/material': function(e){renderMaterialReq(e)},
        'prod/outsource': function(e){renderOutsource(e)},
        'prod/serial': function(e){renderSerial(e)},
        'prod/labor': function(e){renderLabor(e)},
        'prod/packing': function(e){renderPacking(e)},
        'analytics/oee': function(e){renderOEE(e)},
        'analytics/capacity': function(e){renderCapacity(e)},
        'analytics/delivery': function(e){renderDeliveryAlert(e)},
        'analytics/inventory': function(e){renderInventoryAnalysis(e)},
        'analytics/yield': function(e){renderYieldAnalysis(e)},
        'analytics/dashboard': function(e){renderDataDashboard(e)},
        'tool/borrow': function(e){renderToolBorrow(e)},
        'qm/process': function(e){renderQMProcess(e)},
        'notifications': function(e){renderNotifications(e)},
        'warehouse/list': function(e){renderWarehousePage(e)},
        'warehouse/area': function(e){renderAreaPage(e)},
        'warehouse/location': function(e){renderLocationPage(e)},
        'warehouse/arrival': function(e){renderArrivalPage(e)},
        'warehouse/transaction': function(e){renderTransactionPage(e)},
        'qm/template': function(e){renderQualityTemplatePage(e)},
        'eqp/check-project': function(e){renderCheckProjectPage(e)},
        'sched/calendar': function(e){renderScheduleCalendarPage(e)}
    };

    try {
        if(special[key]) {
            special[key](el);
            if(typeof MESUI !== 'undefined' && MESUI.enableTableSorting) MESUI.enableTableSorting(el);
            return;
        }
        if(configs[key]) {
            renderCrud(el, key, configs[key]);
            if(typeof MESUI !== 'undefined' && MESUI.enableTableSorting) MESUI.enableTableSorting(el);
            return;
        }
        el.innerHTML = '<div class="card"><div class="card-title">页面建设中...</div></div>';
    } catch(error) {
        renderModuleError(el, key, error);
    }
}

function renderModuleError(el, title, error) {
    var safeTitle = MESUI.escapeHtml(title || '当前模块');
    var message = error && error.message ? error.message : '模块加载失败';
    el.innerHTML = '<div class="card"><div class="card-title">' + safeTitle + '</div>'
        + '<div class="empty">页面加载失败：' + MESUI.escapeHtml(message)
        + '<br><button class="btn btn-blue" onclick="renderPage(curPage)">重新加载</button></div></div>';
    if(window.console && console.error) console.error('模块加载失败:', title, error);
}
