/* 首页仪表盘 */
function dashboardText(value) {
    return MESUI.escapeHtml(value == null ? '' : String(value));
}

function dashboardChartColor(variableName, fallback) {
    if(typeof getComputedStyle === 'undefined') return fallback;
    var value = getComputedStyle(document.documentElement).getPropertyValue(variableName).trim();
    return value || fallback;
}

function renderHome(el) {
    var today = new Date().toLocaleDateString('zh-CN', {
        year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
    });
    el.innerHTML = '<section class="dashboard-hero">'
        + '<div><p class="eyebrow">PRODUCTION OVERVIEW</p><h1>生产运营工作台</h1>'
        + '<p>聚焦今日产出、质量、设备与库存风险，快速进入关键业务。</p></div>'
        + '<div class="dashboard-date"><span class="status-dot"></span><span>系统运行正常</span><strong>'
        + dashboardText(today) + '</strong></div></section>'
        + '<section class="metrics-grid" aria-label="核心生产指标">'
        + '<article class="metric-card"><div class="metric-head"><span class="metric-code">PR</span><span>产品档案</span></div><strong class="metric-value" id="s1">-</strong><small>已维护产品数量</small></article>'
        + '<article class="metric-card"><div class="metric-head"><span class="metric-code">WO</span><span>进行中工单</span></div><strong class="metric-value" id="s2">-</strong><small>当前生产任务</small></article>'
        + '<article class="metric-card metric-success"><div class="metric-head"><span class="metric-code">FPY</span><span>综合合格率</span></div><strong class="metric-value" id="s5">-</strong><small>质量过程表现</small></article>'
        + '<article class="metric-card metric-primary"><div class="metric-head"><span class="metric-code">OEE</span><span>设备稼动率</span></div><strong class="metric-value" id="s6">-</strong><small>设备运行效率</small></article>'
        + '<article class="metric-card"><div class="metric-head"><span class="metric-code">EQ</span><span>运行设备</span></div><strong class="metric-value" id="s4">-</strong><small>在线设备数量</small></article>'
        + '<article class="metric-card"><div class="metric-head"><span class="metric-code">INV</span><span>库存物料</span></div><strong class="metric-value" id="s3">-</strong><small>库存记录数量</small></article>'
        + '</section>'
        + '<section class="dashboard-grid">'
        + '<article class="card chart-card"><div class="card-title"><div><span class="card-kicker">OUTPUT TREND</span><span>近 7 天产量趋势</span></div><span class="tag tag-blue">实时</span></div><div id="chartOutput" class="chart-frame"></div></article>'
        + '<article class="card chart-card"><div class="card-title"><div><span class="card-kicker">WORK ORDERS</span><span>工单状态分布</span></div><span class="tag tag-gray">全部工单</span></div><div id="chartWO" class="chart-frame"></div></article>'
        + '<article class="card chart-card"><div class="card-title"><div><span class="card-kicker">EQUIPMENT</span><span>设备稼动率</span></div><span class="tag tag-green">运行效率</span></div><div id="chartEqp" class="chart-frame"></div></article>'
        + '<article class="card chart-card"><div class="card-title"><div><span class="card-kicker">WORKSHOPS</span><span>各车间产出</span></div><span class="tag tag-blue">本周期</span></div><div id="chartWS" class="chart-frame"></div></article>'
        + '</section>'
        + '<section class="alert-grid">'
        + '<article class="card alert-card"><div class="card-title"><div><span class="card-kicker">INVENTORY ALERT</span><span>库存预警</span></div><span class="tag tag-red">低于 10 件</span></div>'
        + '<div class="table-wrap"><table><thead><tr><th>物料</th><th>编码</th><th>库存</th></tr></thead><tbody id="lowStock"><tr><td colspan="3" class="empty">加载中...</td></tr></tbody></table></div></article>'
        + '<article class="card alert-card"><div class="card-title"><div><span class="card-kicker">MAINTENANCE</span><span>逾期保养</span></div><span class="tag tag-orange">需要处理</span></div>'
        + '<div class="table-wrap"><table><thead><tr><th>计划</th><th>设备</th><th>到期日</th></tr></thead><tbody id="overdueMaint"><tr><td colspan="3" class="empty">加载中...</td></tr></tbody></table></div></article>'
        + '</section>'
        + '<section class="card quick-section"><div class="card-title"><div><span class="card-kicker">SHORTCUTS</span><span>快捷操作</span></div><small>常用业务入口</small></div>'
        + '<div class="quick-actions">'
        + '<button class="quick-action primary" onclick="goPage(\'prod/workorder\')"><strong>新建工单</strong><span>创建生产任务</span></button>'
        + '<button class="quick-action" onclick="goPage(\'inv/inbound\')"><strong>入库登记</strong><span>处理物料入库</span></button>'
        + '<button class="quick-action" onclick="goPage(\'qm/incoming\')"><strong>来料检验</strong><span>登记质检结果</span></button>'
        + '<button class="quick-action danger" onclick="goPage(\'eqp/repair\')"><strong>设备报修</strong><span>提交维修请求</span></button>'
        + '<button class="quick-action" onclick="goPage(\'flow/pending\')"><strong>待我审批</strong><span>处理待办流程</span></button>'
        + '<button class="quick-action" onclick="window.open(\'/kanban\',\'_blank\')"><strong>生产看板</strong><span>打开现场大屏</span></button>'
        + '<button class="quick-action" onclick="goPage(\'doc/list\')"><strong>文档管理</strong><span>查阅生产文档</span></button>'
        + '<button class="quick-action" onclick="goPage(\'sys/backup\')"><strong>数据备份</strong><span>管理备份任务</span></button>'
        + '</div></section>';

    api('/api/dashboard').then(function(r) {
        if(!r || r.code !== 0) return;
        var d = r.data;
        document.getElementById('s1').textContent = d.products || 0;
        document.getElementById('s2').textContent = d.workorders || 0;
        document.getElementById('s3').textContent = d.inventory || 0;
        document.getElementById('s4').textContent = d.equipment || 0;
    });

    api('/api/dashboard/charts').then(function(r) {
        if(!r || r.code !== 0) return;
        var d = r.data;
        document.getElementById('s5').textContent = d.pass_rate + '%';
        document.getElementById('s6').textContent = d.eqp_rate + '%';

        var primary = dashboardChartColor('--primary-600', '#2563eb');
        var success = dashboardChartColor('--success', '#16845b');
        var danger = dashboardChartColor('--danger', '#cf3f4f');
        var muted = dashboardChartColor('--text-muted', '#667085');
        var border = dashboardChartColor('--border-subtle', '#e2e8f0');
        var chartText = {color: muted, fontFamily: 'Microsoft YaHei UI'};
        var axis = {axisLine:{lineStyle:{color:border}},axisTick:{show:false},axisLabel:chartText,splitLine:{lineStyle:{color:border,type:'dashed'}}};

        var c1 = echarts.init(document.getElementById('chartOutput'));
        c1.setOption({
            color:[success,danger], textStyle:chartText, grid:{left:42,right:18,top:42,bottom:28},
            tooltip:{trigger:'axis'}, legend:{data:['合格','不良'],right:0,textStyle:chartText},
            xAxis:Object.assign({type:'category',data:d.daily_output.map(function(i){return i.date.slice(5)})},axis),
            yAxis:Object.assign({type:'value'},axis),
            series:[
                {name:'合格',type:'line',smooth:true,symbolSize:7,data:d.daily_output.map(function(i){return i.qualified}),lineStyle:{width:3},areaStyle:{opacity:.08}},
                {name:'不良',type:'line',smooth:true,symbolSize:7,data:d.daily_output.map(function(i){return i.defect}),lineStyle:{width:2}}
            ]
        });

        var c2 = echarts.init(document.getElementById('chartWO'));
        c2.setOption({
            color:[primary,success,'#7c8da6','#b56a09'],textStyle:chartText,tooltip:{trigger:'item'},
            series:[{type:'pie',radius:['48%','72%'],center:['50%','52%'],data:d.wo_stats,
                itemStyle:{borderColor:dashboardChartColor('--surface','#fff'),borderWidth:3},label:{color:muted,formatter:'{b}  {c}'}}]
        });

        var c3 = echarts.init(document.getElementById('chartEqp'));
        c3.setOption({
            color:[primary],textStyle:chartText,series:[{
                type:'gauge',progress:{show:true,width:12},radius:'84%',axisLine:{lineStyle:{width:12,color:[[1,border]]}},
                axisTick:{show:false},splitLine:{length:8,lineStyle:{color:muted}},pointer:{length:'58%',width:5},
                axisLabel:{fontSize:10,color:muted},detail:{valueAnimation:true,formatter:'{value}%',fontSize:22,color:primary,offsetCenter:[0,'68%']},
                title:{color:muted,offsetCenter:[0,'92%']},data:[{value:d.eqp_rate,name:'综合稼动率'}]
            }]
        });

        var c4 = echarts.init(document.getElementById('chartWS'));
        c4.setOption({
            color:[primary],textStyle:chartText,grid:{left:42,right:18,top:24,bottom:48},tooltip:{trigger:'axis'},
            xAxis:Object.assign({type:'category',data:d.workshop_output.map(function(i){return i.workshop_name}),axisLabel:{color:muted,rotate:22}},axis),
            yAxis:Object.assign({type:'value'},axis),series:[{type:'bar',barMaxWidth:30,data:d.workshop_output.map(function(i){return i.qty}),itemStyle:{borderRadius:[5,5,0,0]}}]
        });

        window.__mesDashboardCharts = [c1,c2,c3,c4];
        if(!window.__mesDashboardResizeBound) {
            window.addEventListener('resize',function(){
                (window.__mesDashboardCharts || []).forEach(function(chart){ chart.resize(); });
            });
            window.__mesDashboardResizeBound = true;
        }

        var ls = document.getElementById('lowStock');
        if(d.low_stock.length) {
            ls.innerHTML = d.low_stock.map(function(i){return '<tr><td>'+dashboardText(i.product_name)+'</td><td>'+dashboardText(i.code)+'</td><td><strong class="text-danger">'+dashboardText(i.quantity)+'</strong></td></tr>'}).join('');
        } else {
            ls.innerHTML = '<tr><td colspan="3" class="empty">暂无库存预警</td></tr>';
        }

        var om = document.getElementById('overdueMaint');
        if(d.overdue_maint.length) {
            om.innerHTML = d.overdue_maint.map(function(i){return '<tr><td>'+dashboardText(i.plan_name)+'</td><td>'+dashboardText(i.equipment_name)+'</td><td><strong class="text-warning">'+dashboardText(i.next_date)+'</strong></td></tr>'}).join('');
        } else {
            om.innerHTML = '<tr><td colspan="3" class="empty">暂无逾期保养</td></tr>';
        }
    });
}
