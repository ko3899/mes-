/* API 请求模块 */
var apiCache = {};
var apiCacheTTL = 5000; // 5秒缓存

function api(url, opts) {
    opts = opts || {};
    var o = {headers: {'Content-Type': 'application/json'}};
    if(opts.method) o.method = opts.method;
    if(opts.body) o.body = JSON.stringify(opts.body);

    var method = String(opts.method || 'GET').toUpperCase();
    var isGet = method === 'GET';

    // GET请求缓存
    var cacheKey = url + JSON.stringify(opts);
    if(isGet && apiCache[cacheKey]) {
        var cached = apiCache[cacheKey];
        if(Date.now() - cached.time < apiCacheTTL) {
            return Promise.resolve(cached.data);
        }
    }

    return fetch(url, o).then(function(response) {
        if(response.status === 401) doLogout();
        var contentType = response.headers && response.headers.get
            ? response.headers.get('content-type') || ''
            : '';
        if(contentType.toLowerCase().indexOf('json') === -1) {
            return {
                code: response.status,
                message: '请求失败（HTTP ' + response.status + '）'
            };
        }

        return response.json().then(function(data) {
            if(!data || typeof data !== 'object') {
                data = {code: response.ok ? 0 : response.status, data: data};
            }
            if(!response.ok) {
                if(data.code == null || data.code === 0) data.code = response.status;
                if(!data.message) {
                    data.message = '请求失败（HTTP ' + response.status + '）';
                }
            }
            if(response.status !== 401 && data.code === 401) doLogout();

            if(isGet && response.ok && data.code === 0) {
                apiCache[cacheKey] = {data: data, time: Date.now()};
            } else if(!isGet && response.ok && data.code === 0) {
                clearApiCache();
            }
            return data;
        }, function(error) {
            console.error('API Parse Error:', error);
            return {
                code: response.status || -1,
                message: '请求失败（HTTP ' + response.status + '）'
            };
        });
    }, function(error) {
        console.error('API Error:', error);
        return {code: -1, message: '网络请求失败'};
    });
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
