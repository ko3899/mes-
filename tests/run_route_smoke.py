"""遍历 Flask 路由，发现认证态请求中的未处理服务端异常。"""
import os
import re
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import create_app  # noqa: E402
from utils import database  # noqa: E402


TEST_DB = os.path.join(PROJECT_ROOT, 'database', 'route_smoke.db')
SKIP_ENDPOINTS = {
    'static',
    'upload_file',
    'download_file',
    'document.document_upload',
    'document.document_download',
    'backup.backup_download',
    'backup.backup_restore',
    'system_import',
    'update.update_download',
}
EXPECTED_UNAVAILABLE = {
    '/api/ai/inspect': 503,
    '/api/erp/kingdee/sync': 501,
    '/api/erp/sap/sync': 501,
    '/api/erp/sync/inventory': 501,
    '/api/erp/sync/orders': 501,
    '/api/erp/sync/products': 501,
    '/api/erp/yonyou/sync': 501,
    '/api/update/download': 501,
}


def materialize(rule):
    path = rule.rule
    path = re.sub(r'<(?:int|float):[^>]+>', '1', path)
    path = re.sub(r'<path:[^>]+>', 'sample.txt', path)
    path = re.sub(r'<[^>]+>', 'sample', path)
    return path


def run():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    original_path = database.DB_PATH
    try:
        database.DB_PATH = TEST_DB
        database.init_db()
        database._init_extra_tables()
        app = create_app()
        app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False, SECRET_KEY='route-smoke')
        client = app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = 1
            session['username'] = 'admin'

        failures = []
        checked = 0
        for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.rule, item.endpoint)):
            if rule.endpoint in SKIP_ENDPOINTS or not rule.rule.startswith('/api/'):
                continue
            path = materialize(rule)
            for method in sorted(rule.methods & {'GET', 'POST'}):
                checked += 1
                response = client.get(path) if method == 'GET' else client.post(path, json={})
                expected_status = EXPECTED_UNAVAILABLE.get(path)
                if response.status_code >= 500 and response.status_code != expected_status:
                    failures.append((method, path, response.status_code, response.get_data(as_text=True)[:300]))
        if failures:
            details = '\n'.join(f'{method} {path} -> {status}: {body}' for method, path, status, body in failures)
            raise AssertionError(f'{len(failures)} route(s) returned 5xx:\n{details}')
        print(f'PASS route smoke: {checked} authenticated GET/POST requests, no 5xx')
    finally:
        database.DB_PATH = original_path
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


if __name__ == '__main__':
    run()
