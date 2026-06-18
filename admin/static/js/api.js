/* API 请求模块 */
function api(url, opts) {
    opts = opts || {};
    var o = {headers: {'Content-Type': 'application/json'}};
    if (opts.method) o.method = opts.method;
    if (opts.body) o.body = JSON.stringify(opts.body);
    return fetch(url, o).then(function(r) { return r.json(); }).then(function(d) {
        if (d.code === 401) { doLogout(); return null; }
        return d;
    }).catch(function(e) { console.error('API Error:', e); return null; });
}

function escapeJson(obj) {
    return JSON.stringify(obj).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function doExport2(table) {
    window.open('/api/export/' + table, '_blank');
}
