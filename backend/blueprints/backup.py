"""数据备份蓝图"""
import os
import shutil
import datetime
from flask import Blueprint, request, jsonify, send_file
from utils.database import get_db, DB_PATH, BASE_DIR
from utils.helpers import login_required

backup_bp = Blueprint('backup', __name__)

BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)


@backup_bp.route('/api/backup/list')
@login_required
def backup_list():
    db = get_db()
    rows = db.execute("SELECT * FROM sys_backup ORDER BY id DESC").fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@backup_bp.route('/api/backup/create', methods=['POST'])
@login_required
def backup_create():
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    backup_name = f"mes_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    shutil.copy2(DB_PATH, backup_path)
    file_size = os.path.getsize(backup_path)
    
    db = get_db()
    db.execute("INSERT INTO sys_backup (backup_name, file_path, file_size) VALUES (?,?,?)",
               (backup_name, backup_path, file_size))
    db.commit()
    return jsonify({'code': 0, 'message': '备份成功', 'data': {'name': backup_name}})


@backup_bp.route('/api/backup/restore', methods=['POST'])
@login_required
def backup_restore():
    d = request.json
    backup_id = d.get('id')
    db = get_db()
    backup = db.execute("SELECT * FROM sys_backup WHERE id=?", (backup_id,)).fetchone()
    if not backup:
        return jsonify({'code': 404, 'message': '备份不存在'})
    
    if not os.path.exists(backup['file_path']):
        return jsonify({'code': 404, 'message': '备份文件不存在'})
    
    shutil.copy2(backup['file_path'], DB_PATH)
    return jsonify({'code': 0, 'message': '恢复成功，请重启服务'})


@backup_bp.route('/api/backup/download/<int:backup_id>')
@login_required
def backup_download(backup_id):
    db = get_db()
    backup = db.execute("SELECT * FROM sys_backup WHERE id=?", (backup_id,)).fetchone()
    if not backup:
        return jsonify({'code': 404, 'message': '备份不存在'})
    return send_file(backup['file_path'], as_attachment=True, download_name=backup['backup_name'])


@backup_bp.route('/api/backup/delete', methods=['POST'])
@login_required
def backup_delete():
    d = request.json
    backup_id = d.get('id')
    db = get_db()
    backup = db.execute("SELECT * FROM sys_backup WHERE id=?", (backup_id,)).fetchone()
    if backup and os.path.exists(backup['file_path']):
        os.remove(backup['file_path'])
    db.execute("DELETE FROM sys_backup WHERE id=?", (backup_id,))
    db.commit()
    return jsonify({'code': 0, 'message': '删除成功'})
