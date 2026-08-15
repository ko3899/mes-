/* 生产现场/模具工装/公共事业/人力/5S/售后页面 */

// 工位管理
function renderWorkstation(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工位管理</span><button class="btn btn-blue" id="wsAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>工位名称</th><th>编码</th><th>车间</th><th>工序</th><th>产能</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('wsAddBtn').onclick = wsAdd;
    wsLoad();
}
function wsLoad() {
    api('/api/site/workstation/list').then(function(r) {
        if(!r||!r.data) return;
        var tb = document.getElementById('tb');
        if(!r.data.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = r.data.map(function(w) {
            return '<tr><td>'+w.id+'</td><td>'+w.station_name+'</td><td>'+w.code+'</td><td>'+(w.workshop_name||'-')+'</td>'
                +'<td>'+(w.process_name||'-')+'</td><td>'+w.capacity+'</td>'
                +'<td><span class="tag '+(w.status?'tag-ok':'tag-draft')+'">'+(w.status?'启用':'停用')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="wsDel('+w.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function wsAdd() {
    Promise.all([api('/api/base/workshop/list?size=100'), api('/api/base/process/list?size=100')]).then(function(r) {
        var wsOpts = '<option value="">请选择车间</option>';
        (r[0].data?.list||[]).forEach(function(w) { wsOpts += '<option value="'+w.id+'">'+w.workshop_name+'</option>'; });
        var procOpts = '<option value="">请选择工序</option>';
        (r[1].data?.list||[]).forEach(function(p) { procOpts += '<option value="'+p.id+'">'+p.process_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增工位';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工位名称<span style="color:red">*</span></label><input id="f_name"></div>'
            + '<div class="form-item"><label>编码<span style="color:red">*</span></label><input id="f_code"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>车间</label><select id="f_ws">'+wsOpts+'</select></div>'
            + '<div class="form-item"><label>工序</label><select id="f_proc">'+procOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>产能</label><input id="f_cap" type="number"></div></div>';
        modalSaveHandler = function() {
            var d = {station_name:document.getElementById('f_name').value, code:document.getElementById('f_code').value,
                workshop_id:document.getElementById('f_ws').value||null, process_id:document.getElementById('f_proc').value||null,
                capacity:document.getElementById('f_cap').value||0};
            if(!d.station_name||!d.code) { alert('请填写必填项'); return; }
            api('/api/site/workstation/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); wsLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function wsDel(id) { if(!confirm('确定删除？')) return; api('/api/site/workstation/delete',{method:'POST',body:{id:id}}).then(function(r){if(r&&r.code===0)wsLoad();else alert(r?r.message:'删除失败')}); }

// 安灯系统
function renderAndon(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>安灯系统</span><button class="btn btn-red" id="andonCallBtn">呼叫安灯</button></div>'
        + '<table><thead><tr><th>ID</th><th>安灯号</th><th>工位</th><th>类型</th><th>优先级</th><th>状态</th><th>呼叫人</th><th>响应人</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="9" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('andonCallBtn').onclick = andonCall;
    andonLoad();
}
function andonLoad() {
    api('/api/site/andon/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="9" class="empty">暂无安灯</td></tr>'; return; }
        var types = {quality:'质量',equipment:'设备',material:'物料',safety:'安全'};
        var pris = {1:'普通',2:'紧急',3:'危急'};
        var sts = {0:'<span class="tag tag-no">呼叫中</span>',1:'<span class="tag tag-run">响应中</span>',2:'<span class="tag tag-ok">已解决</span>'};
        tb.innerHTML = list.map(function(a) {
            return '<tr><td>'+a.id+'</td><td>'+a.andon_no+'</td><td>'+(a.station_name||'-')+'</td>'
                +'<td>'+(types[a.andon_type]||a.andon_type)+'</td><td>'+(pris[a.priority]||'-')+'</td>'
                +'<td>'+(sts[a.status]||'-')+'</td><td>'+(a.caller_name||'-')+'</td><td>'+(a.responder_name||'-')+'</td>'
                +'<td>'+(a.status===0?'<button class="btn btn-blue btn-sm" onclick="andonRespond('+a.id+')">响应</button>':'')
                +(a.status===1?'<button class="btn btn-green btn-sm" onclick="andonResolve('+a.id+')">解决</button>':'')+'</td></tr>';
        }).join('');
    });
}
function andonCall() {
    api('/api/site/workstation/list').then(function(r) {
        var opts = '<option value="">选择工位</option>';
        (r?.data||[]).filter(function(w) { return Number(w.status) === 1; }).forEach(function(w) { opts += '<option value="'+MESUI.escapeHtml(w.id)+'">'+MESUI.escapeHtml(w.station_name)+'</option>'; });
        document.getElementById('mTitle').textContent = '呼叫安灯';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工位</label><select id="f_ws">'+opts+'</select></div>'
            + '<div class="form-item"><label>类型</label><select id="f_type"><option value="quality">质量</option><option value="equipment">设备</option><option value="material">物料</option><option value="safety">安全</option></select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>优先级</label><select id="f_pri"><option value="1">普通</option><option value="2">紧急</option><option value="3">危急</option></select></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>描述</label><textarea id="f_desc"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {workstation_id:document.getElementById('f_ws').value, andon_type:document.getElementById('f_type').value,
                priority:document.getElementById('f_pri').value, description:document.getElementById('f_desc').value.trim()};
            if(!d.workstation_id) { alert('请选择工位'); return; }
            if(!d.description) { alert('请填写安灯描述'); return; }
            api('/api/site/andon/call',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); andonLoad(); } else alert(r2?r2.message:'操作失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function andonRespond(id) { api('/api/site/andon/respond',{method:'POST',body:{id:id}}).then(function(r){if(r.code===0)andonLoad();else alert(r.message)}); }
function andonResolve(id) { api('/api/site/andon/resolve',{method:'POST',body:{id:id,remark:'已处理'}}).then(function(r){if(r.code===0)andonLoad();else alert(r.message)}); }

// 返工报废
function renderRework(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>返工报废</span><button class="btn btn-blue" id="rwAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>单号</th><th>工单</th><th>数量</th><th>类型</th><th>原因</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('rwAddBtn').onclick = rwAdd;
    rwLoad();
}
function rwLoad() {
    api('/api/site/rework/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(rw) {
            return '<tr><td>'+MESUI.escapeHtml(rw.id)+'</td><td>'+MESUI.escapeHtml(rw.rework_no)+'</td><td>'+MESUI.escapeHtml(rw.workorder_no||'-')+'</td><td>'+MESUI.escapeHtml(rw.quantity)+'</td>'
                +'<td>'+MESUI.escapeHtml(rw.disposition||'-')+'</td><td>'+MESUI.escapeHtml(rw.reason||'-')+'</td>'
                +'<td><span class="tag '+(rw.status?'tag-ok':'tag-wait')+'">'+(rw.status?'已处理':'待处理')+'</span>'
                +(rw.status?'':' <button class="btn btn-green btn-sm" onclick="rwComplete('+rw.id+')">完成</button>')+'</td></tr>';
        }).join('');
    });
}
function rwAdd() {
    api('/api/prod/workorder/list?size=500').then(function(r) {
        var opts = '<option value="">选择工单</option>';
        (r?.data?.list||[]).filter(function(w) { return Number(w.status) < 3; }).forEach(function(w) { opts += '<option value="'+MESUI.escapeHtml(w.id)+'">'+MESUI.escapeHtml(w.order_no)+'</option>'; });
        document.getElementById('mTitle').textContent = '新增返工/报废';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工单</label><select id="f_wo">'+opts+'</select></div>'
            + '<div class="form-item"><label>类型</label><select id="f_type"><option value="返工">返工</option><option value="报废">报废</option></select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>数量<span style="color:red">*</span></label><input id="f_qty" type="number"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>原因</label><textarea id="f_reason"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {workorder_id:document.getElementById('f_wo').value, disposition:document.getElementById('f_type').value,
                quantity:document.getElementById('f_qty').value, reason:document.getElementById('f_reason').value.trim()};
            if(!d.workorder_id) { alert('请选择工单'); return; }
            if(!d.quantity || Number(d.quantity) <= 0) { alert('数量必须大于0'); return; }
            if(!d.reason) { alert('请填写原因'); return; }
            api('/api/site/rework/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); rwLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function rwComplete(id) {
    api('/api/site/rework/'+id+'/complete',{method:'POST',body:{}}).then(function(r) {
        if(r&&r.code===0) rwLoad(); else alert(r?r.message:'操作失败');
    });
}

// CAPA
function renderCAPA(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>CAPA 纠正预防措施</span><button class="btn btn-blue" id="capaAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>编号</th><th>标题</th><th>来源</th><th>责任人</th><th>截止日期</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('capaAddBtn').onclick = capaAdd;
    capaLoad();
}
function capaLoad() {
    api('/api/qm/capa/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        var st = {0:'草稿',1:'进行中',2:'已关闭'};
        tb.innerHTML = list.map(function(c) {
            return '<tr><td>'+c.id+'</td><td>'+c.capa_no+'</td><td>'+c.title+'</td><td>'+(c.source||'-')+'</td>'
                +'<td>'+(c.responsible||'-')+'</td><td>'+(c.due_date||'-')+'</td>'
                +'<td><span class="tag '+(c.status===2?'tag-ok':c.status?'tag-run':'tag-draft')+'">'+(st[c.status]||'草稿')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="capaDel('+c.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function capaAdd() {
    document.getElementById('mTitle').textContent = '新增CAPA';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>标题<span style="color:red">*</span></label><input id="f_title"></div>'
        + '<div class="form-item"><label>来源</label><select id="f_source"><option value="客诉">客诉</option><option value="内审">内审</option><option value="过程">过程</option><option value="其他">其他</option></select></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>问题描述</label><textarea id="f_problem"></textarea></div></div>'
        + '<div class="form-row"><div class="form-item"><label>根本原因</label><textarea id="f_cause"></textarea></div>'
        + '<div class="form-item"><label>纠正措施</label><textarea id="f_corrective"></textarea></div></div>'
        + '<div class="form-row"><div class="form-item"><label>预防措施</label><textarea id="f_preventive"></textarea></div>'
        + '<div class="form-item"><label>责任人</label><input id="f_resp"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>截止日期</label><input id="f_date" type="date"></div></div>';
    modalSaveHandler = function() {
        var d = {title:document.getElementById('f_title').value, source:document.getElementById('f_source').value,
            problem_desc:document.getElementById('f_problem').value, root_cause:document.getElementById('f_cause').value,
            corrective_action:document.getElementById('f_corrective').value, preventive_action:document.getElementById('f_preventive').value,
            responsible:document.getElementById('f_resp').value, due_date:document.getElementById('f_date').value};
        if(!d.title) { alert('请输入标题'); return; }
        api('/api/qm/capa/add',{method:'POST',body:d}).then(function(r2) {
            if(r2&&r2.code===0) { closeModal(); capaLoad(); } else alert(r2?r2.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function capaDel(id) { if(!confirm('确定删除？')) return; api('/api/qm/capa/delete',{method:'POST',body:{id:id}}).then(function(){capaLoad()}); }

// 控制计划
function renderControlPlan(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>控制计划</span><button class="btn btn-blue" id="cpAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>计划名称</th><th>产品</th><th>工序</th><th>特性</th><th>方法</th><th>频次</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('cpAddBtn').onclick = cpAdd;
    cpLoad();
}
function cpLoad() {
    api('/api/qm/control-plan/list').then(function(r) {
        if(!r||!r.data) return;
        var tb = document.getElementById('tb');
        if(!r.data.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = r.data.map(function(c) {
            return '<tr><td>'+c.id+'</td><td>'+c.plan_name+'</td><td>'+(c.product_name||'-')+'</td><td>'+(c.process_name||'-')+'</td>'
                +'<td>'+(c.characteristic||'-')+'</td><td>'+(c.method||'-')+'</td><td>'+(c.frequency||'-')+'</td>'
                +'<td><button class="btn btn-red btn-sm" onclick="cpDel('+c.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function cpAdd() {
    Promise.all([api('/api/base/product/all'), api('/api/base/process/list?size=100')]).then(function(r) {
        var prodOpts = '<option value="">选择产品</option>';
        (r[0]?.data||[]).forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+p.product_name+'</option>'; });
        var procOpts = '<option value="">选择工序</option>';
        (r[1]?.data?.list||[]).forEach(function(p) { procOpts += '<option value="'+p.id+'">'+p.process_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增控制计划';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>计划名称<span style="color:red">*</span></label><input id="f_name"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>产品</label><select id="f_prod">'+prodOpts+'</select></div>'
            + '<div class="form-item"><label>工序</label><select id="f_proc">'+procOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>特性</label><input id="f_char"></div>'
            + '<div class="form-item"><label>方法</label><input id="f_method"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>频次</label><input id="f_freq"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>反应计划</label><textarea id="f_reaction"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {plan_name:document.getElementById('f_name').value, product_id:document.getElementById('f_prod').value||null,
                process_id:document.getElementById('f_proc').value||null, characteristic:document.getElementById('f_char').value,
                method:document.getElementById('f_method').value, frequency:document.getElementById('f_freq').value,
                reaction_plan:document.getElementById('f_reaction').value};
            if(!d.plan_name) { alert('请输入计划名称'); return; }
            api('/api/qm/control-plan/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); cpLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function cpDel(id) { if(!confirm('确定删除？')) return; api('/api/qm/control-plan/delete',{method:'POST',body:{id:id}}).then(function(){cpLoad()}); }

// 工程变更
function renderECO(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工程变更</span><button class="btn btn-blue" id="ecoAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>编号</th><th>标题</th><th>类型</th><th>状态</th><th>生效日期</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('ecoAddBtn').onclick = ecoAdd;
    ecoLoad();
}
function ecoLoad() {
    api('/api/qm/eco/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        var st = {0:'草稿',1:'审批中',2:'已批准',3:'已实施'};
        tb.innerHTML = list.map(function(e) {
            return '<tr><td>'+e.id+'</td><td>'+e.eco_no+'</td><td>'+e.title+'</td><td>'+(e.change_type||'-')+'</td>'
                +'<td><span class="tag '+(e.status>=2?'tag-ok':e.status?'tag-run':'tag-draft')+'">'+(st[e.status]||'草稿')+'</span></td>'
                +'<td>'+(e.effective_date||'-')+'</td>'
                +'<td><button class="btn btn-red btn-sm" onclick="ecoDel('+e.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function ecoAdd() {
    document.getElementById('mTitle').textContent = '新增工程变更';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>标题<span style="color:red">*</span></label><input id="f_title"></div>'
        + '<div class="form-item"><label>类型</label><select id="f_type"><option value="设计">设计</option><option value="工艺">工艺</option><option value="材料">材料</option></select></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>变更描述</label><textarea id="f_desc"></textarea></div></div>'
        + '<div class="form-row"><div class="form-item"><label>变更原因</label><textarea id="f_reason"></textarea></div></div>'
        + '<div class="form-row"><div class="form-item"><label>影响分析</label><textarea id="f_impact"></textarea></div></div>'
        + '<div class="form-row"><div class="form-item"><label>生效日期</label><input id="f_date" type="date"></div></div>';
    modalSaveHandler = function() {
        var d = {title:document.getElementById('f_title').value, change_type:document.getElementById('f_type').value,
            description:document.getElementById('f_desc').value, reason:document.getElementById('f_reason').value,
            impact:document.getElementById('f_impact').value, effective_date:document.getElementById('f_date').value};
        if(!d.title) { alert('请输入标题'); return; }
        api('/api/qm/eco/add',{method:'POST',body:d}).then(function(r2) {
            if(r2&&r2.code===0) { closeModal(); ecoLoad(); } else alert(r2?r2.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function ecoDel(id) { if(!confirm('确定删除？')) return; api('/api/qm/eco/delete',{method:'POST',body:{id:id}}).then(function(){ecoLoad()}); }
