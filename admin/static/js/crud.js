/* CRUD 通用模块 */
var sortField = '';
var sortOrder = 'DESC';
var pageSize = 15;
var currentRowsById = Object.create(null);
var crudRenderToken = 0;
var curDataTable = '';
var curCrudActions = {
    add: true,
    edit: true,
    delete: true,
    import: true,
    export: true
};

// 加载用户偏好
function loadUserPrefs() {
    var prefs = JSON.parse(localStorage.getItem('userPrefs') || '{}');
    if(prefs.pageSize) pageSize = prefs.pageSize;
}
loadUserPrefs();

function renderCrud(el, path, cfg) {
    crudRenderToken += 1;
    curFields = cfg.f;
    curApiBase = cfg.apiBase || ('/api/' + path.split('/')[0] + '/' + path.split('/')[1]);
    curDataTable = cfg.dataTable
        || curApiBase.replace('/api/', '').replace(/\//g, '_');
    curCrudActions = Object.assign({
        add: true,
        edit: true,
        delete: true,
        import: true,
        export: true
    }, cfg.actions || {});
    var fkey = path.replace(/\//g, '_');
    var hasRowActions = curCrudActions.edit || curCrudActions.delete;
    var ths = '<th><input type="checkbox" onchange="toggleSelectAll(this.checked)"></th><th>ID</th>';
    cfg.f.forEach(function(f){
        ths += '<th class="sortable" data-sort="' + MESUI.escapeHtml(f.k)
            + '" onclick="sortTable(\'' + MESUI.escapeHtml(f.k) + '\')">'
            + MESUI.escapeHtml(f.l) + '</th>';
    });
    ths += '<th>创建时间</th>';
    if(hasRowActions) ths += '<th>操作</th>';

    var actionButtons = '<button class="btn btn-gray" onclick="crudLoad(1)">刷新</button>';
    if(curCrudActions.export) {
        actionButtons += '<button class="btn btn-green" id="exportBtn">导出</button>';
    }
    if(curCrudActions.import) {
        actionButtons += '<button class="btn btn-orange" id="importBtn" '
            + 'style="background:#fa8c16;color:#fff">导入</button>';
    }
    if(curCrudActions.add) {
        actionButtons += '<button class="btn btn-blue" id="addBtn">+ 新增</button>';
    }

    el.innerHTML = '<div class="card"><div class="card-title"><span>'
        + MESUI.escapeHtml(cfg.t) + '</span>'
        + '<div style="display:flex;gap:8px">'
        + actionButtons + '</div></div>'
        + '<div class="toolbar"><input id="kw" placeholder="搜索...">'
        + '<button class="btn btn-blue btn-sm" id="searchBtn">搜索</button>'
        + '<button class="btn btn-gray btn-sm" id="resetBtn">重置</button>'
        + '<select id="pageSize" onchange="changePageSize(this.value)" style="margin-left:auto">'
        + '<option value="10"' + (pageSize===10?' selected':'') + '>10条/页</option>'
        + '<option value="15"' + (pageSize===15?' selected':'') + '>15条/页</option>'
        + '<option value="20"' + (pageSize===20?' selected':'') + '>20条/页</option>'
        + '<option value="50"' + (pageSize===50?' selected':'') + '>50条/页</option>'
        + '</select></div>'
        + '<table><thead><tr>' + ths + '</tr></thead><tbody id="tb"><tr><td colspan="'
        + (cfg.f.length + (hasRowActions ? 4 : 3))
        + '" class="empty">加载中...</td></tr></tbody></table>'
        + '<div class="page" id="pg"></div></div>';

    var addBtn = document.getElementById('addBtn');
    var exportBtn = document.getElementById('exportBtn');
    var importBtn = document.getElementById('importBtn');
    if(addBtn) addBtn.onclick = function() { crudAdd(); };
    document.getElementById('searchBtn').onclick = function() { crudLoad(1); };
    document.getElementById('resetBtn').onclick = function() { document.getElementById('kw').value = ''; sortField = ''; crudLoad(1); };
    document.getElementById('kw').onkeydown = function(e) { if(e.key === 'Enter') crudLoad(1); };
    if(exportBtn) exportBtn.onclick = function() { doExport(); };
    if(importBtn) importBtn.onclick = function() { doImport(); };

    selectedRows.clear();
    updateBatchBar();
    crudLoad(1);
}

function changePageSize(val) {
    pageSize = parseInt(val);
    var prefs = JSON.parse(localStorage.getItem('userPrefs') || '{}');
    prefs.pageSize = pageSize;
    localStorage.setItem('userPrefs', JSON.stringify(prefs));
    crudLoad(1);
}

function crudLoad(page, sort, order) {
    page = page || 1;
    var loadToken = crudRenderToken;
    var loadApiBase = curApiBase;
    var loadFields = curFields.slice();
    var loadActions = Object.assign({}, curCrudActions);
    var hasRowActions = loadActions.edit || loadActions.delete;
    var kw = document.getElementById('kw') ? document.getElementById('kw').value : '';
    var url = curApiBase + '/list?page=' + page + '&size=' + pageSize;
    if(kw) url += '&keyword=' + encodeURIComponent(kw);
    if(sort) { sortField = sort; sortOrder = order || 'DESC'; }
    if(sortField) url += '&sort=' + sortField + '&order=' + sortOrder;
    api(url).then(function(r) {
        if(loadToken !== crudRenderToken || loadApiBase !== curApiBase) return;
        if(!r) return;
        var list = Array.isArray(r.data) ? r.data : (r.data && r.data.list ? r.data.list : []);
        var total = Array.isArray(r.data) ? list.length : (r.data ? r.data.total : 0);
        var tb = document.getElementById('tb');
        var pg = document.getElementById('pg');
        currentRowsById = Object.create(null);
        if(!list.length) { tb.innerHTML = '<tr><td colspan="99" class="empty">暂无数据</td></tr>'; pg.innerHTML = ''; return; }

        var h = '';
        list.forEach(function(row) {
            var rowKey = String(row.id);
            var rowIdArg = MESUI.escapeHtml(JSON.stringify(row.id));
            var isSelected = selectedRows.has(rowKey);
            currentRowsById[rowKey] = row;
            h += '<tr><td><input type="checkbox" data-id="' + MESUI.escapeHtml(rowKey) + '" '
                + (isSelected ? 'checked' : '') + ' onchange="toggleSelectRow(' + rowIdArg
                + ',this.checked)"></td><td>' + MESUI.escapeHtml(row.id) + '</td>';
            loadFields.forEach(function(f) {
                var v = row[f.k] != null ? row[f.k] : '';
                if(f.k === 'status') {
                    v = MESUI.statusHtml(f, v);
                } else if(f.s) {
                    f.s.forEach(function(o){ if(String(o.v) === String(v)) v = o.t; });
                    v = MESUI.escapeHtml(v);
                } else {
                    v = MESUI.escapeHtml(v);
                }
                h += '<td>' + v + '</td>';
            });
            h += '<td>' + MESUI.escapeHtml(row.created_at || '') + '</td>';
            if(hasRowActions) {
                h += '<td class="actions">';
                if(loadActions.edit) {
                    h += '<button class="btn btn-blue btn-sm" onclick="crudEdit('
                        + rowIdArg + ')">编辑</button>';
                }
                if(loadActions.delete) {
                    h += '<button class="btn btn-red btn-sm" onclick="crudDel('
                        + rowIdArg + ')">删除</button>';
                }
                h += '</td>';
            }
            h += '</tr>';
        });
        tb.innerHTML = h;

        var pages = Math.ceil(total / pageSize);
        var ph = '<span class="info">共 ' + total + ' 条</span>';
        ph += '<span class="pbtn' + (page <= 1 ? ' off' : '') + '" onclick="crudLoad(' + (page - 1) + ')">&lt;</span>';
        for(var i = Math.max(1, page - 2); i <= Math.min(pages, page + 2); i++) {
            ph += '<span class="pbtn' + (i === page ? ' on' : '') + '" onclick="crudLoad(' + i + ')">' + i + '</span>';
        }
        ph += '<span class="pbtn' + (page >= pages ? ' off' : '') + '" onclick="crudLoad(' + (page + 1) + ')">&gt;</span>';
        pg.innerHTML = ph;
    });
}

function crudActionAllowed(action) {
    if(curCrudActions && curCrudActions[action] === false) {
        alert('当前页面不允许' + ({
            add: '新增',
            edit: '编辑',
            delete: '删除',
            import: '导入',
            export: '导出'
        }[action] || '执行该操作'));
        return false;
    }
    return true;
}

function crudAdd() {
    if(!crudActionAllowed('add')) return;
    editId = null;
    openModal('新增', curFields, {});
}

function crudEdit(id) {
    if(!crudActionAllowed('edit')) return;
    var row = currentRowsById[String(id)];
    if(!row) {
        alert('记录不存在或已刷新，请重新加载');
        return;
    }
    editId = row.id;
    openModal('编辑', curFields, row);
}

function crudDel(id) {
    if(!crudActionAllowed('delete')) return;
    if(!confirm('确定删除？')) return;
    var requestToken = crudRenderToken;
    var requestApiBase = curApiBase;
    api(requestApiBase + '/delete', {method:'POST', body:{id:id}}).then(function(r) {
        if(
            requestToken !== crudRenderToken
            || requestApiBase !== curApiBase
        ) return;
        if(r && r.code === 0) crudLoad(1);
        else alert(r ? r.message : '删除失败');
    });
}

function doExport() {
    if(!crudActionAllowed('export')) return;
    window.open('/api/export/' + curDataTable, '_blank');
}

function doImport() {
    if(!crudActionAllowed('import')) return;
    var table = curDataTable;
    var importToken = crudRenderToken;
    var importApiBase = curApiBase;
    function importPageIsCurrent() {
        return (
            importToken === crudRenderToken
            && importApiBase === curApiBase
        );
    }
    document.getElementById('mTitle').textContent = '导入数据';
    document.getElementById('mBody').innerHTML =
        '<div style="margin-bottom:14px">'
        + '<p style="color:#666;margin-bottom:10px">请上传Excel或CSV文件，第一行为表头</p>'
        + '<a href="/api/template/' + table + '" target="_blank" style="color:#1890ff">下载导入模板</a>'
        + '</div>'
        + '<div class="form-item"><label>选择文件</label>'
        + '<input type="file" id="importFile" accept=".xlsx,.xls,.csv" style="height:auto;padding:8px;border:1px dashed #ddd;border-radius:4px;cursor:pointer"></div>'
        + '<div id="importPreview" style="margin-top:12px"></div>'
        + '<div id="importResult" style="margin-top:12px;color:#666;font-size:13px"></div>';

    // 文件选择后预览
    document.getElementById('importFile').onchange = function() {
        var file = this.files[0];
        if(!file) return;
        var preview = document.getElementById('importPreview');
        preview.innerHTML = '<div style="background:#f0f5ff;padding:12px;border-radius:6px;margin-bottom:12px">'
            + '<b>文件：</b>' + MESUI.escapeHtml(file.name) + ' ('
            + (file.size/1024).toFixed(1) + 'KB)</div>';
    };

    modalSaveHandler = function() {
        if(!importPageIsCurrent()) {
            alert('页面已切换，请重新操作');
            return;
        }
        var fileInput = document.getElementById('importFile');
        if (!fileInput.files.length) { alert('请选择文件'); return; }
        var file = fileInput.files[0];
        var formData = new FormData();
        formData.append('file', file);

        document.getElementById('importResult').innerHTML = '<div class="loading"></div> 导入中...';

        fetch('/api/import/' + table, {
            method: 'POST',
            body: formData
        }).then(function(r) { return r.json(); }).then(function(r) {
            if (r.code === 0) {
                clearApiCache();
                if(!importPageIsCurrent()) return;
                var resultHtml = '<div style="color:#52c41a">'
                    + MESUI.escapeHtml(r.message) + '</div>';
                if (r.data && r.data.errors && r.data.errors.length) {
                    resultHtml += '<div style="color:#f5222d;margin-top:8px"><b>错误信息：</b></div>';
                    resultHtml += '<div style="background:#fff2f0;padding:8px;border-radius:4px;margin-top:4px">';
                    r.data.errors.forEach(function(err) {
                        resultHtml += '<div style="color:#666;font-size:12px;padding:2px 0">'
                            + MESUI.escapeHtml(err) + '</div>';
                    });
                    resultHtml += '</div>';
                }
                document.getElementById('importResult').innerHTML = resultHtml;
                setTimeout(function() {
                    if(!importPageIsCurrent()) return;
                    closeModal();
                    crudLoad(1);
                }, 3000);
            } else {
                if(!importPageIsCurrent()) return;
                document.getElementById('importResult').innerHTML = '<div style="color:#f5222d">'
                    + MESUI.escapeHtml(r.message || '导入失败') + '</div>';
            }
        }).catch(function(e) {
            if(!importPageIsCurrent()) return;
            document.getElementById('importResult').innerHTML = '<div style="color:#f5222d">网络错误</div>';
        });
    };
    document.getElementById('modal').classList.add('show');
}

// 导出自定义字段选择
function doExportCustom() {
    if(!crudActionAllowed('export')) return;
    var table = curDataTable;
    document.getElementById('mTitle').textContent = '自定义导出';
    document.getElementById('mBody').innerHTML = '<div style="margin-bottom:12px"><b>选择导出字段：</b></div>'
        + '<div id="exportFields" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px"></div>';
    
    var fieldsHtml = '';
    curFields.forEach(function(f, i) {
        fieldsHtml += '<label style="display:flex;align-items:center;gap:6px;padding:6px;background:#f5f5f5;border-radius:4px;cursor:pointer">'
            + '<input type="checkbox" checked data-field="' + f.k + '"> ' + f.l + '</label>';
    });
    document.getElementById('exportFields').innerHTML = fieldsHtml;
    
    modalSaveHandler = function() {
        var selected = [];
        document.querySelectorAll('#exportFields input:checked').forEach(function(cb) {
            selected.push(cb.getAttribute('data-field'));
        });
        if(!selected.length) { alert('请选择至少一个字段'); return; }
        // 导出选中字段
        window.open('/api/export/' + table + '?fields=' + selected.join(','), '_blank');
        closeModal();
    };
    document.getElementById('modal').classList.add('show');
}
