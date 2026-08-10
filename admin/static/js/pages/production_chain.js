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

function renderRoute(el) {
    chainPage(el, '工艺路线', ['ID', '路线名称', '产品', '状态', '说明'], '/api/base/route/list?size=1000', function(row) {
        return chainRow([chainEscape(row.id), chainEscape(row.route_name), chainEscape(row.product_name),
            chainStatus(row.status, {0:'停用',1:'启用'}), chainEscape(row.description)]);
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
