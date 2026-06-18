/* 更多业务页面模块 - 第二部分 */

// 生产报表
function renderProdReport(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>生产报表</span>'
        + '<button class="btn btn-green" onclick="exportProdPDF()">导出报表</button></div>'
        + '<div class="stats" style="grid-template-columns:repeat(3,1fr)">'
        + '<div class="stat"><div class="label">工单总数</div><div class="val" id="r1">-</div></div>'
        + '<div class="stat"><div class="label">完成率</div><div class="val" id="r2">-</div></div>'
        + '<div class="stat"><div class="label">不良率</div><div class="val" id="r3">-</div></div>'
        + '</div></div>';
    api('/api/prod/workorder/list?size=1000').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var total = list.length;
        var planned = 0, completed = 0, defect = 0;
        list.forEach(function(w) { planned += w.planned_qty; completed += w.completed_qty; defect += w.defect_qty; });
        document.getElementById('r1').textContent = total;
        document.getElementById('r2').textContent = planned ? (completed / planned * 100).toFixed(1) + '%' : '0%';
        document.getElementById('r3').textContent = planned ? (defect / planned * 100).toFixed(1) + '%' : '0%';
    });
}
function exportProdPDF() {
    window.open('/api/report/production/pdf', '_blank');
}

// 工具领用
function renderToolBorrow(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工具领用</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'tool_borrow\')">导出</button>'
        + '<button class="btn btn-blue" id="tbAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>领用单号</th><th>工具</th><th>领用人</th><th>数量</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('tbAddBtn').onclick = tbAdd;
    tbLoad();
}
function tbLoad() {
    api('/api/tool/borrow/list').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : (Array.isArray(r.data) ? r.data : []);
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + (r2.borrow_no||'') + '</td><td>' + (r2.tool_name||r2.tool_id) + '</td>';
            h += '<td>' + (r2.borrower_name||'') + '</td><td>' + r2.borrow_qty + '</td>';
            h += '<td><span class="tag ' + (r2.status ? 'tag-ok' : 'tag-wait') + '">' + (r2.status ? '已还' : '借出') + '</span></td>';
            h += '<td>' + (r2.borrow_time||'') + '</td>';
            h += '<td class="actions">';
            if(!r2.status) h += '<button class="btn btn-green btn-sm" onclick="tbReturn(' + r2.id + ',' + r2.borrow_qty + ')">归还</button>';
            h += '<button class="btn btn-red btn-sm" onclick="tbDel(' + r2.id + ')">删除</button></td></tr>';
        });
        tb.innerHTML = h;
    });
}
function tbAdd() {
    api('/api/tool/ledger/list?size=1000').then(function(r) {
        var tools = (r && r.data) ? (Array.isArray(r.data) ? r.data : (r.data.list || [])) : [];
        var opts = '<option value="">请选择工具</option>';
        tools.forEach(function(t) { opts += '<option value="' + t.id + '">' + t.tool_name + ' (' + t.code + ')</option>'; });
        document.getElementById('mTitle').textContent = '新增领用';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工具<span style="color:red">*</span></label><select id="f_tid">' + opts + '</select></div>'
            + '<div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_qty" type="number" step="0.01"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>备注</label><textarea id="f_remark"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {tool_id:document.getElementById('f_tid').value, borrow_qty:document.getElementById('f_qty').value, remark:document.getElementById('f_remark').value};
            if(!d.tool_id || !d.borrow_qty) { alert('请填写必填项'); return; }
            api('/api/tool/borrow/add', {method:'POST', body:d}).then(function(r2) {
                if(r2 && r2.code === 0) { closeModal(); tbLoad(); } else alert(r2 ? r2.message : '保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function tbReturn(id, maxQty) {
    document.getElementById('mTitle').textContent = '工具归还';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>归还数量<span style="color:red">*</span></label><input id="f_rqty" type="number" step="0.01" value="' + maxQty + '"></div></div>';
    modalSaveHandler = function() {
        var qty = document.getElementById('f_rqty').value;
        if(!qty || qty <= 0) { alert('请输入归还数量'); return; }
        api('/api/tool/borrow/return', {method:'POST', body:{id:id, return_qty:Number(qty)}}).then(function(r) {
            if(r && r.code === 0) { closeModal(); tbLoad(); } else alert(r ? r.message : '归还失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function tbDel(id) { if(!confirm('确定删除？')) return; api('/api/tool/borrow/delete', {method:'POST', body:{id:id}}).then(function(){tbLoad()}); }

// 过程检验
function renderQMProcess(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>过程检验</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'qm_process_inspection\')">导出</button>'
        + '<button class="btn btn-blue" id="qmProcAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>检验单号</th><th>工单</th><th>结果</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('qmProcAddBtn').onclick = qmProcAdd;
    qmProcLoad();
}
function qmProcLoad() {
    api('/api/qm/process/list').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : (Array.isArray(r.data) ? r.data : []);
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + (r2.inspect_no||'') + '</td><td>' + (r2.workorder_id||'') + '</td>';
            h += '<td>' + (r2.result||'-') + '</td>';
            h += '<td><span class="tag ' + (r2.status ? 'tag-ok' : 'tag-wait') + '">' + (r2.status ? '已检' : '待检') + '</span></td>';
            h += '<td>' + (r2.created_at||'') + '</td>';
            h += '<td><button class="btn btn-red btn-sm" onclick="qmProcDel(' + r2.id + ')">删除</button></td></tr>';
        });
        tb.innerHTML = h;
    });
}
function qmProcAdd() {
    api('/api/prod/workorder/list?size=500').then(function(r) {
        var woList = r && r.data ? (r.data.list || r.data) : [];
        var opts = '<option value="">请选择工单</option>';
        woList.forEach(function(w) { opts += '<option value="' + w.id + '">' + w.order_no + ' - ' + (w.product_name||'') + '</option>'; });
        document.getElementById('mTitle').textContent = '新增过程检验';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工单</label><select id="f_wo">' + opts + '</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>结果</label><select id="f_result"><option value="合格">合格</option><option value="不合格">不合格</option></select></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>备注</label><textarea id="f_remark"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {workorder_id:document.getElementById('f_wo').value || undefined, result:document.getElementById('f_result').value, remark:document.getElementById('f_remark').value, status:1};
            api('/api/qm/process/add', {method:'POST', body:d}).then(function(r2) {
                if(r2 && r2.code === 0) { closeModal(); qmProcLoad(); } else alert(r2 ? r2.message : '保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function qmProcDel(id) { if(!confirm('确定删除？')) return; api('/api/qm/process/delete', {method:'POST', body:{id:id}}).then(function(){qmProcLoad()}); }
