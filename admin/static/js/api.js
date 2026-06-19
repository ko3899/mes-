/* API 请求模块 */
var apiCache = {};
var apiCacheTTL = 5000; // 5秒缓存

function api(url, opts) {
    opts = opts || {};
    var o = {headers: {'Content-Type': 'application/json'}};
    if(opts.method) o.method = opts.method;
    if(opts.body) o.body = JSON.stringify(opts.body);
    
    // GET请求缓存
    var cacheKey = url + JSON.stringify(opts);
    if(!opts.method && apiCache[cacheKey]) {
        var cached = apiCache[cacheKey];
        if(Date.now() - cached.time < apiCacheTTL) {
            return Promise.resolve(cached.data);
        }
    }
    
    return fetch(url, o).then(function(r){return r.json()}).then(function(d){
        if(d.code === 401) { doLogout(); return null; }
        // 缓存GET请求结果
        if(!opts.method) {
            apiCache[cacheKey] = {data: d, time: Date.now()};
        }
        return d;
    }).catch(function(e){ console.error('API Error:', e); return null; });
}

// 清除缓存
function clearApiCache() {
    apiCache = {};
}

function escapeJson(obj) {
    return JSON.stringify(obj).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function doExport2(table) {
    window.open('/api/export/' + table, '_blank');
}

function escapeJson(obj) {
    return JSON.stringify(obj).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function doExport2(table) {
    window.open('/api/export/' + table, '_blank');
}
