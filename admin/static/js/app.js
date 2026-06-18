/* 主应用模块 */
var curUser = null;
var curPage = '';

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('loginBtn').onclick = doLogin;
    document.getElementById('lu').onkeydown = function(e) { if(e.key === 'Enter') document.getElementById('lp').focus(); };
    document.getElementById('lp').onkeydown = function(e) { if(e.key === 'Enter') doLogin(); };
    document.getElementById('logoutBtn').onclick = doLogout;
    document.getElementById('toggleBtn').onclick = function() {
        var sb = document.getElementById('sideBar');
        sb.style.display = sb.style.display === 'none' ? '' : 'none';
    };
    document.getElementById('modalCloseBtn').onclick = closeModal;
    document.getElementById('modalCancelBtn').onclick = closeModal;
    document.getElementById('mSave').onclick = function() {
        if(modalSaveHandler) modalSaveHandler();
    };
    document.getElementById('modal').onclick = function(e) {
        if(e.target === this) closeModal();
    };
});

function doLogin() {
    var u = document.getElementById('lu').value;
    var p = document.getElementById('lp').value;
    if(!u || !p) { document.getElementById('lerr').textContent = '请输入用户名和密码'; return; }
    document.getElementById('lerr').textContent = '登录中...';
    api('/api/login', {method:'POST', body:{username:u, password:p}}).then(function(r) {
        if(!r) { document.getElementById('lerr').textContent = '网络错误'; return; }
        if(r.code !== 0) { document.getElementById('lerr').textContent = r.message; return; }
        curUser = r.data;
        document.getElementById('loginPage').style.display = 'none';
        document.getElementById('appPage').style.display = 'flex';
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
    document.getElementById('loginPage').style.display = '';
    document.getElementById('appPage').style.display = 'none';
}

function renderPage(key) {
    var el = document.getElementById('pageContent');
    if(key === 'home') { renderHome(el); return; }

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
        'tool/borrow': function(e){renderToolBorrow(e)},
        'qm/process': function(e){renderQMProcess(e)},
        'notifications': function(e){renderNotifications(e)}
    };

    if(special[key]) { special[key](el); return; }
    if(configs[key]) { renderCrud(el, key, configs[key]); return; }
    el.innerHTML = '<div class="card"><div class="card-title">页面建设中...</div></div>';
}
