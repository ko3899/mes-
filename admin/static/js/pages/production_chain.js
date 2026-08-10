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

function renderSales(el) {
    chainPage(el, '销售订单', ['ID', '订单号', '客户', '联系人', '电话', '金额', '交期', '状态', '备注'],
        '/api/prod/sales/list?size=1000', function(row) {
            return chainRow([chainEscape(row.id), chainEscape(row.order_no), chainEscape(row.customer_name || row.customer),
                chainEscape(row.contact), chainEscape(row.phone), chainEscape(row.total_amount || 0),
                chainEscape(row.delivery_date), chainStatus(row.status, {0:'草稿',1:'已确认',2:'执行中',3:'已完成',4:'已取消'}),
                chainEscape(row.remark)]);
        });
}

function renderPlan(el) {
    chainPage(el, '生产计划', ['ID', '计划号', '销售订单', '计划类型', '开始日期', '结束日期', '状态', '备注'],
        '/api/prod/plan/list?size=1000', function(row) {
            return chainRow([chainEscape(row.id), chainEscape(row.plan_no), chainEscape(row.order_no || row.sales_order_id),
                chainEscape(row.plan_type), chainEscape(row.start_date), chainEscape(row.end_date),
                chainStatus(row.status, {0:'草稿',1:'已发布',2:'执行中',3:'已完成',4:'已取消'}), chainEscape(row.remark)]);
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
    chainPage(el, '报工管理', ['ID', '报工单号', '任务', '工单', '工序', '报工人', '合格数', '不良数', '报工时间', '备注'],
        '/api/prod/report/list?size=1000', function(row) {
            return chainRow([chainEscape(row.id), chainEscape(row.report_no), chainEscape(row.task_no),
                chainEscape(row.workorder_no || row.order_no), chainEscape(row.process_name),
                chainEscape(row.real_name || row.reporter_name), chainEscape(row.qualified_qty || 0),
                chainEscape(row.defect_qty || 0), chainEscape(row.report_time || row.created_at), chainEscape(row.remark)]);
        });
}
