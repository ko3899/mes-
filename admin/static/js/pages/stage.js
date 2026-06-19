/* 阶段码管理页面 */

// 阶段码定义
function renderStageCode(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>生产阶段管理</span><button class="btn btn-blue" id="stageAddBtn">+ 新增阶段</button></div>'
        + '<table><thead><tr><th>排序</th><th>ID</th><th>阶段名称</th><th>编码</th><th>颜色</th><th>描述</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('stageAddBtn').onclick = stageAdd;
    stageCodeLoad();
}
function stageCodeLoad() {
    api('/api/stage/code/list').then(function(r) {
        if(!r||!r.data) return;
        var tb = document.getElementById('tb');
        if(!r.data.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无阶段，请添加试产/量产等阶段</td></tr>'; return; }
        tb.innerHTML = r.data.map(function(s, i) {
            return '<tr><td>'
                +'<button class="btn btn-gray btn-sm" onclick="stageReorder('+s.id+',\'up\')" '+(i===0?'disabled':'')+'>▲</button> '
                +'<button class="btn btn-gray btn-sm" onclick="stageReorder('+s.id+',\'down\')" '+(i===r.data.length-1?'disabled':'')+'>▼</button></td>'
                +'<td>'+s.id+'</td><td><span style="color:'+s.color+';font-weight:bold">'+s.stage_name+'</span></td>'
                +'<td><code>'+s.code+'</code></td>'
                +'<td><span style="display:inline-block;width:20px;height:20px;background:'+s.color+';border-radius:4px;vertical-align:middle"></span></td>'
                +'<td>'+(s.description||'-')+'</td>'
                +'<td><span class="tag '+(s.status?'tag-ok':'tag-draft')+'">'+(s.status?'启用':'停用')+'</span></td>'
                +'<td class="actions"><button class="btn btn-blue btn-sm" onclick=\'stageEdit('+escapeJson(s)+')\'>编辑</button>'
                +'<button class="btn btn-red btn-sm" onclick="stageDel('+s.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function stageAdd() {
    document.getElementById('mTitle').textContent = '新增阶段码';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>阶段名称<span style="color:red">*</span></label><input id="f_name" placeholder="如: 切割"></div>'
        + '<div class="form-item"><label>编码<span style="color:red">*</span></label><input id="f_code" placeholder="如: CUT"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>颜色</label><input id="f_color" type="color" value="#1890ff"></div>'
        + '<div class="form-item"><label>描述</label><input id="f_desc"></div></div>';
    modalSaveHandler = function() {
        var d = {stage_name:document.getElementById('f_name').value, code:document.getElementById('f_code').value.toUpperCase(),
            color:document.getElementById('f_color').value, description:document.getElementById('f_desc').value};
        if(!d.stage_name||!d.code) { alert('请填写必填项'); return; }
        api('/api/stage/code/add',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); stageCodeLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function stageEdit(row) {
    document.getElementById('mTitle').textContent = '编辑阶段码';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>阶段名称<span style="color:red">*</span></label><input id="f_name" value="'+row.stage_name+'"></div>'
        + '<div class="form-item"><label>编码<span style="color:red">*</span></label><input id="f_code" value="'+row.code+'" disabled></div></div>'
        + '<div class="form-row"><div class="form-item"><label>颜色</label><input id="f_color" type="color" value="'+row.color+'"></div>'
        + '<div class="form-item"><label>描述</label><input id="f_desc" value="'+(row.description||'')+'"></div></div>';
    modalSaveHandler = function() {
        var d = {id:row.id, stage_name:document.getElementById('f_name').value,
            color:document.getElementById('f_color').value, description:document.getElementById('f_desc').value};
        api('/api/stage/code/update',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); stageCodeLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function stageDel(id) { if(!confirm('确定删除？')) return; api('/api/stage/code/delete',{method:'POST',body:{id:id}}).then(function(){stageCodeLoad()}); }
function stageReorder(id, dir) { api('/api/stage/code/reorder',{method:'POST',body:{id:id,direction:dir}}).then(function(r){if(r.code===0)stageCodeLoad();else alert(r.message)}); }

// 阶段记录
function renderStageRecord(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>阶段记录</span><button class="btn btn-blue" id="srAddBtn">+ 新增记录</button></div>'
        + '<table><thead><tr><th>ID</th><th>阶段</th><th>工单</th><th>产品</th><th>数量</th><th>操作人</th><th>开始</th><th>结束</th><th>时长</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="10" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('srAddBtn').onclick = srAdd;
    srLoad();
}
function srLoad() {
    api('/api/stage/record/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="10" class="empty">暂无记录</td></tr>'; return; }
        tb.innerHTML = list.map(function(sr) {
            var isComplete = sr.end_time;
            return '<tr><td>'+sr.id+'</td><td><code>'+sr.stage_code+'</code></td><td>'+(sr.workorder_no||'-')+'</td>'
                +'<td>'+(sr.product_name||'-')+'</td><td>'+sr.quantity+'</td><td>'+(sr.real_name||'-')+'</td>'
                +'<td>'+(sr.start_time||'-')+'</td><td>'+(sr.end_time||'-')+'</td><td>'+(sr.duration?sr.duration+'分钟':'-')+'</td>'
                +'<td>'+(isComplete?'<span class="tag tag-ok">已完成</span>':'<button class="btn btn-green btn-sm" onclick="srComplete('+sr.id+')">完成</button>')+'</td></tr>';
        }).join('');
    });
}
function srAdd() {
    Promise.all([api('/api/stage/code/list'), api('/api/prod/workorder/list?size=500'), api('/api/base/product/all')]).then(function(r) {
        var stageOpts = '<option value="">选择阶段</option>';
        (r[0]?.data||[]).forEach(function(s) { stageOpts += '<option value="'+s.code+'">'+s.stage_name+' ('+s.code+')</option>'; });
        var woOpts = '<option value="">选择工单(可选)</option>';
        (r[1]?.data?.list||[]).forEach(function(w) { woOpts += '<option value="'+w.id+'">'+w.order_no+'</option>'; });
        var prodOpts = '<option value="">选择产品(可选)</option>';
        (r[2]?.data||[]).forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+p.product_name+'</option>'; });
        
        document.getElementById('mTitle').textContent = '新增阶段记录';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>阶段<span style="color:red">*</span></label><select id="f_stage">'+stageOpts+'</select></div>'
            + '<div class="form-item"><label>工单</label><select id="f_wo">'+woOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>产品</label><select id="f_prod">'+prodOpts+'</select></div>'
            + '<div class="form-item"><label>数量</label><input id="f_qty" type="number"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>备注</label><textarea id="f_remark"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {stage_code:document.getElementById('f_stage').value, workorder_id:document.getElementById('f_wo').value||null,
                product_id:document.getElementById('f_prod').value||null, quantity:document.getElementById('f_qty').value||0,
                remark:document.getElementById('f_remark').value, start_time: new Date().toISOString()};
            if(!d.stage_code) { alert('请选择阶段'); return; }
            api('/api/stage/record/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); srLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function srComplete(id) {
    document.getElementById('mTitle').textContent = '完成阶段';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item" style="flex:1"><label>备注</label><textarea id="f_remark"></textarea></div></div>';
    modalSaveHandler = function() {
        api('/api/stage/record/complete',{method:'POST',body:{id:id,remark:document.getElementById('f_remark').value}}).then(function(r) {
            if(r&&r.code===0) { closeModal(); srLoad(); } else alert(r?r.message:'操作失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}

// 阶段统计
function renderStageStatistics(el) {
    el.innerHTML = '<div class="card"><div class="card-title">阶段统计</div>'
        + '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">总记录数</div><div class="val" id="st_total">-</div></div>'
        + '<div class="stat"><div class="label">今日记录</div><div class="val" id="st_today">-</div></div>'
        + '<div class="stat"><div class="label">平均时长</div><div class="val" id="st_avg">-</div></div>'
        + '</div>'
        + '<div id="stageChart" style="height:300px"></div></div>';
    api('/api/stage/statistics').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        var totalRecords = d.stage_counts.reduce(function(s,c){return s+c.count},0);
        document.getElementById('st_total').textContent = totalRecords;
        document.getElementById('st_today').textContent = d.today_records;
        document.getElementById('st_avg').textContent = d.avg_duration + '分钟';
        
        if(d.stage_counts.length) {
            var chart = echarts.init(document.getElementById('stageChart'));
            chart.setOption({
                tooltip:{trigger:'axis'},
                xAxis:{type:'category',data:d.stage_counts.map(function(s){return s.stage_code})},
                yAxis:{type:'value'},
                series:[
                    {name:'记录数',type:'bar',data:d.stage_counts.map(function(s){return s.count}),itemStyle:{color:'#1890ff'}},
                    {name:'总数量',type:'bar',data:d.stage_counts.map(function(s){return s.total_qty||0}),itemStyle:{color:'#52c41a'}}
                ]
            });
        }
    });
}
