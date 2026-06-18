/* 业务页面模块 - 库存、生产、质量、设备等 */

// BOM
function renderBom(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>物料清单(BOM)</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'base_bom\')">导出</button>'
        + '<button class="btn btn-blue" id="bomAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>产品</th><th>物料</th><th>用量</th><th>单位</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('bomAddBtn').onclick = bomAdd;
    bomLoad();
}
function bomLoad() {
    api('/api/base/bom/list').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>'; return; }
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + (r2.product_name||'') + '</td><td>' + (r2.material_name||'') + '</td>';
            h += '<td>' + r2.quantity + '</td><td>' + (r2.unit||'') + '</td>';
            h += '<td><button class="btn btn-red btn-sm" onclick="bomDel(' + r2.id + ')">删除</button></td></tr>';
        });
        tb.innerHTML = h;
    });
}
function bomAdd() {
    api('/api/base/product/all').then(function(r) {
        var opts = '<option value="">请选择</option>';
        (r && r.data ? r.data : []).forEach(function(p) { opts += '<option value="' + p.id + '">' + p.product_name + '(' + p.code + ')</option>'; });
        document.getElementById('mTitle').textContent = '新增BOM';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>产品<span style="color:red">*</span></label><select id="f_pid">' + opts + '</select></div>'
            + '<div class="form-item"><label>物料<span style="color:red">*</span></label><select id="f_mid">' + opts + '</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>用量<span style="color:red">*</span></label><input id="f_qty" type="number" step="0.01"></div>'
            + '<div class="form-item"><label>单位</label><input id="f_unit" type="text"></div></div>';
        modalSaveHandler = function() {
            var d = {product_id:document.getElementById('f_pid').value, material_id:document.getElementById('f_mid').value,
                quantity:document.getElementById('f_qty').value, unit:document.getElementById('f_unit').value};
            if(!d.product_id || !d.material_id || !d.quantity) { alert('请填写必填项'); return; }
            api('/api/base/bom/add', {method:'POST', body:d}).then(function(r2) {
                if(r2 && r2.code === 0) { closeModal(); bomLoad(); } else alert(r2 ? r2.message : '保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function bomDel(id) { if(!confirm('确定删除？')) return; api('/api/base/bom/delete', {method:'POST', body:{id:id}}).then(function(){bomLoad()}); }

// 库存
function renderInv(el, type) {
    var isIn = type === 'in';
    var t = isIn ? '入库单' : '出库单';
    var table = isIn ? 'inv_inbound' : 'inv_outbound';
    el.innerHTML = '<div class="card"><div class="card-title"><span>' + t + '</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'' + table + '\')">导出</button>'
        + '<button class="btn btn-blue" id="invAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>单号</th><th>类型</th><th>' + (isIn ? '供应商' : '客户') + '</th><th>金额</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('invAddBtn').onclick = function() { invAdd(type); };
    invLoad(type);
}
function invLoad(type) {
    var apiP = type === 'in' ? 'inbound' : 'outbound';
    api('/api/inv/' + apiP + '/list').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        var h = '';
        var noKey = type === 'in' ? 'inbound_no' : 'outbound_no';
        var nameKey = type === 'in' ? 'supplier' : 'customer';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + r2[noKey] + '</td><td>' + (r2[type === 'in' ? 'inbound_type' : 'outbound_type']||'') + '</td>';
            h += '<td>' + (r2[nameKey]||'') + '</td><td>' + (r2.total_amount||0) + '</td>';
            h += '<td><span class="tag ' + (r2.status ? 'tag-ok' : 'tag-draft') + '">' + (r2.status ? '已完成' : '草稿') + '</span></td>';
            h += '<td><button class="btn btn-red btn-sm" onclick="invDel(\'' + type + '\',' + r2.id + ')">删除</button></td></tr>';
        });
        tb.innerHTML = h;
    });
}
function invAdd(type) {
    var isIn = type === 'in';
    api('/api/base/product/all').then(function(r) {
        var opts = '<option value="">请选择</option>';
        (r && r.data ? r.data : []).forEach(function(p) { opts += '<option value="' + p.id + '">' + p.product_name + '</option>'; });
        document.getElementById('mTitle').textContent = '新增' + (isIn ? '入库' : '出库') + '单';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>' + (isIn ? '供应商' : '客户') + '</label><input id="f_name" type="text"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>产品<span style="color:red">*</span></label><select id="f_pid">' + opts + '</select></div>'
            + '<div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_qty" type="number" step="0.01"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>单价</label><input id="f_price" type="number" step="0.01"></div>'
            + '<div class="form-item"><label>备注</label><input id="f_remark" type="text"></div></div>';
        modalSaveHandler = function() {
            var d = {product_id:document.getElementById('f_pid').value, quantity:document.getElementById('f_qty').value,
                unit_price:document.getElementById('f_price').value || 0, remark:document.getElementById('f_remark').value};
            d[isIn ? 'supplier' : 'customer'] = document.getElementById('f_name').value;
            d.total_amount = (Number(d.quantity) * Number(d.unit_price)).toFixed(2);
            if(!d.product_id || !d.quantity) { alert('请填写必填项'); return; }
            api('/api/inv/' + (isIn ? 'inbound' : 'outbound') + '/add', {method:'POST', body:d}).then(function(r2) {
                if(r2 && r2.code === 0) { closeModal(); invLoad(type); } else alert(r2 ? r2.message : '保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function invDel(type, id) { if(!confirm('确定删除？')) return; api('/api/inv/' + (type==='in'?'inbound':'outbound') + '/delete', {method:'POST', body:{id:id}}).then(function(){invLoad(type)}); }

// 库存余额
function renderBalance(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>库存余额</span>'
        + '<button class="btn btn-green" onclick="doExport2(\'inv_balance\')">导出</button></div>'
        + '<table><thead><tr><th>ID</th><th>产品</th><th>数量</th><th>金额</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="4" class="empty">加载中...</td></tr></tbody></table></div>';
    api('/api/inv/balance/list').then(function(r) {
        if(!r) return;
        var list = Array.isArray(r.data) ? r.data : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="4" class="empty">暂无库存</td></tr>'; return; }
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + (r2.product_name||r2.product_id) + '</td><td>' + r2.quantity + '</td><td>' + (r2.amount||0) + '</td></tr>';
        });
        tb.innerHTML = h;
    });
}

// 工单
function renderWO(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工单管理</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'prod_workorder\')">导出</button>'
        + '<button class="btn btn-blue" id="woAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>工单号</th><th>产品</th><th>计划数</th><th>完成数</th><th>不良数</th><th>优先级</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="9" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('woAddBtn').onclick = woAdd;
    woLoad();
}
function woLoad() {
    api('/api/prod/workorder/list').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>'; return; }
        var pri = {1:'低',2:'中',3:'高',4:'紧急'};
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + r2.order_no + '</td><td>' + (r2.product_name||r2.product_id) + '</td>';
            h += '<td>' + r2.planned_qty + '</td><td>' + r2.completed_qty + '</td><td>' + r2.defect_qty + '</td>';
            h += '<td><span class="tag ' + (r2.priority >= 3 ? 'tag-no' : 'tag-wait') + '">' + (pri[r2.priority]||'低') + '</span></td>';
            h += '<td><span class="tag ' + (r2.status === 3 ? 'tag-ok' : r2.status ? 'tag-wait' : 'tag-draft') + '">' + (r2.status === 3 ? '已完成' : r2.status ? '进行中' : '草稿') + '</span></td>';
            h += '<td><button class="btn btn-red btn-sm" onclick="woDel(' + r2.id + ')">删除</button></td></tr>';
        });
        tb.innerHTML = h;
    });
}
function woAdd() {
    api('/api/base/product/all').then(function(r) {
        var opts = '<option value="">请选择</option>';
        (r && r.data ? r.data : []).forEach(function(p) { opts += '<option value="' + p.id + '">' + p.product_name + '</option>'; });
        document.getElementById('mTitle').textContent = '新增工单';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>产品<span style="color:red">*</span></label><select id="f_pid">' + opts + '</select></div>'
            + '<div class="form-item"><label>计划数量<span style="color:red">*</span></label><input id="f_qty" type="number"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>优先级</label><select id="f_pri"><option value="1">低</option><option value="2">中</option><option value="3">高</option><option value="4">紧急</option></select></div></div>';
        modalSaveHandler = function() {
            var d = {product_id:document.getElementById('f_pid').value, planned_qty:document.getElementById('f_qty').value, priority:document.getElementById('f_pri').value};
            if(!d.product_id || !d.planned_qty) { alert('请填写必填项'); return; }
            api('/api/prod/workorder/add', {method:'POST', body:d}).then(function(r2) {
                if(r2 && r2.code === 0) { closeModal(); woLoad(); } else alert(r2 ? r2.message : '保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function woDel(id) { if(!confirm('确定删除？')) return; api('/api/prod/workorder/delete', {method:'POST', body:{id:id}}).then(function(){woLoad()}); }

// 设备
function renderEqp(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>设备台账</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'eqp_ledger\')">导出</button>'
        + '<button class="btn btn-blue" id="eqpAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>设备名称</th><th>编码</th><th>型号</th><th>制造商</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('eqpAddBtn').onclick = eqpAdd;
    eqpLoad();
}
function eqpLoad() {
    api('/api/eqp/ledger/list').then(function(r) {
        if(!r) return;
        var list = Array.isArray(r.data) ? r.data : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + r2.equipment_name + '</td><td>' + r2.code + '</td>';
            h += '<td>' + (r2.model||'') + '</td><td>' + (r2.manufacturer||'') + '</td>';
            h += '<td><span class="tag ' + (r2.status === 1 ? 'tag-ok' : r2.status === 2 ? 'tag-wait' : 'tag-draft') + '">' + (r2.status === 1 ? '运行' : r2.status === 2 ? '维修' : '停用') + '</span></td>';
            h += '<td><button class="btn btn-red btn-sm" onclick="eqpDel(' + r2.id + ')">删除</button></td></tr>';
        });
        tb.innerHTML = h;
    });
}
function eqpAdd() {
    document.getElementById('mTitle').textContent = '新增设备';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>设备名称<span style="color:red">*</span></label><input id="f_name" type="text"></div>'
        + '<div class="form-item"><label>编码<span style="color:red">*</span></label><input id="f_code" type="text"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>型号</label><input id="f_model" type="text"></div>'
        + '<div class="form-item"><label>制造商</label><input id="f_mfr" type="text"></div></div>';
    modalSaveHandler = function() {
        var d = {equipment_name:document.getElementById('f_name').value, code:document.getElementById('f_code').value,
            model:document.getElementById('f_model').value, manufacturer:document.getElementById('f_mfr').value};
        if(!d.equipment_name || !d.code) { alert('请填写必填项'); return; }
        api('/api/eqp/ledger/add', {method:'POST', body:d}).then(function(r) {
            if(r && r.code === 0) { closeModal(); eqpLoad(); } else alert(r ? r.message : '保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function eqpDel(id) { if(!confirm('确定删除？')) return; api('/api/eqp/ledger/delete', {method:'POST', body:{id:id}}).then(function(){eqpLoad()}); }
