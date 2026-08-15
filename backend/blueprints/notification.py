"""消息通知蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required

notification_bp = Blueprint('notification', __name__)


@notification_bp.route('/api/notification/list')
@login_required
def notification_list():
    db = get_db()
    user_id = session.get('user_id')
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    unread_only = request.args.get('unread', '0') == '1'

    where = "WHERE user_id=?"
    args = [user_id]
    if unread_only:
        where += " AND is_read=0"

    total = db.execute(f"SELECT COUNT(*) as cnt FROM sys_notification {where}", args).fetchone()['cnt']
    rows = db.execute(f"SELECT * FROM sys_notification {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                      args + [size, (page-1)*size]).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@notification_bp.route('/api/notification/unread/count')
@login_required
def unread_count():
    db = get_db()
    user_id = session.get('user_id')
    cnt = db.execute("SELECT COUNT(*) as c FROM sys_notification WHERE user_id=? AND is_read=0", (user_id,)).fetchone()['c']
    return jsonify({'code': 0, 'data': {'count': cnt}})


@notification_bp.route('/api/notification/read', methods=['POST'])
@login_required
def mark_read():
    db = get_db()
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    if data.get('all'):
        db.execute("UPDATE sys_notification SET is_read=1 WHERE user_id=?", (user_id,))
    else:
        if not data.get('id'):
            return jsonify({'code': 400, 'message': '缺少通知ID'}), 400
        cursor = db.execute("UPDATE sys_notification SET is_read=1 WHERE id=? AND user_id=?", (data['id'], user_id))
        if cursor.rowcount == 0:
            return jsonify({'code': 404, 'message': '通知不存在'}), 404
    db.commit()
    return jsonify({'code': 0})


def send_notification(user_id, title, content, ntype='info', link=''):
    """发送通知"""
    db = get_db()
    db.execute("INSERT INTO sys_notification (user_id, title, content, type, link) VALUES (?,?,?,?,?)",
               (user_id, title, content, ntype, link))
    db.commit()
