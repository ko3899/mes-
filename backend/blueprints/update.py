"""自动更新API"""
import os
import json
from flask import Blueprint, request, jsonify, send_file
from utils.database import BASE_DIR

update_bp = Blueprint('update', __name__)


@update_bp.route('/api/update/check')
def check_update():
    """检查更新"""
    version_file = os.path.join(BASE_DIR, 'version.json')
    if os.path.exists(version_file):
        with open(version_file, 'r', encoding='utf-8') as f:
            version = json.load(f)
        return jsonify({'code': 0, 'data': version})
    return jsonify({'code': 0, 'data': {'version': '1.0.0'}})


@update_bp.route('/api/update/download')
def download_update():
    """下载更新包"""
    return jsonify({'code': 0, 'message': '请从 Gitee 下载最新版本'})


@update_bp.route('/api/version')
def get_version():
    """获取当前版本"""
    version_file = os.path.join(BASE_DIR, 'version.json')
    if os.path.exists(version_file):
        with open(version_file, 'r', encoding='utf-8') as f:
            return jsonify({'code': 0, 'data': json.load(f)})
    return jsonify({'code': 0, 'data': {'version': '1.0.0'}})
