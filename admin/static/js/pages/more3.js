/* 更多业务页面模块 - 第三部分 */

// 保养计划
function renderMaintenance(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>保养计划</span><button class="btn btn-blue" id="maintAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>计划名称</th><th>设备</th><th>检查项</th><th>保养周期</th><th>下次日期</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('maintAddBtn').onclick = maintAdd;
    maintLoad();
}
function maintLoad() {
    api('/api/eqp/maintenance/list?size=100').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        var today = new Date().toISOString().slice(0,10);
        var h = '';
        list.forEach(function(r2) {
            var overdue = r2.next_date && r2.next_date < today && r2.status;
            var statusTag = overdue ? '<span class="tag tag-no">已逾期</span>' : (r2.status ? '<span class="tag tag-ok">启用</span>' : '<span class="tag tag-draft">停用</span>');
            h += '<tr><td>'+MESUI.escapeHtml(r2.id)+'</td><td>'+MESUI.escapeHtml(r2.plan_name)+'</td><td>'+MESUI.escapeHtml(r2.equipment_name||r2.equipment_id)+'</td>';
            h += '<td>'+MESUI.escapeHtml(r2.check_items||'-')+'</td><td>'+MESUI.escapeHtml(r2.frequency||'-')+'</td>';
            h += '<td'+(overdue?' style="color:#f5222d;font-weight:bold"':'')+'>'+MESUI.escapeHtml(r2.next_date||'-')+'</td>';
            h += '<td>'+statusTag+'</td>';
            h += '<td>'+(r2.status ? '<button class="btn btn-green btn-sm" onclick="maintExec('+r2.id+','+r2.equipment_id+')">执行保养</button> ' : '');
            h += '<button class="btn btn-red btn-sm" onclick="maintDel('+r2.id+')">删除</button></td></tr>';
        });
        tb.innerHTML = h;
    });
}
function maintAdd() {
    api('/api/eqp/ledger/list?size=1000').then(function(r) {
        var eqps = (r && r.data) ? (r.data.list || r.data) : [];
        var opts = '<option value="">请选择设备</option>';
        eqps.forEach(function(e) { opts += '<option value="'+MESUI.escapeHtml(e.id)+'">'+MESUI.escapeHtml(e.equipment_name+' ('+e.code+')')+'</option>'; });
        document.getElementById('mTitle').textContent = '新增保养计划';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>计划名称<span style="color:red">*</span></label><input id="f_pn"></div>'
            + '<div class="form-item"><label>设备<span style="color:red">*</span></label><select id="f_eq">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>保养周期</label><select id="f_freq"><option value="日">每日</option><option value="周">每周</option><option value="月" selected>每月</option><option value="季">每季</option><option value="年">每年</option></select></div>'
            + '<div class="form-item"><label>下次日期</label><input id="f_nd" type="date"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>检查项目</label><textarea id="f_ci" placeholder="检查内容描述"></textarea></div></div>';
        document.getElementById('f_nd').value = new Date().toISOString().slice(0,10);
        modalSaveHandler = function() {
            var d = {plan_name:document.getElementById('f_pn').value, equipment_id:document.getElementById('f_eq').value,
                frequency:document.getElementById('f_freq').value, next_date:document.getElementById('f_nd').value,
                check_items:document.getElementById('f_ci').value};
            if(!d.plan_name||!d.equipment_id) { alert('请填写必填项'); return; }
            api('/api/eqp/maintenance/add', {method:'POST', body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); maintLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function maintExec(planId, eqId) {
    document.getElementById('mTitle').textContent = '执行保养';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>保养结果</label><select id="f_cr"><option value="正常">正常</option><option value="异常">异常</option></select></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>备注</label><textarea id="f_rk"></textarea></div></div>';
    modalSaveHandler = function() {
        api('/api/eqp/check/add', {method:'POST', body:{plan_id:planId, equipment_id:eqId, check_result:document.getElementById('f_cr').value, remark:document.getElementById('f_rk').value}}).then(function(r) {
            if(r&&r.code===0) { closeModal(); alert('保养记录已保存'); maintLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function maintDel(id) {
    if(!confirm('确定删除？')) return;
    api('/api/eqp/maintenance/delete',{method:'POST',body:{id:id}}).then(function(r) {
        if(r&&r.code===0) maintLoad(); else alert(r?r.message:'删除失败');
    });
}

// 保养记录
function renderCheckList(el) {
    el.innerHTML = '<div class="card"><div class="card-title">保养记录</div>'
        + '<table><thead><tr><th>ID</th><th>工单号</th><th>计划</th><th>设备</th><th>结果</th><th>状态</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    api('/api/eqp/check/list?size=100').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(r2) {
            return '<tr><td>'+MESUI.escapeHtml(r2.id)+'</td><td>'+MESUI.escapeHtml(r2.workorder_no)+'</td><td>'+MESUI.escapeHtml(r2.plan_name||'-')+'</td><td>'+MESUI.escapeHtml(r2.equipment_name||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(r2.check_result||'-')+'</td><td><span class="tag '+(r2.status?'tag-ok':'tag-wait')+'">'+(r2.status?'已完成':'待执行')+'</span></td>'
                +'<td>'+MESUI.escapeHtml(r2.check_time||r2.created_at||'')+'</td></tr>';
        }).join('');
    });
}

// 批次管理
function renderBatch(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>批次管理</span><button class="btn btn-blue" id="batchAddBtn">+ 新增批次</button></div>'
        + '<div class="toolbar"><input id="kw" placeholder="搜索批次号..."><button class="btn btn-blue btn-sm" onclick="traceBatchLoad(1)">搜索</button></div>'
        + '<table><thead><tr><th>ID</th><th>批次号</th><th>产品</th><th>供应商</th><th>数量</th><th>生产日期</th><th>有效期</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('batchAddBtn').onclick = batchAdd;
    traceBatchLoad(1);
}
function traceBatchLoad(page) {
    var kw = document.getElementById('kw') ? document.getElementById('kw').value : '';
    var url = '/api/trace/batch/list?page='+page+'&size=15';
    if(kw) url += '&keyword='+encodeURIComponent(kw);
    api(url).then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(r2) {
            return '<tr><td>'+MESUI.escapeHtml(r2.id)+'</td><td><b>'+MESUI.escapeHtml(r2.batch_no || '')+'</b></td><td>'+MESUI.escapeHtml(r2.product_name||r2.product_id)+'</td>'
                +'<td>'+MESUI.escapeHtml(r2.supplier||'-')+'</td><td>'+MESUI.escapeHtml(r2.quantity)+'</td><td>'+MESUI.escapeHtml(r2.production_date||'-')+'</td><td>'+MESUI.escapeHtml(r2.expiry_date||'-')+'</td>'
                +'<td><button class="btn btn-blue btn-sm" data-batch-no="'+MESUI.escapeHtml(r2.batch_no || '')+'" onclick="openTraceBatch(this.getAttribute(\'data-batch-no\'))">追溯</button> '
                +'<button class="btn btn-red btn-sm" onclick="batchDel('+r2.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function batchAdd() {
    api('/api/base/product/all').then(function(r) {
        var prods = (r && r.data) ? r.data : [];
        var opts = '<option value="">请选择产品</option>';
        prods.forEach(function(p) { opts += '<option value="'+p.id+'">'+p.product_name+' ('+p.code+')</option>'; });
        document.getElementById('mTitle').textContent = '新增批次';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>批次号<span style="color:red">*</span></label><input id="f_bn"></div>'
            + '<div class="form-item"><label>产品<span style="color:red">*</span></label><select id="f_pid">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>供应商</label><input id="f_sup"></div><div class="form-item"><label>数量</label><input id="f_qty" type="number"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>生产日期</label><input id="f_pd" type="date"></div><div class="form-item"><label>有效期</label><input id="f_ed" type="date"></div></div>';
        modalSaveHandler = function() {
            var d = {batch_no:document.getElementById('f_bn').value, product_id:document.getElementById('f_pid').value,
                supplier:document.getElementById('f_sup').value, quantity:document.getElementById('f_qty').value,
                production_date:document.getElementById('f_pd').value, expiry_date:document.getElementById('f_ed').value};
            if(!d.batch_no || !d.product_id || Number(d.quantity) <= 0) { alert('请选择产品，批次号不能为空，数量必须大于0'); return; }
            api('/api/trace/batch/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); traceBatchLoad(1); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function openTraceBatch(batchNo) {
    goPage('trace/query');
    setTimeout(function() {
        var input = document.getElementById('kw');
        if(!input) return;
        input.value = batchNo;
        traceQuery();
    }, 300);
}
function batchDel(id) {
    if(!confirm('确定删除？')) return;
    api('/api/trace/batch/delete',{method:'POST',body:{id:id}}).then(function(r) {
        if(r && r.code === 0) traceBatchLoad(1);
        else alert(r ? r.message : '删除失败');
    });
}

// 追溯查询
function renderTraceQuery(el) {
    el.innerHTML = '<div class="card"><div class="card-title">追溯查询</div>'
        + '<div class="toolbar"><input id="kw" placeholder="输入批次号或产品名称" style="width:300px">'
        + '<button class="btn btn-blue" onclick="traceQuery()">查询</button></div></div>'
        + '<div id="traceResult"></div>';
    document.getElementById('kw').onkeydown = function(e) { if(e.key==='Enter') traceQuery(); };
}
function traceQuery() {
    var kw = document.getElementById('kw').value;
    if(!kw) { alert('请输入查询条件'); return; }
    api('/api/trace/query?keyword='+encodeURIComponent(kw)).then(function(r) {
        var el = document.getElementById('traceResult');
        if(!r||!r.data||!r.data.length) { el.innerHTML = '<div class="card"><div class="empty">未找到相关批次</div></div>'; return; }
        var h = '';
        r.data.forEach(function(item) {
            var b = item.batch;
            h += '<div class="card"><div class="card-title">批次: '+MESUI.escapeHtml(b.batch_no || '')+' <span class="tag tag-ok">'+MESUI.escapeHtml(b.product_name || '')+'</span></div>';
            h += '<p style="color:#666;margin-bottom:12px">供应商: '+MESUI.escapeHtml(b.supplier||'-')+' | 数量: '+MESUI.escapeHtml(b.quantity)+' | 生产日期: '+MESUI.escapeHtml(b.production_date||'-')+' | 有效期: '+MESUI.escapeHtml(b.expiry_date||'-')+'</p>';
            if(item.traces.length) {
                h += '<table><thead><tr><th>时间</th><th>类型</th><th>单号</th><th>数量</th><th>备注</th></tr></thead><tbody>';
                item.traces.forEach(function(t) {
                    h += '<tr><td>'+MESUI.escapeHtml(t.created_at||'')+'</td><td><span class="tag tag-wait">'+MESUI.escapeHtml(t.trace_type||'')+'</span></td><td>'+MESUI.escapeHtml(t.ref_no||t.biz_no||'-')+'</td><td>'+MESUI.escapeHtml(t.quantity||'-')+'</td><td>'+MESUI.escapeHtml(t.remark||'-')+'</td></tr>';
                });
                h += '</tbody></table>';
            } else {
                h += '<p style="color:#999">暂无追溯记录</p>';
            }
            h += '</div>';
        });
        el.innerHTML = h;
    });
}
