/* 数据分析页面 */

// OEE分析
function renderOEE(el) {
    el.innerHTML = '<div class="card"><div class="card-title">OEE 设备综合效率</div>'
        + '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">OEE</div><div class="val" id="oee" style="color:#1890ff">-</div></div>'
        + '<div class="stat"><div class="label">可用率</div><div class="val" id="availability">-</div></div>'
        + '<div class="stat"><div class="label">表现率</div><div class="val" id="performance">-</div></div>'
        + '<div class="stat"><div class="label">良品率</div><div class="val" id="quality">-</div></div>'
        + '</div>'
        + '<div id="oeeChart" style="height:300px"></div></div>';
    api('/api/analytics/oee').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        document.getElementById('oee').textContent = d.oee+'%';
        document.getElementById('availability').textContent = d.availability+'%';
        document.getElementById('performance').textContent = d.performance+'%';
        document.getElementById('quality').textContent = d.quality+'%';
        var chart = echarts.init(document.getElementById('oeeChart'));
        chart.setOption({
            series:[{
                type:'gauge', radius:'80%',
                axisLine:{lineStyle:{width:20,color:[[0.6,'#f5222d'],[0.8,'#fa8c16'],[1,'#52c41a']]}},
                pointer:{length:'60%'},
                axisTick:{show:false}, splitLine:{length:10},
                axisLabel:{fontSize:11},
                detail:{valueAnimation:true,formatter:'{value}%',fontSize:24,offsetCenter:[0,'70%']},
                data:[{value:d.oee,name:'OEE'}]
            }]
        });
    });
}

// 产能分析
function renderCapacity(el) {
    el.innerHTML = '<div class="card"><div class="card-title">产能分析</div>'
        + '<div id="capacityChart" style="height:300px;margin-bottom:16px"></div></div>'
        + '<div class="card"><div class="card-title">员工效率排名</div>'
        + '<table><thead><tr><th>排名</th><th>员工</th><th>任务数</th><th>合格数</th><th>不良数</th></tr></thead>'
        + '<tbody id="empList"><tr><td colspan="5" class="empty">加载中...</td></tr></tbody></table></div>';
    api('/api/analytics/capacity').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        var chart = echarts.init(document.getElementById('capacityChart'));
        chart.setOption({
            tooltip:{trigger:'axis'},
            legend:{data:['待完成','已完成']},
            xAxis:{type:'category',data:d.workshops.map(function(w){return w.workshop_name})},
            yAxis:{type:'value'},
            series:[
                {name:'待完成',type:'bar',data:d.workshops.map(function(w){return w.pending_qty}),itemStyle:{color:'#fa8c16'}},
                {name:'已完成',type:'bar',data:d.workshops.map(function(w){return w.completed_qty}),itemStyle:{color:'#52c41a'}}
            ]
        });
        var empEl = document.getElementById('empList');
        empEl.innerHTML = d.employees.map(function(e,i) {
            return '<tr><td>'+(i+1)+'</td><td>'+MESUI.escapeHtml(e.real_name)+'</td><td>'+MESUI.escapeHtml(e.task_count)+'</td>'
                +'<td style="color:#52c41a">'+MESUI.escapeHtml(e.total_qualified)+'</td><td style="color:#f5222d">'+MESUI.escapeHtml(e.total_defect)+'</td></tr>';
        }).join('');
    });
}

// 交期预警
function renderDeliveryAlert(el) {
    el.innerHTML = '<div class="card"><div class="card-title" style="color:#f5222d">逾期工单</div>'
        + '<table><thead><tr><th>工单号</th><th>产品</th><th>计划</th><th>完成</th><th>交期</th><th>车间</th></tr></thead>'
        + '<tbody id="overdueList"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>'
        + '<div class="card"><div class="card-title" style="color:#fa8c16">即将到期（3天内）</div>'
        + '<table><thead><tr><th>工单号</th><th>产品</th><th>计划</th><th>完成</th><th>交期</th><th>车间</th></tr></thead>'
        + '<tbody id="upcomingList"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    api('/api/analytics/delivery-alert').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        var ol = document.getElementById('overdueList');
        if(d.overdue.length) {
            ol.innerHTML = d.overdue.map(function(o) {
                return '<tr><td>'+MESUI.escapeHtml(o.order_no)+'</td><td>'+MESUI.escapeHtml(o.product_name)+'</td><td>'+MESUI.escapeHtml(o.planned_qty)+'</td>'
                    +'<td>'+o.completed_qty+'</td><td style="color:#f5222d;font-weight:bold">'+MESUI.escapeHtml(o.end_date)+'</td>'
                    +'<td>'+MESUI.escapeHtml(o.workshop_name||'-')+'</td></tr>';
            }).join('');
        } else { ol.innerHTML = '<tr><td colspan="6" class="empty">无逾期工单</td></tr>'; }
        var ul = document.getElementById('upcomingList');
        if(d.upcoming.length) {
            ul.innerHTML = d.upcoming.map(function(u) {
                return '<tr><td>'+MESUI.escapeHtml(u.order_no)+'</td><td>'+MESUI.escapeHtml(u.product_name)+'</td><td>'+MESUI.escapeHtml(u.planned_qty)+'</td>'
                    +'<td>'+u.completed_qty+'</td><td style="color:#fa8c16">'+MESUI.escapeHtml(u.end_date)+'</td>'
                    +'<td>'+MESUI.escapeHtml(u.workshop_name||'-')+'</td></tr>';
            }).join('');
        } else { ul.innerHTML = '<tr><td colspan="6" class="empty">无即将到期工单</td></tr>'; }
    });
}

// 库存分析
function renderInventoryAnalysis(el) {
    el.innerHTML = '<div class="card"><div class="card-title">库存分析</div>'
        + '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">库存总量</div><div class="val" id="totalQty">-</div></div>'
        + '<div class="stat"><div class="label">库存金额</div><div class="val" id="totalAmt">-</div></div>'
        + '<div class="stat"><div class="label">周转率</div><div class="val" id="turnover">-</div></div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
        + '<div><div class="card-title">ABC分析</div><div id="abcChart" style="height:250px"></div></div>'
        + '<div><div class="card-title">库存预警</div><table><thead><tr><th>物料</th><th>编码</th><th>库存</th></tr></thead>'
        + '<tbody id="lowStock"><tr><td colspan="3" class="empty">加载中...</td></tr></tbody></table></div>'
        + '</div></div>';
    api('/api/analytics/inventory-turnover').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        document.getElementById('totalQty').textContent = d.total_stock_qty;
        document.getElementById('totalAmt').textContent = '¥'+d.total_stock_amount.toFixed(2);
        document.getElementById('turnover').textContent = d.turnover_rate;
        // ABC分析
        var abc = {A:0,B:0,C:0};
        d.abc_analysis.forEach(function(item) { abc[item.abc_class] = (abc[item.abc_class]||0) + 1; });
        var chart = echarts.init(document.getElementById('abcChart'));
        chart.setOption({
            tooltip:{trigger:'item'},
            series:[{type:'pie',radius:['40%','70%'],
                data:[{name:'A类',value:abc.A,itemStyle:{color:'#f5222d'}},{name:'B类',value:abc.B,itemStyle:{color:'#fa8c16'}},{name:'C类',value:abc.C,itemStyle:{color:'#52c41a'}}],
                label:{formatter:'{b}: {c}'}}]
        });
        // 低库存
        var ls = document.getElementById('lowStock');
        if(d.low_stock.length) {
            ls.innerHTML = d.low_stock.map(function(l) {
                return '<tr><td>'+MESUI.escapeHtml(l.product_name)+'</td><td>'+MESUI.escapeHtml(l.code)+'</td><td style="color:#f5222d;font-weight:bold">'+MESUI.escapeHtml(l.quantity)+'</td></tr>';
            }).join('');
        } else { ls.innerHTML = '<tr><td colspan="3" class="empty">暂无预警</td></tr>'; }
    });
}

// 良率统计
function renderYieldAnalysis(el) {
    el.innerHTML = '<div class="card"><div class="card-title">良率统计</div>'
        + '<div class="toolbar"><select id="yieldDays"><option value="7">近7天</option><option value="30" selected>近30天</option><option value="90">近90天</option></select>'
        + '<button class="btn btn-blue" onclick="loadYield()">分析</button></div>'
        + '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">总体良率</div><div class="val" id="y_overall" style="color:#52c41a">-</div></div>'
        + '<div class="stat"><div class="label">平均良率</div><div class="val" id="y_avg">-</div></div>'
        + '<div class="stat"><div class="label">总合格数</div><div class="val" id="y_qualified">-</div></div>'
        + '<div class="stat"><div class="label">总不良数</div><div class="val" id="y_defect" style="color:#f5222d">-</div></div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
        + '<div class="card"><div class="card-title">良率趋势</div><div id="yieldTrendChart" style="height:300px"></div></div>'
        + '<div class="card"><div class="card-title">各工序良率</div><div id="yieldProcessChart" style="height:300px"></div></div>'
        + '</div></div>';
    loadYield();
}
function loadYield() {
    var days = document.getElementById('yieldDays').value;
    api('/api/analytics/yield?days='+days).then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        document.getElementById('y_overall').textContent = d.overall_yield+'%';
        document.getElementById('y_avg').textContent = d.avg_yield+'%';
        document.getElementById('y_qualified').textContent = d.total_qualified;
        document.getElementById('y_defect').textContent = d.total_defect;
        if(d.daily.length) {
            var c1 = echarts.init(document.getElementById('yieldTrendChart'));
            c1.setOption({
                tooltip:{trigger:'axis'},legend:{data:['合格','不良']},
                xAxis:{type:'category',data:d.daily.map(function(i){return i.date.slice(5)})},
                yAxis:{type:'value'},
                series:[
                    {name:'合格',type:'bar',stack:'total',data:d.daily.map(function(i){return i.qualified}),itemStyle:{color:'#52c41a'}},
                    {name:'不良',type:'bar',stack:'total',data:d.daily.map(function(i){return i.defect}),itemStyle:{color:'#f5222d'}}
                ]
            });
            window.addEventListener('resize',function(){c1.resize();});
        }
        if(d.by_process.length) {
            var c2 = echarts.init(document.getElementById('yieldProcessChart'));
            c2.setOption({
                tooltip:{trigger:'axis'},
                xAxis:{type:'category',data:d.by_process.map(function(p){return p.process})},
                yAxis:{type:'value',min:0,max:100,axisLabel:{formatter:'{value}%'}},
                series:[{
                    type:'bar',data:d.by_process.map(function(p){return p.yield_rate}),
                    itemStyle:{color:function(p){return p.value>=95?'#52c41a':(p.value>=80?'#fa8c16':'#f5222d')}},
                    label:{show:true,position:'top',formatter:'{c}%',fontSize:11}
                }]
            });
            window.addEventListener('resize',function(){c2.resize();});
        }
    });
}

// 数据看板
function renderDataDashboard(el) {
    el.innerHTML = '<div class="card"><div class="card-title">数据看板 <span style="color:#999;font-size:12px;font-weight:normal">实时刷新</span></div>'
        + '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">今日产出</div><div class="val" id="d_output">-</div></div>'
        + '<div class="stat"><div class="label">今日良率</div><div class="val" id="d_yield" style="color:#52c41a">-</div></div>'
        + '<div class="stat"><div class="label">待处理异常</div><div class="val" id="d_alerts" style="color:#f5222d">-</div></div>'
        + '<div class="stat"><div class="label">库存预警</div><div class="val" id="d_stock" style="color:#fa8c16">-</div></div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">'
        + '<div class="card"><div class="card-title">工单状态</div><div id="dashWOChart" style="height:250px"></div></div>'
        + '<div class="card"><div class="card-title">设备状态</div><div id="dashEqpChart" style="height:250px"></div></div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
        + '<div class="card"><div class="card-title">近7天良率趋势</div><div id="dashYieldChart" style="height:250px"></div></div>'
        + '<div class="card"><div class="card-title">库存预警</div><table><thead><tr><th>物料</th><th>编码</th><th>库存</th></tr></thead>'
        + '<tbody id="dashLowStock"><tr><td colspan="3" class="empty">加载中...</td></tr></tbody></table></div>'
        + '</div></div>';
    loadDashboard();
}
function loadDashboard() {
    api('/api/analytics/data-dashboard').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        document.getElementById('d_output').textContent = d.today.output;
        document.getElementById('d_yield').textContent = d.today.yield_rate+'%';
        var yieldEl = document.getElementById('d_yield');
        yieldEl.style.color = d.today.yield_rate >= 95 ? '#52c41a' : (d.today.yield_rate >= 80 ? '#fa8c16' : '#f5222d');
        document.getElementById('d_alerts').textContent = d.alerts.exceptions + d.alerts.defects;
        document.getElementById('d_stock').textContent = d.low_stock.length;
        if(d.wo_stats.length) {
            var c1 = echarts.init(document.getElementById('dashWOChart'));
            c1.setOption({tooltip:{trigger:'item'},legend:{bottom:0},series:[{type:'pie',radius:['40%','65%'],data:d.wo_stats,label:{formatter:'{b}\n{c}'}}]});
            window.addEventListener('resize',function(){c1.resize();});
        }
        if(d.eqp_stats.length) {
            var colors = {'运行':'#52c41a','维修':'#fa8c16','停用':'#f5222d'};
            var c2 = echarts.init(document.getElementById('dashEqpChart'));
            c2.setOption({tooltip:{trigger:'item'},legend:{bottom:0},series:[{type:'pie',radius:['40%','65%'],data:d.eqp_stats.map(function(e){return {name:e.name,value:e.value,itemStyle:{color:colors[e.name]||'#999'}}}),label:{formatter:'{b}\n{c}'}}]});
            window.addEventListener('resize',function(){c2.resize();});
        }
        if(d.yield_trend.length) {
            var c3 = echarts.init(document.getElementById('dashYieldChart'));
            c3.setOption({tooltip:{trigger:'axis'},xAxis:{type:'category',data:d.yield_trend.map(function(i){return i.date.slice(5)})},yAxis:{type:'value',min:80,max:100,axisLabel:{formatter:'{value}%'}},series:[{type:'line',smooth:true,data:d.yield_trend.map(function(i){return i.rate}),markLine:{data:[{yAxis:95,lineStyle:{color:'#52c41a',type:'dashed'}}]},itemStyle:{color:'#1890ff'}}]});
            window.addEventListener('resize',function(){c3.resize();});
        }
        var ls = document.getElementById('dashLowStock');
        if(d.low_stock.length) {
            ls.innerHTML = d.low_stock.map(function(l) { return '<tr><td>'+MESUI.escapeHtml(l.product_name)+'</td><td>'+MESUI.escapeHtml(l.code)+'</td><td style="color:#f5222d;font-weight:bold">'+MESUI.escapeHtml(l.quantity)+'</td></tr>'; }).join('');
        } else { ls.innerHTML = '<tr><td colspan="3" class="empty">暂无预警</td></tr>'; }
    });
}
