/* 数据查询页面 */

// 生产查询
function renderQueryProduction(el) {
    el.innerHTML = '<div class="card"><div class="card-title">生产数据查询</div>'
        + '<div class="toolbar">'
        + '<input id="q_start" type="date" style="width:140px">'
        + '<input id="q_end" type="date" style="width:140px">'
        + '<select id="q_status"><option value="">全部状态</option><option value="0">草稿</option><option value="1">已下达</option><option value="2">生产中</option><option value="3">已完工</option><option value="4">已暂停</option><option value="5">已关闭</option><option value="6">已取消</option></select>'
        + '<button class="btn btn-blue" onclick="queryProduction()">查询</button>'
        + '<button class="btn btn-gray" onclick="queryProductionReset()">重置</button>'
        + '</div></div>'
        + '<div class="card"><table><thead><tr><th>工单号</th><th>产品</th><th>计划数</th><th>完成数</th><th>不良数</th><th>车间</th><th>状态</th><th>创建时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">请输入查询条件</td></tr></tbody></table></div>';
}
function queryProduction() {
    var params = new URLSearchParams();
    var start = document.getElementById('q_start').value;
    var end = document.getElementById('q_end').value;
    var status = document.getElementById('q_status').value;
    if(start) params.set('start_date', start);
    if(end) params.set('end_date', end);
    if(status) params.set('status', status);
    api('/api/query/production?' + params.toString()).then(function(r) {
        if(!r) return;
        var list = r.data || [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">无匹配数据</td></tr>'; return; }
        var st = {0:'<span class="tag tag-draft">草稿</span>',1:'<span class="tag tag-wait">已下达</span>',2:'<span class="tag tag-run">生产中</span>',3:'<span class="tag tag-ok">已完工</span>',4:'<span class="tag tag-wait">已暂停</span>',5:'<span class="tag tag-ok">已关闭</span>',6:'<span class="tag tag-no">已取消</span>'};
        tb.innerHTML = list.map(function(w) {
            return '<tr><td>'+MESUI.escapeHtml(w.order_no)+'</td><td>'+MESUI.escapeHtml(w.product_name||'-')+'</td><td>'+MESUI.escapeHtml(w.planned_qty)+'</td><td>'+w.completed_qty+'</td>'
                +'<td>'+(w.defect_qty||0)+'</td><td>'+MESUI.escapeHtml(w.workshop_name||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(st[w.status]||'-')+'</td><td>'+(w.created_at||'')+'</td></tr>';
        }).join('');
    });
}
function queryProductionReset() {
    document.getElementById('q_start').value = '';
    document.getElementById('q_end').value = '';
    document.getElementById('q_status').value = '';
    document.getElementById('tb').innerHTML = '<tr><td colspan="8" class="empty">请输入查询条件</td></tr>';
}

// 库存查询
function renderQueryInventory(el) {
    el.innerHTML = '<div class="card"><div class="card-title">库存数据查询</div>'
        + '<div class="toolbar">'
        + '<input id="q_keyword" placeholder="产品名称/编码">'
        + '<select id="q_type"><option value="">全部类型</option><option value="成品">成品</option><option value="半成品">半成品</option><option value="原材料">原材料</option></select>'
        + '<input id="q_min" type="number" placeholder="最小数量" style="width:100px">'
        + '<input id="q_max" type="number" placeholder="最大数量" style="width:100px">'
        + '<button class="btn btn-blue" onclick="queryInventory()">查询</button>'
        + '</div></div>'
        + '<div class="card"><table><thead><tr><th>产品</th><th>编码</th><th>类型</th><th>库存</th><th>单位</th><th>金额</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">请输入查询条件</td></tr></tbody></table></div>';
}
function queryInventory() {
    var params = new URLSearchParams();
    var kw = document.getElementById('q_keyword').value;
    var type = document.getElementById('q_type').value;
    var min = document.getElementById('q_min').value;
    var max = document.getElementById('q_max').value;
    if(kw) params.set('keyword', kw);
    if(type) params.set('product_type', type);
    if(min) params.set('min_qty', min);
    if(max) params.set('max_qty', max);
    api('/api/query/inventory?' + params.toString()).then(function(r) {
        if(!r) return;
        var list = r.data || [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">无匹配数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(b) {
            var qtyColor = b.quantity < 10 ? '#f5222d' : '#333';
            return '<tr><td>'+MESUI.escapeHtml(b.product_name)+'</td><td>'+MESUI.escapeHtml(b.code)+'</td><td>'+(b.product_type||'-')+'</td>'
                +'<td style="color:'+qtyColor+';font-weight:bold">'+MESUI.escapeHtml(b.quantity)+'</td><td>'+MESUI.escapeHtml(b.unit||'-')+'</td>'
                +'<td>¥'+(b.amount||0).toFixed(2)+'</td></tr>';
        }).join('');
    });
}

// 质量查询
function renderQueryQuality(el) {
    el.innerHTML = '<div class="card"><div class="card-title">质量数据查询</div>'
        + '<div class="toolbar">'
        + '<select id="q_type"><option value="incoming">来料检验</option><option value="process">过程检验</option><option value="outgoing">出货检验</option></select>'
        + '<input id="q_start" type="date" style="width:140px">'
        + '<input id="q_end" type="date" style="width:140px">'
        + '<select id="q_result"><option value="">全部结果</option><option value="合格">合格</option><option value="不合格">不合格</option></select>'
        + '<button class="btn btn-blue" onclick="queryQuality()">查询</button>'
        + '</div></div>'
        + '<div class="card"><table><thead><tr><th>检验单号</th><th>供应商/工单/客户</th><th>结果</th><th>状态</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="5" class="empty">请输入查询条件</td></tr></tbody></table></div>';
}
function queryQuality() {
    var params = new URLSearchParams();
    params.set('inspect_type', document.getElementById('q_type').value);
    var start = document.getElementById('q_start').value;
    var end = document.getElementById('q_end').value;
    var result = document.getElementById('q_result').value;
    if(start) params.set('start_date', start);
    if(end) params.set('end_date', end);
    if(result) params.set('result', result);
    api('/api/query/quality?' + params.toString()).then(function(r) {
        if(!r) return;
        var list = r.data || [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="5" class="empty">无匹配数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(q) {
            var resultTag = q.result === '合格' ? '<span class="tag tag-ok">合格</span>' : '<span class="tag tag-no">不合格</span>';
            return '<tr><td>'+MESUI.escapeHtml(q.inspect_no)+'</td><td>'+(q.supplier||q.workorder_id||q.customer||'-')+'</td>'
                +'<td>'+resultTag+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(q.status?'tag-ok':'tag-wait')+'">'+MESUI.escapeHtml(q.status?'已检':'待检')+'</span></td>'
                +'<td>'+(q.created_at||'')+'</td></tr>';
        }).join('');
    });
}

// 设备查询
function renderQueryEquipment(el) {
    el.innerHTML = '<div class="card"><div class="card-title">设备数据查询</div>'
        + '<div class="toolbar">'
        + '<input id="q_keyword" placeholder="设备名称/编码">'
        + '<select id="q_status"><option value="">全部状态</option><option value="1">运行</option><option value="2">维修</option><option value="0">停用</option></select>'
        + '<button class="btn btn-blue" onclick="queryEquipment()">查询</button>'
        + '</div></div>'
        + '<div class="card"><table><thead><tr><th>设备名称</th><th>编码</th><th>型号</th><th>制造商</th><th>车间</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">请输入查询条件</td></tr></tbody></table></div>';
}
function queryEquipment() {
    var params = new URLSearchParams();
    var kw = document.getElementById('q_keyword').value;
    var status = document.getElementById('q_status').value;
    if(kw) params.set('keyword', kw);
    if(status) params.set('status', status);
    api('/api/query/equipment?' + params.toString()).then(function(r) {
        if(!r) return;
        var list = r.data || [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">无匹配数据</td></tr>'; return; }
        var st = {1:'<span class="tag tag-ok">运行</span>',2:'<span class="tag tag-run">维修</span>',0:'<span class="tag tag-draft">停用</span>'};
        tb.innerHTML = list.map(function(e) {
            return '<tr><td>'+MESUI.escapeHtml(e.equipment_name)+'</td><td>'+MESUI.escapeHtml(e.code)+'</td><td>'+MESUI.escapeHtml(e.model||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(e.manufacturer||'-')+'</td><td>'+MESUI.escapeHtml(e.workshop_name||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(st[e.status]||'-')+'</td></tr>';
        }).join('');
    });
}

// 员工查询
function renderQueryEmployee(el) {
    el.innerHTML = '<div class="card"><div class="card-title">员工数据查询</div>'
        + '<div class="toolbar">'
        + '<input id="q_keyword" placeholder="姓名/工号/手机">'
        + '<button class="btn btn-blue" onclick="queryEmployee()">查询</button>'
        + '</div></div>'
        + '<div class="card"><table><thead><tr><th>工号</th><th>姓名</th><th>手机</th><th>部门</th><th>角色</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">请输入查询条件</td></tr></tbody></table></div>';
}
function queryEmployee() {
    var kw = document.getElementById('q_keyword').value;
    if(!kw) { alert('请输入搜索关键词'); return; }
    api('/api/query/employee?keyword=' + encodeURIComponent(kw)).then(function(r) {
        if(!r) return;
        var list = r.data || [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">无匹配数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(u) {
            return '<tr><td>'+MESUI.escapeHtml(u.username)+'</td><td>'+MESUI.escapeHtml(u.real_name)+'</td><td>'+MESUI.escapeHtml(u.phone||'-')+'</td>'
                +'<td>'+(u.dept_name||'-')+'</td><td>'+MESUI.escapeHtml(u.role_name||'-')+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(u.status?'tag-ok':'tag-draft')+'">'+MESUI.escapeHtml(u.status?'在职':'离职')+'</span></td></tr>';
        }).join('');
    });
}

// 综合统计
function renderQueryStatistics(el) {
    el.innerHTML = '<div class="card"><div class="card-title">综合统计</div>'
        + '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">工单总数</div><div class="val" id="s_orders">-</div></div>'
        + '<div class="stat"><div class="label">完成率</div><div class="val" id="s_rate" style="color:#52c41a">-</div></div>'
        + '<div class="stat"><div class="label">总产出</div><div class="val" id="s_output">-</div></div>'
        + '<div class="stat"><div class="label">不良率</div><div class="val" id="s_defect" style="color:#f5222d">-</div></div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">产品种类</div><div class="val" id="s_products">-</div></div>'
        + '<div class="stat"><div class="label">库存总量</div><div class="val" id="s_stock">-</div></div>'
        + '<div class="stat"><div class="label">设备总数</div><div class="val" id="s_eqp">-</div></div>'
        + '<div class="stat"><div class="label">员工总数</div><div class="val" id="s_users">-</div></div>'
        + '</div></div>';
    api('/api/query/statistics').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        document.getElementById('s_orders').textContent = d.production.total_orders;
        document.getElementById('s_rate').textContent = d.production.completion_rate + '%';
        document.getElementById('s_output').textContent = d.production.total_output;
        document.getElementById('s_defect').textContent = d.production.defect_rate + '%';
        document.getElementById('s_products').textContent = d.inventory.total_products;
        document.getElementById('s_stock').textContent = d.inventory.total_stock;
        document.getElementById('s_eqp').textContent = d.equipment.total + ' (运行' + d.equipment.running + ')';
        document.getElementById('s_users').textContent = d.personnel.total_users;
    });
}
