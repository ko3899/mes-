/* 生产增强页面模块 */

// 工序转移
function renderTransfer(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工序转移单</span>'
        + '<button class="btn btn-blue" id="transferAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>转移单号</th><th>工单</th><th>从工序</th><th>到工序</th><th>数量</th><th>状态</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('transferAddBtn').onclick = transferAdd;
    transferLoad();
}
function transferLoad() {
    api('/api/prod/transfer/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(t) {
            return '<tr><td>'+t.id+'</td><td>'+t.transfer_no+'</td><td>'+(t.workorder_no||'-')+'</td>'
                +'<td>'+(t.from_process||'-')+'</td><td>'+(t.to_process||'-')+'</td><td>'+t.quantity+'</td>'
                +'<td><span class="tag '+(t.status?'tag-ok':'tag-wait')+'">'+(t.status?'已完成':'待转移')+'</span></td>'
                +'<td>'+(t.created_at||'')+'</td></tr>';
        }).join('');
    });
}
function transferAdd() {
    Promise.all([api('/api/prod/workorder/list?size=500'), api('/api/base/process/list?size=500')]).then(function(r) {
        var woList = r[0] && r[0].data ? (r[0].data.list||r[0].data) : [];
        var procList = r[1] && r[1].data ? (r[1].data.list||r[1].data) : [];
        var woOpts = '<option value="">请选择工单</option>';
        woList.forEach(function(w) { woOpts += '<option value="'+w.id+'">'+w.order_no+'</option>'; });
        var procOpts = '<option value="">请选择工序</option>';
        procList.forEach(function(p) { procOpts += '<option value="'+p.id+'">'+p.process_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增工序转移';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工单<span style="color:red">*</span></label><select id="f_wo">'+woOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>从工序<span style="color:red">*</span></label><select id="f_from">'+procOpts+'</select></div>'
            + '<div class="form-item"><label>到工序<span style="color:red">*</span></label><select id="f_to">'+procOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_qty" type="number"></div></div>';
        modalSaveHandler = function() {
            var d = {workorder_id:document.getElementById('f_wo').value, from_process_id:document.getElementById('f_from').value,
                to_process_id:document.getElementById('f_to').value, quantity:document.getElementById('f_qty').value};
            if(!d.workorder_id||!d.from_process_id||!d.to_process_id||!d.quantity) { alert('请填写必填项'); return; }
            api('/api/prod/transfer/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); transferLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 生产领料
function renderMaterialReq(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>生产领料</span>'
        + '<button class="btn btn-blue" id="matReqAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>领料单号</th><th>工单</th><th>物料</th><th>数量</th><th>类型</th><th>状态</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('matReqAddBtn').onclick = matReqAdd;
    matReqLoad();
}
function matReqLoad() {
    api('/api/prod/material/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(m) {
            return '<tr><td>'+m.id+'</td><td>'+m.req_no+'</td><td>'+(m.workorder_no||'-')+'</td>'
                +'<td>'+(m.product_name||'-')+'</td><td>'+m.quantity+'</td><td>'+m.req_type+'</td>'
                +'<td><span class="tag '+(m.status?'tag-ok':'tag-wait')+'">'+(m.status?'已领':'待领')+'</span></td>'
                +'<td>'+(m.created_at||'')+'</td></tr>';
        }).join('');
    });
}
function matReqAdd() {
    Promise.all([api('/api/prod/workorder/list?size=500'), api('/api/base/product/all')]).then(function(r) {
        var woList = r[0] && r[0].data ? (r[0].data.list||r[0].data) : [];
        var prodList = r[1] && r[1].data ? r[1].data : [];
        var woOpts = '<option value="">请选择工单</option>';
        woList.forEach(function(w) { woOpts += '<option value="'+w.id+'">'+w.order_no+'</option>'; });
        var prodOpts = '<option value="">请选择物料</option>';
        prodList.forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+p.product_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增领料';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工单<span style="color:red">*</span></label><select id="f_wo">'+woOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>物料<span style="color:red">*</span></label><select id="f_prod">'+prodOpts+'</select></div>'
            + '<div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_qty" type="number"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>类型</label><select id="f_type"><option value="领料">领料</option><option value="退料">退料</option><option value="超领">超领</option></select></div></div>';
        modalSaveHandler = function() {
            var d = {workorder_id:document.getElementById('f_wo').value, product_id:document.getElementById('f_prod').value,
                quantity:document.getElementById('f_qty').value, req_type:document.getElementById('f_type').value};
            if(!d.workorder_id||!d.product_id||!d.quantity) { alert('请填写必填项'); return; }
            api('/api/prod/material/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); matReqLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 委外加工
function renderOutsource(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>委外加工</span>'
        + '<button class="btn btn-blue" id="osAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>委外单号</th><th>供应商</th><th>产品</th><th>数量</th><th>单价</th><th>交期</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('osAddBtn').onclick = osAdd;
    osLoad();
}
function osLoad() {
    api('/api/prod/outsource/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(o) {
            var st = {0:'待发料',1:'加工中',2:'已收货',3:'已完成'};
            return '<tr><td>'+o.id+'</td><td>'+o.outsource_no+'</td><td>'+(o.supplier_name||'-')+'</td>'
                +'<td>'+(o.product_name||'-')+'</td><td>'+o.quantity+'</td><td>'+o.unit_price+'</td>'
                +'<td>'+(o.delivery_date||'-')+'</td>'
                +'<td><span class="tag '+(o.status>=2?'tag-ok':o.status?'tag-run':'tag-wait')+'">'+(st[o.status]||'待发料')+'</span></td></tr>';
        }).join('');
    });
}
function osAdd() {
    Promise.all([api('/api/base/supplier/all'), api('/api/base/product/all')]).then(function(r) {
        var supList = r[0] && r[0].data ? r[0].data : [];
        var prodList = r[1] && r[1].data ? r[1].data : [];
        var supOpts = '<option value="">请选择供应商</option>';
        supList.forEach(function(s) { supOpts += '<option value="'+s.id+'">'+s.supplier_name+'</option>'; });
        var prodOpts = '<option value="">请选择产品</option>';
        prodList.forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+p.product_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增委外加工';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>供应商<span style="color:red">*</span></label><select id="f_sup">'+supOpts+'</select></div>'
            + '<div class="form-item"><label>产品<span style="color:red">*</span></label><select id="f_prod">'+prodOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_qty" type="number"></div>'
            + '<div class="form-item"><label>单价</label><input id="f_price" type="number" step="0.01"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>交期</label><input id="f_date" type="date"></div></div>';
        modalSaveHandler = function() {
            var d = {supplier_id:document.getElementById('f_sup').value, product_id:document.getElementById('f_prod').value,
                quantity:document.getElementById('f_qty').value, unit_price:document.getElementById('f_price').value,
                delivery_date:document.getElementById('f_date').value};
            if(!d.supplier_id||!d.product_id||!d.quantity) { alert('请填写必填项'); return; }
            api('/api/prod/outsource/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); osLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 序列号
function renderSerial(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>产品序列号</span>'
        + '<button class="btn btn-blue" id="serialGenBtn">生成序列号</button></div>'
        + '<div class="toolbar"><input id="kw" placeholder="搜索序列号..."><button class="btn btn-blue btn-sm" onclick="serialLoad(1)">搜索</button></div>'
        + '<table><thead><tr><th>ID</th><th>序列号</th><th>产品</th><th>工单</th><th>状态</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('serialGenBtn').onclick = serialGen;
    serialLoad(1);
}
function serialLoad(page) {
    var kw = document.getElementById('kw') ? document.getElementById('kw').value : '';
    var url = '/api/prod/serial/list?page='+page+'&size=20';
    if(kw) url += '&keyword='+encodeURIComponent(kw);
    api(url).then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(s) {
            return '<tr><td>'+s.id+'</td><td><b>'+s.serial_no+'</b></td><td>'+(s.product_name||'-')+'</td>'
                +'<td>'+(s.workorder_id||'-')+'</td>'
                +'<td><span class="tag '+(s.status?'tag-ok':'tag-wait')+'">'+(s.status?'已使用':'可用')+'</span></td>'
                +'<td>'+(s.created_at||'')+'</td></tr>';
        }).join('');
    });
}
function serialGen() {
    api('/api/base/product/all').then(function(r) {
        var prodList = r && r.data ? r.data : [];
        var prodOpts = '<option value="">请选择产品</option>';
        prodList.forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+p.product_name+'</option>'; });
        document.getElementById('mTitle').textContent = '生成序列号';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>产品<span style="color:red">*</span></label><select id="f_prod">'+prodOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_count" type="number" value="10"></div></div>';
        modalSaveHandler = function() {
            var d = {product_id:document.getElementById('f_prod').value, count:document.getElementById('f_count').value};
            if(!d.product_id||!d.count) { alert('请填写必填项'); return; }
            api('/api/prod/serial/generate',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); alert('生成成功: '+r2.data.serials.length+'个'); serialLoad(1); } else alert(r2?r2.message:'生成失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 工时统计
function renderLabor(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工时统计</span></div>'
        + '<div id="laborSummary" style="margin-bottom:16px"></div>'
        + '<table><thead><tr><th>ID</th><th>员工</th><th>任务</th><th>工单</th><th>时长</th><th>加班</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    laborLoad();
    laborSummaryLoad();
}
function laborLoad() {
    api('/api/prod/labor/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(l) {
            return '<tr><td>'+l.id+'</td><td>'+(l.real_name||'-')+'</td><td>'+(l.task_no||'-')+'</td>'
                +'<td>'+(l.workorder_no||'-')+'</td><td>'+l.duration+'h</td><td>'+(l.overtime||0)+'h</td>'
                +'<td>'+(l.created_at||'')+'</td></tr>';
        }).join('');
    });
}
function laborSummaryLoad() {
    api('/api/prod/labor/summary').then(function(r) {
        if(!r||!r.data) return;
        var el = document.getElementById('laborSummary');
        el.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px">'
            +r.data.slice(0,6).map(function(e) {
                return '<div style="background:#f0f5ff;padding:12px;border-radius:8px;text-align:center">'
                    +'<div style="font-weight:bold">'+e.real_name+'</div>'
                    +'<div style="font-size:18px;color:#1890ff">'+e.total_hours+'h</div>'
                    +'<div style="font-size:12px;color:#666">'+e.task_count+'个任务</div></div>';
            }).join('')+'</div>';
    });
}

// 包装管理
function renderPacking(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>包装管理</span>'
        + '<button class="btn btn-blue" id="packAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>包装单号</th><th>工单</th><th>箱数</th><th>每箱数量</th><th>总数量</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('packAddBtn').onclick = packAdd;
    packLoad();
}
function packLoad() {
    api('/api/prod/packing/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(p) {
            return '<tr><td>'+p.id+'</td><td>'+p.packing_no+'</td><td>'+(p.workorder_no||'-')+'</td>'
                +'<td>'+p.box_count+'</td><td>'+p.quantity_per_box+'</td><td>'+p.total_quantity+'</td>'
                +'<td><span class="tag '+(p.status?'tag-ok':'tag-wait')+'">'+(p.status?'已完成':'待包装')+'</span></td></tr>';
        }).join('');
    });
}
function packAdd() {
    api('/api/prod/workorder/list?size=500').then(function(r) {
        var list = r && r.data ? (r.data.list||r.data) : [];
        var opts = '<option value="">请选择工单</option>';
        list.forEach(function(w) { opts += '<option value="'+w.id+'">'+w.order_no+'</option>'; });
        document.getElementById('mTitle').textContent = '新增包装';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工单</label><select id="f_wo">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>箱数<span style="color:red">*</span></label><input id="f_box" type="number"></div>'
            + '<div class="form-item"><label>每箱数量<span style="color:red">*</span></label><input id="f_qty" type="number"></div></div>';
        modalSaveHandler = function() {
            var d = {workorder_id:document.getElementById('f_wo').value, box_count:document.getElementById('f_box').value,
                quantity_per_box:document.getElementById('f_qty').value};
            if(!d.box_count||!d.quantity_per_box) { alert('请填写必填项'); return; }
            api('/api/prod/packing/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); packLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
