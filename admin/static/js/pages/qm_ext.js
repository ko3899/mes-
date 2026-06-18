/* 质量管理增强页面 */

// 首件检验
function renderFirstInspect(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>首件检验</span>'
        + '<button class="btn btn-blue" id="fiAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>检验单号</th><th>工单</th><th>工序</th><th>自检</th><th>互检</th><th>专检</th><th>结果</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="9" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('fiAddBtn').onclick = fiAdd;
    fiLoad();
}
function fiLoad() {
    api('/api/qm/first/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(f) {
            return '<tr><td>'+f.id+'</td><td>'+f.inspect_no+'</td><td>'+(f.workorder_no||'-')+'</td>'
                +'<td>'+(f.process_name||'-')+'</td>'
                +'<td>'+(f.self_check?'<span class="tag tag-ok">✓</span>':'<span class="tag tag-draft">-</span>')+'</td>'
                +'<td>'+(f.mutual_check?'<span class="tag tag-ok">✓</span>':'<span class="tag tag-draft">-</span>')+'</td>'
                +'<td>'+(f.special_check?'<span class="tag tag-ok">✓</span>':'<span class="tag tag-draft">-</span>')+'</td>'
                +'<td>'+(f.result||'-')+'</td>'
                +'<td><span class="tag '+(f.status?'tag-ok':'tag-wait')+'">'+(f.status?'已检':'待检')+'</span></td></tr>';
        }).join('');
    });
}
function fiAdd() {
    Promise.all([api('/api/prod/workorder/list?size=500'), api('/api/base/process/list?size=500')]).then(function(r) {
        var woList = r[0] && r[0].data ? (r[0].data.list||r[0].data) : [];
        var procList = r[1] && r[1].data ? (r[1].data.list||r[1].data) : [];
        var woOpts = '<option value="">请选择工单</option>';
        woList.forEach(function(w) { woOpts += '<option value="'+w.id+'">'+w.order_no+'</option>'; });
        var procOpts = '<option value="">请选择工序</option>';
        procList.forEach(function(p) { procOpts += '<option value="'+p.id+'">'+p.process_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增首件检验';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工单<span style="color:red">*</span></label><select id="f_wo">'+woOpts+'</select></div>'
            + '<div class="form-item"><label>工序<span style="color:red">*</span></label><select id="f_proc">'+procOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label><input type="checkbox" id="f_self"> 自检</label></div>'
            + '<div class="form-item"><label><input type="checkbox" id="f_mutual"> 互检</label></div>'
            + '<div class="form-item"><label><input type="checkbox" id="f_special"> 专检</label></div></div>'
            + '<div class="form-row"><div class="form-item"><label>结果</label><select id="f_result"><option value="合格">合格</option><option value="不合格">不合格</option></select></div></div>';
        modalSaveHandler = function() {
            var d = {workorder_id:document.getElementById('f_wo').value, process_id:document.getElementById('f_proc').value,
                self_check:document.getElementById('f_self').checked?1:0, mutual_check:document.getElementById('f_mutual').checked?1:0,
                special_check:document.getElementById('f_special').checked?1:0, result:document.getElementById('f_result').value, status:1};
            if(!d.workorder_id||!d.process_id) { alert('请填写必填项'); return; }
            api('/api/qm/first/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); fiLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 不良品处理
function renderDefectProcess(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>不良品处理</span>'
        + '<button class="btn btn-blue" id="dpAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>处理单号</th><th>工单</th><th>缺陷</th><th>数量</th><th>处理方式</th><th>结果</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('dpAddBtn').onclick = dpAdd;
    dpLoad();
}
function dpLoad() {
    api('/api/qm/defect/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(d) {
            return '<tr><td>'+d.id+'</td><td>'+d.process_no+'</td><td>'+(d.workorder_no||'-')+'</td>'
                +'<td>'+(d.defect_name||'-')+'</td><td>'+d.quantity+'</td><td>'+d.process_type+'</td>'
                +'<td>'+(d.result||'-')+'</td>'
                +'<td><span class="tag '+(d.status?'tag-ok':'tag-wait')+'">'+(d.status?'已处理':'待处理')+'</span></td></tr>';
        }).join('');
    });
}
function dpAdd() {
    Promise.all([api('/api/prod/workorder/list?size=500'), api('/api/base/defect/list?size=500')]).then(function(r) {
        var woList = r[0] && r[0].data ? (r[0].data.list||r[0].data) : [];
        var defList = r[1] && r[1].data ? (r[1].data.list||r[1].data) : [];
        var woOpts = '<option value="">请选择工单</option>';
        woList.forEach(function(w) { woOpts += '<option value="'+w.id+'">'+w.order_no+'</option>'; });
        var defOpts = '<option value="">请选择缺陷</option>';
        defList.forEach(function(d) { defOpts += '<option value="'+d.id+'">'+d.defect_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增不良品处理';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工单</label><select id="f_wo">'+woOpts+'</select></div>'
            + '<div class="form-item"><label>缺陷</label><select id="f_def">'+defOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_qty" type="number"></div>'
            + '<div class="form-item"><label>处理方式</label><select id="f_type"><option value="返工">返工</option><option value="报废">报废</option><option value="让步接收">让步接收</option></select></div></div>';
        modalSaveHandler = function() {
            var d = {workorder_id:document.getElementById('f_wo').value, defect_id:document.getElementById('f_def').value,
                quantity:document.getElementById('f_qty').value, process_type:document.getElementById('f_type').value};
            if(!d.quantity) { alert('请填写数量'); return; }
            api('/api/qm/defect/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); dpLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 8D报告
function render8DReport(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>8D报告</span>'
        + '<button class="btn btn-blue" id="d8AddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>报告编号</th><th>标题</th><th>责任人</th><th>截止日期</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('d8AddBtn').onclick = d8Add;
    d8Load();
}
function d8Load() {
    api('/api/qm/8d/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        var st = {0:'草稿',1:'进行中',2:'已完成'};
        tb.innerHTML = list.map(function(d) {
            return '<tr><td>'+d.id+'</td><td>'+d.report_no+'</td><td>'+d.title+'</td>'
                +'<td>'+(d.responsible||'-')+'</td><td>'+(d.due_date||'-')+'</td>'
                +'<td><span class="tag '+(d.status===2?'tag-ok':d.status?'tag-run':'tag-draft')+'">'+(st[d.status]||'草稿')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="d8Del('+d.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function d8Add() {
    document.getElementById('mTitle').textContent = '新增8D报告';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>标题<span style="color:red">*</span></label><input id="f_title"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>问题描述</label><textarea id="f_problem"></textarea></div></div>'
        + '<div class="form-row"><div class="form-item"><label>根本原因</label><textarea id="f_cause"></textarea></div></div>'
        + '<div class="form-row"><div class="form-item"><label>纠正措施</label><textarea id="f_corrective"></textarea></div>'
        + '<div class="form-item"><label>预防措施</label><textarea id="f_preventive"></textarea></div></div>'
        + '<div class="form-row"><div class="form-item"><label>责任人</label><input id="f_resp"></div>'
        + '<div class="form-item"><label>截止日期</label><input id="f_date" type="date"></div></div>';
    modalSaveHandler = function() {
        var d = {title:document.getElementById('f_title').value, problem_desc:document.getElementById('f_problem').value,
            root_cause:document.getElementById('f_cause').value, corrective_action:document.getElementById('f_corrective').value,
            preventive_action:document.getElementById('f_preventive').value, responsible:document.getElementById('f_resp').value,
            due_date:document.getElementById('f_date').value};
        if(!d.title) { alert('请填写标题'); return; }
        api('/api/qm/8d/add',{method:'POST',body:d}).then(function(r2) {
            if(r2&&r2.code===0) { closeModal(); d8Load(); } else alert(r2?r2.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function d8Del(id) { if(!confirm('确定删除？')) return; api('/api/qm/8d/delete',{method:'POST',body:{id:id}}).then(function(){d8Load()}); }

// 供方评审
function renderSupplierEval(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>供方评审</span>'
        + '<button class="btn btn-blue" id="seAddBtn">+ 新增评审</button></div></div>'
        + '<div id="ranking" style="margin-bottom:16px"></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>供应商</th><th>质量</th><th>交期</th><th>服务</th><th>总分</th><th>等级</th><th>日期</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('seAddBtn').onclick = seAdd;
    seLoad();
    seRanking();
}
function seLoad() {
    api('/api/qm/supplier-eval/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(e) {
            var gradeColor = {A:'#52c41a',B:'#1890ff',C:'#fa8c16',D:'#f5222d'};
            return '<tr><td>'+e.id+'</td><td>'+(e.supplier_name||'-')+'</td>'
                +'<td>'+e.quality_score+'</td><td>'+e.delivery_score+'</td><td>'+e.service_score+'</td>'
                +'<td><b>'+e.total_score+'</b></td>'
                +'<td><span style="color:'+(gradeColor[e.grade]||'#333')+';font-weight:bold">'+e.grade+'</span></td>'
                +'<td>'+(e.eval_date||'')+'</td></tr>';
        }).join('');
    });
}
function seRanking() {
    api('/api/qm/supplier-eval/ranking').then(function(r) {
        if(!r||!r.data) return;
        var el = document.getElementById('ranking');
        el.innerHTML = '<div class="card"><div class="card-title">供应商排名</div>'
            +'<table><thead><tr><th>排名</th><th>供应商</th><th>平均分</th><th>评审次数</th><th>等级</th></tr></thead><tbody>'
            +r.data.map(function(s,i) {
                return '<tr><td>'+(i+1)+'</td><td>'+s.supplier_name+'</td><td>'+s.avg_score.toFixed(2)+'</td>'
                    +'<td>'+s.eval_count+'</td><td><b>'+s.latest_grade+'</b></td></tr>';
            }).join('')+'</tbody></table></div>';
    });
}
function seAdd() {
    api('/api/base/supplier/all').then(function(r) {
        var list = r && r.data ? r.data : [];
        var opts = '<option value="">请选择供应商</option>';
        list.forEach(function(s) { opts += '<option value="'+s.id+'">'+s.supplier_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增供方评审';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>供应商<span style="color:red">*</span></label><select id="f_sup">'+opts+'</select></div>'
            + '<div class="form-item"><label>评审日期<span style="color:red">*</span></label><input id="f_date" type="date"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>质量评分(0-100)</label><input id="f_q" type="number" max="100"></div>'
            + '<div class="form-item"><label>交期评分(0-100)</label><input id="f_d" type="number" max="100"></div>'
            + '<div class="form-item"><label>服务评分(0-100)</label><input id="f_s" type="number" max="100"></div></div>';
        document.getElementById('f_date').value = new Date().toISOString().slice(0,10);
        modalSaveHandler = function() {
            var d = {supplier_id:document.getElementById('f_sup').value, eval_date:document.getElementById('f_date').value,
                quality_score:document.getElementById('f_q').value, delivery_score:document.getElementById('f_d').value,
                service_score:document.getElementById('f_s').value};
            if(!d.supplier_id||!d.eval_date) { alert('请填写必填项'); return; }
            api('/api/qm/supplier-eval/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); seLoad(); seRanking(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 质量统计
function renderQMStatistics(el) {
    el.innerHTML = '<div class="card"><div class="card-title">质量统计（近30天）</div>'
        + '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">来料合格率</div><div class="val" id="incomingRate">-</div></div>'
        + '<div class="stat"><div class="label">过程合格率</div><div class="val" id="processRate">-</div></div>'
        + '<div class="stat"><div class="label">出货合格率</div><div class="val" id="outgoingRate">-</div></div>'
        + '</div>'
        + '<div id="defectChart" style="height:300px"></div></div>';
    api('/api/qm/statistics').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        document.getElementById('incomingRate').textContent = d.incoming_rate+'%';
        document.getElementById('processRate').textContent = d.process_rate+'%';
        document.getElementById('outgoingRate').textContent = d.outgoing_rate+'%';
        if(d.defect_stats.length) {
            var chart = echarts.init(document.getElementById('defectChart'));
            chart.setOption({
                title:{text:'不良品TOP10',left:'center'},
                tooltip:{trigger:'axis'},
                xAxis:{type:'category',data:d.defect_stats.map(function(d){return d.defect_name||'未知'})},
                yAxis:{type:'value'},
                series:[{type:'bar',data:d.defect_stats.map(function(d){return d.count}),itemStyle:{color:'#f5222d'}}]
            });
        }
    });
}
