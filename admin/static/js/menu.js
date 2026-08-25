/* 菜单模块 */
var MENUS = [
    {k:'home', t:'工作台', home:true},
    {k:'analytics/dashboard', t:'数据看板', home:true},
    {k:'process', t:'制程管控', sub:[
        {k:'process/station-config',t:'站点配置'},{k:'process/flow',t:'过站记录'},{k:'process/record',t:'操作记录'},
        {k:'process/box',t:'箱号管理'},{k:'process/lock',t:'锁料管理'},
        {k:'process/defect',t:'不良品接收'},{k:'process/material',t:'料号维护'},
        {k:'process/exception',t:'异常处理'},{k:'process/statistics',t:'制程统计'}
    ]},
    {k:'search', t:'数据查询', sub:[
        {k:'query/production',t:'生产查询'},{k:'query/inventory',t:'库存查询'},
        {k:'query/quality',t:'质量查询'},{k:'query/equipment',t:'设备查询'},
        {k:'query/employee',t:'员工查询'},{k:'query/statistics',t:'综合统计'}
    ]},
    {k:'base', t:'基础数据', sub:[
        {k:'base/workshop',t:'车间设置'},{k:'base/process',t:'工序管理'},
        {k:'base/product',t:'产品定义'},{k:'base/bom',t:'物料清单'},
        {k:'base/defect',t:'不良品项'},{k:'base/unit',t:'单位管理'},{k:'base/route',t:'工艺路线'},
        {k:'base/supplier',t:'供应商管理'},{k:'base/customer',t:'客户管理'},
        {k:'stage/code',t:'阶段码管理'}
    ]},
    {k:'inv', t:'库存管理', sub:[
        {k:'inv/inbound',t:'入库单'},{k:'inv/outbound',t:'出库单'},{k:'inv/balance',t:'库存余额'},
        {k:'warehouse/list',t:'仓库设置'},{k:'warehouse/area',t:'库区管理'},{k:'warehouse/location',t:'库位管理'},
        {k:'warehouse/arrival',t:'到货通知'},{k:'warehouse/transaction',t:'库存事务'}
    ]},
    {k:'prod', t:'生产管理', sub:[
        {k:'prod/sales',t:'销售订单'},{k:'prod/plan',t:'生产计划'},{k:'prod/plan-control',t:'计划控制'},{k:'prod/batch',t:'生产批次'},
        {k:'prod/workorder',t:'工单管理'},{k:'prod/task',t:'任务管理'},{k:'prod/report',t:'报工管理'},
        {k:'prod/transfer',t:'工序转移'},{k:'prod/material',t:'生产领料'},
        {k:'prod/outsource',t:'委外加工'},{k:'prod/serial',t:'序列号'},{k:'prod/labor',t:'工时统计'},{k:'prod/packing',t:'包装管理'},
        {k:'site/workstation',t:'工位管理'},{k:'site/andon',t:'安灯系统'},{k:'site/rework',t:'返工报废'},
        {k:'stage/record',t:'阶段记录'},{k:'stage/statistics',t:'阶段统计'}
    ]},
    {k:'qm', t:'质量管理', sub:[
        {k:'qm/incoming',t:'来料检验'},{k:'qm/process',t:'过程检验'},{k:'qm/outgoing',t:'出货检验'},
        {k:'qm/first',t:'首件检验'},{k:'qm/defect',t:'不良品处理'},{k:'qm/8d',t:'8D报告'},{k:'qm/supplier-eval',t:'供方评审'},{k:'qm/statistics',t:'质量统计'},
        {k:'qm/capa',t:'CAPA'},{k:'qm/control-plan',t:'控制计划'},{k:'qm/eco',t:'工程变更'},
        {k:'qm/template',t:'质检方案'}
    ]},
    {k:'eqp2', t:'模具工装', sub:[{k:'eqp/mold',t:'模具管理'},{k:'eqp/fixture',t:'工装夹具'}]},
    {k:'util', t:'公共事业', sub:[{k:'util/energy',t:'能耗管理'},{k:'util/environment',t:'环境监控'}]},
    {k:'hr', t:'人力资源', sub:[{k:'hr/training',t:'培训管理'},{k:'hr/skill-matrix',t:'技能矩阵'}]},
    {k:'5s', t:'5S管理', sub:[{k:'5s/audit',t:'5S检查'}]},
    {k:'svc', t:'售后管理', sub:[{k:'svc/complaint',t:'客诉管理'},{k:'svc/return',t:'退换货'}]},
    {k:'analytics', t:'数据分析', sub:[
        {k:'analytics/oee',t:'OEE分析'},{k:'analytics/capacity',t:'产能分析'},
        {k:'analytics/delivery',t:'交期预警'},{k:'analytics/inventory',t:'库存分析'},
        {k:'analytics/yield',t:'良率统计'},{k:'analytics/dashboard',t:'数据看板'}
    ]},
    {k:'eqp', t:'设备管理', sub:[{k:'eqp/ledger',t:'设备台账'},{k:'eqp/machine-iot',t:'机台通讯'},{k:'eqp/repair',t:'维修单'},{k:'eqp/maintenance',t:'保养计划'},{k:'eqp/check',t:'保养记录'},{k:'eqp/check-project',t:'点检项目'}]},
    {k:'trace', t:'物料追溯', sub:[{k:'trace/batch',t:'批次管理'},{k:'trace/query',t:'追溯查询'}]},
    {k:'flow', t:'审批管理', sub:[{k:'flow/def',t:'流程定义'},{k:'flow/instance',t:'我的审批'},{k:'flow/pending',t:'待我审批'}]},
    {k:'sched', t:'排班管理', sub:[{k:'sched/team',t:'班组管理'},{k:'sched/plan',t:'排班计划'},{k:'sched/calendar',t:'排班日历'}]},
    {k:'tool', t:'工具管理', sub:[{k:'tool/ledger',t:'工具台账'},{k:'tool/borrow',t:'工具领用'}]},
    {k:'report', t:'报表管理', sub:[{k:'report/production',t:'生产报表'},{k:'report/spc',t:'SPC分析'},{k:'report/cost',t:'成本核算'}]},
    {k:'notifications', t:'消息通知', home:true},
    {k:'doc', t:'文档管理', sub:[{k:'doc/list',t:'文档列表'}]},
    {k:'sys', t:'系统管理', sub:[
        {k:'sys/user',t:'用户管理'},{k:'sys/role',t:'角色管理'},
        {k:'sys/dept',t:'部门管理'},{k:'sys/dict',t:'数据字典'},{k:'sys/log',t:'系统日志'},
        {k:'sys/backup',t:'数据备份'},{k:'sys/security',t:'安全设置'},
        {k:'sys/login-log',t:'登录日志'},{k:'sys/config',t:'系统配置'},
        {k:'sys/announcement',t:'系统公告'},{k:'sys/online',t:'在线用户'},
        {k:'sys/monitor',t:'系统监控'},        {k:'sys/ip-whitelist',t:'IP白名单'},
        {k:'sys/print-template',t:'打印模板'},
        {k:'sys/notify-channel',t:'通知渠道'}
    ]}
];

var openMenus = {};

function buildMenu() {
    var h = '';
    MENUS.forEach(function(m) {
        if(m.home) {
            h += '<button class="menu-title menu-item menu-root" type="button" data-page="'
                + MESUI.escapeHtml(MESUI.menuPage(m)) + '">'
                + '<span class="menu-label">' + MESUI.escapeHtml(m.t) + '</span></button>';
            return;
        }
        var op = openMenus[m.k];
        h += '<section class="menu-group" data-group="' + MESUI.escapeHtml(m.k) + '">';
        h += '<button class="menu-title menu-parent" type="button" data-menu="'
            + MESUI.escapeHtml(m.k) + '" aria-expanded="' + (op ? 'true' : 'false') + '">'
            + '<span class="menu-label">' + MESUI.escapeHtml(m.t) + '</span><span class="arr" aria-hidden="true">'
            + (op ? '&#8722;' : '&#43;') + '</span></button>';
        h += '<div class="sub' + (op ? ' show' : '') + '" id="sub_'
            + MESUI.escapeHtml(m.k) + '">';
        m.sub.forEach(function(s) {
            h += '<button class="menu-title menu-item" type="button" data-page="'
                + MESUI.escapeHtml(s.k) + '"><span class="menu-label">'
                + MESUI.escapeHtml(s.t) + '</span></button>';
        });
        h += '</div></section>';
    });
    var sideBar = document.getElementById('sideBar');
    sideBar.innerHTML = h;

    var items = sideBar.querySelectorAll('.menu-title');
    for(var i = 0; i < items.length; i++) {
        if(typeof curPage !== 'undefined' && items[i].getAttribute('data-page') === curPage) {
            items[i].classList.add('active');
        }
        items[i].onclick = function() {
            var page = this.getAttribute('data-page');
            var menu = this.getAttribute('data-menu');
            if(page) {
                goPage(page);
            } else if(menu) {
                openMenus[menu] = !openMenus[menu];
                buildMenu();
            }
        };
    }
}

function goPage(key) {
    curPage = key;
    var items = document.querySelectorAll('.menu-title');
    for(var i = 0; i < items.length; i++) {
        items[i].classList.remove('active');
        if(items[i].getAttribute('data-page') === key) items[i].classList.add('active');
    }
    var bc = '工作台';
    MENUS.forEach(function(m) {
        if(m.k === key) { bc = m.t; return; }
        if(m.sub) m.sub.forEach(function(s) { if(s.k === key) bc = m.t + ' / ' + s.t; });
    });
    document.getElementById('bread').textContent = bc;
    renderPage(key);
    if(typeof closeMobileSidebar === 'function') {
        closeMobileSidebar();
    } else {
        var appPage = document.getElementById('appPage');
        if(appPage) appPage.classList.remove('sidebar-open');
    }
}
