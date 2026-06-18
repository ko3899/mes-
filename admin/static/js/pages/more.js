/* 更多业务页面模块 */

// 维修单
function renderRepair(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>维修单</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'eqp_repair_order\')">导出</button>'
        + '<button class="btn btn-blue" id="repairAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>维修单号</th><th>设备</th><th>故障</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('repairAddBtn').onclick = repairAdd;
    repairLoad();
}
function repairLoad() {
    api('/api/eqp/repair/list').then(function(r) {
        if(!r) return;
        var list = Array.isArray(r.data) ? r.data : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>'; return; }
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + r2.repair_no + '</td><td>' + (r2.equipment_name||r2.equipment_id) + '</td>';
            h += '<td>' + (r2.fault_desc||'') + '</td>';
            h += '<td><span class="tag ' + (r2.status === 2 ? 'tag-ok' : r2.status ? 'tag-wait' : 'tag-draft') + '">' + (r2.status === 2 ? '已完成' : r2.status ? '维修中' : '待修') + '</span></td>';
            h += '<td><button class="btn btn-red btn-sm" onclick="repairDel(' + r2.id + ')">删除</button></td></tr>';
        });
        tb.innerHTML = h;
    });
}
function repairAdd() {
    document.getElementById('mTitle').textContent = '新增维修单';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>设备ID<span style="color:red">*</span></label><input id="f_eqid" type="number"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>故障描述</label><textarea id="f_fault"></textarea></div></div>';
    modalSaveHandler = function() {
        var d = {equipment_id:document.getElementById('f_eqid').value, fault_desc:document.getElementById('f_fault').value};
        if(!d.equipment_id) { alert('请填写设备ID'); return; }
        api('/api/eqp/repair/add', {method:'POST', body:d}).then(function(r) {
            if(r && r.code === 0) { closeModal(); repairLoad(); } else alert(r ? r.message : '保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function repairDel(id) { if(!confirm('确定删除？')) return; api('/api/eqp/repair/delete', {method:'POST', body:{id:id}}).then(function(){repairLoad()}); }

// 用户管理
function renderUser(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>用户管理</span>'
        + '<div style="display:flex;gap:8px"><button class="btn btn-green" onclick="doExport2(\'sys_user\')">导出</button>'
        + '<button class="btn btn-blue" id="userAddBtn">+ 新增</button></div></div>'
        + '<table><thead><tr><th>ID</th><th>用户名</th><th>姓名</th><th>手机</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('userAddBtn').onclick = userAdd;
    userLoad();
}
function userLoad() {
    api('/api/sys/user/list').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>'; return; }
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + r2.username + '</td><td>' + (r2.real_name||'') + '</td>';
            h += '<td>' + (r2.phone||'') + '</td>';
            h += '<td><span class="tag ' + (r2.status ? 'tag-ok' : 'tag-draft') + '">' + (r2.status ? '正常' : '禁用') + '</span></td>';
            h += '<td class="actions"><button class="btn btn-blue btn-sm" onclick=\'userEdit(' + escapeJson(r2) + ')\'>编辑</button>';
            if(r2.id !== 1) h += '<button class="btn btn-red btn-sm" onclick="userDel(' + r2.id + ')">删除</button>';
            h += '</td></tr>';
        });
        tb.innerHTML = h;
    });
}
function userAdd() {
    document.getElementById('mTitle').textContent = '新增用户';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>用户名<span style="color:red">*</span></label><input id="f_uname" type="text"></div>'
        + '<div class="form-item"><label>密码<span style="color:red">*</span></label><input id="f_pwd" type="password" value="123456"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>姓名</label><input id="f_rname" type="text"></div>'
        + '<div class="form-item"><label>手机</label><input id="f_phone" type="text"></div></div>';
    modalSaveHandler = function() {
        var d = {username:document.getElementById('f_uname').value, password:document.getElementById('f_pwd').value,
            real_name:document.getElementById('f_rname').value, phone:document.getElementById('f_phone').value};
        if(!d.username || !d.password) { alert('请填写必填项'); return; }
        api('/api/sys/user/add', {method:'POST', body:d}).then(function(r) {
            if(r && r.code === 0) { closeModal(); userLoad(); } else alert(r ? r.message : '保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function userEdit(row) {
    document.getElementById('mTitle').textContent = '编辑用户';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>用户名</label><input type="text" value="' + row.username + '" disabled></div>'
        + '<div class="form-item"><label>新密码(留空不改)</label><input id="f_pwd" type="password"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>姓名</label><input id="f_rname" type="text" value="' + (row.real_name||'') + '"></div>'
        + '<div class="form-item"><label>手机</label><input id="f_phone" type="text" value="' + (row.phone||'') + '"></div></div>';
    modalSaveHandler = function() {
        var d = {id:row.id, real_name:document.getElementById('f_rname').value, phone:document.getElementById('f_phone').value};
        var pwd = document.getElementById('f_pwd').value;
        if(pwd) d.password = pwd;
        api('/api/sys/user/update', {method:'POST', body:d}).then(function(r) {
            if(r && r.code === 0) { closeModal(); userLoad(); } else alert(r ? r.message : '保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function userDel(id) { if(!confirm('确定删除？')) return; api('/api/sys/user/delete', {method:'POST', body:{id:id}}).then(function(){userLoad()}); }

// 系统日志
function renderLog(el) {
    el.innerHTML = '<div class="card"><div class="card-title">系统日志</div>'
        + '<table><thead><tr><th>ID</th><th>用户</th><th>操作</th><th>URL</th><th>IP</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    api('/api/sys/log/list').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无日志</td></tr>'; return; }
        var h = '';
        list.forEach(function(r2) {
            h += '<tr><td>' + r2.id + '</td><td>' + (r2.username||'') + '</td><td>' + (r2.operation||'') + '</td>';
            h += '<td>' + (r2.url||'') + '</td><td>' + (r2.ip||'') + '</td><td>' + (r2.created_at||'') + '</td></tr>';
        });
        tb.innerHTML = h;
    });
}
