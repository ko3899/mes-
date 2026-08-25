# -*- coding: utf-8 -*-
"""文档管理蓝图"""
import os
import secrets
import datetime

from flask import Blueprint, request, jsonify, session, send_file
from werkzeug.utils import secure_filename

from utils.database import get_db, BASE_DIR
from utils.helpers import login_required, crud_list, crud_delete, permission_required

document_bp = Blueprint('document', __name__)

UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads', 'documents')
ALLOWED_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.png', '.jpg', '.jpeg', '.gif',
}
os.makedirs(UPLOAD_DIR, exist_ok=True)


@document_bp.route('/api/document/list')
@login_required
def document_list():
    return jsonify(crud_list('sys_document', request.args))


@document_bp.route('/api/document/upload', methods=['POST'])
@permission_required('doc:write')
def document_upload():
    if 'file' not in request.files:
        return jsonify({'code': 400, 'message': '请选择文件'})

    file = request.files['file']
    if not file.filename:
        return jsonify({'code': 400, 'message': '文件名为空'})

    original_name = secure_filename(file.filename) or 'document'
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'code': 400, 'message': '不支持的文件类型'}), 400

    # 使用随机文件名，避免路径穿越/覆盖，同时保留原始文件名用于展示
    stored_name = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(8)}{ext}"
    filepath = os.path.join(UPLOAD_DIR, stored_name)
    file.save(filepath)

    db = get_db()
    db.execute(
        "INSERT INTO sys_document (doc_name, doc_type, category, file_path, file_size, uploader) "
        "VALUES (?,?,?,?,?,?)",
        (file.filename, request.form.get('doc_type', ''), request.form.get('category', ''),
         filepath, os.path.getsize(filepath), session.get('user_id')),
    )
    db.commit()
    return jsonify({'code': 0, 'message': '上传成功'})


@document_bp.route('/api/document/download/<int:doc_id>')
@login_required
def document_download(doc_id):
    db = get_db()
    doc = db.execute("SELECT * FROM sys_document WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        return jsonify({'code': 404, 'message': '文档不存在'})
    return send_file(doc['file_path'], as_attachment=True, download_name=doc['doc_name'])


@document_bp.route('/api/document/delete', methods=['POST'])
@permission_required('doc:write')
def document_delete():
    db = get_db()
    doc_id = request.json.get('id')
    doc = db.execute("SELECT * FROM sys_document WHERE id=?", (doc_id,)).fetchone()
    if doc and os.path.exists(doc['file_path']):
        os.remove(doc['file_path'])
    return jsonify(crud_delete('sys_document', doc_id))
