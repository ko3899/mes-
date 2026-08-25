/* 计划控制页面 - 计划员按 产品+阶段码 控制计划镭雕数量 */
/* 对接后端：
   GET  /api/prod/plan-control/list?product_id=&stage_code=&keyword=
        -> {code:0, data:{list:[{id, product_id, product_name, product_code, stage_code,
                                 plan_qty, ok_qty, balance_qty, adjust_qty, status}],
                           total:{plan_qty, ok_qty, balance_qty}, count:n}}
   POST /api/prod/plan-control/adjust  body {product_id, stage_code, adjust_qty}
        -> 成功 {code:0, message, data:{...}}；失败 HTTP 400 {code:400, message}
   POST /api/prod/plan-control/init   管理员用，批量初始化计划行
*/

var pcFailKeys = {}; // 提交失败行标记 "product_id:stage_code" -> true（用于刷新后红色标注）

function pcInjectStyle() {
    if (document.getElementById('pcPageStyle')) return;
    var st = document.createElement('style');
    st.id = 'pcPageStyle';
    st.textContent =
        '.pc-ro{background:var(--workspace);color:var(--text-muted);user-select:none}'
        + '.pc-num{text-align:right;font-variant-numeric:tabular-nums}'
        + '.pc-adjust{width:110px;text-align:right;font-variant-numeric:tabular-nums}'
        + '.pc-err{color:var(--danger)!important;font-weight:700}'
        + '.pc-err .pc-adjust{border-color:var(--danger)}'
        + '.pc-total-row td{background:var(--workspace);color:var(--text-strong);font-weight:800}';
    document.head.appendChild(st);
}

function renderPlanControl(el) {
    pcInjectStyle();
    pcFailKeys = {};
    el.innerHTML =
        '<div class="card"><div class="card-title"><span>计划控制</span>'
        + '<span class="muted">计划员按 产品+阶段码 控制计划镭雕数量，避免多版本共用多做返工</span>'
        + '<button class="btn btn-orange" id="pcInitBtn">初始化计划</button></div>'
        + '<div class="toolbar">'
        + '<select id="pcProduct" style="min-width:200px"><option value="">全部产品</option></select>'
        + '<select id="pcStage" style="min-width:160px"><option value="">全部阶段</option></select>'
        + '<input id="pcKeyword" placeholder="客户品名/料号搜索">'
        + '<button class="btn btn-blue" onclick="pcLoad()">查询</button>'
        + '<button class="btn btn-gray" onclick="pcReset()">重置</button>'
        + '</div></div>'
        + '<div class="card"><div class="table-wrap"><table>'
        + '<thead><tr><th>序号</th><th>项目号</th><th>客户品名</th><th>客户料号</th><th>阶段码</th>'
        + '<th>计划镭雕数量</th><th>镭雕OK数量</th><th>余量</th><th>增减计划数量</th></tr></thead>'
        + '<tbody id="pcTb"><tr><td colspan="9" class="empty">加载中...</td></tr></tbody>'
        + '<tfoot id="pcFoot" style="display:none"></tfoot>'
        + '</table></div>'
        + '<div style="display:flex;justify-content:flex-end;align-items:center;gap:10px;margin-top:12px">'
        + '<span class="muted" style="font-size:12px">增减数量支持负数：正数增加、负数减少</span>'
        + '<button class="btn btn-green" onclick="pcSubmit()">提交</button></div>'
        + '</div>';

    document.getElementById('pcInitBtn').onclick = pcInit;
    pcLoadFilters();
    pcLoad();
}

// 加载筛选下拉：产品 / 阶段码
function pcLoadFilters() {
    api('/api/base/product/all').then(function(r) {
        if (!r || r.code !== 0) return;
        var sel = document.getElementById('pcProduct');
        var opts = '<option value="">全部产品</option>';
        (r.data || []).forEach(function(p) {
            opts += '<option value="' + p.id + '">' + MESUI.escapeHtml(p.product_name)
                + (p.code ? ' (' + MESUI.escapeHtml(p.code) + ')' : '') + '</option>';
        });
        if (sel) sel.innerHTML = opts;
    });
    api('/api/stage/code/list').then(function(r) {
        if (!r || r.code !== 0) return;
        var sel = document.getElementById('pcStage');
        var opts = '<option value="">全部阶段</option>';
        (r.data || []).forEach(function(s) {
            opts += '<option value="' + MESUI.escapeHtml(s.code) + '">'
                + MESUI.escapeHtml(s.stage_name || s.code) + ' (' + MESUI.escapeHtml(s.code) + ')</option>';
        });
        if (sel) sel.innerHTML = opts;
    });
}

// 查询列表 + TOTAL
function pcLoad() {
    var params = new URLSearchParams();
    var pid = document.getElementById('pcProduct') ? document.getElementById('pcProduct').value : '';
    var stage = document.getElementById('pcStage') ? document.getElementById('pcStage').value : '';
    var kw = document.getElementById('pcKeyword') ? document.getElementById('pcKeyword').value.trim() : '';
    if (pid) params.set('product_id', pid);
    if (stage) params.set('stage_code', stage);
    if (kw) params.set('keyword', kw);
    var qs = params.toString();

    api('/api/prod/plan-control/list' + (qs ? '?' + qs : '')).then(function(r) {
        var tb = document.getElementById('pcTb');
        var foot = document.getElementById('pcFoot');
        if (!tb) return;
        if (!r || r.code !== 0) {
            tb.innerHTML = '<tr><td colspan="9" class="empty">加载失败：'
                + MESUI.escapeHtml(r && r.message ? r.message : '网络错误') + '</td></tr>';
            if (foot) foot.style.display = 'none';
            return;
        }
        var data = r.data || {};
        var list = data.list || [];
        if (!list.length) {
            tb.innerHTML = '<tr><td colspan="9" class="empty">暂无数据，可点击右上角「初始化计划」为每个产品生成计划行</td></tr>';
            if (foot) foot.style.display = 'none';
            return;
        }
        tb.innerHTML = list.map(function(row, i) {
            var key = row.product_id + ':' + (row.stage_code || '');
            var errCls = pcFailKeys[key] ? ' pc-err' : '';
            return '<tr>'
                + '<td>' + (i + 1) + '</td>'
                + '<td class="pc-ro">' + MESUI.escapeHtml(row.product_code || '-') + '</td>'
                + '<td class="pc-ro">' + MESUI.escapeHtml(row.product_name || '-') + '</td>'
                + '<td class="pc-ro">' + MESUI.escapeHtml(row.product_code || '-') + '</td>'
                + '<td class="pc-ro"><code>' + MESUI.escapeHtml(row.stage_code || '') + '</code></td>'
                + '<td class="pc-ro pc-num">' + Number(row.plan_qty || 0) + '</td>'
                + '<td class="pc-ro pc-num">' + Number(row.ok_qty || 0) + '</td>'
                + '<td class="pc-ro pc-num">' + Number(row.balance_qty || 0) + '</td>'
                + '<td class="pc-adjust-cell' + errCls + '">'
                + '<input type="number" class="pc-adjust" step="1" placeholder="0"'
                + ' data-pid="' + row.product_id + '"'
                + ' data-stage="' + MESUI.escapeHtml(row.stage_code || '') + '"'
                + ' data-label="' + MESUI.escapeHtml((row.product_name || row.product_code || '') + ' / ' + (row.stage_code || '')) + '"></td>'
                + '</tr>';
        }).join('');

        var total = data.total || {};
        foot.style.display = '';
        foot.innerHTML = '<tr class="pc-total-row">'
            + '<td colspan="5">TOTAL 合计</td>'
            + '<td class="pc-num">' + Number(total.plan_qty || 0) + '</td>'
            + '<td class="pc-num">' + Number(total.ok_qty || 0) + '</td>'
            + '<td class="pc-num">' + Number(total.balance_qty || 0) + '</td>'
            + '<td></td></tr>';
    });
}

function pcReset() {
    pcFailKeys = {};
    if (document.getElementById('pcProduct')) document.getElementById('pcProduct').value = '';
    if (document.getElementById('pcStage')) document.getElementById('pcStage').value = '';
    if (document.getElementById('pcKeyword')) document.getElementById('pcKeyword').value = '';
    pcLoad();
}

// 初始化计划（管理员用，后端校验权限）
function pcInit() {
    if (!confirm('初始化计划将按当前产品主数据为每个产品创建计划行（计划镭雕数量=0），已存在的行不会被覆盖。确认初始化？')) return;
    api('/api/prod/plan-control/init', {method: 'POST', body: {}}).then(function(r) {
        if (r && r.code === 0) {
            alert('初始化成功，新建 ' + Number(r.data && r.data.created || 0) + ' 行');
            pcFailKeys = {};
            pcLoad();
        } else {
            alert(r && r.message ? r.message : '初始化失败');
        }
    });
}

// 提交：逐行调用 /adjust；失败行红色标注 + 提示后端 message，不保存该行；成功后刷新列表
function pcSubmit() {
    var inputs = document.querySelectorAll('#pcTb .pc-adjust');
    var pending = [];
    for (var i = 0; i < inputs.length; i++) {
        var inp = inputs[i];
        var val = inp.value.trim();
        if (val === '') continue;
        var adjust = Number(val);
        if (isNaN(adjust)) continue;
        pending.push({
            inp: inp,
            pid: inp.getAttribute('data-pid'),
            stage: inp.getAttribute('data-stage') || '',
            label: inp.getAttribute('data-label') || '该行',
            adjust: adjust
        });
    }
    if (!pending.length) { alert('请先填写需要增减的计划数量'); return; }

    var failed = [];
    var idx = 0;
    (function next() {
        if (idx >= pending.length) {
            if (failed.length) {
                alert('以下行提交失败：\n' + failed.map(function(f) { return f.msg; }).join('\n'));
            }
            pcLoad(); // 提交后刷新列表，balance_qty 以后端为准
            return;
        }
        var item = pending[idx++];
        api('/api/prod/plan-control/adjust', {
            method: 'POST',
            body: {product_id: item.pid, stage_code: item.stage, adjust_qty: item.adjust}
        }).then(function(r) {
            if (r && r.code === 0) {
                item.inp.value = '';
                item.inp.classList.remove('pc-err');
                delete pcFailKeys[item.pid + ':' + item.stage];
            } else {
                item.inp.classList.add('pc-err');
                var cell = item.inp.closest('td');
                if (cell) cell.classList.add('pc-err');
                pcFailKeys[item.pid + ':' + item.stage] = true;
                failed.push({msg: item.label + '：' + (r && r.message ? r.message : '调整失败')});
            }
            next();
        });
    })();
}
