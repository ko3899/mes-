/* 扩展功能页面模块 */

// 工序管理（带调序）
function renderProcess(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工序管理</span>'
        + '<button class="btn btn-blue" id="processAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>排序</th><th>ID</th><th>工序名称</th><th>编码</th><th>车间</th><th>标准工时</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('processAddBtn').onclick = processAdd;
    processLoad();
}
function processLoad() {
    api('/api/base/process/list?size=500').then(function(r) {
        if(!r||!r.data) return;
        var list = Array.isArray(r.data) ? r.data : (r.data.list || []);
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(p, i) {
            return '<tr><td>'
                +'<button class="btn btn-gray btn-sm" onclick="processReorder('+p.id+',\'up\')" '+(i===0?'disabled':'')+'>▲</button> '
                +'<button class="btn btn-gray btn-sm" onclick="processReorder('+p.id+',\'down\')" '+(i===list.length-1?'disabled':'')+'>▼</button></td>'
                +'<td>'+p.id+'</td><td>'+p.process_name+'</td><td>'+p.code+'</td><td>'+(p.workshop_name||'-')+'</td>'
                +'<td>'+(p.standard_time||'-')+'</td>'
                +'<td><span class="tag '+(p.status?'tag-ok':'tag-draft')+'">'+(p.status?'启用':'禁用')+'</span></td>'
                +'<td class="actions"><button class="btn btn-blue btn-sm" onclick=\'processEdit('+escapeJson(p)+')\'>编辑</button>'
                +'<button class="btn btn-red btn-sm" onclick="processDel('+p.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function processAdd() {
    api('/api/base/workshop/list?size=1000').then(function(r) {
        var opts = '<option value="">请选择车间</option>';
        (r?.data?.list||[]).forEach(function(w) { opts += '<option value="'+w.id+'">'+w.workshop_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增工序';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工序名称<span style="color:red">*</span></label><input id="f_name"></div>'
            + '<div class="form-item"><label>编码<span style="color:red">*</span></label><input id="f_code"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>车间</label><select id="f_ws">'+opts+'</select></div>'
            + '<div class="form-item"><label>标准工时(分钟)</label><input id="f_time" type="number" step="0.1"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>描述</label><textarea id="f_desc"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {process_name:document.getElementById('f_name').value, code:document.getElementById('f_code').value,
                workshop_id:document.getElementById('f_ws').value||null, standard_time:document.getElementById('f_time').value||null,
                description:document.getElementById('f_desc').value};
            if(!d.process_name||!d.code) { alert('请填写必填项'); return; }
            api('/api/base/process/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); processLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function processEdit(row) {
    api('/api/base/workshop/list?size=1000').then(function(r) {
        var opts = '<option value="">请选择车间</option>';
        (r?.data?.list||[]).forEach(function(w) { opts += '<option value="'+w.id+'"'+(w.id==row.workshop_id?' selected':'')+'>'+w.workshop_name+'</option>'; });
        document.getElementById('mTitle').textContent = '编辑工序';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工序名称<span style="color:red">*</span></label><input id="f_name" value="'+row.process_name+'"></div>'
            + '<div class="form-item"><label>编码<span style="color:red">*</span></label><input id="f_code" value="'+row.code+'"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>车间</label><select id="f_ws">'+opts+'</select></div>'
            + '<div class="form-item"><label>标准工时(分钟)</label><input id="f_time" type="number" step="0.1" value="'+(row.standard_time||'')+'"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>描述</label><textarea id="f_desc">'+(row.description||'')+'</textarea></div></div>';
        modalSaveHandler = function() {
            var d = {id:row.id, process_name:document.getElementById('f_name').value, code:document.getElementById('f_code').value,
                workshop_id:document.getElementById('f_ws').value||null, standard_time:document.getElementById('f_time').value||null,
                description:document.getElementById('f_desc').value};
            if(!d.process_name||!d.code) { alert('请填写必填项'); return; }
            api('/api/base/process/update',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); processLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function processDel(id) { if(!confirm('确定删除？')) return; api('/api/base/process/delete',{method:'POST',body:{id:id}}).then(function(){processLoad()}); }
function processReorder(id, direction) {
    api('/api/base/process/reorder',{method:'POST',body:{id:id,direction:direction}}).then(function(r) {
        if(r&&r.code===0) { processLoad(); } else alert(r?r.message:'调序失败');
    });
}

// 供应商管理
function renderSupplier(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>供应商管理</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'base_supplier\')">导出</button>'
        + '<button class="btn btn-blue" id="supplierAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>供应商名称</th><th>编码</th><th>联系人</th><th>电话</th><th>评分</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('supplierAddBtn').onclick = function(){crudAdd()};
    curFields = [{k:'supplier_name',l:'供应商名称',r:1},{k:'code',l:'编码',r:1},{k:'contact',l:'联系人'},{k:'phone',l:'电话'},{k:'email',l:'邮箱'},{k:'address',l:'地址'},{k:'rating',l:'评分',type:'number'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}];
    curApiBase = '/api/base/supplier';
    crudLoad(1);
}

// 客户管理
function renderCustomer(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>客户管理</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'base_customer\')">导出</button>'
        + '<button class="btn btn-blue" id="customerAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>客户名称</th><th>编码</th><th>联系人</th><th>电话</th><th>信用额度</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('customerAddBtn').onclick = function(){crudAdd()};
    curFields = [{k:'customer_name',l:'客户名称',r:1},{k:'code',l:'编码',r:1},{k:'contact',l:'联系人'},{k:'phone',l:'电话'},{k:'email',l:'邮箱'},{k:'address',l:'地址'},{k:'credit_limit',l:'信用额度',type:'number'},{k:'status',l:'状态',s:[{v:1,t:'启用'},{v:0,t:'禁用'}]}];
    curApiBase = '/api/base/customer';
    crudLoad(1);
}

// 文档管理
function renderDocList(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>文档管理</span>'
        + '<button class="btn btn-blue" id="docUploadBtn">上传文档</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>文档名称</th><th>类型</th><th>大小</th><th>上传时间</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('docUploadBtn').onclick = docUpload;
    docLoad();
}
function docLoad() {
    api('/api/document/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无文档</td></tr>'; return; }
        tb.innerHTML = list.map(function(d) {
            var size = d.file_size ? (d.file_size/1024).toFixed(1) + 'KB' : '-';
            return '<tr><td>'+d.id+'</td><td>'+d.doc_name+'</td><td>'+(d.doc_type||'-')+'</td><td>'+size+'</td><td>'+(d.created_at||'')+'</td>'
                +'<td><a href="/api/document/download/'+d.id+'" class="btn btn-blue btn-sm">下载</a> '
                +'<button class="btn btn-red btn-sm" onclick="docDel('+d.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function docUpload() {
    document.getElementById('mTitle').textContent = '上传文档';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>文档类型</label><select id="f_type"><option value="SOP">SOP作业指导书</option><option value="图纸">图纸</option><option value="规范">规范</option><option value="其他">其他</option></select></div></div>'
        + '<div class="form-row"><div class="form-item"><label>选择文件</label><input type="file" id="f_file"></div></div>';
    modalSaveHandler = function() {
        var fileInput = document.getElementById('f_file');
        if(!fileInput.files.length) { alert('请选择文件'); return; }
        var formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('doc_type', document.getElementById('f_type').value);
        fetch('/api/document/upload', {method:'POST', body:formData}).then(r=>r.json()).then(r=>{
            if(r.code===0) { closeModal(); docLoad(); } else alert(r.message||'上传失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function docDel(id) { if(!confirm('确定删除？')) return; api('/api/document/delete',{method:'POST',body:{id:id}}).then(function(){docLoad()}); }

// 成本核算
function renderCostReport(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>成本核算</span>'
        + '<button class="btn btn-blue" id="costAddBtn">+ 新增</button></div>'
        + '<div id="costSummary" style="margin-bottom:16px"></div>'
        + '<table><thead><tr><th>ID</th><th>工单</th><th>类型</th><th>金额</th><th>说明</th><th>时间</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('costAddBtn').onclick = costAdd;
    costLoad();
    costSummaryLoad();
}
function costLoad() {
    api('/api/cost/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(c) {
            return '<tr><td>'+c.id+'</td><td>'+(c.workorder_no||c.workorder_id)+'</td><td>'+c.cost_type+'</td>'
                +'<td style="color:#f5222d;font-weight:bold">¥'+c.amount+'</td><td>'+(c.description||'-')+'</td><td>'+(c.created_at||'')+'</td>'
                +'<td><button class="btn btn-red btn-sm" onclick="costDel('+c.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function costSummaryLoad() {
    api('/api/cost/summary').then(function(r) {
        if(!r||!r.data) return;
        var el = document.getElementById('costSummary');
        var total = r.data.reduce((s,c)=>s+c.total,0);
        el.innerHTML = '<div style="display:flex;gap:20px">'+r.data.map(c=>'<div style="flex:1;background:#f0f5ff;padding:12px;border-radius:8px;text-align:center">'
            +'<div style="font-size:18px;font-weight:bold;color:#1890ff">¥'+c.total.toFixed(2)+'</div><div style="color:#666;font-size:13px">'+c.cost_type+'</div></div>').join('')
            +'<div style="flex:1;background:#fff2f0;padding:12px;border-radius:8px;text-align:center">'
            +'<div style="font-size:18px;font-weight:bold;color:#f5222d">¥'+total.toFixed(2)+'</div><div style="color:#666;font-size:13px">总计</div></div></div>';
    });
}
function costAdd() {
    api('/api/prod/workorder/list?size=500').then(function(r) {
        var list = r && r.data ? (r.data.list||r.data) : [];
        var opts = '<option value="">请选择工单</option>';
        list.forEach(function(w) { opts += '<option value="'+w.id+'">'+w.order_no+'</option>'; });
        document.getElementById('mTitle').textContent = '新增成本';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>工单<span style="color:red">*</span></label><select id="f_wo">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>成本类型</label><select id="f_type"><option value="材料">材料</option><option value="人工">人工</option><option value="设备">设备</option><option value="其他">其他</option></select></div>'
            + '<div class="form-item"><label>金额<span style="color:red">*</span></label><input id="f_amt" type="number" step="0.01"></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>说明</label><textarea id="f_desc"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {workorder_id:document.getElementById('f_wo').value, cost_type:document.getElementById('f_type').value,
                amount:document.getElementById('f_amt').value, description:document.getElementById('f_desc').value};
            if(!d.workorder_id||!d.amount) { alert('请填写必填项'); return; }
            api('/api/cost/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); costLoad(); costSummaryLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function costDel(id) { if(!confirm('确定删除？')) return; api('/api/cost/delete',{method:'POST',body:{id:id}}).then(function(){costLoad();costSummaryLoad()}); }

// 数据备份
function renderBackup(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>数据备份</span>'
        + '<button class="btn btn-blue" onclick="createBackup()">立即备份</button></div>'
        + '<table><thead><tr><th>ID</th><th>备份名称</th><th>大小</th><th>时间</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="5" class="empty">加载中...</td></tr></tbody></table></div>';
    backupLoad();
}
function backupLoad() {
    api('/api/backup/list').then(function(r) {
        if(!r) return;
        var list = r.data || [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="5" class="empty">暂无备份</td></tr>'; return; }
        tb.innerHTML = list.map(function(b) {
            return '<tr><td>'+b.id+'</td><td>'+b.backup_name+'</td><td>'+(b.file_size/1024/1024).toFixed(2)+'MB</td><td>'+(b.created_at||'')+'</td>'
                +'<td><a href="/api/backup/download/'+b.id+'" class="btn btn-blue btn-sm">下载</a> '
                +'<button class="btn btn-orange btn-sm" onclick="restoreBackup('+b.id+')">恢复</button> '
                +'<button class="btn btn-red btn-sm" onclick="delBackup('+b.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function createBackup() {
    api('/api/backup/create',{method:'POST'}).then(function(r) {
        if(r&&r.code===0) { alert('备份成功'); backupLoad(); } else alert(r?r.message:'备份失败');
    });
}
function restoreBackup(id) { if(!confirm('确定恢复此备份？当前数据将被覆盖！')) return; api('/api/backup/restore',{method:'POST',body:{id:id}}).then(function(r){if(r&&r.code===0)alert('恢复成功，请重启服务');else alert(r?r.message:'恢复失败')}); }
function delBackup(id) { if(!confirm('确定删除？')) return; api('/api/backup/delete',{method:'POST',body:{id:id}}).then(function(){backupLoad()}); }

// 安全设置
function renderSecurity(el) {
    el.innerHTML = '<div class="card"><div class="card-title">安全设置</div>'
        + '<div style="margin-bottom:16px"><h3>API Token</h3><p style="color:#666;margin:8px 0">用于第三方系统对接</p>'
        + '<button class="btn btn-blue" onclick="generateToken()">生成新Token</button></div>'
        + '<div id="tokenResult" style="margin-top:12px"></div></div>'
        + '<div class="card"><div class="card-title">安全日志</div>'
        + '<table><thead><tr><th>时间</th><th>用户</th><th>操作</th><th>URL</th><th>IP</th></tr></thead>'
        + '<tbody id="secLog"><tr><td colspan="5" class="empty">加载中...</td></tr></tbody></table></div>';
    loadSecLog();
}
function generateToken() {
    api('/api/security/token/generate',{method:'POST'}).then(function(r) {
        if(r&&r.code===0) {
            document.getElementById('tokenResult').innerHTML = '<div style="background:#f6ffed;padding:12px;border-radius:6px;border:1px solid #b7eb8f">'
                +'<b>新Token:</b> <code style="background:#fff;padding:4px 8px;border-radius:4px">'+r.data.token+'</code>'
                +'<p style="color:#999;font-size:12px;margin-top:8px">请妥善保管，此Token不会再次显示</p></div>';
        }
    });
}
function loadSecLog() {
    api('/api/security/log').then(function(r) {
        if(!r) return;
        var list = r.data || [];
        var tb = document.getElementById('secLog');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="5" class="empty">暂无日志</td></tr>'; return; }
        tb.innerHTML = list.map(function(l) {
            return '<tr><td>'+(l.created_at||'')+'</td><td>'+(l.username||'')+'</td><td>'+(l.operation||'')+'</td><td>'+(l.url||'')+'</td><td>'+(l.ip||'')+'</td></tr>';
        }).join('');
    });
}
