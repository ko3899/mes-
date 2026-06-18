/* 通知模块 */
function loadNotifications() {
    api('/api/notification/unread/count').then(function(r) {
        if (r && r.code === 0) {
            var badge = document.getElementById('notifBadge');
            if (badge) {
                badge.textContent = r.data.count;
                badge.style.display = r.data.count > 0 ? 'block' : 'none';
            }
        }
    });
}

function renderNotifications(el) {
    el.innerHTML = '<div class="card"><div class="card-title"><span>消息通知</span>'
        + '<button class="btn btn-blue" onclick="markAllRead()">全部已读</button></div>'
        + '<div id="notifList"><div class="empty">加载中...</div></div></div>';
    notifLoad();
}

function notifLoad() {
    api('/api/notification/list?size=50').then(function(r) {
        if (!r) return;
        var list = r.data && r.data.list ? r.data.list : [];
        var el = document.getElementById('notifList');
        if (!list.length) { el.innerHTML = '<div class="empty">暂无通知</div>'; return; }
        var h = '';
        list.forEach(function(n) {
            var typeIcon = {info: '📢', warning: '⚠️', error: '❌', success: '✅'}[n.type] || '📢';
            h += '<div style="padding:12px;border-bottom:1px solid #f0f0f0;cursor:pointer;transition:all 0.2s;'
                + (n.is_read ? 'opacity:0.6;' : 'background:#f6ffed;')
                + '" onclick="readNotif(' + n.id + ')">'
                + '<div style="display:flex;justify-content:space-between;align-items:center">'
                + '<span style="font-weight:' + (n.is_read ? 'normal' : 'bold') + '">' + typeIcon + ' ' + n.title + '</span>'
                + '<span style="color:#999;font-size:12px">' + (n.created_at || '') + '</span></div>'
                + '<div style="color:#666;font-size:13px;margin-top:4px">' + (n.content || '') + '</div>'
                + '</div>';
        });
        el.innerHTML = h;
    });
}

function readNotif(id) {
    api('/api/notification/read', {method: 'POST', body: {id: id}}).then(function() {
        loadNotifications();
        notifLoad();
    });
}

function markAllRead() {
    api('/api/notification/read', {method: 'POST', body: {all: true}}).then(function() {
        loadNotifications();
        notifLoad();
    });
}

// 定时刷新通知
setInterval(loadNotifications, 30000);
