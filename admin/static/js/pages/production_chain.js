/* 订单驱动的生产业务链页面 */

function chainEscape(value) {
    return MESUI.escapeHtml(value == null || value === '' ? '-' : String(value));
}

function chainList(response) {
    if(!response || !response.data) return [];
    if(Array.isArray(response.data)) return response.data;
    return Array.isArray(response.data.list) ? response.data.list : [];
}

function chainStatus(value, labels) {
    var text = labels[value] == null ? value : labels[value];
    var className = Number(value) >= 2 ? 'tag-ok' : (Number(value) === 1 ? 'tag-run' : 'tag-draft');
    return '<span class="tag ' + className + '">' + chainEscape(text) + '</span>';
}

function chainPage(el, title, columns, endpoint, rowBuilder) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>' + chainEscape(title) + '</span>'
        + '<span class="muted">生产业务链</span></div>'
        + '<div class="table-wrap"><table><thead><tr>'
        + columns.map(function(column) { return '<th>' + chainEscape(column) + '</th>'; }).join('')
        + '</tr></thead><tbody id="tb"><tr><td colspan="' + columns.length
        + '" class="empty">加载中...</td></tr></tbody></table></div></div>';
    api(endpoint).then(function(response) {
        var tb = el.querySelector('#tb');
        if(!tb) return;
        if(!response || response.code !== 0) {
            tb.innerHTML = '<tr><td colspan="' + columns.length + '" class="empty">数据加载失败</td></tr>';
            return;
        }
        var list = chainList(response);
        tb.innerHTML = list.length
            ? list.map(rowBuilder).join('')
            : '<tr><td colspan="' + columns.length + '" class="empty">暂无数据</td></tr>';
    }).catch(function(error) {
        var tb = el.querySelector('#tb');
        if(tb) tb.innerHTML = '<tr><td colspan="' + columns.length + '" class="empty">'
            + chainEscape(error && error.message ? error.message : '数据加载失败') + '</td></tr>';
    });
}

function chainRow(values) {
    return '<tr>' + values.map(function(value) { return '<td>' + value + '</td>'; }).join('') + '</tr>';
}

var salesLineItems = [];
var salesProducts = [];

function renderSales(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>销售订单</span><button class="btn btn-blue" id="salesAddBtn">+ 新增订单</button></div>'
        + '<div class="table-wrap"><table><thead><tr><th>ID</th><th>订单号</th><th>客户</th><th>明细数</th><th>金额</th><th>交期</th><th>状态</th><th>备注</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div></div>';
    document.getElementById('salesAddBtn').onclick = salesOpenEditor;
    salesLoad();
}

function salesLoad() {
    api('/api/prod/sales/list?size=1000').then(function(response) {
        var rows = chainList(response), tb = document.getElementById('tb');
        if(!tb) return;
        tb.innerHTML = rows.length ? rows.map(function(row) {
            return chainRow([chainEscape(row.id), chainEscape(row.order_no), chainEscape(row.customer_name || row.customer),
                chainEscape(row.line_count || 0), chainEscape(row.total_amount || 0), chainEscape(row.delivery_date),
                chainStatus(row.status, {0:'草稿',1:'已确认',2:'生产中',3:'已完成',4:'已取消'}), chainEscape(row.remark)]);
        }).join('') : '<tr><td colspan="8" class="empty">暂无数据</td></tr>';
    });
}

function salesOpenEditor() {
    Promise.all([api('/api/base/customer/all'), api('/api/base/product/all')]).then(function(responses) {
        var customers = chainList(responses[0]);
        salesProducts = chainList(responses[1]);
        salesLineItems = [{product_id:'', quantity:1, unit_price:0, remark:''}];
        document.getElementById('mTitle').textContent = '新增销售订单（订单头 + 产品明细）';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>客户 *</label><select id="salesCustomer">'
            + routeOptions(customers, 'id', 'customer_name', '') + '</select></div><div class="form-item"><label>交货日期 *</label><input id="salesDelivery" type="date"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>联系人</label><input id="salesContact"></div><div class="form-item"><label>电话</label><input id="salesPhone"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>备注</label><input id="salesRemark" value="生产业务链测试"></div></div>'
            + '<div class="card-title"><span>产品明细</span><button type="button" class="btn btn-blue btn-sm" id="salesLineAdd">+ 添加产品</button></div>'
            + '<div class="table-wrap"><table><thead><tr><th>产品 *</th><th>数量 *</th><th>单价</th><th>金额</th><th>备注</th><th>操作</th></tr></thead><tbody id="salesLineBody"></tbody><tfoot><tr><td colspan="3">合计</td><td id="salesTotal">0.00</td><td colspan="2"></td></tr></tfoot></table></div>';
        document.getElementById('salesLineAdd').onclick = function() {
            salesLineItems.push({product_id:'', quantity:1, unit_price:0, remark:''});
            salesRenderLines();
        };
        salesRenderLines();
        modalSaveHandler = salesSave;
        document.getElementById('modal').classList.add('show');
    });
}

function salesRenderLines() {
    var body = document.getElementById('salesLineBody');
    body.innerHTML = salesLineItems.map(function(item, index) {
        var amount = Number(item.quantity || 0) * Number(item.unit_price || 0);
        return '<tr><td><select data-sales-index="' + index + '" data-sales-field="product_id">'
            + routeOptions(salesProducts, 'id', 'product_name', item.product_id) + '</select></td>'
            + '<td><input type="number" min="0.000001" data-sales-index="' + index + '" data-sales-field="quantity" value="' + chainEscape(item.quantity) + '"></td>'
            + '<td><input type="number" min="0" step="0.01" data-sales-index="' + index + '" data-sales-field="unit_price" value="' + chainEscape(item.unit_price) + '"></td>'
            + '<td>' + amount.toFixed(2) + '</td><td><input data-sales-index="' + index + '" data-sales-field="remark" value="' + chainEscape(item.remark) + '"></td>'
            + '<td><button type="button" class="btn btn-red btn-sm" data-sales-remove="' + index + '">删除</button></td></tr>';
    }).join('');
    body.querySelectorAll('[data-sales-field]').forEach(function(input) {
        input.onchange = function() {
            var index = Number(input.getAttribute('data-sales-index'));
            salesLineItems[index][input.getAttribute('data-sales-field')] = input.value;
            salesRenderLines();
        };
    });
    body.querySelectorAll('[data-sales-remove]').forEach(function(button) {
        button.onclick = function() { salesLineItems.splice(Number(button.getAttribute('data-sales-remove')), 1); salesRenderLines(); };
    });
    document.getElementById('salesTotal').textContent = salesLineItems.reduce(function(total, item) {
        return total + Number(item.quantity || 0) * Number(item.unit_price || 0);
    }, 0).toFixed(2);
}

function salesSave() {
    var payload = {customer_id:document.getElementById('salesCustomer').value,
        delivery_date:document.getElementById('salesDelivery').value,
        contact:document.getElementById('salesContact').value, phone:document.getElementById('salesPhone').value,
        remark:document.getElementById('salesRemark').value, items:salesLineItems};
    if(!payload.customer_id || !payload.delivery_date || !payload.items.length
        || payload.items.some(function(item) { return !item.product_id || Number(item.quantity) <= 0; })) {
        alert('请补全客户、交期和有效的产品明细'); return;
    }
    api('/api/prod/sales/save', {method:'POST', body:payload}).then(function(response) {
        if(response && response.code === 0) { closeModal(); salesLoad(); }
        else alert(response ? response.message : '保存失败');
    });
}

var planLineItems = [];
var planWorkshops = [];

function renderPlan(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>生产计划</span><button class="btn btn-blue" id="planAddBtn">+ 新增计划</button></div>'
        + '<div class="table-wrap"><table><thead><tr><th>ID</th><th>计划号</th><th>销售订单</th><th>类型</th><th>明细数</th><th>日期范围</th><th>状态</th><th>备注</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div></div>';
    document.getElementById('planAddBtn').onclick = planOpenEditor;
    planLoad();
}

function planLoad() {
    api('/api/prod/plan/list?size=1000').then(function(response) {
        var rows = chainList(response), tb = document.getElementById('tb');
        if(!tb) return;
        tb.innerHTML = rows.length ? rows.map(function(row) {
            return chainRow([chainEscape(row.id), chainEscape(row.plan_no), chainEscape(row.sales_order_no),
                chainEscape(row.plan_type), chainEscape(row.line_count || 0),
                chainEscape((row.start_date || '-') + ' 至 ' + (row.end_date || '-')),
                chainStatus(row.status, {0:'草稿',1:'已发布',2:'生产中',3:'已完成',4:'已取消'}), chainEscape(row.remark)]);
        }).join('') : '<tr><td colspan="8" class="empty">暂无数据</td></tr>';
    });
}

function planOpenEditor() {
    Promise.all([api('/api/prod/sales/list?size=1000'), api('/api/base/workshop/list?size=1000')]).then(function(responses) {
        var sales = chainList(responses[0]);
        planWorkshops = chainList(responses[1]);
        planLineItems = [];
        document.getElementById('mTitle').textContent = '新增生产计划（从销售订单带入明细）';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>销售订单 *</label><select id="planSales">'
            + routeOptions(sales, 'id', 'order_no', '') + '</select></div><div class="form-item"><label>计划类型</label><select id="planType"><option>订单生产</option><option>备货生产</option></select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>开始日期 *</label><input id="planStart" type="date"></div><div class="form-item"><label>结束日期 *</label><input id="planEnd" type="date"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>备注</label><input id="planRemark" value="生产业务链测试"></div></div>'
            + '<div class="table-wrap"><table><thead><tr><th>产品</th><th>可计划数</th><th>本次计划数 *</th><th>生产车间 *</th><th>备注</th></tr></thead><tbody id="planLineBody"><tr><td colspan="5" class="empty">请先选择销售订单</td></tr></tbody></table></div>';
        document.getElementById('planSales').onchange = planLoadSource;
        modalSaveHandler = planSave;
        document.getElementById('modal').classList.add('show');
    });
}

function planLoadSource() {
    var salesId = document.getElementById('planSales').value;
    if(!salesId) { planLineItems = []; planRenderLines(); return; }
    api('/api/prod/plan/source/' + encodeURIComponent(salesId)).then(function(response) {
        planLineItems = ((response && response.data && response.data.items) || []).map(function(item) {
            return {sales_order_item_id:item.id, product_id:item.product_id, product_name:item.product_name,
                remaining_qty:item.remaining_qty, planned_qty:item.remaining_qty, workshop_id:'', remark:''};
        });
        planRenderLines();
    });
}

function planRenderLines() {
    var body = document.getElementById('planLineBody');
    if(!planLineItems.length) { body.innerHTML = '<tr><td colspan="5" class="empty">没有可计划的订单明细</td></tr>'; return; }
    body.innerHTML = planLineItems.map(function(item, index) {
        return '<tr><td>' + chainEscape(item.product_name) + '</td><td>' + chainEscape(item.remaining_qty) + '</td>'
            + '<td><input type="number" min="0.000001" max="' + chainEscape(item.remaining_qty) + '" data-plan-index="' + index + '" data-plan-field="planned_qty" value="' + chainEscape(item.planned_qty) + '"></td>'
            + '<td><select data-plan-index="' + index + '" data-plan-field="workshop_id">' + routeOptions(planWorkshops, 'id', 'workshop_name', item.workshop_id) + '</select></td>'
            + '<td><input data-plan-index="' + index + '" data-plan-field="remark" value="' + chainEscape(item.remark) + '"></td></tr>';
    }).join('');
    body.querySelectorAll('[data-plan-field]').forEach(function(input) {
        input.onchange = function() { planLineItems[Number(input.getAttribute('data-plan-index'))][input.getAttribute('data-plan-field')] = input.value; };
    });
}

function planSave() {
    var payload = {sales_order_id:document.getElementById('planSales').value,
        plan_type:document.getElementById('planType').value, start_date:document.getElementById('planStart').value,
        end_date:document.getElementById('planEnd').value, remark:document.getElementById('planRemark').value,
        items:planLineItems};
    if(!payload.sales_order_id || !payload.start_date || !payload.end_date || !payload.items.length
        || payload.items.some(function(item) { return !item.workshop_id || Number(item.planned_qty) <= 0 || Number(item.planned_qty) > Number(item.remaining_qty); })) {
        alert('请补全销售订单、日期、计划数量和生产车间'); return;
    }
    api('/api/prod/plan/save', {method:'POST', body:payload}).then(function(response) {
        if(response && response.code === 0) { closeModal(); planLoad(); }
        else alert(response ? response.message : '保存失败');
    });
}

function renderProductionBatch(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>生产批次</span><button class="btn btn-blue" id="batchAddBtn">+ 拆分批次</button></div>'
        + '<div class="table-wrap"><table><thead><tr><th>ID</th><th>批次号</th><th>计划</th><th>销售订单</th><th>产品</th><th>车间</th><th>计划数</th><th>完成数</th><th>状态</th><th>备注</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="10" class="empty">加载中...</td></tr></tbody></table></div></div>';
    document.getElementById('batchAddBtn').onclick = batchOpenEditor;
    productionBatchLoad();
}

function productionBatchLoad() {
    api('/api/prod/batch/list?size=1000').then(function(response) {
        var rows = chainList(response), tb = document.getElementById('tb');
        if(!tb) return;
        tb.innerHTML = rows.length ? rows.map(function(row) {
            return chainRow([chainEscape(row.id), chainEscape(row.batch_no), chainEscape(row.plan_no), chainEscape(row.sales_order_no),
                chainEscape(row.product_name), chainEscape(row.workshop_name), chainEscape(row.planned_qty), chainEscape(row.completed_qty || 0),
                chainStatus(row.status, {0:'草稿',1:'已排产',2:'生产中',3:'已完成',4:'已取消'}), chainEscape(row.remark)]);
        }).join('') : '<tr><td colspan="10" class="empty">暂无数据</td></tr>';
    });
}

function batchOpenEditor() {
    api('/api/prod/plan/list?size=1000').then(function(response) {
        var plans = chainList(response);
        document.getElementById('mTitle').textContent = '拆分生产批次';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>生产计划 *</label><select id="batchPlan">'
            + routeOptions(plans, 'id', 'plan_no', '') + '</select></div><div class="form-item"><label>计划明细 *</label><select id="batchPlanItem"><option value="">先选计划</option></select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>批次数量 *</label><input id="batchQty" type="number" min="0.000001"></div><div class="form-item"><label>备注</label><input id="batchRemark" value="生产业务链测试"></div></div>';
        document.getElementById('batchPlan').onchange = function() {
            var id = this.value;
            if(!id) return;
            api('/api/prod/plan/' + encodeURIComponent(id)).then(function(detail) {
                var items = detail && detail.data ? detail.data.items || [] : [];
                document.getElementById('batchPlanItem').innerHTML = routeOptions(items.map(function(item) {
                    return {id:item.id, label:(item.product_name || item.product_id) + ' / 计划 ' + item.planned_qty};
                }), 'id', 'label', '');
            });
        };
        modalSaveHandler = function() {
            var payload = {plan_item_id:document.getElementById('batchPlanItem').value,
                planned_qty:document.getElementById('batchQty').value, remark:document.getElementById('batchRemark').value};
            if(!payload.plan_item_id || Number(payload.planned_qty) <= 0) { alert('请选择计划明细并填写批次数量'); return; }
            api('/api/prod/batch/save', {method:'POST', body:payload}).then(function(result) {
                if(result && result.code === 0) { closeModal(); productionBatchLoad(); }
                else alert(result ? result.message : '保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

var routeStepRows = [];
var routeEditorLookups = {products:[], workshops:[], processes:[]};

function renderRoute(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工艺路线</span>'
        + '<button class="btn btn-blue" id="routeAddBtn">+ 新增路线</button></div>'
        + '<div class="table-wrap"><table><thead><tr><th>ID</th><th>路线名称</th><th>产品</th>'
        + '<th>默认车间</th><th>版本</th><th>步骤数</th><th>状态</th><th>说明</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="9" class="empty">加载中...</td></tr></tbody></table></div></div>';
    document.getElementById('routeAddBtn').onclick = function() { routeOpenEditor(null); };
    routeLoad();
}

function routeLoad() {
    api('/api/base/route/list?size=1000').then(function(response) {
        var list = chainList(response);
        var tb = document.getElementById('tb');
        if(!tb) return;
        if(!list.length) {
            tb.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>';
            return;
        }
        tb.innerHTML = list.map(function(row) {
            var payload = chainEscape(JSON.stringify(row));
            return chainRow([chainEscape(row.id), chainEscape(row.route_name), chainEscape(row.product_name),
                chainEscape(row.workshop_name || row.workshop_id), chainEscape(row.version || 1),
                chainEscape((row.steps || []).length), chainStatus(row.status, {0:'停用',1:'启用'}),
                chainEscape(row.description), '<button class="btn btn-blue btn-sm route-edit" data-route="'
                + payload + '">编辑</button>']);
        }).join('');
        tb.querySelectorAll('.route-edit').forEach(function(button) {
            button.onclick = function() { routeOpenEditor(JSON.parse(button.getAttribute('data-route'))); };
        });
    });
}

function routeOpenEditor(route) {
    Promise.all([
        api('/api/base/product/all'),
        api('/api/base/workshop/list?size=1000'),
        api('/api/base/process/list?status=1&size=1000')
    ]).then(function(responses) {
        routeEditorLookups.products = chainList(responses[0]);
        routeEditorLookups.workshops = chainList(responses[1]);
        routeEditorLookups.processes = chainList(responses[2]);
        routeStepRows = (route && route.steps ? route.steps : []).map(function(step) {
            return {process_id:step.process_id, workshop_id:step.workshop_id,
                standard_time:step.standard_time, is_inspection_point:step.is_inspection_point,
                description:step.description || ''};
        });
        if(!routeStepRows.length) routeStepRows.push({workshop_id:route ? route.workshop_id : '', process_id:'', standard_time:'', is_inspection_point:0, description:''});
        document.getElementById('mTitle').textContent = route ? '编辑工艺路线' : '新增工艺路线';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>路线名称 *</label>'
            + '<input id="routeName" value="' + chainEscape(route ? route.route_name : '') + '"></div>'
            + '<div class="form-item"><label>适用产品 *</label><select id="routeProduct">'
            + routeOptions(routeEditorLookups.products, 'id', 'product_name', route ? route.product_id : '') + '</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>默认车间 *</label><select id="routeWorkshop">'
            + routeOptions(routeEditorLookups.workshops, 'id', 'workshop_name', route ? route.workshop_id : '') + '</select></div>'
            + '<div class="form-item"><label>版本</label><input id="routeVersion" type="number" min="1" value="'
            + chainEscape(route ? route.version || 1 : 1) + '"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>状态</label><select id="routeStatus"><option value="1">启用</option><option value="0"'
            + (route && Number(route.status) === 0 ? ' selected' : '') + '>停用</option></select></div>'
            + '<div class="form-item"><label>说明</label><input id="routeDescription" value="'
            + chainEscape(route ? route.description : '') + '"></div></div>'
            + '<div class="card-title"><span>路线步骤</span><button type="button" class="btn btn-blue btn-sm" id="routeStepAdd">+ 添加步骤</button></div>'
            + '<div class="table-wrap"><table><thead><tr><th>步骤</th><th>执行车间</th><th>工序</th><th>标准工时</th><th>检验点</th><th>说明</th><th>操作</th></tr></thead>'
            + '<tbody id="routeStepBody"></tbody></table></div>';
        document.getElementById('routeStepAdd').onclick = function() {
            routeStepRows.push({workshop_id:document.getElementById('routeWorkshop').value, process_id:'', standard_time:'', is_inspection_point:0, description:''});
            routeRenderSteps();
        };
        routeRenderSteps();
        modalSaveHandler = function() { routeSave(route ? route.id : null); };
        document.getElementById('modal').classList.add('show');
    });
}

function routeOptions(list, valueKey, textKey, selected, emptyText) {
    var html = '<option value="">' + chainEscape(emptyText || '请选择') + '</option>';
    list.forEach(function(item) {
        html += '<option value="' + chainEscape(item[valueKey]) + '"'
            + (String(item[valueKey]) === String(selected) ? ' selected' : '') + '>'
            + chainEscape(item[textKey]) + '</option>';
    });
    return html;
}

function routeRenderSteps() {
    var body = document.getElementById('routeStepBody');
    if(!body) return;
    body.innerHTML = routeStepRows.map(function(step, index) {
        var processes = routeEditorLookups.processes.filter(function(process) {
            return String(process.workshop_id) === String(step.workshop_id);
        });
        return '<tr><td>' + (index + 1) + '</td><td><select data-index="' + index + '" data-field="workshop_id">'
            + routeOptions(routeEditorLookups.workshops, 'id', 'workshop_name', step.workshop_id) + '</select></td>'
            + '<td><select data-index="' + index + '" data-field="process_id">'
            + routeOptions(processes, 'id', 'process_name', step.process_id, '先选车间') + '</select></td>'
            + '<td><input type="number" min="0" step="0.1" data-index="' + index + '" data-field="standard_time" value="'
            + chainEscape(step.standard_time) + '"></td><td><input type="checkbox" data-index="' + index
            + '" data-field="is_inspection_point"' + (step.is_inspection_point ? ' checked' : '') + '></td>'
            + '<td><input data-index="' + index + '" data-field="description" value="' + chainEscape(step.description) + '"></td>'
            + '<td><button type="button" class="btn btn-red btn-sm" data-remove="' + index + '">删除</button></td></tr>';
    }).join('');
    body.querySelectorAll('[data-field]').forEach(function(input) {
        input.onchange = function() {
            var index = Number(input.getAttribute('data-index'));
            var field = input.getAttribute('data-field');
            routeStepRows[index][field] = input.type === 'checkbox' ? (input.checked ? 1 : 0) : input.value;
            if(field === 'workshop_id') {
                routeStepRows[index].process_id = '';
                routeRenderSteps();
            }
        };
    });
    body.querySelectorAll('[data-remove]').forEach(function(button) {
        button.onclick = function() {
            routeStepRows.splice(Number(button.getAttribute('data-remove')), 1);
            routeRenderSteps();
        };
    });
}

function routeSave(id) {
    var payload = {id:id, route_name:document.getElementById('routeName').value,
        product_id:document.getElementById('routeProduct').value,
        workshop_id:document.getElementById('routeWorkshop').value,
        version:Number(document.getElementById('routeVersion').value || 1),
        status:Number(document.getElementById('routeStatus').value),
        description:document.getElementById('routeDescription').value, steps:routeStepRows};
    if(!payload.route_name || !payload.product_id || !payload.workshop_id || !payload.steps.length
        || payload.steps.some(function(step) { return !step.workshop_id || !step.process_id; })) {
        alert('请补全路线名称、产品、默认车间和所有工序步骤');
        return;
    }
    api('/api/base/route/save', {method:'POST', body:payload}).then(function(response) {
        if(response && response.code === 0) { closeModal(); routeLoad(); }
        else alert(response ? response.message : '保存失败');
    });
}

function renderTask(el) {
    chainPage(el, '任务管理', ['ID', '任务号', '工单', '工序', '执行人', '计划数', '完成数', '不良数', '状态'],
        '/api/prod/task/list?size=1000', function(row) {
            return chainRow([chainEscape(row.id), chainEscape(row.task_no), chainEscape(row.workorder_no || row.order_no),
                chainEscape(row.process_name), chainEscape(row.assigned_name || row.real_name), chainEscape(row.planned_qty),
                chainEscape(row.completed_qty || 0), chainEscape(row.defect_qty || 0),
                chainStatus(row.status, {0:'待执行',1:'执行中',2:'已完成',3:'已暂停',4:'已取消'})]);
        });
}

function renderReport2(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>报工管理</span><button class="btn btn-blue" id="reportAddBtn">+ 提交报工</button></div>'
        + '<div class="table-wrap"><table><thead><tr><th>ID</th><th>报工单号</th><th>任务</th><th>工单</th><th>工序</th><th>报工人</th><th>合格数</th><th>不良数</th><th>状态</th><th>报工时间</th><th>备注</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="12" class="empty">加载中...</td></tr></tbody></table></div></div>';
    document.getElementById('reportAddBtn').onclick = reportOpenEditor;
    reportLoad();
}

function reportLoad() {
    api('/api/prod/report/list?size=1000').then(function(response) {
        var rows = chainList(response), tb = document.getElementById('tb');
        var labels = {0:'已提交',1:'已审核',2:'已记账',3:'已驳回'};
        if(!tb) return;
        tb.innerHTML = rows.length ? rows.map(function(row) {
            var actions = '';
            if(Number(row.approval_status) === 0) actions = '<button class="btn btn-green btn-sm" onclick="reportApprove('+row.id+')">审核</button> '
                + '<button class="btn btn-red btn-sm" onclick="reportReject('+row.id+')">驳回</button>';
            if(Number(row.approval_status) === 1) actions = '<button class="btn btn-blue btn-sm" onclick="reportPost('+row.id+')">记账</button>';
            return chainRow([chainEscape(row.id), chainEscape(row.report_no), chainEscape(row.task_no),
                chainEscape(row.workorder_no), chainEscape(row.process_name), chainEscape(row.real_name),
                chainEscape(row.qualified_qty || 0), chainEscape(row.defect_qty || 0),
                chainStatus(row.approval_status, labels), chainEscape(row.report_time), chainEscape(row.remark), actions]);
        }).join('') : '<tr><td colspan="12" class="empty">暂无数据</td></tr>';
    });
}

function reportOpenEditor() {
    api('/api/prod/task/list?size=1000').then(function(response) {
        var tasks = chainList(response).filter(function(task) { return Number(task.status) < 3; });
        document.getElementById('mTitle').textContent = '提交生产报工';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>生产任务 *</label><select id="reportTask">'
            + routeOptions(tasks.map(function(task) { return {id:task.id,label:task.task_no+' / '+task.workorder_no+' / '+task.process_name}; }), 'id', 'label', '')
            + '</select></div><div class="form-item"><label>当前可执行数量</label><input id="reportAvailable" readonly value="请先选择任务"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>合格数量 *</label><input id="reportQualified" type="number" min="0"></div><div class="form-item"><label>不良数量</label><input id="reportDefect" type="number" min="0" value="0"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>备注</label><input id="reportRemark" value="生产业务链测试"></div></div>';
        var selectedTask = null, availability = null;
        document.getElementById('reportTask').onchange = function() {
            selectedTask = tasks.find(function(task) { return String(task.id) === String(document.getElementById('reportTask').value); });
            if(!selectedTask) return;
            api('/api/prod/task/' + selectedTask.id + '/availability').then(function(result) {
                availability = result && result.data;
                document.getElementById('reportAvailable').value = availability ? availability.available_qty : '读取失败';
            });
        };
        modalSaveHandler = function() {
            var qualified = Number(document.getElementById('reportQualified').value || 0);
            var defect = Number(document.getElementById('reportDefect').value || 0);
            if(!selectedTask || !availability || qualified <= 0 || qualified + defect > Number(availability.available_qty)) {
                alert('请选择任务，并确保报工总数不超过可执行数量'); return;
            }
            api('/api/prod/report/add', {method:'POST', body:{task_id:selectedTask.id,
                workorder_id:selectedTask.workorder_id, process_id:selectedTask.process_id,
                qualified_qty:qualified, defect_qty:defect, controlled:true,
                remark:document.getElementById('reportRemark').value}}).then(function(result) {
                if(result && result.code === 0) { closeModal(); reportLoad(); }
                else alert(result ? result.message : '提交失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

function reportApprove(id) {
    api('/api/prod/report/' + id + '/approve', {method:'POST',body:{}}).then(function(result) {
        if(result && result.code === 0) reportLoad(); else alert(result ? result.message : '审核失败');
    });
}
function reportPost(id) {
    if(!confirm('记账后将累计任务和工单数量，确认继续？')) return;
    api('/api/prod/report/' + id + '/post', {method:'POST',body:{}}).then(function(result) {
        if(result && result.code === 0) reportLoad(); else alert(result ? result.message : '记账失败');
    });
}
function reportReject(id) {
    var remark = prompt('请输入驳回原因', '数据需核对');
    if(remark == null) return;
    api('/api/prod/report/' + id + '/reject', {method:'POST',body:{remark:remark}}).then(function(result) {
        if(result && result.code === 0) reportLoad(); else alert(result ? result.message : '驳回失败');
    });
}
