/* 制程管控页面 - 过站/跳站/出站/重工/关箱/拆箱/锁料/解料/返线/不良品/料号/异常 */

// 站点配置
function renderStationConfig(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>站点配置</span><button class="btn btn-blue" id="scAddBtn">+ 新增站点</button></div>'
        + '<p style="color:#666;font-size:13px;margin-bottom:12px">配置每个站点的过站规则：允许重复过站、最大过站次数</p>'
        + '<table><thead><tr><th>ID</th><th>站点编码</th><th>站点名称</th><th>允许重复过站</th><th>最大过站次数</th><th>描述</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('scAddBtn').onclick = scAdd;
    scLoad();
}
function scLoad() {
    api('/api/process/station-config/list?size=100').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无站点配置，请添加</td></tr>'; return; }
        tb.innerHTML = list.map(function(s) {
            var repeatTag = s.allow_repeat ? '<span class="tag tag-ok">允许</span>' : '<span class="tag tag-no">禁止</span>';
            var maxTag = s.max_pass_count > 0 ? s.max_pass_count + '次' : '不限';
            return '<tr><td>'+s.id+'</td><td><code>'+MESUI.escapeHtml(s.station)+'</code></td><td>'+MESUI.escapeHtml(s.station_name)+'</td>'
                +'<td>'+repeatTag+'</td><td>'+maxTag+'</td><td>'+MESUI.escapeHtml(s.description||'-')+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(s.status?'tag-ok':'tag-draft')+'">'+MESUI.escapeHtml(s.status?'启用':'停用')+'</span></td>'
                +'<td class="actions"><button class="btn btn-blue btn-sm" onclick=\'scEdit('+escapeJson(s)+')\'>编辑</button>'
                +'<button class="btn btn-red btn-sm" onclick="scDel('+s.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function scAdd() {
    document.getElementById('mTitle').textContent = '新增站点配置';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>站点编码<span style="color:red">*</span></label><input id="f_station" placeholder="如: SMT01"></div>'
        + '<div class="form-item"><label>站点名称</label><input id="f_name" placeholder="如: SMT贴片区"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>允许重复过站</label><select id="f_repeat"><option value="1">允许</option><option value="0">禁止</option></select></div>'
        + '<div class="form-item"><label>最大过站次数</label><input id="f_max" type="number" value="0" placeholder="0=不限"></div></div>'
        + '<div style="background:#f0f5ff;padding:12px;border-radius:6px;margin-bottom:12px"><b>防呆设置</b></div>'
        + '<div class="form-row"><div class="form-item"><label>必须扫描SN</label><select id="f_sn"><option value="0">否</option><option value="1">是</option></select></div>'
        + '<div class="form-item"><label>必须扫描物料</label><select id="f_mat"><option value="0">否</option><option value="1">是</option></select></div></div>'
        + '<div class="form-row"><div class="form-item"><label>校验站点顺序</label><select id="f_seq"><option value="0">否</option><option value="1">是</option></select></div>'
        + '<div class="form-item"><label>前置站点</label><input id="f_prev" placeholder="如: SMT01"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>要求工序</label><input id="f_proc" placeholder="留空不限"></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>描述</label><textarea id="f_desc"></textarea></div></div>';
    modalSaveHandler = function() {
        var d = {station:document.getElementById('f_station').value, station_name:document.getElementById('f_name').value,
            allow_repeat:parseInt(document.getElementById('f_repeat').value), max_pass_count:parseInt(document.getElementById('f_max').value),
            required_sn:parseInt(document.getElementById('f_sn').value), required_material:parseInt(document.getElementById('f_mat').value),
            check_sequence:parseInt(document.getElementById('f_seq').value), prev_station:document.getElementById('f_prev').value,
            required_process:document.getElementById('f_proc').value, description:document.getElementById('f_desc').value};
        if(!d.station) { alert('请输入站点编码'); return; }
        api('/api/process/station-config/add',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); scLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function scEdit(row) {
    document.getElementById('mTitle').textContent = '编辑站点配置';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>站点编码</label><input value="'+MESUI.escapeHtml(row.station)+'" disabled></div>'
        + '<div class="form-item"><label>站点名称</label><input id="f_name" value="'+MESUI.escapeHtml(row.station_name)+'"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>允许重复过站</label><select id="f_repeat"><option value="1"'+(row.allow_repeat?' selected':'')+'>允许</option><option value="0"'+(!row.allow_repeat?' selected':'')+'>禁止</option></select></div>'
        + '<div class="form-item"><label>最大过站次数</label><input id="f_max" type="number" value="'+row.max_pass_count+'" placeholder="0=不限"></div></div>'
        + '<div style="background:#f0f5ff;padding:12px;border-radius:6px;margin-bottom:12px"><b>防呆设置</b></div>'
        + '<div class="form-row"><div class="form-item"><label>必须扫描SN</label><select id="f_sn"><option value="0"'+(!row.required_sn?' selected':'')+'>否</option><option value="1"'+(row.required_sn?' selected':'')+'>是</option></select></div>'
        + '<div class="form-item"><label>必须扫描物料</label><select id="f_mat"><option value="0"'+(!row.required_material?' selected':'')+'>否</option><option value="1"'+(row.required_material?' selected':'')+'>是</option></select></div></div>'
        + '<div class="form-row"><div class="form-item"><label>校验站点顺序</label><select id="f_seq"><option value="0"'+(!row.check_sequence?' selected':'')+'>否</option><option value="1"'+(row.check_sequence?' selected':'')+'>是</option></select></div>'
        + '<div class="form-item"><label>前置站点</label><input id="f_prev" value="'+(row.prev_station||'')+'" placeholder="如: SMT01"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>要求工序</label><input id="f_proc" value="'+(row.required_process||'')+'" placeholder="留空不限"></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>描述</label><textarea id="f_desc">'+MESUI.escapeHtml(row.description||'')+'</textarea></div></div>';
    modalSaveHandler = function() {
        var d = {id:row.id, station_name:document.getElementById('f_name').value,
            allow_repeat:parseInt(document.getElementById('f_repeat').value), max_pass_count:parseInt(document.getElementById('f_max').value),
            required_sn:parseInt(document.getElementById('f_sn').value), required_material:parseInt(document.getElementById('f_mat').value),
            check_sequence:parseInt(document.getElementById('f_seq').value), prev_station:document.getElementById('f_prev').value,
            required_process:document.getElementById('f_proc').value, description:document.getElementById('f_desc').value};
        api('/api/process/station-config/update',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); scLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function scDel(id) { if(!confirm('确定删除？')) return; api('/api/process/station-config/delete',{method:'POST',body:{id:id}}).then(function(){scLoad()}); }

// 过站记录
function renderProcessFlow(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>过站记录</span>'
        + '<button class="btn btn-blue" onclick="showPassDialog()">过站</button> '
        + '<button class="btn btn-orange" onclick="showReworkDialog()">重工</button> '
        + '<button class="btn btn-green" onclick="showReturnDialog()">返线</button></div>'
        + '<div class="toolbar"><input id="kw" placeholder="搜索SN/单号..."><button class="btn btn-blue btn-sm" onclick="flowLoad(1)">搜索</button></div>'
        + '<table><thead><tr><th>ID</th><th>流转单号</th><th>SN</th><th>当前站点</th><th>当前工序</th><th>状态</th><th>更新时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    flowLoad(1);
}
function flowLoad(page) {
    var kw = document.getElementById('kw') ? document.getElementById('kw').value : '';
    var url = '/api/process/flow/list?page='+page+'&size=20';
    if(kw) url += '&keyword='+encodeURIComponent(kw);
    api(url).then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(f) {
            return '<tr><td>'+f.id+'</td><td>'+MESUI.escapeHtml(f.flow_no)+'</td><td><b>'+MESUI.escapeHtml(f.sn)+'</b></td>'
                +'<td>'+f.current_station+'</td><td>'+(f.current_process||'-')+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(f.status?'tag-ok':'tag-run')+'">'+MESUI.escapeHtml(f.status?'完成':'流转中')+'</span></td>'
                +'<td>'+(f.updated_at||'')+'</td></tr>';
        }).join('');
    });
}

function showPassDialog() {
    document.getElementById('mTitle').textContent = '过站';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>SN条码<span style="color:red">*</span></label><input id="f_sn" placeholder="扫描或输入SN" autofocus></div></div>'
        + '<div class="form-row"><div class="form-item"><label>站点<span style="color:red">*</span></label><input id="f_station" placeholder="如: SMT01"></div>'
        + '<div class="form-item"><label>工序</label><input id="f_process" placeholder="如: 贴片"></div></div>';
    modalSaveHandler = function() {
        var d = {sn:document.getElementById('f_sn').value, station:document.getElementById('f_station').value, process_name:document.getElementById('f_process').value};
        if(!d.sn||!d.station) { alert('请填写必填项'); return; }
        api('/api/process/pass-station',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); showToast(r.message); flowLoad(1); } else alert(r?r.message:'操作失败');
        });
    };
    document.getElementById('modal').classList.add('show');
    setTimeout(function(){document.getElementById('f_sn').focus()},300);
}

function showReworkDialog() {
    document.getElementById('mTitle').textContent = '重工';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>SN<span style="color:red">*</span></label><input id="f_sn" autofocus></div></div>'
        + '<div class="form-row"><div class="form-item"><label>目标站点<span style="color:red">*</span></label><input id="f_station"></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>原因</label><textarea id="f_reason"></textarea></div></div>';
    modalSaveHandler = function() {
        var d = {sn:document.getElementById('f_sn').value, target_station:document.getElementById('f_station').value, reason:document.getElementById('f_reason').value};
        if(!d.sn||!d.target_station) { alert('请填写必填项'); return; }
        api('/api/process/rework',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); showToast(r.message); flowLoad(1); } else alert(r?r.message:'操作失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}

function showReturnDialog() {
    document.getElementById('mTitle').textContent = '返线';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>SN<span style="color:red">*</span></label><input id="f_sn" autofocus></div></div>'
        + '<div class="form-row"><div class="form-item"><label>返回站点<span style="color:red">*</span></label><input id="f_station"></div></div>';
    modalSaveHandler = function() {
        var d = {sn:document.getElementById('f_sn').value, station:document.getElementById('f_station').value};
        if(!d.sn||!d.station) { alert('请填写必填项'); return; }
        api('/api/process/return-to-line',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); showToast(r.message); flowLoad(1); } else alert(r?r.message:'操作失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}

// 操作记录
function renderProcessRecord(el) {
    el.innerHTML = '<div class="card"><div class="card-title">操作记录</div>'
        + '<div class="toolbar"><input id="kw" placeholder="搜索SN/站点..."><button class="btn btn-blue btn-sm" onclick="recordLoad(1)">搜索</button>'
        + '<button class="btn btn-orange btn-sm" onclick="showSNTimeline()">SN轨迹</button></div>'
        + '<table><thead><tr><th>ID</th><th>SN</th><th>站点</th><th>工序</th><th>操作</th><th>结果</th><th>操作人</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    recordLoad(1);
}
function recordLoad(page) {
    var kw = document.getElementById('kw') ? document.getElementById('kw').value : '';
    var url = '/api/process/record/list?page='+page+'&size=20';
    if(kw) url += '&keyword='+encodeURIComponent(kw);
    api(url).then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        var actionColors = {'过站':'#52c41a','跳站':'#fa8c16','出站':'#1890ff','重工':'#f5222d','返线':'#722ed1','关箱':'#13c2c2','拆箱':'#eb2f96'};
        tb.innerHTML = list.map(function(r) {
            var color = actionColors[r.action]||'#333';
            return '<tr><td>'+r.id+'</td><td><b>'+MESUI.escapeHtml(r.sn)+'</b></td><td>'+MESUI.escapeHtml(r.station)+'</td><td>'+MESUI.escapeHtml(r.process_name||'-')+'</td>'
                +'<td><span style="color:'+color+';font-weight:bold">'+MESUI.escapeHtml(r.action)+'</span></td>'
                +'<td>'+(r.result||'-')+'</td><td>'+MESUI.escapeHtml(r.real_name||'-')+'</td><td>'+(r.created_at||'')+'</td></tr>';
        }).join('');
    });
}

// SN轨迹 - 甘特图
function showSNTimeline() {
    document.getElementById('mTitle').textContent = 'SN过站轨迹';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>输入SN<span style="color:red">*</span></label><input id="f_sn" placeholder="输入SN查询完整轨迹" autofocus></div></div>'
        + '<div id="timelineResult"></div>';
    modalSaveHandler = function() { loadSNTimeline(); };
    document.getElementById('modal').classList.add('show');
    setTimeout(function(){document.getElementById('f_sn').focus()},300);
}

function loadSNTimeline() {
    var sn = document.getElementById('f_sn').value.trim();
    if(!sn) { alert('请输入SN'); return; }
    
    api('/api/process/record/sn/'+encodeURIComponent(sn)).then(function(r) {
        if(!r||r.code!==0) { alert('查询失败'); return; }
        var records = r.data||[];
        var el = document.getElementById('timelineResult');
        
        if(!records.length) {
            el.innerHTML = '<div style="text-align:center;padding:20px;color:#999">未找到SN: '+MESUI.escapeHtml(sn)+' 的过站记录</div>';
            return;
        }
        
        // 时间线展示
        var h = '<div style="margin-top:16px">';
        h += '<h3 style="margin-bottom:16px">SN: <span style="color:#1890ff">'+sn+'</span> 的过站轨迹</h3>';
        
        // 甘特图数据
        var stations = [];
        var minTime = null;
        var maxTime = null;
        
        records.forEach(function(rec, i) {
            var startTime = new Date(rec.created_at);
            var endTime = records[i+1] ? new Date(records[i+1].created_at) : new Date();
            
            if(!minTime || startTime < minTime) minTime = startTime;
            if(!maxTime || endTime > maxTime) maxTime = endTime;
            
            stations.push({
                station: rec.station,
                action: rec.action,
                start: startTime,
                end: endTime,
                duration: Math.round((endTime - startTime) / 1000),
                operator: rec.real_name||'-',
                result: rec.result||'-'
            });
        });
        
        // 绘制甘特图
        var totalDuration = maxTime - minTime;
        var chartHeight = Math.max(200, stations.length * 50 + 80);
        
        h += '<div style="position:relative;height:'+chartHeight+'px;background:#f9f9f9;border-radius:8px;padding:20px;margin-bottom:16px">';
        
        // 时间轴
        h += '<div style="display:flex;justify-content:space-between;margin-bottom:10px;font-size:11px;color:#999">';
        h += '<span>'+formatTime(minTime)+'</span>';
        h += '<span>'+formatTime(maxTime)+'</span>';
        h += '</div>';
        
        // 每个站点的甘特条
        var colors = {'过站':'#52c41a','跳站':'#fa8c16','出站':'#1890ff','重工':'#f5222d','返线':'#722ed1','关箱':'#13c2c2','拆箱':'#eb2f96'};
        
        stations.forEach(function(s, i) {
            var left = totalDuration > 0 ? ((s.start - minTime) / totalDuration * 100) : 0;
            var width = totalDuration > 0 ? Math.max(2, ((s.end - s.start) / totalDuration * 100)) : 100;
            var color = colors[s.action]||'#1890ff';
            
            h += '<div style="display:flex;align-items:center;margin-bottom:8px">';
            h += '<div style="width:80px;font-size:12px;font-weight:bold;color:'+color+'">'+MESUI.escapeHtml(s.station)+'</div>';
            h += '<div style="flex:1;position:relative;height:30px">';
            h += '<div style="position:absolute;left:'+left+'%;width:'+width+'%;height:100%;background:'+color+';border-radius:4px;opacity:0.8;display:flex;align-items:center;justify-content:center">';
            h += '<span style="color:white;font-size:11px;font-weight:bold">'+MESUI.escapeHtml(s.action)+'</span>';
            h += '</div>';
            h += '</div>';
            h += '<div style="width:80px;text-align:right;font-size:11px;color:#666">'+formatDuration(s.duration)+'</div>';
            h += '</div>';
        });
        
        h += '</div>';
        
        // 详细记录表格
        h += '<table style="font-size:13px"><thead><tr><th>站点</th><th>操作</th><th>时间</th><th>时长</th><th>操作人</th><th>结果</th></tr></thead><tbody>';
        stations.forEach(function(s) {
            h += '<tr><td><b>'+MESUI.escapeHtml(s.station)+'</b></td><td><span style="color:'+(colors[s.action]||'#333')+'">'+MESUI.escapeHtml(s.action)+'</span></td>';
            h += '<td>'+formatTime(s.start)+'</td><td>'+formatDuration(s.duration)+'</td>';
            h += '<td>'+s.operator+'</td><td>'+s.result+'</td></tr>';
        });
        h += '</tbody></table>';
        
        h += '</div>';
        el.innerHTML = h;
    });
}

function formatTime(date) {
    if(!(date instanceof Date)) date = new Date(date);
    return date.toLocaleString('zh-CN', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

function formatDuration(seconds) {
    if(seconds < 60) return seconds+'秒';
    if(seconds < 3600) return Math.round(seconds/60)+'分钟';
    return (seconds/3600).toFixed(1)+'小时';
}

// 箱号管理
function renderBoxManage(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>箱号管理</span>'
        + '<button class="btn btn-blue" onclick="showCloseBox()">关箱</button> '
        + '<button class="btn btn-orange" onclick="showOpenBox()">拆箱</button></div>'
        + '<table><thead><tr><th>ID</th><th>箱号</th><th>类型</th><th>产品数</th><th>状态</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    boxLoad();
}
function boxLoad() {
    api('/api/process/box/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(b) {
            var st = {0:'<span class="tag tag-draft">空箱</span>',1:'<span class="tag tag-ok">已关箱</span>',2:'<span class="tag tag-wait">已拆箱</span>'};
            return '<tr><td>'+b.id+'</td><td><b>'+MESUI.escapeHtml(b.box_no)+'</b></td><td>'+MESUI.escapeHtml(b.box_type)+'</td><td>'+MESUI.escapeHtml(b.quantity)+'</td>'
                +'<td>'+MESUI.escapeHtml(st[b.status]||'-')+'</td><td>'+(b.created_at||'')+'</td></tr>';
        }).join('');
    });
}
function showCloseBox() {
    document.getElementById('mTitle').textContent = '关箱';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>SN列表(每行一个)<span style="color:red">*</span></label><textarea id="f_sns" rows="6" placeholder="SN001\nSN002\nSN003"></textarea></div></div>';
    modalSaveHandler = function() {
        var sns = document.getElementById('f_sns').value.split('\n').filter(function(s){return s.trim()});
        if(!sns.length) { alert('请输入SN'); return; }
        api('/api/process/close-box',{method:'POST',body:{sn_list:sns}}).then(function(r) {
            if(r&&r.code===0) { closeModal(); showToast(r.message); boxLoad(); } else alert(r?r.message:'操作失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function showOpenBox() {
    document.getElementById('mTitle').textContent = '拆箱';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>箱号<span style="color:red">*</span></label><input id="f_box" autofocus></div></div>';
    modalSaveHandler = function() {
        var box_no = document.getElementById('f_box').value;
        if(!box_no) { alert('请输入箱号'); return; }
        api('/api/process/open-box',{method:'POST',body:{box_no:box_no}}).then(function(r) {
            if(r&&r.code===0) { closeModal(); showToast(r.message); boxLoad(); } else alert(r?r.message:'操作失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}

// 锁料管理
function renderLockManage(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>锁料管理</span>'
        + '<button class="btn btn-blue" onclick="showLockDialog()">锁料</button></div>'
        + '<table><thead><tr><th>ID</th><th>锁料单号</th><th>物料</th><th>类型</th><th>原因</th><th>状态</th><th>操作人</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    lockLoad();
}
function lockLoad() {
    api('/api/process/lock/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(l) {
            return '<tr><td>'+l.id+'</td><td>'+MESUI.escapeHtml(l.lock_no)+'</td><td>'+(l.material_name||l.material_id)+'</td>'
                +'<td>'+l.lock_type+'</td><td>'+(l.reason||'-')+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(l.status?'tag-no':'tag-ok')+'">'+MESUI.escapeHtml(l.status?'已锁':'已解')+'</span></td>'
                +'<td>'+MESUI.escapeHtml(l.real_name||'-')+'</td>'
                +'<td>'+(l.status?'<button class="btn btn-green btn-sm" onclick="unlockMaterial('+l.id+')">解料</button>':'已解')+'</td></tr>';
        }).join('');
    });
}
function showLockDialog() {
    api('/api/process/material/list?size=500').then(function(r) {
        var opts = '<option value="">选择物料</option>';
        (r?.data?.list||[]).forEach(function(m) { opts += '<option value="'+m.id+'">'+MESUI.escapeHtml(m.material_name)+' ('+MESUI.escapeHtml(m.material_no)+')</option>'; });
        document.getElementById('mTitle').textContent = '锁料';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>物料<span style="color:red">*</span></label><select id="f_mat">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item" style="flex:1"><label>原因</label><textarea id="f_reason"></textarea></div></div>';
        modalSaveHandler = function() {
            var d = {material_id:document.getElementById('f_mat').value, reason:document.getElementById('f_reason').value};
            if(!d.material_id) { alert('请选择物料'); return; }
            api('/api/process/lock-material',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); showToast(r2.message); lockLoad(); } else alert(r2?r2.message:'操作失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function unlockMaterial(id) { if(!confirm('确定解料？')) return; api('/api/process/unlock-material',{method:'POST',body:{id:id}}).then(function(r){if(r.code===0){showToast(r.message);lockLoad()}else alert(r.message)}); }

// 不良品接收
function renderDefectReceive(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>不良品接收</span>'
        + '<button class="btn btn-blue" onclick="showDefectDialog()">接收</button></div>'
        + '<table><thead><tr><th>ID</th><th>接收单号</th><th>SN</th><th>产品</th><th>缺陷</th><th>站点</th><th>数量</th><th>处理</th><th>状态</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="9" class="empty">加载中...</td></tr></tbody></table></div>';
    defectLoad();
}
function defectLoad() {
    api('/api/process/defect/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(d) {
            return '<tr><td>'+d.id+'</td><td>'+MESUI.escapeHtml(d.receive_no)+'</td><td>'+MESUI.escapeHtml(d.sn||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(d.product_name||'-')+'</td><td>'+MESUI.escapeHtml(d.defect_name||'-')+'</td><td>'+MESUI.escapeHtml(d.station||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(d.quantity)+'</td><td>'+d.process_type+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(d.status?'tag-ok':'tag-wait')+'">'+MESUI.escapeHtml(d.status?'已处理':'待处理')+'</span></td></tr>';
        }).join('');
    });
}
function showDefectDialog() {
    Promise.all([api('/api/base/product/all'), api('/api/base/defect/list?size=100')]).then(function(r) {
        var prodOpts = '<option value="">选择产品</option>';
        (r[0]?.data||[]).forEach(function(p) { prodOpts += '<option value="'+p.id+'">'+MESUI.escapeHtml(p.product_name)+'</option>'; });
        var defOpts = '<option value="">选择缺陷</option>';
        (r[1]?.data?.list||[]).forEach(function(d) { defOpts += '<option value="'+d.id+'">'+MESUI.escapeHtml(d.defect_name)+'</option>'; });
        document.getElementById('mTitle').textContent = '不良品接收';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>SN</label><input id="f_sn" autofocus></div></div>'
            + '<div class="form-row"><div class="form-item"><label>产品</label><select id="f_prod">'+prodOpts+'</select></div>'
            + '<div class="form-item"><label>缺陷</label><select id="f_def">'+defOpts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>站点</label><input id="f_station"></div>'
            + '<div class="form-item"><label>数量</label><input id="f_qty" type="number" value="1"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>处理方式</label><select id="f_type"><option value="待处理">待处理</option><option value="返工">返工</option><option value="报废">报废</option></select></div></div>';
        modalSaveHandler = function() {
            var d = {sn:document.getElementById('f_sn').value, product_id:document.getElementById('f_prod').value||null,
                defect_id:document.getElementById('f_def').value||null, station:document.getElementById('f_station').value,
                quantity:document.getElementById('f_qty').value, process_type:document.getElementById('f_type').value};
            api('/api/process/defect-receive',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); showToast(r2.message); defectLoad(); } else alert(r2?r2.message:'操作失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 料号维护
function renderMaterialManage(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>料号维护</span>'
        + '<button class="btn btn-blue" onclick="materialAdd()">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>物料名称</th><th>料号</th><th>规格</th><th>单位</th><th>分类</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    materialLoad();
}
function materialLoad() {
    api('/api/process/material/list?size=100').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无物料</td></tr>'; return; }
        tb.innerHTML = list.map(function(m) {
            return '<tr><td>'+m.id+'</td><td>'+MESUI.escapeHtml(m.material_name)+'</td><td><code>'+MESUI.escapeHtml(m.material_no)+'</code></td>'
                +'<td>'+MESUI.escapeHtml(m.specification||'-')+'</td><td>'+MESUI.escapeHtml(m.unit||'-')+'</td><td>'+MESUI.escapeHtml(m.category||'-')+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(m.status?'tag-ok':'tag-draft')+'">'+MESUI.escapeHtml(m.status?'启用':'停用')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="materialDel('+m.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function materialAdd() {
    document.getElementById('mTitle').textContent = '新增物料';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>物料名称<span style="color:red">*</span></label><input id="f_name"></div>'
        + '<div class="form-item"><label>料号<span style="color:red">*</span></label><input id="f_no"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>规格</label><input id="f_spec"></div>'
        + '<div class="form-item"><label>单位</label><input id="f_unit"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>分类</label><select id="f_cat"><option value="原材料">原材料</option><option value="半成品">半成品</option><option value="成品">成品</option><option value="辅料">辅料</option></select></div></div>';
    modalSaveHandler = function() {
        var d = {material_name:document.getElementById('f_name').value, material_no:document.getElementById('f_no').value,
            specification:document.getElementById('f_spec').value, unit:document.getElementById('f_unit').value,
            category:document.getElementById('f_cat').value};
        if(!d.material_name||!d.material_no) { alert('请填写必填项'); return; }
        api('/api/process/material/add',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); materialLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function materialDel(id) { if(!confirm('确定删除？')) return; api('/api/process/material/delete',{method:'POST',body:{id:id}}).then(function(){materialLoad()}); }

// 异常处理
function renderExceptionManage(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>异常处理</span>'
        + '<button class="btn btn-blue" onclick="exceptionAdd()">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>异常单号</th><th>类型</th><th>站点</th><th>严重度</th><th>描述</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="8" class="empty">加载中...</td></tr></tbody></table></div>';
    exceptionLoad();
}
function exceptionLoad() {
    api('/api/process/exception/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="8" class="empty">暂无异常</td></tr>'; return; }
        var sevColor = {low:'#52c41a',medium:'#fa8c16',high:'#f5222d',critical:'#722ed1'};
        tb.innerHTML = list.map(function(e) {
            return '<tr><td>'+e.id+'</td><td>'+MESUI.escapeHtml(e.exception_no)+'</td><td>'+MESUI.escapeHtml(e.exception_type||'-')+'</td>'
                +'<td>'+MESUI.escapeHtml(e.station||'-')+'</td><td style="color:'+(sevColor[e.severity]||'#333')+'">'+(e.severity||'-')+'</td>'
                +'<td>'+(e.description||'-').substring(0,30)+'</td>'
                +'<td><span class="tag '+MESUI.escapeHtml(e.status?'tag-ok':'tag-no')+'">'+MESUI.escapeHtml(e.status?'已处理':'待处理')+'</span></td>'
                +'<td>'+(e.status?'':'<button class="btn btn-green btn-sm" onclick="resolveException('+e.id+')">处理</button>')+'</td></tr>';
        }).join('');
    });
}
function exceptionAdd() {
    document.getElementById('mTitle').textContent = '新增异常';
    document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>类型</label><select id="f_type"><option value="设备">设备</option><option value="物料">物料</option><option value="质量">质量</option><option value="人员">人员</option><option value="其他">其他</option></select></div>'
        + '<div class="form-item"><label>站点</label><input id="f_station"></div></div>'
        + '<div class="form-row"><div class="form-item"><label>严重度</label><select id="f_sev"><option value="low">低</option><option value="medium" selected>中</option><option value="high">高</option><option value="critical">危急</option></select></div></div>'
        + '<div class="form-row"><div class="form-item" style="flex:1"><label>描述</label><textarea id="f_desc"></textarea></div></div>';
    modalSaveHandler = function() {
        var d = {exception_type:document.getElementById('f_type').value, station:document.getElementById('f_station').value,
            severity:document.getElementById('f_sev').value, description:document.getElementById('f_desc').value};
        api('/api/process/exception/add',{method:'POST',body:d}).then(function(r) {
            if(r&&r.code===0) { closeModal(); exceptionLoad(); } else alert(r?r.message:'保存失败');
        });
    };
    document.getElementById('modal').classList.add('show');
}
function resolveException(id) { if(!confirm('确定处理？')) return; api('/api/process/exception/resolve',{method:'POST',body:{id:id}}).then(function(r){if(r.code===0){showToast(r.message);exceptionLoad()}else alert(r.message)}); }

// 制程统计
function renderProcessStats(el) {
    el.innerHTML = '<div class="card"><div class="card-title">制程统计</div>'
        + '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">总流转数</div><div class="val" id="ps1">-</div></div>'
        + '<div class="stat"><div class="label">流转中</div><div class="val" id="ps2" style="color:#fa8c16">-</div></div>'
        + '<div class="stat"><div class="label">今日过站</div><div class="val" id="ps3">-</div></div>'
        + '<div class="stat"><div class="label">待处理异常</div><div class="val" id="ps4" style="color:#f5222d">-</div></div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px">'
        + '<div class="stat"><div class="label">不良品待处理</div><div class="val" id="ps5" style="color:#f5222d">-</div></div>'
        + '<div class="stat"><div class="label">锁料中</div><div class="val" id="ps6" style="color:#fa8c16">-</div></div>'
        + '</div>'
        + '<div id="stationChart" style="height:300px"></div></div>';
    api('/api/process/statistics').then(function(r) {
        if(!r||r.code!==0) return;
        var d = r.data;
        document.getElementById('ps1').textContent = d.total_flows;
        document.getElementById('ps2').textContent = d.active_flows;
        document.getElementById('ps3').textContent = d.today_pass;
        document.getElementById('ps4').textContent = d.exception_count;
        document.getElementById('ps5').textContent = d.defect_count;
        document.getElementById('ps6').textContent = d.lock_count;
        
        if(d.station_stats.length) {
            var chart = echarts.init(document.getElementById('stationChart'));
            chart.setOption({
                title:{text:'各站点过站次数',left:'center'},
                tooltip:{trigger:'axis'},
                xAxis:{type:'category',data:d.station_stats.map(function(s){return s.station})},
                yAxis:{type:'value'},
                series:[{type:'bar',data:d.station_stats.map(function(s){return s.count}),itemStyle:{color:'#1890ff'}}]
            });
        }
    });
}
