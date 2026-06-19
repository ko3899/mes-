"""自动更新模块"""
import os
import json
import hashlib
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(BASE_DIR, 'version.json')
UPDATE_URL = "https://gitee.com/api/v5/repos/korean-wave-enthusiast/mes-system/releases/latest"


def get_current_version():
    """获取当前版本"""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'version': '1.0.0', 'build': '20260619'}


def check_update():
    """检查更新"""
    try:
        resp = requests.get(UPDATE_URL, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            remote_version = data.get('tag_name', '').replace('v', '')
            current = get_current_version()
            
            if remote_version > current['version']:
                return {
                    'has_update': True,
                    'current': current['version'],
                    'latest': remote_version,
                    'download_url': data.get('zipball_url', ''),
                    'changelog': data.get('body', '')
                }
        return {'has_update': False, 'current': get_current_version()['version']}
    except Exception as e:
        return {'has_update': False, 'error': str(e)}


def update_version(version, build=None):
    """更新版本号"""
    data = {
        'version': version,
        'build': build or datetime.now().strftime('%Y%m%d'),
        'updated_at': datetime.now().isoformat()
    }
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data
