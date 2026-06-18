/* 模具/工装/能耗/环境/培训/技能/5S/售后页面 */

// 模具管理
function renderMold(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>模具管理</span><button class="btn btn-blue" id="moldAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>模具名称</th><th>编码</th><th>类型</th><th>产品</th><th>寿命</th><th>已用</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="9" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('moldAddBtn').onclick = moldAdd;
    moldLoad();
}
function moldLoad() {
    api('/api/eqp/mold/list').then(function(r) {
        if(!r||!r.data) return;
        var tb = document.getElementById('tb');
        if(!r.data.length) { tb.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = r.data.map(function(m) {
            var lifePercent = m.total_life > 0 ? Math.round(m.used_life/m.total_life*100) : 0;
            var lifeColor = lifePercent > 80 ? '#f5222d' : (lifePercent > 50 ? '#fa8c16' : '#52c41a');
            return '<tr><td>'+m.id+'</td><td>'+m.mold_name+'</td><td>'+m.code+'</td><td>'+(m.mold_type||'-')+'</td>'
                +'<td>'+(m.product_name||'-')+'</td><td>'+m.total_life+'</td>'
                +'<td><span style="color:'+lifeColor+';font-weight:bold">'+m.used_life+' ('+lifePercent+'%)</span></td>'
                +'<td><span class="tag '+(m.status?'tag-ok':'tag-draft')+'">'+(m.status?'在用':'停用')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="moldDel('+m.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function moldAdd() {
    api('/api/base/product/all').then(function(r) {
        var opts = '<option value="">选择产品</option>';
        (r?.data||[]).forEach(function(p) { opts += '<option value="'+p.id+'">'+p.product_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增模具';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>模具名称<span style="color:red">*</span></label><input id="f_name"></div>'
            + '<div class="form-item"><label>编码<span style="color:red">*</span></label><input id="f_code"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>类型</label><select id="f_type"><option value="注塑">注塑</option><option value="冲压">冲压</option><option value="压铸">压铸</option><option value="其他">其他</option></select></div>'
            + '<div class="form-item"><label>产品</label><select id="f_prod">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>制造商</label><input id="f_mfr"></div>'
            + '<div class="form-item"><label>总寿命</label><input id="f_life" type="number"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>位置</label><input id="f_loc"></div></div>';
        modalSaveHandler = function() {
            var d = {mold_name:document.getElementById('f_name').value, code:document.getElementById('f_code').value,
                mold_type:document.getElementById('f_type').value, product_id:document.getElementById('f_prod').value||null,
                manufacturer:document.getElementById('f_mfr').value, total_life:document.getElementById('f_life').value||0,
                location:document.getElementById('f_loc').value};
            if(!d.mold_name||!d.code) { alert('请填写必填项'); return; }
            api('/api/eqp/mold/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); moldLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function moldDel(id) { if(!confirm('确定删除？')) return; api('/api/eqp/mold/delete',{method:'POST',body:{id:id}}).then(function(){moldLoad()}); }

// 工装夹具
function renderFixture(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>工装夹具</span><button class="btn btn-blue" id="fixAddBtn">+ 新增</button></div>'
        + '<table><thead><tr><th>ID</th><th>名称</th><th>编码</th><th>类型</th><th>工序</th><th>校准日期</th><th>下次校准</th><th>状态</th><th>操作</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="9" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('fixAddBtn').onclick = fixAdd;
    fixLoad();
}
function fixLoad() {
    api('/api/eqp/fixture/list').then(function(r) {
        if(!r||!r.data) return;
        var tb = document.getElementById('tb');
        if(!r.data.length) { tb.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>'; return; }
        var today = new Date().toISOString().slice(0,10);
        tb.innerHTML = r.data.map(function(f) {
            var overdue = f.next_calibration && f.next_calibration < today;
            return '<tr><td>'+f.id+'</td><td>'+f.fixture_name+'</td><td>'+f.code+'</td><td>'+(f.fixture_type||'-')+'</td>'
                +'<td>'+(f.process_name||'-')+'</td><td>'+(f.calibration_date||'-')+'</td>'
                +'<td'+(overdue?' style="color:#f5222d;font-weight:bold"':'')+'>'+(f.next_calibration||'-')+'</td>'
                +'<td><span class="tag '+(f.status?'tag-ok':'tag-draft')+'">'+(f.status?'正常':'停用')+'</span></td>'
                +'<td><button class="btn btn-red btn-sm" onclick="fixDel('+f.id+')">删除</button></td></tr>';
        }).join('');
    });
}
function fixAdd() {
    api('/api/base/process/list?size=100').then(function(r) {
        var opts = '<option value="">选择工序</option>';
        (r?.data?.list||[]).forEach(function(p) { opts += '<option value="'+p.id+'">'+p.process_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增工装夹具';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>名称<span style="color:red">*</span></label><input id="f_name"></div>'
            + '<div class="form-item"><label>编码<span style="color:red">*</span></label><input id="f_code"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>类型</label><select id="f_type"><option value="夹具">夹具</option><option value="量具">量具</option><option value="检具">检具</option><option value="其他">其他</option></select></div>'
            + '<div class="form-item"><label>工序</label><select id="f_proc">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>校准日期</label><input id="f_cal" type="date"></div>'
            + '<div class="form-item"><label>下次校准</label><input id="f_next" type="date"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>位置</label><input id="f_loc"></div></div>';
        modalSaveHandler = function() {
            var d = {fixture_name:document.getElementById('f_name').value, code:document.getElementById('f_code').value,
                fixture_type:document.getElementById('f_type').value, process_id:document.getElementById('f_proc').value||null,
                calibration_date:document.getElementById('f_cal').value, next_calibration:document.getElementById('f_next').value,
                location:document.getElementById('f_loc').value};
            if(!d.fixture_name||!d.code) { alert('请填写必填项'); return; }
            api('/api/eqp/fixture/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); fixLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
function fixDel(id) { if(!confirm('确定删除？')) return; api('/api/eqp/fixture/delete',{method:'POST',body:{id:id}}).then(function(){fixLoad()}); }

// 能耗管理
function renderEnergy(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>能耗管理</span><button class="btn btn-blue" id="energyAddBtn">+ 新增</button></div>'
        + '<div id="energyStats" style="margin-bottom:16px"></div>'
        + '<table><thead><tr><th>ID</th><th>日期</th><th>车间</th><th>类型</th><th>用量</th><th>单位</th><th>费用</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="7" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('energyAddBtn').onclick = energyAdd;
    energyLoad();
    energyStatsLoad();
}
function energyLoad() {
    api('/api/util/energy/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(e) {
            return '<tr><td>'+e.id+'</td><td>'+e.record_date+'</td><td>'+(e.workshop_name||'-')+'</td><td>'+e.energy_type+'</td>'
                +'<td>'+e.quantity+'</td><td>'+(e.unit||'-')+'</td><td style="color:#f5222d">¥'+(e.cost||0).toFixed(2)+'</td></tr>';
        }).join('');
    });
}
function energyStatsLoad() {
    api('/api/util/energy/statistics').then(function(r) {
        if(!r||!r.data) return;
        var el = document.getElementById('energyStats');
        el.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px">'
            +r.data.map(function(e) {
                return '<div style="background:#f0f5ff;padding:12px;border-radius:8px;text-align:center">'
                    +'<div style="font-weight:bold">'+e.energy_type+'</div>'
                    +'<div style="font-size:16px;color:#1890ff">'+e.total_qty.toFixed(1)+'</div>'
                    +'<div style="font-size:12px;color:#666">¥'+e.total_cost.toFixed(2)+'</div></div>';
            }).join('')+'</div>';
    });
}
function energyAdd() {
    api('/api/base/workshop/list?size=100').then(function(r) {
        var opts = '<option value="">选择车间</option>';
        (r?.data?.list||[]).forEach(function(w) { opts += '<option value="'+w.id+'">'+w.workshop_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增能耗记录';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>日期<span style="color:red">*</span></label><input id="f_date" type="date"></div>'
            + '<div class="form-item"><label>车间</label><select id="f_ws">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>类型</label><select id="f_type"><option value="电">电</option><option value="水">水</option><option value="气">气</option><option value="蒸汽">蒸汽</option></select></div>'
            + '<div class="form-item"><label>用量<span style="color:red">*</span></label><input id="f_qty" type="number" step="0.01"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>单位</label><input id="f_unit" value="kWh"></div>'
            + '<div class="form-item"><label>费用</label><input id="f_cost" type="number" step="0.01"></div></div>';
        document.getElementById('f_date').value = new Date().toISOString().slice(0,10);
        modalSaveHandler = function() {
            var d = {record_date:document.getElementById('f_date').value, workshop_id:document.getElementById('f_ws').value||null,
                energy_type:document.getElementById('f_type').value, quantity:document.getElementById('f_qty').value,
                unit:document.getElementById('f_unit').value, cost:document.getElementById('f_cost').value||0};
            if(!d.record_date||!d.quantity) { alert('请填写必填项'); return; }
            api('/api/util/energy/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); energyLoad(); energyStatsLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}

// 环境监控
function renderEnvironment(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>环境监控</span><button class="btn btn-blue" id="envAddBtn">+ 新增</button></div>'
        + '<div id="envLatest" style="margin-bottom:16px"></div>'
        + '<table><thead><tr><th>ID</th><th>车间</th><th>温度°C</th><th>湿度%</th><th>洁净度</th><th>时间</th></tr></thead>'
        + '<tbody id="tb"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody></table></div>';
    document.getElementById('envAddBtn').onclick = envAdd;
    envLoad();
    envLatestLoad();
}
function envLoad() {
    api('/api/util/environment/list?size=50').then(function(r) {
        if(!r) return;
        var list = r.data?.list||[];
        var tb = document.getElementById('tb');
        if(!list.length) { tb.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>'; return; }
        tb.innerHTML = list.map(function(e) {
            var tempColor = e.temperature > 30 ? '#f5222d' : (e.temperature < 10 ? '#1890ff' : '#52c41a');
            return '<tr><td>'+e.id+'</td><td>'+(e.workshop_name||'-')+'</td>'
                +'<td style="color:'+tempColor+';font-weight:bold">'+e.temperature+'</td><td>'+e.humidity+'</td>'
                +'<td>'+(e.cleanliness||'-')+'</td><td>'+(e.record_time||'')+'</td></tr>';
        }).join('');
    });
}
function envLatestLoad() {
    api('/api/util/environment/latest').then(function(r) {
        if(!r||!r.data) return;
        var el = document.getElementById('envLatest');
        el.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px">'
            +r.data.map(function(e) {
                return '<div style="background:#f0f5ff;padding:12px;border-radius:8px">'
                    +'<div style="font-weight:bold">'+e.workshop_name+'</div>'
                    +'<div style="display:flex;gap:16px;margin-top:8px">'
                    +'<div>🌡️ '+e.temperature+'°C</div><div>💧 '+e.humidity+'%</div></div></div>';
            }).join('')+'</div>';
    });
}
function envAdd() {
    api('/api/base/workshop/list?size=100').then(function(r) {
        var opts = '<option value="">选择车间</option>';
        (r?.data?.list||[]).forEach(function(w) { opts += '<option value="'+w.id+'">'+w.workshop_name+'</option>'; });
        document.getElementById('mTitle').textContent = '新增环境记录';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>车间</label><select id="f_ws">'+opts+'</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>温度°C</label><input id="f_temp" type="number" step="0.1"></div>'
            + '<div class="form-item"><label>湿度%</label><input id="f_hum" type="number" step="0.1"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>洁净度</label><input id="f_clean"></div></div>';
        modalSaveHandler = function() {
            var d = {workshop_id:document.getElementById('f_ws').value||null, temperature:document.getElementById('f_temp').value,
                humidity:document.getElementById('f_hum').value, cleanliness:document.getElementById('f_clean').value};
            api('/api/util/environment/add',{method:'POST',body:d}).then(function(r2) {
                if(r2&&r2.code===0) { closeModal(); envLoad(); envLatestLoad(); } else alert(r2?r2.message:'保存失败');
            });
        };
        document.getElementById('modal').classList.add('show');
    });
}
