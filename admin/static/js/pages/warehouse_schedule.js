/* 仓库、质检、设备点检与排班日历页面 */
function renderWarehousePage(el) {
    renderCrud(el, 'warehouse/list', {
        t: '仓库设置',
        apiBase: '/api/warehouse',
        dataTable: 'inv_warehouse',
        f: [
            {k: 'warehouse_name', l: '仓库名称', r: 1},
            {k: 'code', l: '仓库编码', r: 1},
            {k: 'address', l: '地址'},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]}
        ]
    });
}

function renderAreaPage(el) {
    renderCrud(el, 'warehouse/area', {
        t: '库区设置',
        apiBase: '/api/area',
        dataTable: 'inv_area',
        f: [
            {
                k: 'warehouse_id',
                l: '仓库',
                r: 1,
                type: 'select',
                api: '/api/warehouse/list?size=1000',
                vk: 'id',
                tk: 'warehouse_name'
            },
            {k: 'area_name', l: '库区名称', r: 1},
            {k: 'code', l: '库区编码', r: 1},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]}
        ]
    });
}

function renderLocationPage(el) {
    renderCrud(el, 'warehouse/location', {
        t: '库位设置',
        apiBase: '/api/location',
        dataTable: 'inv_location',
        f: [
            {
                k: 'area_id',
                l: '库区',
                r: 1,
                type: 'select',
                api: '/api/area/list?size=1000',
                vk: 'id',
                tk: 'area_name'
            },
            {k: 'location_name', l: '库位名称', r: 1},
            {k: 'code', l: '库位编码', r: 1},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]}
        ]
    });
}

function renderArrivalPage(el) {
    renderCrud(el, 'warehouse/arrival', {
        t: '到货通知',
        apiBase: '/api/arrival',
        dataTable: 'inv_arrival_notice',
        f: [
            {k: 'notice_no', l: '通知单号', generated: true},
            {
                k: 'supplier_id',
                l: '供应商',
                type: 'select',
                api: '/api/base/supplier/list?size=1000',
                vk: 'id',
                tk: 'supplier_name'
            },
            {k: 'expected_date', l: '预计到货日', type: 'date'},
            {
                k: 'status',
                l: '状态',
                s: [
                    {v: 0, t: '待到货'},
                    {v: 1, t: '部分到货'},
                    {v: 2, t: '已完成'}
                ]
            },
            {k: 'remark', l: '备注'}
        ]
    });
}

function renderTransactionPage(el) {
    renderCrud(el, 'warehouse/transaction', {
        t: '库存事务',
        apiBase: '/api/transaction',
        dataTable: 'inv_transaction_log',
        actions: {edit: false, delete: false, import: false},
        f: [
            {
                k: 'trans_type',
                l: '事务类型',
                r: 1,
                s: [
                    {v: 'IN', t: '入库'},
                    {v: 'OUT', t: '出库'},
                    {v: 'MOVE', t: '移库'},
                    {v: 'ADJUST', t: '调整'}
                ]
            },
            {
                k: 'product_id',
                l: '产品',
                r: 1,
                type: 'select',
                api: '/api/base/product/all',
                vk: 'id',
                tk: 'product_name'
            },
            {k: 'quantity', l: '数量', r: 1, type: 'number'},
            {
                k: 'warehouse_id',
                l: '仓库',
                type: 'select',
                api: '/api/warehouse/list?size=1000',
                vk: 'id',
                tk: 'warehouse_name'
            },
            {
                k: 'area_id',
                l: '库区',
                type: 'select',
                api: '/api/area/list?size=1000',
                vk: 'id',
                tk: 'area_name'
            },
            {
                k: 'location_id',
                l: '库位',
                type: 'select',
                api: '/api/location/list?size=1000',
                vk: 'id',
                tk: 'location_name'
            },
            {k: 'batch_no', l: '批次号'},
            {k: 'ref_no', l: '关联单号'},
            {k: 'remark', l: '备注'}
        ]
    });
}

function renderQualityTemplatePage(el) {
    renderCrud(el, 'qm/template', {
        t: '质检模板',
        apiBase: '/api/qm/template',
        dataTable: 'qm_inspect_template',
        f: [
            {k: 'template_name', l: '模板名称', r: 1},
            {
                k: 'inspect_type',
                l: '检验类型',
                r: 1,
                s: [
                    {v: 'incoming', t: '来料'},
                    {v: 'process', t: '过程'},
                    {v: 'outgoing', t: '出货'}
                ]
            },
            {k: 'items', l: '检验项目 JSON'},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]}
        ]
    });
}

function renderCheckProjectPage(el) {
    renderCrud(el, 'eqp/check-project', {
        t: '设备点检项目',
        apiBase: '/api/eqp/check-project',
        dataTable: 'eqp_check_project',
        f: [
            {k: 'project_name', l: '项目名称', r: 1},
            {k: 'check_type', l: '点检类型'},
            {k: 'standard', l: '点检标准'},
            {k: 'method', l: '点检方法'},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]}
        ]
    });
}

function renderScheduleCalendarPage(el) {
    renderCrud(el, 'sched/calendar', {
        t: '排班日历',
        apiBase: '/api/sched/calendar',
        dataTable: 'sched_calendar',
        f: [
            {
                k: 'plan_id',
                l: '排班计划',
                r: 1,
                type: 'select',
                api: '/api/sched/plan/list?size=1000',
                vk: 'id',
                tk: 'plan_name'
            },
            {k: 'work_date', l: '工作日期', r: 1, type: 'date'},
            {
                k: 'shift_type',
                l: '班次类型',
                s: [{v: 'day', t: '白班'}, {v: 'night', t: '夜班'}]
            },
            {k: 'user_ids', l: '人员 ID（逗号分隔）'}
        ]
    });
}
