/* 审批流程和 SPC 分析模块 */

// 流程定义
function renderFlowDef(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>流程定义</span><button class="btn btn-blue" id="flowDefAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>流程名称</th><th>标识</th><th>描述</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('flowDefAddBtn').onclick = flowDefAdd;
    flowDefLoad();
}
function flowDefLoad() {
    api('/api/flow/definition/list?size=100').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(r2) {
            return '<tr><td>'+r2.id+'</td><td>'+r2.flow_name+'</td><td>'+r2.flow_key+'</td><td>'+(r2.description||'-')+'</td>'
                +'<td><span class="tag '+(r2.status?'tag-ok':'tag-draft')+'">'+(r2.status?'启用':'停用')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="flowDefDel('+r2.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function flowDefAdd() {
    document.getElementById('mTitle').textContent = '新增流程定义';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>流程名称<span style="color:red">*</span></label><input id="f_fn"></div>'
        + '<div class="form-item"><label>标识<span style="color:red">*</span></label><input id="f_fk" placeholder="如: workorder_approval"></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>描述</label><textarea id="f_desc"></textarea></div></div>';
    modalSaveHandler = function() {
        var d = {flow_name:document.getElementById('f_fn').value, flow_key:document.getElementById('f_fk').value, description:document.getElementById('f_desc').value, steps:'[{"step":1,"name":"审批","assignee":1}]'};
        if(!d.flow_name||!d.flow_key) { alert('请填写必填项'); return; }
        api('/api/flow/definition/add',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); flowDefLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function flowDefDel(id) { if(!confirm('确定删除？')) return; api('/api/flow/definition/delete',{method:'POST',body:{id:id}}).then(function(){flowDefLoad()}); }

// 我的审批
function renderFlowInstance(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>我的审批</span><button class="btn btn-blue" onclick="flowSubmit()">提交审批</button></div>'
        + '<table><thead><tr><th>ID</th><th>流程</th><th>标题</th><th>当前步骤</th><th>状态</th><th>创建时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    flowInstLoad();
}
function flowInstLoad() {
    api('/api/flow/instance/list?tab=mine&size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(r2) {
            var st = {0:'<span class="tag tag-wait">审批中</span>',1:'<span class="tag tag-ok">已通过</span>',2:'<span class="tag tag-no">已驳回</span>'};
            return '<tr><td>'+r2.id+'</td><td>'+(r2.flow_name||'-')+'</td><td>'+(r2.title||'-')+'</td><td>第'+r2.current_step+'步</td>'
                +'<td>'+(st[r2.status]||'未知')+'</td><td>'+(r2.created_at||'')+'</td></tr>';
        }).join('');
    });
}
function flowSubmit() {
    api('/api/flow/definition/list?size=100').then(function(r) {
        var flows = (r && r.data) ? (r.data.list||[]) : [];
        var opts = '<option value="">请选择流程</option>';
        flows.forEach(function(f) { if(f.status) opts += '<option value="'+f.id+'">'+f.flow_name+'</option>'; });
        document.getElementById('mTitle').textContent = '提交审批';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>流程<span style="color:red">*</span></label><select id="f_fid">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>标题<span style="color:red">*</span></label><input id="f_ttl"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>关联类型</label><select id="f_bt"><option value="">无</option><option value="workorder">工单</option><option value="inbound">入库</option><option value="outbound">出库</option></select></div>'
            + '<div class="form-item"><label>关联ID</label><input id="f_bid" type="number"></div></div>';
        modalSaveHandler = function() {
            var d = {flow_id:document.getElementById('f_fid').value, title:document.getElementById('f_ttl').value,
                biz_type:document.getElementById('f_bt').value, biz_id:document.getElementById('f_bid').value||0};
            if(!d.flow_id||!d.title) { alert('请填写必填项'); return; }
            api('/api/flow/instance/submit',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); flowInstLoad(); } else alert(r2?r2.message:'提交失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 待我审批
function renderFlowPending(el) {
    el.innerHTML = '<div class="card"><div class="card-title">待我审批</div>'
        + '<table><thead><tr><th>ID</th><th>流程</th><th>标题</th><th>步骤</th><th>创建时间</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    flowPendingLoad();
}
function flowPendingLoad() {
    api('/api/flow/instance/list?tab=pending&size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无待审批</td></tr>'; return; }
        tb.innerHTML = list.map(function(r2) {
            return '<tr><td>'+r2.id+'</td><td>'+(r2.flow_name||'-')+'</td><td>'+(r2.title||'-')+'</td><td>第'+r2.current_step+'步</td>'
                +'<td>'+(r2.created_at||'')+'</td>'
                +'<td><button class="btn btn-green btn-sm" onclick="flowApprove('+r2.id+')">通过</button> '
                +'<button class="btn btn-red btn-sm" onclick="flowReject('+r2.id+')">驳回</button></td></tr>';
        }).join('');
    });
}
function flowApprove(taskId) {
    document.getElementById('mTitle').textContent = '审批通过';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item" style="flex:1"><label>审批意见</label><textarea id="f_cmt" placeholder="同意"></textarea></div></div>';
    modalSaveHandler = function() {
        api('/api/flow/task/approve',{method:'POST',body:{id:taskId,comment:document.getElementById('f_cmt').value||'同意'}}).then(function(r) {
            if(r&&r.code===0) { closeModal(); flowPendingLoad(); } else alert(r?r.message:'审批失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function flowReject(taskId) {
    document.getElementById('mTitle').textContent = '审批驳回';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item" style="flex:1"><label>驳回原因<span style="color:red">*</span></label><textarea id="f_cmt"></textarea></div></div>';
    modalSaveHandler = function() {
        var cmt = document.getElementById('f_cmt').value;
        if(!cmt) { alert('请填写驳回原因'); return; }
        api('/api/flow/task/reject',{method:'POST',body:{id:taskId,comment:cmt}}).then(function(r) {
            if(r&&r.code===0) { closeModal(); flowPendingLoad(); } else alert(r?r.message:'操作失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}

// SPC 分析
function renderSPC(el) {
    el.innerHTML = '<div class="card"><div class="card-title">SPC 统计过程控制</div>'
        + '<div class="toolbar"><select id="spcProc"><option value="">全部工序</option></select>'
        + '<select id="spcDays"><option value="7">近7天</option><option value="30" selected>近30天</option><option value="90">近90天</option></select>'
        + '<label style="margin-left:12px">USL:</label><input id="spcUSL" type="number" value="100" style="width:80px">'
        + '<label>LSL:</label><input id="spcLSL" type="number" value="0" style="width:80px">'
        + '<button class="btn btn-blue" onclick="spcLoad()">分析</button></div></div>'
        + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">'
        + '<div class="card"><div class="card-title">合格率控制图 (X̄图)</div><div id="spcChart1" style="height:300px"></div></div>'
        + '<div class="card"><div class="card-title">CPK 分析</div><div id="spcChart2" style="height:300px"></div></div>'
        + '</div>'
        + '<div class="card"><div class="card-title">分析结果</div><div id="spcResult" style="line-height:2;color:#333">请选择工序后点击"分析"</div></div>';

    api('/api/base/process/list?size=100').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var sel = document.getElementById('spcProc');
        list.forEach(function(p) { sel.innerHTML += '<option value="'+p.id+'">'+p.process_name+'</option>'; });
    });
}
function spcLoad() {
    var pid = document.getElementById('spcProc').value;
    var days = document.getElementById('spcDays').value;
    var usl = document.getElementById('spcUSL').value || 100;
    var lsl = document.getElementById('spcLSL').value || 0;

    var url1 = '/api/spc/chart?days='+days;
    if(pid) url1 += '&process_id='+pid;
    api(url1).then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        var c1 = echarts.init(document.getElementById('spcChart1'));
        c1.setOption({
            tooltip:{trigger:'axis'},
            xAxis:{type:'category',data:d.points.map(function(p){return p.date.slice(5)})},
            yAxis:{type:'value',min:function(v){return Math.max(0,v.min-5)},max:100},
            series:[
                {name:'合格率',type:'line',data:d.points.map(function(p){return p.rate}),markLine:{data:[
                    {name:'UCL',yAxis:d.ucl,lineStyle:{color:'#f5222d'},label:{formatter:'UCL: '+d.ucl}},
                    {name:'CL',yAxis:d.cl,lineStyle:{color:'#52c41a',type:'dashed'},label:{formatter:'CL: '+d.cl}},
                    {name:'LCL',yAxis:d.lcl,lineStyle:{color:'#fa8c16'},label:{formatter:'LCL: '+d.lcl}}
                ]}},
                {name:'UCL',type:'line',data:d.points.map(function(){return d.ucl}),lineStyle:{color:'#f5222d',type:'dashed'},showSymbol:false},
                {name:'LCL',type:'line',data:d.points.map(function(){return d.lcl}),lineStyle:{color:'#fa8c16',type:'dashed'},showSymbol:false}
            ]
        });
        window.addEventListener('resize',function(){c1.resize();});
    });

    var url2 = '/api/spc/cpk?days='+days+'&usl='+usl+'&lsl='+lsl;
    if(pid) url2 += '&process_id='+pid;
    api(url2).then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        var color = d.cpk>=1.33?'#52c41a':(d.cpk>=1.0?'#fa8c16':'#f5222d');
        var c2 = echarts.init(document.getElementById('spcChart2'));
        c2.setOption({
            series:[{
                type:'gauge', radius:'80%',
                axisLine:{lineStyle:{width:20,color:[[0.6,'#f5222d'],[0.8,'#fa8c16'],[1,'#52c41a']]}},
                pointer:{length:'60%'},
                axisTick:{show:false}, splitLine:{length:10},
                axisLabel:{fontSize:11},
                detail:{valueAnimation:true,formatter:'{value}',fontSize:24,offsetCenter:[0,'70%'],color:color},
                data:[{value:d.cpk,name:'CPK'}]
            }]
        });
        window.addEventListener('resize',function(){c2.resize();});

        document.getElementById('spcResult').innerHTML = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px">'
            + '<div><b>CP值:</b> <span style="font-size:18px;color:'+color+'">'+d.cp+'</span></div>'
            + '<div><b>CPK值:</b> <span style="font-size:18px;color:'+color+'">'+d.cpk+'</span></div>'
            + '<div><b>均值(X̄):</b> '+d.x_bar+'</div>'
            + '<div><b>标准差(σ):</b> '+d.std+'</div>'
            + '<div><b>USL:</b> '+d.usl+'</div>'
            + '<div><b>LSL:</b> '+d.lsl+'</div>'
            + '<div><b>样本数:</b> '+d.count+'</div>'
            + '<div><b>判定:</b> <span style="color:'+color+';font-weight:bold">'+d.judgment+'</span></div>'
            + '</div>';
    });
}
