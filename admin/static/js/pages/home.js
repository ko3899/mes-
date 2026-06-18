/* 首页仪表盘 */
function renderHome(el) {
    el.innerHTML = '<div class="stats">'
        + '<div class="stat"><div class="label">产品数量</div><div class="val" id="s1">-</div></div>'
        + '<div class="stat"><div class="label">进行中工单</div><div class="val" id="s2">-</div></div>'
        + '<div class="stat"><div class="label">合格率</div><div class="val" id="s5" style="color:#52c41a">-</div></div>'
        + '<div class="stat"><div class="label">设备稼动率</div><div class="val" id="s6" style="color:#1890ff">-</div></div>'
        + '<div class="stat"><div class="label">运行设备</div><div class="val" id="s4">-</div></div>'
        + '<div class="stat"><div class="label">库存物料</div><div class="val" id="s3">-</div></div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">'
        + '<div class="card"><div class="card-title">近7天产量趋势</div><div id="chartOutput" style="height:280px"></div></div>'
        + '<div class="card"><div class="card-title">工单状态分布</div><div id="chartWO" style="height:280px"></div></div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">'
        + '<div class="card"><div class="card-title">设备稼动率</div><div id="chartEqp" style="height:280px"></div></div>'
        + '<div class="card"><div class="card-title">各车间产出</div><div id="chartWS" style="height:280px"></div></div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">'
        + '<div class="card"><div class="card-title">库存预警 <span style="color:#f5222d;font-size:12px">（低于10件）</span></div>'
        + '<table><thead><tr><th>物料</th><th>编码</th><th>库存</th></tr></thead><tbody id="lowStock"></tbody></table></div>'
        + '<div class="card"><div class="card-title">逾期保养 <span style="color:#fa8c16;font-size:12px">⚠</span></div>'
        + '<table><thead><tr><th>计划</th><th>设备</th><th>到期日</th></tr></thead><tbody id="overdueMaint"></tbody></table></div>'
        + '</div>'
        + '<div class="card"><div class="card-title">快捷操作</div>'
        + '<div class="quick-btns">'
        + '<button class="btn btn-blue" onclick="goPage(\'prod/workorder\')">新建工单</button>'
        + '<button class="btn btn-green" onclick="goPage(\'inv/inbound\')">入库登记</button>'
        + '<button class="btn btn-blue" onclick="goPage(\'qm/incoming\')">来料检验</button>'
        + '<button class="btn btn-red" onclick="goPage(\'eqp/repair\')">设备报修</button>'
        + '<button class="btn btn-orange" style="background:#fa8c16;color:#fff" onclick="goPage(\'flow/pending\')">待审批</button>'
        + '<button class="btn btn-blue" onclick="window.open(\'/kanban\',\'_blank\')">生产看板</button>'
        + '<button class="btn btn-green" onclick="goPage(\'doc/list\')">文档管理</button>'
        + '<button class="btn btn-gray" onclick="goPage(\'sys/backup\')">数据备份</button>'
        + '</div></div>';

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

        var c1 = echarts.init(document.getElementById('chartOutput'));
        c1.setOption({
            tooltip:{trigger:'axis'}, legend:{data:['合格','不良']},
            xAxis:{type:'category',data:d.daily_output.map(function(i){return i.date.slice(5)})},
            yAxis:{type:'value'},
            series:[
                {name:'合格',type:'line',smooth:true,data:d.daily_output.map(function(i){return i.qualified}),itemStyle:{color:'#52c41a'}},
                {name:'不良',type:'line',smooth:true,data:d.daily_output.map(function(i){return i.defect}),itemStyle:{color:'#f5222d'}}
            ]
        });

        var c2 = echarts.init(document.getElementById('chartWO'));
        c2.setOption({
            tooltip:{trigger:'item'},
            series:[{type:'pie',radius:['40%','70%'],data:d.wo_stats,label:{formatter:'{b}: {c}'}}]
        });

        var c3 = echarts.init(document.getElementById('chartEqp'));
        c3.setOption({
            series:[{
                type:'gauge', progress:{show:true}, radius:'80%',
                axisLine:{lineStyle:{width:12}},
                axisTick:{show:false}, splitLine:{length:10},
                pointer:{length:'60%'},
                axisLabel:{fontSize:11},
                detail:{valueAnimation:true,formatter:'{value}%',fontSize:20,offsetCenter:[0,'70%']},
                data:[{value:d.eqp_rate,name:'稼动率'}]
            }]
        });

        var c4 = echarts.init(document.getElementById('chartWS'));
        c4.setOption({
            tooltip:{trigger:'axis'},
            xAxis:{type:'category',data:d.workshop_output.map(function(i){return i.workshop_name}),axisLabel:{rotate:30}},
            yAxis:{type:'value'},
            series:[{type:'bar',data:d.workshop_output.map(function(i){return i.qty}),itemStyle:{color:'#1890ff'}}]
        });

        window.addEventListener('resize',function(){c1.resize();c2.resize();c3.resize();c4.resize();});

        var ls = document.getElementById('lowStock');
        if(d.low_stock.length) {
            ls.innerHTML = d.low_stock.map(function(i){return '<tr><td>'+i.product_name+'</td><td>'+i.code+'</td><td style="color:#f5222d;font-weight:bold">'+i.quantity+'</td></tr>'}).join('');
        } else {
            ls.innerHTML = '<tr><td colspan="3" class="empty">暂无预警</td></tr>';
        }

        var om = document.getElementById('overdueMaint');
        if(d.overdue_maint.length) {
            om.innerHTML = d.overdue_maint.map(function(i){return '<tr><td>'+i.plan_name+'</td><td>'+i.equipment_name+'</td><td style="color:#fa8c16">'+i.next_date+'</td></tr>'}).join('');
        } else {
            om.innerHTML = '<tr><td colspan="3" class="empty">暂无逾期</td></tr>';
        }
    });
}
