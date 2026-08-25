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
            return '<tr><td>'+t.id+'</td><td>'+MESUI.escapeHtml(t.transfer_no)+'</td><td>'+MESUI.escapeHtml(t.workorder_no||'-')+'</td>'
                +'<td>'+(t.from_process||'-')+'</td><td>'+(t.to_process||'-')+'</td><td>'+MESUI.escapeHtml(t.quantity)+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(t.status?'tag-ok':'tag-wait')+'">'+MESUI.escapeHtml(t.status?'已完成':'待转移')+'</span></td>'
                +'<td>'+(t.created_at||'')+'</td></tr>';
        }).join('');
    });
}
function transferAdd() {
    api('/api/prod/workorder/list?size=500').then(function(response) {
        var r = [response];
        var woList = r[0] && r[0].data ? (r[0].data.list||r[0].data) : [];
        var woOpts = '<option value="">请选择工单</option>';
        woList.forEach(function(w) { woOpts += '<option value="'+w.id+'">'+MESUI.escapeHtml(w.order_no)+'</option>'; });
        document.getElementById('mTitle').textContent = '新增工序转移';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工单<span style="color:red">*</span></label><select id="f_wo">'+woOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>从工序<span style="color:red">*</span></label><select id="f_from"><option value="">先选工单</option></select></div>'
            + '<div class="form-item"><label>到工序<span style="color:red">*</span></label><select id="f_to"><option value="">先选工单</option></select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_qty" type="number"></div><div class="form-item"><label>备注</label><input id="f_transfer_remark" value="生产业务链测试"></div></div>';
        document.getElementById('f_wo').onchange = function() {
            var workorderId = this.value;
            if(!workorderId) return;
            api('/api/prod/workorder/' + workorderId + '/executable-steps').then(function(result) {
                var steps = result && result.data ? result.data : [];
                var options = '<option value="">请选择冻结路线工序</option>';
                steps.forEach(function(step) { options += '<option value="'+step.process_id+'">'+MESUI.escapeHtml(step.step_no+' / '+step.process_name)+'</option>'; });
                document.getElementById('f_from').innerHTML = options;
                document.getElementById('f_to').innerHTML = options;
            });
        };
        modalSaveHandler = function() {
            var d = {workorder_id:document.getElementById('f_wo').value, from_process_id:document.getElementById('f_from').value,
                to_process_id:document.getElementById('f_to').value, quantity:document.getElementById('f_qty').value,
                remark:document.getElementById('f_transfer_remark').value};
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
        + '<span class="muted">领料需求必须从已下达工单的冻结 BOM 生成</span></div>'
        + '<div class="table-wrap"><table><thead><tr><th>ID</th><th>领料单号</th><th>工单</th><th>物料</th><th>需求数</th><th>申请数</th><th>实发数</th><th>收料数</th><th>退料数</th><th>欠料数</th><th>物料批次</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="13" class="empty">加载中...</td></tr></tbody></table></div></div>';
    matReqLoad();
}
function matReqLoad() {
    api('/api/prod/material/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="13" class="empty">暂无数据，请先在工单管理中生成领料需求</td></tr>'; return; }
        tb.innerHTML = list.map(function(m) {
            var required = Number(m.required_qty || m.quantity || 0);
            var requested = Number(m.requested_qty || 0), issued = Number(m.issued_qty || 0);
            var received = Number(m.received_qty || 0), returned = Number(m.returned_qty || 0);
            var shortage = Math.max(0, required - issued + returned);
            var labels = {0:'待申请',1:'待发料',2:'已发料',3:'已收料'};
            var actions = '';
            if(requested < required) actions += '<button class="btn btn-blue btn-sm" onclick="materialAction('+m.id+',\'request\','+(required-requested)+')">申请</button> ';
            if(issued < requested) actions += '<button class="btn btn-green btn-sm" onclick="materialAction('+m.id+',\'issue\','+(requested-issued)+')">发料</button> ';
            if(received < issued) actions += '<button class="btn btn-blue btn-sm" onclick="materialAction('+m.id+',\'receive\','+(issued-received)+')">收料</button> ';
            if(received > returned) actions += '<button class="btn btn-gray btn-sm" onclick="materialAction('+m.id+',\'return\','+(received-returned)+')">退料</button>';
            return '<tr><td>'+MESUI.escapeHtml(m.id)+'</td><td>'+MESUI.escapeHtml(m.req_no)+'</td><td>'+MESUI.escapeHtml(m.workorder_no||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(m.product_name||'-')+'</td><td>'+required+'</td><td>'+requested+'</td><td>'+issued+'</td><td>'+received+'</td><td>'+returned+'</td><td>'+shortage+'</td>'
                +'<td>'+MESUI.escapeHtml(m.material_batch_no||'-')+'</td><td><span class="tag '+(m.status>=2?'tag-ok':'tag-wait')+'">'+(labels[m.status]||m.status)+'</span></td>'
                +'<td class="actions">'+actions+'</td></tr>';
        }).join('');
    });
}
function materialAction(id, action, maximum) {
    var labels = {request:'申请',issue:'发料',receive:'收料',return:'退料'};
    var quantity = prompt(labels[action] + '数量（最大 ' + maximum + '）', String(maximum));
    if(quantity == null) return;
    quantity = Number(quantity);
    if(!quantity || quantity <= 0 || quantity > maximum) { alert('请输入不超过最大值的有效数量'); return; }
    var payload = {quantity:quantity};
    if(action === 'issue') {
        payload.warehouse_id = prompt('仓库 ID', '1');
        payload.location_id = prompt('库位 ID（可留空）', '') || null;
        payload.batch_no = prompt('物料批次号', '生产业务链测试');
        if(!payload.warehouse_id) return;
    }
    api('/api/prod/material/' + id + '/' + action, {method:'POST', body:payload}).then(function(response) {
        if(response && response.code === 0) matReqLoad();
        else alert(response ? response.message : '操作失败');
    });
}
function matReqAdd() {
    Promise.all([api('/api/prod/workorder/list?size=500'), api('/api/base/product/all')]).then(function(r) {
        var woList = r[0] && r[0].data ? (r[0].data.list||r[0].data) : [];
        var prodList = r[1] && r[1].data ? r[1].data : [];
        var woOpts = '<option value="">请选择工单</option>';
        woList.forEach(function(w) { woOpts += '<option value="'+w.id+'">'+MESUI.escapeHtml(w.order_no)+'</option>'; });
        var prodOpts = '<option value="">请选择物料</option>';
        prodList.forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+MESUI.escapeHtml(p.product_name)+'</option>'; });
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
        + '<span class="muted">当前页面仅供查询，请通过受控委外业务服务创建</span></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>委外单号</th><th>供应商</th><th>产品</th><th>数量</th><th>单价</th><th>交期</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
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
            return '<tr><td>'+o.id+'</td><td>'+o.outsource_no+'</td><td>'+MESUI.escapeHtml(o.supplier_name||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(o.product_name||'-')+'</td><td>'+MESUI.escapeHtml(o.quantity)+'</td><td>'+o.unit_price+'</td>'
                +'<td>'+(o.delivery_date||'-')+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(o.status>=2?'tag-ok':o.status?'tag-run':'tag-wait')+'">'+MESUI.escapeHtml(st[o.status]||'待发料')+'</span></td></tr>';
        }).join('');
    });
}
function osAdd() {
    Promise.all([api('/api/base/supplier/all'), api('/api/base/product/all')]).then(function(r) {
        var supList = r[0] && r[0].data ? r[0].data : [];
        var prodList = r[1] && r[1].data ? r[1].data : [];
        var supOpts = '<option value="">请选择供应商</option>';
        supList.forEach(function(s) { supOpts += '<option value="'+s.id+'">'+MESUI.escapeHtml(s.supplier_name)+'</option>'; });
        var prodOpts = '<option value="">请选择产品</option>';
        prodList.forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+MESUI.escapeHtml(p.product_name)+'</option>'; });
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
        var qualityMap = {
            normal:['正常','tag-ok'], quality_hold:['质量冻结','tag-hold'],
            rework:['返工中','tag-rework'], scrapped:['已报废','tag-scrap'],
            concession:['让步接收','tag-concession']
        };
        tb.innerHTML = list.map(function(s) {
            var quality = qualityMap[s.quality_status || 'normal'] || [s.quality_status || '正常','tag-wait'];
            return '<tr><td>'+s.id+'</td><td><b>'+MESUI.escapeHtml(s.serial_no)+'</b></td><td>'+MESUI.escapeHtml(s.product_name||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(s.workorder_id||'-')+'</td>'
                +'<td><span class="tag '+quality[1]+'">'+quality[0]+'</span></td>'
                +'<td>'+(s.created_at||'')+'</td></tr>';
        }).join('');
    });
}
function serialGen() {
    api('/api/base/product/all').then(function(r) {
        var prodList = r && r.data ? r.data : [];
        var prodOpts = '<option value="">请选择产品</option>';
        prodList.forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+MESUI.escapeHtml(p.product_name)+'</option>'; });
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
            return '<tr><td>'+l.id+'</td><td>'+MESUI.escapeHtml(l.real_name||'-')+'</td><td>'+MESUI.escapeHtml(l.task_no||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(l.workorder_no||'-')+'</td><td>'+l.duration+'h</td><td>'+(l.overtime||0)+'h</td>'
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
                    +'<div style="font-weight:bold">'+MESUI.escapeHtml(e.real_name)+'</div>'
                    +'<div style="font-size:18px;color:#1890ff">'+e.total_hours+'h</div>'
                    +'<div style="font-size:12px;color:#666">'+MESUI.escapeHtml(e.task_count)+'个任务</div></div>';
            }).join('')+'</div>';
    });
}

// 包装管理
function renderPacking(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>包装管理</span>'
        + '<span class="muted">当前页面仅供查询，请通过受控包装业务服务创建</span></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>包装单号</th><th>工单</th><th>箱数</th><th>每箱数量</th><th>总数量</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    packLoad();
}
function packLoad() {
    api('/api/prod/packing/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(p) {
            return '<tr><td>'+p.id+'</td><td>'+MESUI.escapeHtml(p.packing_no)+'</td><td>'+MESUI.escapeHtml(p.workorder_no||'-')+'</td>'
                +'<td>'+p.box_count+'</td><td>'+p.quantity_per_box+'</td><td>'+p.total_quantity+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(p.status?'tag-ok':'tag-wait')+'">'+MESUI.escapeHtml(p.status?'已完成':'待包装')+'</span></td></tr>';
        }).join('');
    });
}
function packAdd() {
    api('/api/prod/workorder/list?size=500').then(function(r) {
        var list = r && r.data ? (r.data.list||r.data) : [];
        var opts = '<option value="">请选择工单</option>';
        list.forEach(function(w) { opts += '<option value="'+w.id+'">'+MESUI.escapeHtml(w.order_no)+'</option>'; });
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
