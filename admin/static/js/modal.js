/* 模态框模块 */
var editId = null;
var curFields = null;
var curApiBase = '';
var modalSaveHandler = null;

function openModal(title, fields, data) {
    var requestToken = typeof crudRenderToken === 'undefined'
        ? null : crudRenderToken;
    var requestApiBase = curApiBase;
    var apiFields = fields.filter(function(f) {
        return !f.generated && f.type === 'select' && f.api;
    });
    if (apiFields.length > 0) {
        var promises = apiFields.map(function(f) {
            return api(f.api).then(function(r) {
                f._options = (r && r.data) ? (Array.isArray(r.data) ? r.data : (r.data.list || [])) : [];
            });
        });
        Promise.all(promises).then(function() {
            if(requestToken !== null && (
                requestToken !== crudRenderToken
                || requestApiBase !== curApiBase
            )) return;
            openModalSync(title, fields, data);
        });
    } else {
        openModalSync(title, fields, data);
    }
}

function openModalSync(title, fields, data) {
    var formToken = typeof crudRenderToken === 'undefined'
        ? null : crudRenderToken;
    var formApiBase = curApiBase;
    var formEditId = editId;
    document.getElementById('mTitle').textContent = title;
    var h = '';
    fields = fields.filter(function(f) { return !f.generated; });
    var formFields = fields.slice();
    fields.forEach(function(f, i) {
        if(i % 2 === 0) h += '<div class="form-row">';
        var val = data[f.k] != null ? data[f.k] : '';
        var fieldId = MESUI.escapeHtml('f_' + String(f.k));
        var safeVal = MESUI.escapeHtml(val);
        h += '<div class="form-item"><label>' + MESUI.escapeHtml(f.l)
            + (f.r ? '<span style="color:red">*</span>' : '') + '</label>';
        if(f.s) {
            h += '<select id="' + fieldId + '"><option value="">请选择</option>';
            f.s.forEach(function(o) {
                h += '<option value="' + MESUI.escapeHtml(o.v) + '"'
                    + (String(o.v) === String(val) ? ' selected' : '') + '>'
                    + MESUI.escapeHtml(o.t) + '</option>';
            });
            h += '</select>';
        } else if(f.type === 'select' && f.api) {
            h += '<select id="' + fieldId + '"><option value="">请选择</option>';
            (f._options || []).forEach(function(o) {
                h += '<option value="' + MESUI.escapeHtml(o[f.vk]) + '"'
                    + (String(o[f.vk]) === String(val) ? ' selected' : '') + '>'
                    + MESUI.escapeHtml(o[f.tk]) + '</option>';
            });
            h += '</select>';
        } else if(f.type === 'date') {
            h += '<input id="' + fieldId + '" type="date" value="' + safeVal + '">';
        } else if(f.type === 'number') {
            h += '<input id="' + fieldId + '" type="number" value="' + safeVal + '" step="0.01">';
        } else {
            h += '<input id="' + fieldId + '" type="text" value="' + safeVal + '">';
        }
        h += '</div>';
        if(i % 2 === 1 || i === fields.length - 1) h += '</div>';
    });
    document.getElementById('mBody').innerHTML = h;

    modalSaveHandler = function() {
        if(formToken !== null && formToken !== crudRenderToken) {
            alert('页面已切换，请重新操作');
            closeModal();
            return;
        }
        var data = {};
        if(formEditId) data.id = formEditId;
        for(var i = 0; i < formFields.length; i++) {
            var f = formFields[i];
            var el = document.getElementById('f_' + f.k);
            if(!el) continue;
            var v = el.value;
            if(f.r && !v) { alert(f.l + '不能为空'); el.focus(); return; }
            if(f.type === 'number') {
                data[f.k] = v ? Number(v) : null;
            } else if((f.s || (f.type === 'select' && f.api))) {
                data[f.k] = (v !== '' && !isNaN(v)) ? Number(v) : (v === '' ? null : v);
            } else {
                data[f.k] = v;
            }
        }
        api(formApiBase + (formEditId ? '/update' : '/add'), {method:'POST', body:data}).then(function(r) {
            if(r && r.code === 0) {
                closeModal();
                if(formToken === null || formToken === crudRenderToken) crudLoad(1);
            }
            else alert(r ? r.message : '保存失败');
        });
    };

    document.getElementById('modal').classList.add('show');
}

function closeModal() {
    document.getElementById('modal').classList.remove('show');
    modalSaveHandler = null;
}
