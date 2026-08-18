/* 系统管理增强页面 */

// 登录日志
function renderLoginLog(el) {
    el.innerHTML = '<div class="card"><div class="card-title">登录日志</div>'
        + '<div id="loginStats" style="margin-bottom:16px"></div>'
        + '<div class="toolbar"><input id="kw" placeholder="搜索用户名..."><button class="btn btn-blue btn-sm" onclick="loginLogLoad(1)">搜索</button></div>'
        + '<table><thead><tr><th>ID</th><th>用户名</th><th>IP</th><th>状态</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="5" class="empty">加载中...</td></tr></tbody></table></div>';
    loginLogLoad(1);
    loginLogStats();
}
function loginLogLoad(page) {
    var kw = document.getElementById('kw') ? document.getElementById('kw').value : '';
    var url = '/api/sys/login-log/list?page='+page+'&size=20';
    if(kw) url += '&keyword='+encodeURIComponent(kw);
    api(url).then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="5" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(l) {
            return '<tr><td>'+MESUI.escapeHtml(l.id)+'</td><td>'+MESUI.escapeHtml(l.username)+'</td><td>'+MESUI.escapeHtml(l.login_ip||'-')+'</td>'
                +'<td><span class="tag '+(l.status?'tag-ok':'tag-no')+'">'+(l.status?'成功':'失败')+'</span></td>'
                +'<td>'+MESUI.escapeHtml(l.login_time||'')+'</td></tr>';
        }).join('');
    });
}
function loginLogStats() {
    api('/api/sys/login-log/statistics').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        document.getElementById('loginStats').innerHTML = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px">'
            +'<div class="stat"><div class="label">今日登录</div><div class="val">'+d.today+'</div></div>'
            +'<div class="stat"><div class="label">总登录数</div><div class="val">'+d.total+'</div></div>'
            +'<div class="stat"><div class="label">登录失败</div><div class="val" style="color:#f5222d">'+d.failed+'</div></div>'
            +'</div>';
    });
}

// 系统配置
function renderSysConfig(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>系统配置</span>'
        + '<button class="btn btn-blue" id="configAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>配置键</th><th>配置值</th><th>类型</th><th>说明</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('configAddBtn').onclick = configAdd;
    configLoad();
}
function configLoad() {
    api('/api/sys/config/list?size=100').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无配置</td></tr>'; return; }
        tb.innerHTML = list.map(function(c, index) {
            var value = c.value_configured
                ? '<span class="tag tag-ok">已配置</span>'
                : MESUI.escapeHtml((c.config_value||'').substring(0,50));
            return '<tr><td>'+MESUI.escapeHtml(c.id)+'</td><td><b>'+MESUI.escapeHtml(c.config_key)+'</b></td><td>'+value+'</td>'
                +'<td>'+MESUI.escapeHtml(c.config_type)+'</td><td>'+MESUI.escapeHtml(c.description||'-')+'</td>'
                +'<td class="actions"><button class="btn btn-blue btn-sm config-edit" data-config-index="'+index+'">编辑</button></td></tr>';
        }).join('');
        Array.prototype.forEach.call(
            tb.querySelectorAll('.config-edit'),
            function(button) {
                button.onclick = function() {
                    configEdit(list[Number(button.getAttribute('data-config-index'))]);
                };
            }
        );
    });
}
function configAdd() {
    document.getElementById('mTitle').textContent = '新增配置';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>配置键<span style="color:red">*</span></label><input id="f_key"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>配置值</label><input id="f_value"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>类型</label><select id="f_type"><option value="string">字符串</option><option value="number">数字</option><option value="boolean">布尔</option><option value="json">JSON</option></select></div>'
        + '<div class="form-item"><label>说明</label><input id="f_desc"></div></div>';
    modalSaveHandler = function() {
        var d = {config_key:document.getElementById('f_key').value, config_value:document.getElementById('f_value').value,
            config_type:document.getElementById('f_type').value, description:document.getElementById('f_desc').value};
        if(!d.config_key) { alert('请输入配置键'); return; }
        api('/api/sys/config/save',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); configLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function configEdit(row) {
    var configuredSecret = row.value_configured === true;
    document.getElementById('mTitle').textContent = '编辑配置';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>配置键</label><input value="'+MESUI.escapeHtml(row.config_key)+'" disabled></div></div>'
        + '<div class="form-row"><div class="form-item"><label>配置值</label><input id="f_value" value="'+(configuredSecret?'':MESUI.escapeHtml(row.config_value||''))+'"'
        +(configuredSecret?' placeholder="留空则保留现有值"':'')+'></div></div>'
        + '<div class="form-row"><div class="form-item"><label>说明</label><input id="f_desc" value="'+MESUI.escapeHtml(row.description||'')+'"></div></div>';
    modalSaveHandler = function() {
        var value = document.getElementById('f_value').value;
        var body = {config_key:row.config_key, description:document.getElementById('f_desc').value};
        if(!configuredSecret || String(value).trim()) body.config_value = value;
        api('/api/sys/config/save',{method:'POST',body:body}).then(function(r) {
            if(r&&r.code===0) { closeModal(); configLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}

// 系统公告
function renderAnnouncement(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>系统公告</span>'
        + '<button class="btn btn-blue" id="annAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>标题</th><th>类型</th><th>优先级</th><th>状态</th><th>发布时间</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('annAddBtn').onclick = annAdd;
    annLoad();
}
function annLoad() {
    api('/api/sys/announcement/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无公告</td></tr>'; return; }
        tb.innerHTML = list.map(function(a) {
            var id = Number(a.id);
            return '<tr><td>'+MESUI.escapeHtml(a.id)+'</td><td>'+MESUI.escapeHtml(a.title)+'</td><td>'+MESUI.escapeHtml(a.notice_type)+'</td>'
                +'<td>'+MESUI.escapeHtml(a.priority)+'</td>'
                +'<td><span class="tag '+(a.status?'tag-ok':'tag-draft')+'">'+(a.status?'发布':'草稿')+'</span></td>'
                +'<td>'+MESUI.escapeHtml(a.publish_time||'')+'</td>'
                +'<td><button class="btn btn-red btn-sm" onclick="annDel('+id+')">删除</button></td></tr>';
        }).join('');
    });
}
function annAdd() {
    document.getElementById('mTitle').textContent = '新增公告';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>标题<span style="color:red">*</span></label><input id="f_title"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>类型</label><select id="f_type"><option value="notice">通知</option><option value="announcement">公告</option><option value="warning">警告</option></select></div>'
        + '<div class="form-item"><label>优先级</label><select id="f_pri"><option value="0">普通</option><option value="1">重要</option><option value="2">紧急</option></select></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>内容</label><textarea id="f_content"></textarea></div></div>';
    modalSaveHandler = function() {
        var d = {title:document.getElementById('f_title').value, notice_type:document.getElementById('f_type').value,
            priority:document.getElementById('f_pri').value, content:document.getElementById('f_content').value, status:1};
        if(!d.title) { alert('请输入标题'); return; }
        api('/api/sys/announcement/add',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); annLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function annDel(id) { if(!confirm('确定删除？')) return; api('/api/sys/announcement/delete',{method:'POST',body:{id:id}}).then(function(){annLoad()}); }

// 在线用户
function renderOnlineUsers(el) {
    el.innerHTML = '<div class="card"><div class="card-title">在线用户</div>'
        + '<table><thead><tr><th>用户ID</th><th>用户名</th><th>IP</th><th>登录时间</th><th>最后活跃</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    onlineLoad();
}
function onlineLoad() {
    api('/api/sys/online/list').then(function(r) {
        if(!r) return;
        var list = r.data || [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无在线用户</td></tr>'; return; }
        tb.innerHTML = list.map(function(u) {
            var userId = Number(u.user_id);
            return '<tr><td>'+MESUI.escapeHtml(u.user_id)+'</td><td>'+MESUI.escapeHtml(u.username)+'</td><td>'+MESUI.escapeHtml(u.login_ip||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(u.login_time||'')+'</td><td>'+MESUI.escapeHtml(u.last_active||'')+'</td>'
                +'<td><button class="btn btn-red btn-sm" onclick="kickUser('+userId+')">移出在线列表</button></td></tr>';
        }).join('');
    });
}
function kickUser(userId) {
    if(!confirm('确定从在线列表移除？现有会话不会被强制失效。')) return;
    api('/api/sys/online/kick',{method:'POST',body:{user_id:userId}}).then(function(r) {
        if(r&&r.code===0) { onlineLoad(); } else alert(r?r.message:'操作失败');
    });
}

// 系统监控
function renderSysMonitor(el) {
    el.innerHTML = '<div class="card"><div class="card-title">系统监控</div>'
        + '<div id="monitorData" style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px"></div></div>';
    monitorLoad();
}
function monitorLoad() {
    api('/api/sys/monitor').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        var el = document.getElementById('monitorData');
        var cpuColor = d.cpu.percent > 80 ? '#f5222d' : (d.cpu.percent > 50 ? '#fa8c16' : '#52c41a');
        var memColor = d.memory.percent > 80 ? '#f5222d' : (d.memory.percent > 50 ? '#fa8c16' : '#52c41a');
        var diskColor = d.disk.percent > 80 ? '#f5222d' : (d.disk.percent > 50 ? '#fa8c16' : '#52c41a');
        el.innerHTML = '<div style="background:#f0f5ff;padding:20px;border-radius:8px">'
            +'<div style="font-weight:bold;margin-bottom:8px">CPU</div>'
            +'<div style="font-size:28px;color:'+cpuColor+'">'+d.cpu.percent+'%</div>'
            +'<div style="color:#666;font-size:13px">'+d.cpu.count+' 核心</div></div>'
            +'<div style="background:#f0f5ff;padding:20px;border-radius:8px">'
            +'<div style="font-weight:bold;margin-bottom:8px">内存</div>'
            +'<div style="font-size:28px;color:'+memColor+'">'+d.memory.percent+'%</div>'
            +'<div style="color:#666;font-size:13px">'+(d.memory.used/1024/1024/1024).toFixed(1)+'GB / '+(d.memory.total/1024/1024/1024).toFixed(1)+'GB</div></div>'
            +'<div style="background:#f0f5ff;padding:20px;border-radius:8px">'
            +'<div style="font-weight:bold;margin-bottom:8px">磁盘</div>'
            +'<div style="font-size:28px;color:'+diskColor+'">'+d.disk.percent+'%</div>'
            +'<div style="color:#666;font-size:13px">'+(d.disk.used/1024/1024/1024).toFixed(1)+'GB / '+(d.disk.total/1024/1024/1024).toFixed(1)+'GB</div></div>'
            +'<div style="background:#f0f5ff;padding:20px;border-radius:8px">'
            +'<div style="font-weight:bold;margin-bottom:8px">数据库</div>'
            +'<div style="font-size:28px;color:#1890ff">'+(d.database_size/1024/1024).toFixed(2)+'MB</div>'
            +'<div style="color:#666;font-size:13px">SQLite</div></div>';
    });
}

// IP白名单
function renderIPWhitelist(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>IP白名单</span>'
        + '<button class="btn btn-blue" id="ipAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>IP地址</th><th>说明</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="5" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('ipAddBtn').onclick = ipAdd;
    ipLoad();
}
function ipLoad() {
    api('/api/sys/ip-whitelist/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="5" class="empty">暂无IP白名单</td></tr>'; return; }
        tb.innerHTML = list.map(function(ip) {
            var id = Number(ip.id);
            return '<tr><td>'+MESUI.escapeHtml(ip.id)+'</td><td><b>'+MESUI.escapeHtml(ip.ip_address)+'</b></td><td>'+MESUI.escapeHtml(ip.description||'-')+'</td>'
                +'<td><span class="tag '+(ip.status?'tag-ok':'tag-draft')+'">'+(ip.status?'启用':'禁用')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="ipDel('+id+')">删除</button></td></tr>';
        }).join('');
    });
}
function ipAdd() {
    document.getElementById('mTitle').textContent = '新增IP白名单';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>IP地址<span style="color:red">*</span></label><input id="f_ip" placeholder="如: 192.168.1.100"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>说明</label><input id="f_desc"></div></div>';
    modalSaveHandler = function() {
        var d = {ip_address:document.getElementById('f_ip').value, description:document.getElementById('f_desc').value};
        if(!d.ip_address) { alert('请输入IP地址'); return; }
        api('/api/sys/ip-whitelist/add',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); ipLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function ipDel(id) { if(!confirm('确定删除？')) return; api('/api/sys/ip-whitelist/delete',{method:'POST',body:{id:id}}).then(function(){ipLoad()}); }

// 打印模板
function renderPrintTemplate(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>打印模板</span>'
        + '<button class="btn btn-blue" id="ptAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>模板名称</th><th>业务类型</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="5" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('ptAddBtn').onclick = ptAdd;
    ptLoad();
}
function ptLoad() {
    api('/api/sys/print-template/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="5" class="empty">暂无模板</td></tr>'; return; }
        tb.innerHTML = list.map(function(t) {
            var id = Number(t.id);
            return '<tr><td>'+MESUI.escapeHtml(t.id)+'</td><td>'+MESUI.escapeHtml(t.template_name)+'</td><td>'+MESUI.escapeHtml(t.biz_type)+'</td>'
                +'<td><span class="tag '+(t.status?'tag-ok':'tag-draft')+'">'+(t.status?'启用':'禁用')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="ptDel('+id+')">删除</button></td></tr>';
        }).join('');
    });
}
function ptAdd() {
    document.getElementById('mTitle').textContent = '新增打印模板';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>模板名称<span style="color:red">*</span></label><input id="f_name"></div>'
        + '<div class="form-item"><label>业务类型</label><select id="f_type"><option value="workorder">工单</option><option value="sales">销售订单</option><option value="inbound">入库单</option><option value="outbound">出库单</option></select></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>模板内容(HTML)</label><textarea id="f_content" rows="6"></textarea></div></div>';
    modalSaveHandler = function() {
        var d = {template_name:document.getElementById('f_name').value, biz_type:document.getElementById('f_type').value, template_content:document.getElementById('f_content').value};
        if(!d.template_name) { alert('请输入模板名称'); return; }
        api('/api/sys/print-template/add',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); ptLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function ptDel(id) { if(!confirm('确定删除？')) return; api('/api/sys/print-template/delete',{method:'POST',body:{id:id}}).then(function(){ptLoad()}); }

// 通知渠道
function renderNotifyChannel(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>通知渠道</span>'
        + '<button class="btn btn-blue" id="ncAddBtn">+ 新增</button></div></div>'
        + '<div class="card"><table><thead><tr><th>ID</th><th>渠道名称</th><th>类型</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="5" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('ncAddBtn').onclick = ncAdd;
    ncLoad();
}
function ncLoad() {
    api('/api/sys/notify-channel/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="5" class="empty">暂无渠道</td></tr>'; return; }
        var types = {email:'邮件',dingtalk:'钉钉',wechat:'企业微信',sms:'短信'};
        tb.innerHTML = list.map(function(n) {
            var id = Number(n.id);
            return '<tr><td>'+MESUI.escapeHtml(n.id)+'</td><td>'+MESUI.escapeHtml(n.channel_name)+'</td><td>'+MESUI.escapeHtml(types[n.channel_type]||n.channel_type)+'</td>'
                +'<td><span class="tag '+(n.enabled?'tag-ok':'tag-draft')+'">'+(n.enabled?'启用':'禁用')+'</span></td>'
                +'<td><button class="btn btn-blue btn-sm" onclick="ncTest('+id+')">测试</button> '
                +'<button class="btn btn-red btn-sm" onclick="ncDel('+id+')">删除</button></td></tr>';
        }).join('');
    });
}
function ncAdd() {
    document.getElementById('mTitle').textContent = '新增通知渠道';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>渠道名称<span style="color:red">*</span></label><input id="f_name"></div>'
        + '<div class="form-item"><label>类型</label><select id="f_type"><option value="email">邮件</option><option value="dingtalk">钉钉</option><option value="wechat">企业微信</option><option value="sms">短信</option></select></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>配置(JSON)</label><textarea id="f_config" placeholder=\'{"smtp_host":"smtp.example.com","smtp_port":465}\'></textarea></div></div>';
    modalSaveHandler = function() {
        var d = {channel_name:document.getElementById('f_name').value, channel_type:document.getElementById('f_type').value, config:document.getElementById('f_config').value};
        if(!d.channel_name) { alert('请输入渠道名称'); return; }
        api('/api/sys/notify-channel/add',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); ncLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function ncTest(id) { api('/api/sys/notify-channel/test',{method:'POST',body:{id:id}}).then(function(r){alert(r.message||'测试完成')}); }
function ncDel(id) { if(!confirm('确定删除？')) return; api('/api/sys/notify-channel/delete',{method:'POST',body:{id:id}}).then(function(){ncLoad()}); }

// 用户密码重置
function userResetPwd(id) {
    if(!confirm('确定重置密码为123456？')) return;
    api('/api/sys/user/reset-password',{method:'POST',body:{user_id:id,new_password:'123456'}}).then(function(r) {
        if(r&&r.code===0) alert('密码已重置为: 123456');
        else alert(r?r.message:'重置失败');
    });
}

// 修改密码
function changePassword() {
    document.getElementById('mTitle').textContent = '修改密码';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>旧密码<span style="color:red">*</span></label><input id="f_old" type="password"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>新密码<span style="color:red">*</span></label><input id="f_new" type="password"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>确认密码<span style="color:red">*</span></label><input id="f_confirm" type="password"></div></div>';
    modalSaveHandler = function() {
        var old = document.getElementById('f_old').value;
        var newPwd = document.getElementById('f_new').value;
        var confirm = document.getElementById('f_confirm').value;
        if(!old||!newPwd) { alert('请输入密码'); return; }
        if(newPwd !== confirm) { alert('两次密码不一致'); return; }
        if(newPwd.length < 6) { alert('密码至少6位'); return; }
        api('/api/sys/user/change-password',{method:'POST',body:{old_password:old,new_password:newPwd}}).then(function(r) {
            if(r&&r.code===0) { closeModal(); alert('密码修改成功'); } else alert(r?r.message:'修改失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}

// 角色动作权限（查看/维护/审核等）
function renderRolePermissions(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>角色动作权限</span>'
        + '<button class="btn btn-gray" id="backRoleList">返回角色列表</button>'
        + '<span class="muted">仅管理员可配置，旧菜单权限仍可兼容读取</span></div>'
        + '<div class="form-row"><div class="form-item"><label>选择角色</label><select id="rolePermissionRole"></select></div></div>'
        + '<div id="rolePermissionBody" class="empty">请选择角色</div></div>';
    document.getElementById('backRoleList').onclick = function() { renderPage('sys/role'); };
    Promise.all([api('/api/sys/role/list?size=1000'), api('/api/sys/permissions/catalog')]).then(function(values) {
        var roles = values[0] && values[0].data ? (values[0].data.list || values[0].data) : [];
        var catalog = values[1] && values[1].data ? values[1].data : [];
        var select = document.getElementById('rolePermissionRole');
        select.innerHTML = '<option value="">请选择角色</option>' + roles.map(function(role) {
            return '<option value="' + MESUI.escapeHtml(role.id) + '">' + MESUI.escapeHtml(role.role_name) + '</option>';
        }).join('');
        select.onchange = function() {
            if(!this.value) return;
            api('/api/sys/role/permissions/' + encodeURIComponent(this.value)).then(function(response) {
                var current = response && response.data && response.data.permissions || [];
                var body = document.getElementById('rolePermissionBody');
                body.className = '';
                body.innerHTML = '<div class="permission-grid">' + catalog.map(function(item) {
                    var checked = current.indexOf(item.key) >= 0 ? ' checked' : '';
                    return '<label class="permission-item"><input type="checkbox" value="'
                        + MESUI.escapeHtml(item.key) + '"' + checked + '>'
                        + MESUI.escapeHtml(item.label) + '<code>' + MESUI.escapeHtml(item.key) + '</code></label>';
                }).join('') + '</div><button class="btn btn-blue" id="saveRolePermissions">保存权限</button>';
                document.getElementById('saveRolePermissions').onclick = function() {
                    var permissions = Array.prototype.slice.call(body.querySelectorAll('input:checked')).map(function(input) { return input.value; });
                    api('/api/sys/role/permissions', {method:'POST', body:{role_id:Number(select.value), permissions:permissions}}).then(function(result) {
                        if(result && result.code === 0) alert('权限保存成功');
                        else alert(result ? result.message : '权限保存失败');
                    });
                };
            });
        };
    });
}
