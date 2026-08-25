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
            h += '<tr><td>' + r2.id + '</td><td>' +MESUI.escapeHtml(r2.product_name||'')+ '</td><td>' +MESUI.escapeHtml(r2.material_name||'')+ '</td>';
            h += '<td>' +MESUI.escapeHtml(r2.quantity)+ '</td><td>' +MESUI.escapeHtml(r2.unit||'')+ '</td>';
            h += '<td><button class="btn btn-red btn-sm" onclick="bomDel(' + r2.id + ')">删除</button></td></tr>';
        });
        tb.innerHTML = h;
    });
}
function bomAdd() {
    api('/api/base/product/all').then(function(r) {
        var opts = '<option value="">请选择</option>';
        (r && r.data ? r.data : []).forEach(function(p) { opts += '<option value="' + p.id + '">' +MESUI.escapeHtml(p.product_name)+ '(' +MESUI.escapeHtml(p.code)+ ')</option>'; });
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
        + '<table><thead><tr><th>ID</th><th>单号</th><th>产品</th><th>类型</th><th>' + (isIn ? '供应商' : '客户') + '</th><th>数量</th><th>金额</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="9" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('invAddBtn').onclick = function() { invAdd(type); };
    invLoad(type);
}
function invLoad(type) {
    var apiP = type === 'in' ? 'inbound' : 'outbound';
    api('/api/inv/' + apiP + '/list').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>'; return; }
        var h = '';
        var noKey = type === 'in' ? 'inbound_no' : 'outbound_no';
        var nameKey = type === 'in' ? 'supplier' : 'customer';
        list.forEach(function(r2) {
            var isDraft = Number(r2.status) === 0;
            h += '<tr><td>' + r2.id + '</td><td>' + MESUI.escapeHtml(r2[noKey] || '') + '</td>';
            h += '<td>' + MESUI.escapeHtml(r2.product_summary || '') + '</td><td>' + MESUI.escapeHtml(r2[type === 'in' ? 'inbound_type' : 'outbound_type'] || '') + '</td>';
            h += '<td>' + MESUI.escapeHtml(r2[nameKey] || '') + '</td><td>' + Number(r2.total_quantity || 0) + '</td><td>' + Number(r2.total_amount || 0).toFixed(2) + '</td>';
            h += '<td><span class="tag ' + (isDraft ? 'tag-draft' : 'tag-ok') + '">' + (isDraft ? '草稿' : '已过账') + '</span></td>';
            h += '<td>' + (isDraft
                ? '<button class="btn btn-blue btn-sm" onclick="invPost(\'' + type + '\',' + r2.id + ')">过账</button> '
                    + '<button class="btn btn-red btn-sm" onclick="invDel(\'' + type + '\',' + r2.id + ')">删除</button>'
                : '<span class="text-muted">已完成</span>') + '</td></tr>';
        });
        tb.innerHTML = h;
    });
}
function invAdd(type) {
    var isIn = type === 'in';
    api('/api/base/product/all').then(function(r) {
        var opts = '<option value="">请选择</option>';
        (r && r.data ? r.data : []).forEach(function(p) { opts += '<option value="' + p.id + '">' +MESUI.escapeHtml(p.product_name)+ '</option>'; });
        var typeOptions = isIn
            ? '<option value="采购">采购</option><option value="生产入库">生产入库</option><option value="退料">退料</option><option value="其他">其他</option>'
            : '<option value="销售">销售</option><option value="生产领料">生产领料</option><option value="调拨">调拨</option><option value="其他">其他</option>';
        document.getElementById('mTitle').textContent = '新增' + (isIn ? '入库' : '出库') + '单';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>单据类型</label><select id="f_type">' + typeOptions + '</select></div>'
            + '<div class="form-item"><label>' + (isIn ? '供应商' : '客户') + '</label><input id="f_name" type="text"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>产品<span style="color:red">*</span></label><select id="f_pid">' + opts + '</select></div>'
            + '<div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_qty" type="number" step="0.01"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>单价</label><input id="f_price" type="number" step="0.01"></div>'
            + '<div class="form-item"><label>备注</label><input id="f_remark" type="text"></div></div>';
        modalSaveHandler = function() {
            var d = {product_id:document.getElementById('f_pid').value, quantity:document.getElementById('f_qty').value,
                unit_price:document.getElementById('f_price').value || 0, remark:document.getElementById('f_remark').value};
            d[isIn ? 'supplier' : 'customer'] = document.getElementById('f_name').value;
            d[isIn ? 'inbound_type' : 'outbound_type'] = document.getElementById('f_type').value;
            if(!d.product_id || Number(d.quantity) <= 0 || Number(d.unit_price) < 0) { alert('请选择产品，数量必须大于0，单价不能小于0'); return; }
            api('/api/inv/' + (isIn ? 'inbound' : 'outbound') + '/add', {method:'POST', body:d}).then(function(r2) {
                if(r2 && r2.code === 0) { closeModal(); invLoad(type); alert('草稿已保存，请核对后过账'); } else alert(r2 ? r2.message : '保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function invPost(type, id) {
    if(!confirm('过账后将立即更新库存且不能修改或删除，确定继续？')) return;
    var apiP = type === 'in' ? 'inbound' : 'outbound';
    api('/api/inv/' + apiP + '/' + id + '/post', {method:'POST', body:{}}).then(function(r) {
        if(r && r.code === 0) { alert('过账成功'); invLoad(type); }
        else alert(r ? r.message : '过账失败');
    });
}
function invDel(type, id) {
    if(!confirm('确定删除草稿？')) return;
    api('/api/inv/' + (type === 'in' ? 'inbound' : 'outbound') + '/delete', {method:'POST', body:{id:id}}).then(function(r) {
        if(r && r.code === 0) invLoad(type);
        else alert(r ? r.message : '删除失败');
    });
}

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
            h += '<tr><td>' + r2.id + '</td><td>' +MESUI.escapeHtml(r2.product_name||r2.product_id)+ '</td><td>' +MESUI.escapeHtml(r2.quantity)+ '</td><td>' + (r2.amount||0) + '</td></tr>';
        });
        tb.innerHTML = h;
    });
}

// 工单
function renderWO(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工单管理</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'prod_workorder\')">导出</button>'
        + '<button class="btn btn-blue" id="woAddBtn">+ 新增</button></div></div>'
        + '<div class="table-wrap"><table><thead><tr><th>ID</th><th>工单号</th><th>生产批次</th><th>计划</th><th>产品</th><th>车间</th><th>路线/版本</th><th>计划数</th><th>完成/不良</th><th>优先级</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="12" class="empty">加载中...</td></tr></tbody></table></div></div>';
    document.getElementById('woAddBtn').onclick = woAdd;
    woLoad();
}
function woLoad() {
    api('/api/prod/workorder/list').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="12" class="empty">暂无数据</td></tr>'; return; }
        var pri = {1:'低',2:'中',3:'高',4:'紧急'};
        var status = {0:'草稿',1:'已下达',2:'生产中',3:'已完工',4:'已暂停',5:'已关闭',6:'已取消'};
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + MESUI.escapeHtml(r2.id) + '</td><td>' + MESUI.escapeHtml(r2.order_no) + '</td>'
                + '<td>' + MESUI.escapeHtml(r2.batch_no||'-') + '</td><td>' + MESUI.escapeHtml(r2.plan_no||'-') + '</td>'
                + '<td>' + MESUI.escapeHtml(r2.product_name||r2.product_id) + '</td><td>' + MESUI.escapeHtml(r2.workshop_name||'-') + '</td>'
                + '<td>' + MESUI.escapeHtml((r2.route_name||'-') + (r2.route_version ? ' / V'+r2.route_version : '')) + '</td>';
            h += '<td>' + MESUI.escapeHtml(r2.planned_qty) + '</td><td>' + MESUI.escapeHtml((r2.completed_qty||0) + ' / ' + (r2.defect_qty||0)) + '</td>';
            h += '<td><span class="tag ' + (r2.priority >= 3 ? 'tag-no' : 'tag-wait') + '">' + (pri[r2.priority]||'低') + '</span></td>';
            h += '<td><span class="tag ' +MESUI.escapeHtml(r2.status >= 3 && r2.status !== 4 ? 'tag-ok' : r2.status ? 'tag-wait' : 'tag-draft')+ '">' +MESUI.escapeHtml(status[r2.status]||r2.status)+ '</span></td><td class="actions">';
            if(Number(r2.status) === 0) h += '<button class="btn btn-blue btn-sm" onclick="woRelease(' + r2.id + ')">下达并冻结</button> '
                + '<button class="btn btn-red btn-sm" onclick="woDel(' + r2.id + ')">删除</button>';
            if(Number(r2.status) >= 1 && Number(r2.status) < 5) h += '<button class="btn btn-green btn-sm" onclick="woGenerateTasks(' + r2.id + ')">生成任务</button> '
                + '<button class="btn btn-blue btn-sm" onclick="woGenerateMaterials(' + r2.id + ')">生成领料需求</button>';
            h += '</td></tr>';
        });
        tb.innerHTML = h;
    });
}
function woAdd() {
    api('/api/prod/batch/list?size=1000').then(function(r) {
        var opts = '<option value="">请选择生产批次</option>';
        (r && r.data ? r.data.list || [] : []).filter(function(batch) { return Number(batch.status) !== 4; }).forEach(function(batch) {
            opts += '<option value="' + MESUI.escapeHtml(batch.id) + '">' + MESUI.escapeHtml(batch.batch_no + ' / ' + batch.product_name + ' / ' + batch.planned_qty) + '</option>';
        });
        document.getElementById('mTitle').textContent = '新增工单';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>生产批次<span style="color:red">*</span></label><select id="f_batch">' + opts + '</select></div>'
            + '<div class="form-item"><label>计划数量<span style="color:red">*</span></label><input id="f_qty" type="number"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>产品（自动带入）</label><input id="f_product_name" readonly></div><div class="form-item"><label>车间（自动带入）</label><input id="f_workshop_name" readonly></div></div>'
            + '<div class="form-row"><div class="form-item"><label>工艺路线<span style="color:red">*</span></label><select id="f_route"><option value="">先选批次</option></select></div>'
            + '<div class="form-item"><label>优先级</label><select id="f_pri"><option value="1">低</option><option value="2">中</option><option value="3">高</option><option value="4">紧急</option></select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>开始日期</label><input id="f_start" type="date"></div><div class="form-item"><label>结束日期</label><input id="f_end" type="date"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>备注</label><input id="f_remark" value="生产业务链测试"></div></div>';
        var selectedOptions = null;
        document.getElementById('f_batch').onchange = function() {
            if(!this.value) return;
            api('/api/prod/workorder/options?batch_id=' + encodeURIComponent(this.value)).then(function(response) {
                if(!response || response.code !== 0) { alert(response ? response.message : '批次资料加载失败'); return; }
                selectedOptions = response.data;
                document.getElementById('f_qty').value = response.data.remaining_qty;
                var selectedBatch = (r.data.list || []).find(function(batch) { return String(batch.id) === String(response.data.production_batch_id); });
                document.getElementById('f_product_name').value = selectedBatch ? selectedBatch.product_name : response.data.product_id;
                document.getElementById('f_workshop_name').value = selectedBatch ? selectedBatch.workshop_name : response.data.workshop_id;
                var routeOptions = '<option value="">请选择匹配路线</option>';
                (response.data.routes || []).forEach(function(route) { routeOptions += '<option value="' + route.id + '">' + MESUI.escapeHtml(route.route_name + ' / V' + route.version) + '</option>'; });
                document.getElementById('f_route').innerHTML = routeOptions;
            });
        };
        modalSaveHandler = function() {
            if(!selectedOptions) { alert('请选择生产批次'); return; }
            var d = {production_batch_id:selectedOptions.production_batch_id, plan_item_id:selectedOptions.plan_item_id,
                product_id:selectedOptions.product_id, workshop_id:selectedOptions.workshop_id,
                route_id:document.getElementById('f_route').value, planned_qty:document.getElementById('f_qty').value,
                priority:document.getElementById('f_pri').value, start_date:document.getElementById('f_start').value,
                end_date:document.getElementById('f_end').value, remark:document.getElementById('f_remark').value};
            if(!d.route_id || Number(d.planned_qty) <= 0) { alert('请选择工艺路线并填写有效数量'); return; }
            api('/api/prod/workorder/save', {method:'POST', body:d}).then(function(r2) {
                if(r2 && r2.code === 0) { closeModal(); woLoad(); } else alert(r2 ? r2.message : '保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function woDel(id) { if(!confirm('确定删除？')) return; api('/api/prod/workorder/delete', {method:'POST', body:{id:id}}).then(function(){woLoad()}); }
function woRelease(id) {
    if(!confirm('下达后将冻结当前工艺路线和BOM，确认继续？')) return;
    api('/api/prod/workorder/' + id + '/release', {method:'POST', body:{remark:'生产业务链测试'}}).then(function(response) {
        if(response && response.code === 0) { alert('已冻结路线和BOM'); woLoad(); }
        else alert(response ? response.message : '下达失败');
    });
}
function woGenerateTasks(id) {
    api('/api/prod/workorder/' + id + '/generate-tasks', {method:'POST', body:{}}).then(function(response) {
        if(response && response.code === 0) { alert('已按冻结路线生成 ' + response.data.length + ' 个任务'); woLoad(); }
        else alert(response ? response.message : '任务生成失败');
    });
}
function woGenerateMaterials(id) {
    api('/api/prod/workorder/' + id + '/generate-materials', {method:'POST', body:{}}).then(function(response) {
        if(response && response.code === 0) { alert('已按冻结BOM生成 ' + response.data.length + ' 条领料需求'); woLoad(); }
        else alert(response ? response.message : '领料需求生成失败');
    });
}

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
            h += '<tr><td>' + r2.id + '</td><td>' + MESUI.escapeHtml(r2.equipment_name) + '</td><td>' + MESUI.escapeHtml(r2.code) + '</td>';
            h += '<td>' + MESUI.escapeHtml(r2.model||'') + '</td><td>' + MESUI.escapeHtml(r2.manufacturer||'') + '</td>';
            h += '<td><span class="tag ' +MESUI.escapeHtml(r2.status === 1 ? 'tag-ok' : r2.status === 2 ? 'tag-wait' : 'tag-draft')+ '">' +MESUI.escapeHtml(r2.status === 1 ? '运行' : r2.status === 2 ? '维修' : '停用')+ '</span></td>';
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
function eqpDel(id) {
    if(!confirm('确定删除？')) return;
    api('/api/eqp/ledger/delete', {method:'POST', body:{id:id}}).then(function(r) {
        if(r&&r.code===0) eqpLoad(); else alert(r?r.message:'删除失败');
    });
}
