/* 培训/技能/5S/售后页面 */

// 培训管理
function renderTraining(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>培训管理</span><button class="btn btn-blue" id="trainAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>培训名称</th><th>类型</th><th>讲师</th><th>开始</th><th>结束</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('trainAddBtn').onclick = trainAdd;
    trainLoad();
}
function trainLoad() {
    api('/api/hr/training/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        var st = {0:'待开始',1:'进行中',2:'已完成'};
        tb.innerHTML = list.map(function(t) {
            return '<tr><td>'+t.id+'</td><td>'+t.training_name+'</td><td>'+(t.training_type||'-')+'</td>'
                +'<td>'+(t.trainer||'-')+'</td><td>'+(t.start_date||'-')+'</td><td>'+(t.end_date||'-')+'</td>'
                +'<td><span class="tag '+(t.status===2?'tag-ok':t.status?'tag-run':'tag-wait')+'">'+(st[t.status]||'待开始')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="trainDel('+t.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function trainAdd() {
    document.getElementById('mTitle').textContent = '新增培训';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>培训名称<span style="color:red">*</span></label><input id="f_name"></div>'
        + '<div class="form-item"><label>类型</label><select id="f_type"><option value="入职">入职</option><option value="技能">技能</option><option value="安全">安全</option><option value="质量">质量</option></select></div></div>'
        + '<div class="form-row"><div class="form-item"><label>讲师</label><input id="f_trainer"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>开始日期</label><input id="f_start" type="date"></div>'
        + '<div class="form-item"><label>结束日期</label><input id="f_end" type="date"></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>培训内容</label><textarea id="f_content"></textarea></div></div>';
    modalSaveHandler = function() {
        var d = {training_name:document.getElementById('f_name').value, training_type:document.getElementById('f_type').value,
            trainer:document.getElementById('f_trainer').value, start_date:document.getElementById('f_start').value,
            end_date:document.getElementById('f_end').value, content:document.getElementById('f_content').value};
        if(!d.training_name) { alert('请输入培训名称'); return; }
        api('/api/hr/training/add',{method:'POST',body:d}).then(function(r2) {
            if(r2&&r2.code===0) { closeModal(); trainLoad(); } else alert(r2?r2.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function trainDel(id) { if(!confirm('确定删除？')) return; api('/api/hr/training/delete',{method:'POST',body:{id:id}}).then(function(){trainLoad()}); }

// 技能矩阵
function renderSkillMatrix(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>技能矩阵</span><button class="btn btn-blue" id="skillAddBtn">+ 新增</button></div>'
        + '<div id="skillMatrixView" style="margin-bottom:16px;overflow-x:auto"></div>'
        + '<table><thead><tr><th>ID</th><th>员工</th><th>工序</th><th>技能等级</th><th>认证日期</th><th>有效期</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('skillAddBtn').onclick = skillAdd;
    skillLoad();
    skillMatrixView();
}
function skillLoad() {
    api('/api/hr/skill-matrix/list').then(function(r) {
        if(!r||!r.data) return;
        var tb = document.getElementById('tb');
        if(!r.data.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        var levels = {0:'未评估',1:'初级',2:'中级',3:'高级',4:'专家'};
        var colors = {'0':'#999','1':'#fa8c16','2':'#1890ff','3':'#52c41a','4':'#722ed1'};
        tb.innerHTML = r.data.map(function(s) {
            return '<tr><td>'+s.id+'</td><td>'+(s.real_name||'-')+'</td><td>'+(s.process_name||'-')+'</td>'
                +'<td><span style="color:'+(colors[s.skill_level]||'#333')+';font-weight:bold">'+(levels[s.skill_level]||'-')+'</span></td>'
                +'<td>'+(s.cert_date||'-')+'</td><td>'+(s.expiry_date||'-')+'</td>'
                +'<td><button class="btn btn-red btn-sm" onclick="skillDel('+s.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function skillMatrixView() {
    api('/api/hr/skill-matrix/matrix').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        if(!d.users.length||!d.processes.length) return;
        var el = document.getElementById('skillMatrixView');
        var levels = {0:'-',1:'初',2:'中',3:'高',4:'专'};
        var colors = {'0':'#f5f5f5','1':'#fff7e6','2':'#e6f7ff','3':'#f6ffed','4':'#f9f0ff'};
        var h = '<table style="font-size:12px"><thead><tr><th>员工</th>';
        d.processes.forEach(function(p) { h += '<th>'+p.process_name+'</th>'; });
        h += '</tr></thead><tbody>';
        d.users.forEach(function(u) {
            h += '<tr><td>'+u.real_name+'</td>';
            d.processes.forEach(function(p) {
                var level = d.matrix[u.id+'_'+p.id] || 0;
                h += '<td style="background:'+(colors[level]||'#f5f5f5')+';text-align:center;font-weight:bold">'+(levels[level]||'-')+'</td>';
            });
            h += '</tr>';
        });
        h += '</tbody></table>';
        el.innerHTML = h;
    });
}
function skillAdd() {
    Promise.all([api('/api/sys/user/list?size=100'), api('/api/base/process/list?size=100')]).then(function(r) {
        var userOpts = '<option value="">选择员工</option>';
        (r[0]?.data?.list||[]).forEach(function(u) { userOpts += '<option value="'+u.id+'">'+u.real_name+'</option>'; });
        var procOpts = '<option value="">选择工序</option>';
        (r[1]?.data?.list||[]).forEach(function(p) { procOpts += '<option value="'+p.id+'">'+p.process_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增技能评估';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>员工<span style="color:red">*</span></label><select id="f_user">'+userOpts+'</select></div>'
            + '<div class="form-item"><label>工序<span style="color:red">*</span></label><select id="f_proc">'+procOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>技能等级</label><select id="f_level"><option value="1">初级</option><option value="2">中级</option><option value="3">高级</option><option value="4">专家</option></select></div>'
            + '<div class="form-item"><label>认证日期</label><input id="f_date" type="date"></div></div>';
        document.getElementById('f_date').value = new Date().toISOString().slice(0,10);
        modalSaveHandler = function() {
            var d = {user_id:document.getElementById('f_user').value, process_id:document.getElementById('f_proc').value,
                skill_level:document.getElementById('f_level').value, cert_date:document.getElementById('f_date').value};
            if(!d.user_id||!d.process_id) { alert('请填写必填项'); return; }
            api('/api/hr/skill-matrix/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); skillLoad(); skillMatrixView(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function skillDel(id) { if(!confirm('确定删除？')) return; api('/api/hr/skill-matrix/delete',{method:'POST',body:{id:id}}).then(function(){skillLoad();skillMatrixView()}); }

// 5S检查
function render5SAudit(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>5S检查</span><button class="btn btn-blue" id="audit5sAddBtn">+ 新增</button></div>'
        + '<div id="audit5sStats" style="margin-bottom:16px"></div>'
        + '<table><thead><tr><th>ID</th><th>编号</th><th>车间</th><th>日期</th><th>整理</th><th>整顿</th><th>清扫</th><th>清洁</th><th>素养</th><th>总分</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="11" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('audit5sAddBtn').onclick = audit5sAdd;
    audit5sLoad();
    audit5sStatsLoad();
}
function audit5sLoad() {
    api('/api/5s/audit/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="11" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(a) {
            var scoreColor = a.total_score >= 80 ? '#52c41a' : (a.total_score >= 60 ? '#fa8c16' : '#f5222d');
            return '<tr><td>'+a.id+'</td><td>'+a.audit_no+'</td><td>'+(a.workshop_name||'-')+'</td><td>'+a.audit_date+'</td>'
                +'<td>'+a.sort_score+'</td><td>'+a.set_in_order_score+'</td><td>'+a.shine_score+'</td>'
                +'<td>'+a.standardize_score+'</td><td>'+a.sustain_score+'</td>'
                +'<td style="color:'+scoreColor+';font-weight:bold">'+a.total_score+'</td>'
                +'<td><span class="tag '+(a.status?'tag-ok':'tag-wait')+'">'+(a.status?'已整改':'待整改')+'</span></td></tr>';
        }).join('');
    });
}
function audit5sStatsLoad() {
    api('/api/5s/statistics').then(function(r) {
        if(!r||!r.data) return;
        var el = document.getElementById('audit5sStats');
        el.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px">'
            +r.data.map(function(s) {
                var color = s.avg_score >= 80 ? '#52c41a' : (s.avg_score >= 60 ? '#fa8c16' : '#f5222d');
                return '<div style="background:#f0f5ff;padding:12px;border-radius:8px;text-align:center">'
                    +'<div style="font-weight:bold">'+s.workshop_name+'</div>'
                    +'<div style="font-size:20px;color:'+color+'">'+s.avg_score.toFixed(1)+'分</div>'
                    +'<div style="font-size:12px;color:#666">'+s.audit_count+'次检查</div></div>';
            }).join('')+'</div>';
    });
}
function audit5sAdd() {
    api('/api/base/workshop/list?size=100').then(function(r) {
        var opts = '<option value="">选择车间</option>';
        (r?.data?.list||[]).forEach(function(w) { opts += '<option value="'+w.id+'">'+w.workshop_name+'</option>'; });
        document.getElementById('mTitle').textContent = '5S检查';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>车间<span style="color:red">*</span></label><select id="f_ws">'+opts+'</select></div>'
            + '<div class="form-item"><label>日期</label><input id="f_date" type="date"></div></div>'
            + '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:14px">'
            + '<div><label>整理(0-20)</label><input id="f_s1" type="number" max="20" value="0"></div>'
            + '<div><label>整顿(0-20)</label><input id="f_s2" type="number" max="20" value="0"></div>'
            + '<div><label>清扫(0-20)</label><input id="f_s3" type="number" max="20" value="0"></div>'
            + '<div><label>清洁(0-20)</label><input id="f_s4" type="number" max="20" value="0"></div>'
            + '<div><label>素养(0-20)</label><input id="f_s5" type="number" max="20" value="0"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>发现问题</label><textarea id="f_findings"></textarea></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>整改措施</label><textarea id="f_corrective"></textarea></div></div>';
        document.getElementById('f_date').value = new Date().toISOString().slice(0,10);
        modalSaveHandler = function() {
            var d = {workshop_id:document.getElementById('f_ws').value, audit_date:document.getElementById('f_date').value,
                sort_score:document.getElementById('f_s1').value, set_in_order_score:document.getElementById('f_s2').value,
                shine_score:document.getElementById('f_s3').value, standardize_score:document.getElementById('f_s4').value,
                sustain_score:document.getElementById('f_s5').value, findings:document.getElementById('f_findings').value,
                corrective:document.getElementById('f_corrective').value};
            if(!d.workshop_id) { alert('请选择车间'); return; }
            api('/api/5s/audit/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); audit5sLoad(); audit5sStatsLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 客诉管理
function renderComplaint(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>客诉管理</span><button class="btn btn-blue" id="csAddBtn">+ 新增</button></div>'
        + '<div id="csStats" style="margin-bottom:16px"></div>'
        + '<table><thead><tr><th>ID</th><th>编号</th><th>客户</th><th>产品</th><th>类型</th><th>严重度</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('csAddBtn').onclick = csAdd;
    csLoad();
    csStatsLoad();
}
function csLoad() {
    api('/api/svc/complaint/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        var st = {0:'待处理',1:'处理中',2:'已关闭'};
        var sev = {low:'低',medium:'中',high:'高',critical:'危急'};
        var sevColor = {low:'#52c41a',medium:'#1890ff',high:'#fa8c16',critical:'#f5222d'};
        tb.innerHTML = list.map(function(c) {
            return '<tr><td>'+c.id+'</td><td>'+c.complaint_no+'</td><td>'+(c.customer_name||'-')+'</td>'
                +'<td>'+(c.product_name||'-')+'</td><td>'+(c.complaint_type||'-')+'</td>'
                +'<td style="color:'+(sevColor[c.severity]||'#333')+'">'+(sev[c.severity]||'-')+'</td>'
                +'<td><span class="tag '+(c.status===2?'tag-ok':c.status?'tag-run':'tag-wait')+'">'+(st[c.status]||'待处理')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="csDel('+c.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function csStatsLoad() {
    api('/api/svc/statistics').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        document.getElementById('csStats').innerHTML = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px">'
            +'<div class="stat"><div class="label">总客诉</div><div class="val">'+d.total_complaints+'</div></div>'
            +'<div class="stat"><div class="label">待处理</div><div class="val" style="color:#f5222d">'+d.pending+'</div></div>'
            +'<div class="stat"><div class="label">退换货</div><div class="val">'+d.total_returns+'</div></div></div>';
    });
}
function csAdd() {
    Promise.all([api('/api/base/customer/all'), api('/api/base/product/all')]).then(function(r) {
        var custOpts = '<option value="">选择客户</option>';
        (r[0]?.data||[]).forEach(function(c) { custOpts += '<option value="'+c.id+'">'+c.customer_name+'</option>'; });
        var prodOpts = '<option value="">选择产品</option>';
        (r[1]?.data||[]).forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+p.product_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增客诉';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>客户</label><select id="f_cust">'+custOpts+'</select></div>'
            + '<div class="form-item"><label>产品</label><select id="f_prod">'+prodOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>类型</label><select id="f_type"><option value="质量">质量</option><option value="服务">服务</option><option value="交付">交付</option></select></div>'
            + '<div class="form-item"><label>严重度</label><select id="f_sev"><option value="low">低</option><option value="medium">中</option><option value="high">高</option><option value="critical">危急</option></select></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>描述</label><textarea id="f_desc"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {customer_id:document.getElementById('f_cust').value||null, product_id:document.getElementById('f_prod').value||null,
                complaint_type:document.getElementById('f_type').value, severity:document.getElementById('f_sev').value,
                description:document.getElementById('f_desc').value};
            api('/api/svc/complaint/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); csLoad(); csStatsLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function csDel(id) {
    if(!confirm('确定删除？')) return;
    api('/api/svc/complaint/delete', {method:'POST', body:{id:id}}).then(function(r) {
        if(r && r.code === 0) {
            csLoad();
            csStatsLoad();
        } else {
            alert(r ? r.message : '删除失败');
        }
    });
}

// 退换货
function renderReturn(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>退换货</span><button class="btn btn-blue" id="srAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>编号</th><th>客诉</th><th>客户</th><th>产品</th><th>数量</th><th>原因</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('srAddBtn').onclick = serviceReturnAdd;
    serviceReturnLoad();
}
function serviceReturnLoad() {
    api('/api/svc/return/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        var st = {0:'待处理',1:'已收货',2:'已换货',3:'已退款'};
        tb.innerHTML = list.map(function(sr) {
            return '<tr><td>'+sr.id+'</td><td>'+sr.return_no+'</td><td>'+(sr.complaint_id||'-')+'</td>'
                +'<td>'+(sr.customer_name||'-')+'</td><td>'+(sr.product_name||'-')+'</td><td>'+sr.quantity+'</td>'
                +'<td>'+MESUI.escapeHtml(sr.return_reason||'-')+'</td>'
                +'<td><span class="tag '+(sr.status>=2?'tag-ok':sr.status?'tag-run':'tag-wait')+'">'+(st[sr.status]||'待处理')+'</span></td></tr>';
        }).join('');
    });
}
function serviceReturnAdd() {
    Promise.all([api('/api/base/customer/all'), api('/api/base/product/all')]).then(function(r) {
        var custOpts = '<option value="">选择客户</option>';
        (r[0]?.data||[]).forEach(function(c) { custOpts += '<option value="'+c.id+'">'+c.customer_name+'</option>'; });
        var prodOpts = '<option value="">选择产品</option>';
        (r[1]?.data||[]).forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+p.product_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增退换货';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>客户</label><select id="f_cust">'+custOpts+'</select></div>'
            + '<div class="form-item"><label>产品</label><select id="f_prod">'+prodOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>数量</label><input id="f_qty" type="number"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>原因</label><textarea id="f_reason"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {customer_id:document.getElementById('f_cust').value||null, product_id:document.getElementById('f_prod').value||null,
                quantity:document.getElementById('f_qty').value, return_reason:document.getElementById('f_reason').value};
            if(!d.customer_id || !d.product_id || Number(d.quantity) <= 0 || !d.return_reason.trim()) {
                alert('请选择客户和产品，数量必须大于0，原因不能为空'); return;
            }
            api('/api/svc/return/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); serviceReturnLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
