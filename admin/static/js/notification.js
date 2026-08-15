/* 通知模块 */
var lastNotifCount = 0;

function loadNotifications() {
    if(typeof curUser === 'undefined' || !curUser) return Promise.resolve(null);
    api('/api/notification/unread/count').then(function(r) {
        if (r && r.code === 0) {
            var count = r.data.count;
            var badge = document.getElementById('notifBadge');
            if (badge) {
                badge.textContent = count;
                badge.style.display = count > 0 ? 'block' : 'none';
            }
            // 新通知声音提醒
            if(count > lastNotifCount && lastNotifCount > 0) {
                playNotifSound();
                showBrowserNotification('新通知', '您有 ' + count + ' 条未读通知');
            }
            lastNotifCount = count;
        }
    });
}

// 播放通知声音
function playNotifSound() {
    try {
        var audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbsGczIj2NysijaTkmTaLC2rh1QjVHj7nWxa2AVjA+jLjR0bp6VSI0hLfNxaN+UjQ7h7rQ0bp+VCMzh7rOxaZ+VDM7iLzS0bp+VCM0h7rOxaZ+VDM7h7rOxaZ+VDM7h7rQ=');
        audio.volume = 0.3;
        audio.play().catch(function(){});
    } catch(e) {}
}

// 浏览器桌面通知
function showBrowserNotification(title, body) {
    if(!('Notification' in window)) return;
    if(Notification.permission === 'granted') {
        new Notification(title, {body: body, icon: '/favicon.ico'});
    } else if(Notification.permission !== 'denied') {
        Notification.requestPermission().then(function(permission) {
            if(permission === 'granted') {
                new Notification(title, {body: body, icon: '/favicon.ico'});
            }
        });
    }
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
                + '<span style="font-weight:' + (n.is_read ? 'normal' : 'bold') + '">' + typeIcon + ' ' + MESUI.escapeHtml(n.title || '') + '</span>'
                + '<span style="color:#999;font-size:12px">' + MESUI.escapeHtml(n.created_at || '') + '</span></div>'
                + '<div style="color:#666;font-size:13px;margin-top:4px">' + MESUI.escapeHtml(n.content || '') + '</div>'
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
setInterval(function() {
    if(typeof curUser !== 'undefined' && curUser) loadNotifications();
}, 30000);
