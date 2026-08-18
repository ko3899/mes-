/* AIM机台通讯中心 */
var machineIotTab = 'endpoints';
var machineIotEquipment = [];
var machineIotProcesses = [];

function machineEscape(value) {
    return MESUI.escapeHtml(value === null || value === undefined || value === '' ? '-' : String(value));
}

function renderMachineIot(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>机台通讯中心</span>'
        + '<button class="btn btn-blue" id="machineAdd">+ 新增端点</button></div>'
        + '<div class="toolbar" id="machineHealth">正在读取通讯状态...</div>'
        + '<div class="toolbar"><button class="btn btn-blue btn-sm machine-tab" data-tab="endpoints">通讯端点</button>'
        + '<button class="btn btn-gray btn-sm machine-tab" data-tab="sessions">在线会话</button>'
        + '<button class="btn btn-gray btn-sm machine-tab" data-tab="requests">准入日志 L1/L3</button>'
        + '<button class="btn btn-gray btn-sm machine-tab" data-tab="reports">检测报告</button></div>'
        + '<div id="machineIotBody"></div></div>';
    document.getElementById('machineAdd').onclick = function(){ machineEndpointEdit(null); };
    document.querySelectorAll('.machine-tab').forEach(function(button) {
        button.onclick = function() {
            machineIotTab = button.getAttribute('data-tab');
            document.querySelectorAll('.machine-tab').forEach(function(item) {
                item.className = 'btn btn-gray btn-sm machine-tab';
            });
            button.className = 'btn btn-blue btn-sm machine-tab';
            machineIotLoad();
        };
    });
    machineIotHealth();
    machineIotLoad();
}

function machineIotHealth() {
    api('/api/iot/machine/health').then(function(response) {
        if(!response || response.code !== 0) return;
        var data = response.data;
        document.getElementById('machineHealth').innerHTML = '启用端点 <b>' + machineEscape(data.enabled_endpoints)
            + '</b>　监听在线 <b>' + machineEscape(data.listening_endpoints) + '</b>　监听异常 <b>'
            + machineEscape(data.listener_errors) + '</b>　机台会话 <b>' + machineEscape(data.online_sessions) + '</b>　待报告 <b>'
            + machineEscape(data.pending_reports) + '</b>　失败报告 <b>' + machineEscape(data.failed_reports) + '</b>';
        document.getElementById('machineHealth').innerHTML += '　CSV采集 <b>' + machineEscape(data.collector_status)
            + '</b>　采集目录 <b>' + machineEscape(data.collector_directories)
            + '</b>　目录缺失 <b>' + machineEscape(data.missing_directories) + '</b>　待稳定文件 <b>'
            + machineEscape(data.unstable_files) + '</b>　最后扫描 <b>' + machineEscape(data.last_collection_at) + '</b>';
    });
}

function machineIotLoad() {
    var body = document.getElementById('machineIotBody');
    if(!body) return;
    body.innerHTML = '<div class="empty">加载中...</div>';
    if(machineIotTab === 'endpoints') return machineEndpointLoad(body);
    if(machineIotTab === 'sessions') return machineSessionLoad(body);
    if(machineIotTab === 'requests') return machineRequestLoad(body);
    return machineReportLoad(body);
}

function machineTable(headers, rows) {
    var head = headers.map(function(value){ return '<th>' + value + '</th>'; }).join('');
    return '<div style="overflow:auto"><table><thead><tr>' + head + '</tr></thead><tbody>'
        + (rows.length ? rows.join('') : '<tr><td colspan="' + headers.length + '" class="empty">暂无数据</td></tr>')
        + '</tbody></table></div>';
}

function machineEndpointLoad(body) {
    api('/api/iot/machine/endpoints').then(function(response) {
        var list = response && response.data ? response.data.list || [] : [];
        var rows = list.map(function(row) {
            var encoded = encodeURIComponent(JSON.stringify(row));
            return '<tr><td>' + machineEscape(row.id) + '</td><td>' + machineEscape(row.device_code)
                + '</td><td>' + machineEscape(row.station_code) + '</td><td>' + machineEscape(row.process_name)
                + '</td><td>' + machineEscape(row.cavity_code) + '</td><td>'
                + machineEscape(row.transport_mode === 'reader_client' ? (row.reader_ip + ':' + row.reader_port) : (row.bind_ip + ':' + row.listen_port))
                + '</td><td>' + machineEscape(row.transport_mode === 'reader_client' ? '海康直连' : ('V' + row.protocol_version)) + '</td><td>'
                + (row.enabled ? '<span class="tag tag-ok">启用</span>' : '<span class="tag tag-draft">停用</span>')
                + '</td><td>' + machineEscape(row.listener_status)
                + (row.last_error ? '<br><span class="tag tag-no">' + machineEscape(row.last_error) + '</span>' : '')
                + '</td><td><button class="btn btn-blue btn-sm machine-endpoint-edit" data-endpoint="' + machineEscape(encoded) + '">编辑</button> '
                + '<button class="btn btn-gray btn-sm machine-endpoint-toggle" data-id="' + Number(row.id) + '" data-enabled="' + (row.enabled ? 0 : 1) + '">'
                + (row.enabled ? '停用' : '启用') + '</button></td></tr>';
        });
        body.innerHTML = machineTable(['ID','设备','工站','工序','穴位','监听地址','协议','配置','运行','操作'], rows);
        body.querySelectorAll('.machine-endpoint-edit').forEach(function(button) {
            button.onclick = function() { machineEndpointEditJson(button.getAttribute('data-endpoint')); };
        });
        body.querySelectorAll('.machine-endpoint-toggle').forEach(function(button) {
            button.onclick = function() {
                machineEndpointToggle(Number(button.getAttribute('data-id')), Number(button.getAttribute('data-enabled')));
            };
        });
    });
}

function machineSessionLoad(body) {
    api('/api/iot/machine/sessions?size=100').then(function(response) {
        var list = response && response.data ? response.data.list || [] : [];
        body.innerHTML = machineTable(['设备','工站/穴位','远端地址','状态','连接时间','最后心跳','请求数'], list.map(function(row) {
            return '<tr><td>' + machineEscape(row.device_code) + '</td><td>' + machineEscape(row.station_code + '/' + row.cavity_code)
                + '</td><td>' + machineEscape(row.remote_address) + '</td><td>' + machineEscape(row.status)
                + '</td><td>' + machineEscape(row.connected_at) + '</td><td>' + machineEscape(row.last_heartbeat_at)
                + '</td><td>' + machineEscape(row.request_count) + '</td></tr>';
        }));
    });
}

function machineRequestLoad(body) {
    api('/api/iot/machine/requests?size=100').then(function(response) {
        var list = response && response.data ? response.data.list || [] : [];
        body.innerHTML = machineTable(['时间','设备','SN','判定','原因','耗时','报告'], list.map(function(row) {
            var tag = row.decision === 'L1' ? 'tag-ok' : 'tag-no';
            return '<tr><td>' + machineEscape(row.requested_at) + '</td><td>' + machineEscape(row.device_code)
                + '</td><td>' + machineEscape(row.sn) + '</td><td><span class="tag ' + tag + '">' + machineEscape(row.decision)
                + '</span></td><td>' + machineEscape(row.reason_code + ' ' + (row.reason_message || ''))
                + '</td><td>' + machineEscape(row.elapsed_ms) + 'ms</td><td>' + machineEscape(row.report_status) + '</td></tr>';
        }));
    });
}

function machineReportLoad(body) {
    api('/api/iot/machine/reports?size=100').then(function(response) {
        var list = response && response.data ? response.data.list || [] : [];
        body.innerHTML = '<div class="toolbar"><input type="number" id="machineUploadEndpoint" placeholder="端点ID">'
            + '<input type="file" id="machineUploadFile" accept=".csv"><button class="btn btn-blue btn-sm" onclick="machineReportUpload()">上传CSV</button></div>'
            + machineTable(['时间','设备','SN','结果','文件','导入状态','处置单','失败原因','操作'], list.map(function(row) {
                return '<tr><td>' + machineEscape(row.inspected_at) + '</td><td>' + machineEscape(row.device_code)
                    + '</td><td>' + machineEscape(row.sn) + '</td><td>' + machineEscape(row.result)
                    + '</td><td>' + machineEscape(row.original_filename) + '</td><td>' + machineEscape(row.import_status)
                    + '</td><td>' + machineEscape(row.disposition_no || '-') + ' ' + machineEscape(row.disposition_status || '')
                    + '</td><td>' + machineEscape(row.failure_reason) + '</td><td>'
                    + (row.import_status === 'failed' ? '<button class="btn btn-blue btn-sm machine-report-retry" data-id="' + Number(row.id) + '">重试</button>' : '-')
                    + '</td></tr>';
            }));
        body.querySelectorAll('.machine-report-retry').forEach(function(button) {
            button.onclick = function() { machineReportRetry(Number(button.getAttribute('data-id'))); };
        });
    });
}

function machineEndpointEditJson(encoded) { machineEndpointEdit(JSON.parse(decodeURIComponent(encoded))); }

function machineEndpointEdit(row) {
    Promise.all([api('/api/eqp/ledger/list'), api('/api/base/process/list?size=1000')]).then(function(results) {
        machineIotEquipment = results[0] && results[0].data ? results[0].data.list || results[0].data : [];
        machineIotProcesses = results[1] && results[1].data ? results[1].data.list || results[1].data : [];
        var option = function(list, valueKey, textKey, current) {
            return list.map(function(item) { return '<option value="' + machineEscape(item[valueKey]) + '"'
                + (String(item[valueKey]) === String(current || '') ? ' selected' : '') + '>' + machineEscape(item[textKey]) + '</option>'; }).join('');
        };
        document.getElementById('mTitle').textContent = row ? '编辑通讯端点' : '新增通讯端点';
        document.getElementById('mBody').innerHTML = '<div class="form-row"><div class="form-item"><label>设备 *</label><select id="miEquipment"><option value="">请选择</option>'
            + option(machineIotEquipment, 'id', 'equipment_name', row && row.equipment_id) + '</select></div><div class="form-item"><label>工序 *</label><select id="miProcess"><option value="">请选择</option>'
            + option(machineIotProcesses, 'id', 'process_name', row && row.process_id) + '</select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>工站 *</label><input id="miStation" value="' + machineEscape(row && row.station_code || '') + '"></div>'
            + '<div class="form-item"><label>穴位 *</label><input id="miCavity" value="' + machineEscape(row && row.cavity_code || 'C1') + '"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>通讯方向</label><select id="miTransport"><option value="server">MES监听机台</option><option value="reader_client"' + (row && row.transport_mode === 'reader_client' ? ' selected' : '') + '>MES直连海康读码器</option></select></div>'
            + '<div class="form-item"><label>MES监听IP *</label><input id="miIp" value="' + machineEscape(row && row.bind_ip || '0.0.0.0') + '"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>MES监听端口 *</label><input type="number" id="miPort" value="' + machineEscape(row && row.listen_port || 2004) + '"></div>'
            + '<div class="form-item"><label>读码器IP（直连）</label><input id="miReaderIp" value="' + machineEscape(row && row.reader_ip || '') + '" placeholder="例如 192.168.0.23"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>读码器端口</label><input type="number" id="miReaderPort" value="' + machineEscape(row && row.reader_port || 2002) + '"></div>'
            + '<div class="form-item"><label>无结束符切帧空闲(ms)</label><input type="number" min="20" max="2000" id="miReaderIdle" value="' + machineEscape(row && row.reader_frame_idle_ms || 80) + '"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>机台来源IP</label><input id="miRemoteIp" value="' + machineEscape(row && row.allowed_remote_ip || '') + '" placeholder="V1正式生产建议必填"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>CSV输入目录</label><input id="miCsvDir" value="' + machineEscape(row && row.csv_input_dir || '') + '" placeholder="例如 D:\\AIM\\Result"></div>'
            + '<div class="form-item"><label>文件稳定秒数</label><input type="number" min="1" max="60" id="miStableSeconds" value="' + machineEscape(row && row.csv_stable_seconds || 2) + '"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>协议</label><select id="miProtocol"><option value="1">V1 原协议</option><option value="2"' + (row && Number(row.protocol_version) === 2 ? ' selected' : '') + '>V2 增强协议</option></select></div>'
            + '<div class="form-item"><label>编码</label><select id="miEncoding"><option value="utf-8">UTF-8</option><option value="gbk"' + (row && row.encoding === 'gbk' ? ' selected' : '') + '>GBK</option></select></div></div>'
            + '<div class="form-row"><div class="form-item"><label>请求超时(ms)</label><input type="number" min="500" max="5000" id="miTimeout" value="' + machineEscape(row && row.timeout_ms || 1000) + '"></div>'
            + '<div class="form-item"><label>心跳周期(s)</label><input type="number" min="5" max="3600" id="miHeartbeat" value="' + machineEscape(row && row.heartbeat_seconds || 30) + '"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>V2共享密钥</label><input type="password" id="miSecret" placeholder="' + (row && row.shared_secret_configured ? '已配置，留空保持不变' : '可选') + '"></div>'
            + '<div class="form-item"><label>加工模板</label><input id="miLaserTemplate" value="' + machineEscape(row && row.laser_template || '') + '" placeholder="镭雕/加工模板编号"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>检测模板</label><input id="miInspectionTemplate" value="' + machineEscape(row && row.inspection_template || '') + '" placeholder="CCD模板编号"></div></div>'
            + '<div class="form-row"><div class="form-item"><label>设备生命周期ID</label><input id="miLifecycle" value="' + machineEscape(row && row.lifecycle_id || 'legacy') + '" placeholder="设备重启/换机时变更"></div>'
            + '<div class="form-item"><label><input type="checkbox" id="miNonce"' + ((!row || Number(row.require_request_nonce) === 1) ? ' checked' : '') + '> V2启用时间戳/nonce防重放</label></div></div>';
        modalSaveHandler = function(){ machineEndpointSave(row); };
        document.getElementById('modal').classList.add('show');
    });
}

function machineEndpointSave(row) {
    var payload = {id:row && row.id, equipment_id:document.getElementById('miEquipment').value,
        process_id:document.getElementById('miProcess').value, station_code:document.getElementById('miStation').value,
        cavity_code:document.getElementById('miCavity').value, bind_ip:document.getElementById('miIp').value,
        transport_mode:document.getElementById('miTransport').value,
        reader_ip:document.getElementById('miReaderIp').value,
        reader_port:Number(document.getElementById('miReaderPort').value),
        reader_frame_idle_ms:Number(document.getElementById('miReaderIdle').value),
        allowed_remote_ip:document.getElementById('miRemoteIp').value,
        csv_input_dir:document.getElementById('miCsvDir').value,
        csv_stable_seconds:Number(document.getElementById('miStableSeconds').value),
        listen_port:Number(document.getElementById('miPort').value), protocol_version:Number(document.getElementById('miProtocol').value),
        encoding:document.getElementById('miEncoding').value,
        timeout_ms:Number(document.getElementById('miTimeout').value),
        heartbeat_seconds:Number(document.getElementById('miHeartbeat').value),
        enabled:row ? Number(row.enabled) : 1,
        shared_secret:document.getElementById('miSecret').value,
        laser_template:document.getElementById('miLaserTemplate').value,
         inspection_template:document.getElementById('miInspectionTemplate').value,
         lifecycle_id:document.getElementById('miLifecycle').value,
         require_request_nonce:document.getElementById('miNonce').checked ? 1 : 0};
    api('/api/iot/machine/endpoints/save', {method:'POST', body:payload}).then(function(response) {
        if(response && response.code === 0) { closeModal(); machineIotLoad(); machineIotHealth(); }
        else alert(response ? response.message : '保存失败');
    });
}

function machineEndpointToggle(id, enabled) {
    api('/api/iot/machine/endpoints/' + id + '/toggle', {method:'POST', body:{enabled:enabled}}).then(function(){ machineIotLoad(); machineIotHealth(); });
}

function machineReportUpload() {
    var endpoint = document.getElementById('machineUploadEndpoint').value;
    var file = document.getElementById('machineUploadFile').files[0];
    if(!endpoint || !file) { alert('请填写端点ID并选择CSV'); return; }
    var form = new FormData(); form.append('endpoint_id', endpoint); form.append('file', file);
    fetch('/api/iot/machine/reports/upload', {method:'POST', body:form}).then(function(response){ return response.json(); }).then(function(result) {
        if(result.code === 0) { alert('检测报告导入成功'); machineIotLoad(); machineIotHealth(); }
        else alert(result.message || '上传失败');
    });
}

function machineReportRetry(id) {
    api('/api/iot/machine/reports/' + id + '/retry', {method:'POST', body:{}}).then(function(result) {
        if(result && result.code === 0) { alert('失败报告重试成功'); machineIotLoad(); machineIotHealth(); }
        else alert(result ? result.message : '重试失败');
    });
}
