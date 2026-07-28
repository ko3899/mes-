"""MES工厂管家 - 综合Pytest测试套件"""
import os
import sys
import hashlib
import sqlite3
import tempfile
import json
import uuid
import pytest
from flask import jsonify, session

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from app import create_app
from utils.database import DB_PATH, init_db, _init_extra_tables, get_db
from utils.helpers import permission_required


TEST_DB_PATH = None


@pytest.fixture(scope='session')
def app():
    global TEST_DB_PATH
    TEST_DB_PATH = tempfile.mktemp(suffix='.db')
    _setup_test_db(TEST_DB_PATH)

    import utils.database as db_mod
    db_mod.DB_PATH = TEST_DB_PATH

    application = create_app()
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret-key'
    yield application

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    resp = client.post('/api/login', json={'username': 'admin', 'password': 'admin123'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('code') == 0
    return client


@pytest.fixture()
def plain_auth_client(app):
    username = f"plain_{os.urandom(6).hex()}"
    password = 'plainpass123'
    with app.app_context():
        db = get_db()
        role = db.execute(
            "INSERT INTO sys_role (role_name, role_key, menu_ids) VALUES (?,?,?)",
            (f'{username}角色', f'{username}_role', json.dumps(['sys:user:list'])),
        )
        role_id = role.lastrowid
        user = db.execute(
            "INSERT INTO sys_user (username, password, role_id) VALUES (?,?,?)",
            (username, hashlib.md5(password.encode()).hexdigest(), role_id),
        )
        user_id = user.lastrowid
        db.commit()

    plain = app.test_client()
    response = plain.post('/api/login', json={
        'username': username,
        'password': password,
    })
    assert response.get_json()['code'] == 0
    plain.user_id = user_id
    plain.role_id = role_id
    plain.username = username
    plain.password = password
    return plain


def _setup_test_db(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys = ON")

    db.executescript('''
        CREATE TABLE IF NOT EXISTS sys_user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            real_name TEXT, phone TEXT, email TEXT,
            dept_id INTEGER, role_id INTEGER, tenant_id INTEGER DEFAULT 1,
            status INTEGER DEFAULT 1, avatar TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sys_role (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL, role_key TEXT NOT NULL UNIQUE,
            description TEXT, menu_ids TEXT, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sys_dept (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_name TEXT NOT NULL, parent_id INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0, leader TEXT, phone TEXT,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sys_menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_name TEXT NOT NULL, parent_id INTEGER DEFAULT 0,
            path TEXT, component TEXT, icon TEXT,
            sort_order INTEGER DEFAULT 0, menu_type TEXT DEFAULT 'M',
            perms TEXT, status INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS sys_dict (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dict_type TEXT NOT NULL, dict_label TEXT NOT NULL,
            dict_value TEXT NOT NULL, sort_order INTEGER DEFAULT 0,
            status INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS sys_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, operation TEXT,
            method TEXT, url TEXT, ip TEXT, params TEXT,
            result TEXT, cost_time INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sys_login_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, login_ip TEXT, status INTEGER DEFAULT 1,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sys_numbering (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prefix TEXT NOT NULL, entity_type TEXT NOT NULL UNIQUE,
            current_no INTEGER DEFAULT 0, digit_count INTEGER DEFAULT 6,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS sys_notification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, title TEXT NOT NULL,
            content TEXT, type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0, link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES sys_user(id)
        );
        CREATE TABLE IF NOT EXISTS sys_barcode (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT NOT NULL, biz_type TEXT, biz_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS base_workshop (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workshop_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            description TEXT, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS base_process (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            workshop_id INTEGER, description TEXT,
            standard_time REAL, sort_order INTEGER DEFAULT 0,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workshop_id) REFERENCES base_workshop(id)
        );
        CREATE TABLE IF NOT EXISTS base_product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            specification TEXT, unit TEXT, product_type TEXT,
            description TEXT, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS base_bom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL, material_id INTEGER NOT NULL,
            quantity REAL NOT NULL, unit TEXT, description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES base_product(id),
            FOREIGN KEY (material_id) REFERENCES base_product(id)
        );
        CREATE TABLE IF NOT EXISTS base_process_route (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL, route_name TEXT NOT NULL,
            description TEXT, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES base_product(id)
        );
        CREATE TABLE IF NOT EXISTS base_defect (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            defect_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            defect_type TEXT, description TEXT, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS base_unit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_name TEXT NOT NULL, unit_symbol TEXT NOT NULL,
            status INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS base_supplier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            contact TEXT, phone TEXT, address TEXT,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS base_customer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            contact TEXT, phone TEXT, address TEXT,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS inv_inbound (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inbound_no TEXT NOT NULL UNIQUE, inbound_type TEXT,
            supplier TEXT, total_amount REAL DEFAULT 0,
            status INTEGER DEFAULT 0, remark TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS inv_outbound (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            outbound_no TEXT NOT NULL UNIQUE, outbound_type TEXT,
            customer TEXT, total_amount REAL DEFAULT 0,
            status INTEGER DEFAULT 0, remark TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS inv_balance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL UNIQUE,
            quantity REAL DEFAULT 0, amount REAL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES base_product(id)
        );
        CREATE TABLE IF NOT EXISTS inv_batch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_no TEXT NOT NULL, product_id INTEGER,
            supplier TEXT, quantity REAL DEFAULT 0,
            production_date TEXT, expiry_date TEXT,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS inv_trace (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL, trace_type TEXT,
            ref_no TEXT, ref_id INTEGER, quantity REAL,
            operator INTEGER, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES inv_batch(id)
        );
        CREATE TABLE IF NOT EXISTS prod_sales_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL UNIQUE, customer TEXT NOT NULL,
            contact TEXT, phone TEXT, total_amount REAL DEFAULT 0,
            delivery_date TEXT, status INTEGER DEFAULT 0,
            remark TEXT, created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS prod_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_no TEXT NOT NULL UNIQUE, sales_order_id INTEGER,
            plan_type TEXT, start_date TEXT, end_date TEXT,
            status INTEGER DEFAULT 0, remark TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS prod_workorder (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL UNIQUE, plan_id INTEGER,
            sales_order_id INTEGER, product_id INTEGER NOT NULL,
            route_id INTEGER, planned_qty REAL NOT NULL,
            completed_qty REAL DEFAULT 0, defect_qty REAL DEFAULT 0,
            workshop_id INTEGER, priority INTEGER DEFAULT 1,
            status INTEGER DEFAULT 0, start_date TEXT, end_date TEXT,
            remark TEXT, created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES base_product(id)
        );
        CREATE TABLE IF NOT EXISTS prod_task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_no TEXT NOT NULL UNIQUE, workorder_id INTEGER NOT NULL,
            process_id INTEGER NOT NULL, assigned_to INTEGER,
            planned_qty REAL NOT NULL, completed_qty REAL DEFAULT 0,
            defect_qty REAL DEFAULT 0, status INTEGER DEFAULT 0,
            start_time TIMESTAMP, end_time TIMESTAMP, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id),
            FOREIGN KEY (process_id) REFERENCES base_process(id)
        );
        CREATE TABLE IF NOT EXISTS prod_report (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_no TEXT NOT NULL UNIQUE, task_id INTEGER NOT NULL,
            workorder_id INTEGER NOT NULL, process_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, qualified_qty REAL NOT NULL,
            defect_qty REAL DEFAULT 0,
            report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            remark TEXT,
            FOREIGN KEY (task_id) REFERENCES prod_task(id),
            FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id)
        );
        CREATE TABLE IF NOT EXISTS qm_incoming_inspection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inspect_no TEXT NOT NULL UNIQUE, inbound_id INTEGER,
            supplier TEXT, template_id INTEGER, result TEXT,
            status INTEGER DEFAULT 0, inspector INTEGER,
            inspect_time TIMESTAMP, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS qm_process_inspection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inspect_no TEXT NOT NULL UNIQUE, workorder_id INTEGER,
            task_id INTEGER, template_id INTEGER, result TEXT,
            status INTEGER DEFAULT 0, inspector INTEGER,
            inspect_time TIMESTAMP, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS qm_outgoing_inspection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inspect_no TEXT NOT NULL UNIQUE, outbound_id INTEGER,
            customer TEXT, template_id INTEGER, result TEXT,
            status INTEGER DEFAULT 0, inspector INTEGER,
            inspect_time TIMESTAMP, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS eqp_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            description TEXT, status INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS eqp_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            type_id INTEGER, model TEXT, manufacturer TEXT,
            purchase_date TEXT, workshop_id INTEGER, location TEXT,
            status INTEGER DEFAULT 1, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (type_id) REFERENCES eqp_type(id)
        );
        CREATE TABLE IF NOT EXISTS eqp_repair_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_no TEXT NOT NULL UNIQUE, equipment_id INTEGER NOT NULL,
            fault_desc TEXT, repair_desc TEXT, reporter INTEGER,
            repairer INTEGER, status INTEGER DEFAULT 0,
            report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            repair_time TIMESTAMP, remark TEXT,
            FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id)
        );
        CREATE TABLE IF NOT EXISTS eqp_maintenance_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name TEXT NOT NULL, equipment_id INTEGER NOT NULL,
            check_items TEXT, frequency TEXT, next_date TEXT,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id)
        );
        CREATE TABLE IF NOT EXISTS eqp_check_workorder (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workorder_no TEXT NOT NULL UNIQUE, plan_id INTEGER NOT NULL,
            equipment_id INTEGER NOT NULL, check_result TEXT,
            status INTEGER DEFAULT 0, assigned_to INTEGER,
            check_time TIMESTAMP, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES eqp_maintenance_plan(id),
            FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id)
        );
        CREATE TABLE IF NOT EXISTS tool_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            description TEXT, status INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS tool_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            type_id INTEGER, specification TEXT,
            quantity REAL DEFAULT 0, location TEXT,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (type_id) REFERENCES tool_type(id)
        );
        CREATE TABLE IF NOT EXISTS tool_borrow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrow_no TEXT NOT NULL UNIQUE, tool_id INTEGER NOT NULL,
            borrower INTEGER NOT NULL, borrow_qty REAL NOT NULL,
            borrow_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            return_time TIMESTAMP, return_qty REAL DEFAULT 0,
            status INTEGER DEFAULT 0, remark TEXT,
            FOREIGN KEY (tool_id) REFERENCES tool_ledger(id)
        );
        CREATE TABLE IF NOT EXISTS sched_team (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
            leader TEXT, member_count INTEGER DEFAULT 0,
            workshop_id INTEGER, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sched_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name TEXT NOT NULL, team_id INTEGER NOT NULL,
            start_date TEXT NOT NULL, end_date TEXT NOT NULL,
            shift_type TEXT, status INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES sched_team(id)
        );
        CREATE TABLE IF NOT EXISTS flow_definition (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_name TEXT NOT NULL, flow_key TEXT NOT NULL UNIQUE,
            description TEXT, steps TEXT, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS flow_instance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_id INTEGER NOT NULL, biz_type TEXT, biz_id INTEGER,
            title TEXT, current_step INTEGER DEFAULT 1,
            status INTEGER DEFAULT 0, creator INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (flow_id) REFERENCES flow_definition(id)
        );
        CREATE TABLE IF NOT EXISTS flow_task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id INTEGER NOT NULL, step_no INTEGER NOT NULL,
            assignee INTEGER NOT NULL, action TEXT, comment TEXT,
            status INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (instance_id) REFERENCES flow_instance(id)
        );
        CREATE TABLE IF NOT EXISTS sys_document (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name TEXT NOT NULL, doc_type TEXT, category TEXT,
            file_path TEXT, file_size INTEGER, uploader INTEGER,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS prod_cost (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workorder_id INTEGER, cost_type TEXT, amount REAL DEFAULT 0,
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sys_backup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backup_name TEXT NOT NULL, file_path TEXT, file_size INTEGER,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    pwd = hashlib.md5('admin123'.encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO sys_user (username, password, real_name, phone, status) VALUES (?,?,?,?,?)",
               ('admin', pwd, '系统管理员', '13800000000', 1))

    db.execute("INSERT OR IGNORE INTO sys_role (role_name, role_key, description, menu_ids) VALUES (?,?,?,?)",
               ('超级管理员', 'admin', '拥有所有权限', ''))
    db.execute("INSERT OR IGNORE INTO sys_role (role_name, role_key, description, menu_ids) VALUES (?,?,?,?)",
               ('普通用户', 'user', '普通用户权限', ''))

    db.execute("INSERT OR IGNORE INTO sys_dept (dept_name, parent_id, sort_order) VALUES (?,?,?)", ('总经办', 0, 1))
    db.execute("INSERT OR IGNORE INTO sys_dept (dept_name, parent_id, sort_order) VALUES (?,?,?)", ('生产部', 0, 2))

    db.commit()
    db.close()


# ==================== Helper Functions ====================

def login(client, username='admin', password='admin123'):
    return client.post('/api/login', json={'username': username, 'password': password})


def assert_success(resp, expect_code=0):
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None, "Response is not JSON"
    assert data.get('code') == expect_code, f"Expected code {expect_code}, got {data.get('code')}: {data.get('message')}"
    return data


def response_id(response):
    payload = response.get_json()
    assert payload['code'] == 0, payload
    return payload['data']['id']


def create_production_chain(client, planned_qty=10):
    suffix = uuid.uuid4().hex[:8]
    workshop_id = response_id(client.post('/api/base/workshop/add', json={
        'workshop_name': f'报工车间-{suffix}',
        'code': f'WS_{suffix}',
    }))
    process_id = response_id(client.post('/api/base/process/add', json={
        'process_name': f'报工工序-{suffix}',
        'code': f'PS_{suffix}',
        'workshop_id': workshop_id,
    }))
    product_id = response_id(client.post('/api/base/product/add', json={
        'product_name': f'报工产品-{suffix}',
        'code': f'PD_{suffix}',
        'unit': '件',
    }))
    workorder_id = response_id(client.post('/api/prod/workorder/add', json={
        'product_id': product_id,
        'workshop_id': workshop_id,
        'planned_qty': planned_qty,
    }))
    task_id = response_id(client.post('/api/prod/task/add', json={
        'workorder_id': workorder_id,
        'process_id': process_id,
        'planned_qty': planned_qty,
    }))
    return {
        'workshop_id': workshop_id,
        'process_id': process_id,
        'product_id': product_id,
        'workorder_id': workorder_id,
        'task_id': task_id,
    }


def find_by_id(payload, row_id):
    return next(row for row in payload['data']['list'] if row['id'] == row_id)


def assert_fail(resp, expect_code=400):
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get('code') == expect_code, f"Expected code {expect_code}, got {data.get('code')}"
    return data


def assert_unauthorized(resp):
    assert resp.status_code == 401
    data = resp.get_json()
    assert data.get('code') == 401


# ==================== 1. Authentication Tests ====================

class TestAuthentication:
    def test_login_success(self, client):
        resp = login(client)
        data = assert_success(resp)
        assert data['data']['username'] == 'admin'
        assert data['data']['real_name'] == '系统管理员'

    def test_login_wrong_password(self, client):
        resp = login(client, 'admin', 'wrongpassword')
        data = resp.get_json()
        assert data.get('code') == 400
        assert '错误' in data.get('message', '')

    def test_login_wrong_username(self, client):
        resp = login(client, 'nonexistent', 'admin123')
        data = resp.get_json()
        assert data.get('code') == 400

    def test_login_empty_credentials(self, client):
        resp = client.post('/api/login', json={'username': '', 'password': ''})
        data = resp.get_json()
        assert data.get('code') == 400

    def test_login_no_body(self, client):
        resp = client.post('/api/login', json={})
        data = resp.get_json()
        assert data.get('code') == 400

    def test_logout(self, auth_client):
        resp = auth_client.post('/api/logout')
        assert_success(resp)
        resp = auth_client.get('/api/user/info')
        assert_unauthorized(resp)

    def test_user_info(self, auth_client):
        resp = auth_client.get('/api/user/info')
        data = assert_success(resp)
        assert data['data']['username'] == 'admin'
        assert 'password' not in data['data']

    def test_captcha(self, client):
        resp = client.get('/api/captcha')
        data = assert_success(resp)
        assert 'key' in data['data']
        assert 'hint' in data['data']

    def test_protected_endpoint_no_login(self, client):
        endpoints = [
            '/api/user/info', '/api/dashboard', '/api/sys/user/list',
            '/api/base/product/list', '/api/prod/workorder/list',
            '/api/inv/balance/list', '/api/notification/list',
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 401, f"Expected 401 for {ep}"

    def test_protected_post_no_login(self, client):
        endpoints = [
            '/api/base/product/add', '/api/prod/workorder/add',
            '/api/base/supplier/add',
        ]
        for ep in endpoints:
            resp = client.post(ep, json={})
            assert resp.status_code == 401, f"Expected 401 for {ep}"


# ==================== 2. System Management Tests ====================

class TestSystemManagement:
    def test_user_list(self, auth_client):
        resp = auth_client.get('/api/sys/user/list')
        data = assert_success(resp)
        assert 'list' in data['data']
        assert data['data']['total'] >= 1

    def test_user_add_and_delete(self, auth_client):
        resp = auth_client.post('/api/sys/user/add', json={
            'username': 'testuser001', 'password': 'test123456',
            'real_name': '测试用户', 'phone': '13900000001'
        })
        data = assert_success(resp)
        user_id = data['data']['id']

        resp = auth_client.get('/api/sys/user/list')
        data = assert_success(resp)
        usernames = [u['username'] for u in data['data']['list']]
        assert 'testuser001' in usernames

        resp = auth_client.post('/api/sys/user/delete', json={'id': user_id})
        assert_success(resp)

    def test_user_update(self, auth_client):
        resp = auth_client.post('/api/sys/user/add', json={
            'username': 'upduser001', 'password': 'test123', 'real_name': '原名'
        })
        user_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/sys/user/update', json={
            'id': user_id, 'real_name': '新名称', 'phone': '13999999999'
        })
        assert_success(resp)

        resp = auth_client.get('/api/sys/user/list')
        users = assert_success(resp)['data']['list']
        updated = [u for u in users if u['id'] == user_id][0]
        assert updated['real_name'] == '新名称'

        auth_client.post('/api/sys/user/delete', json={'id': user_id})

    def test_role_list(self, auth_client):
        resp = auth_client.get('/api/sys/role/list')
        data = assert_success(resp)
        assert data['data']['total'] >= 2

    def test_dept_list(self, auth_client):
        resp = auth_client.get('/api/sys/dept/list')
        data = assert_success(resp)
        assert data['data']['total'] >= 2

    def test_menu_list(self, auth_client):
        resp = auth_client.get('/api/sys/menu/list')
        data = assert_success(resp)
        assert isinstance(data['data'], list)

    def test_dict_list(self, auth_client):
        resp = auth_client.get('/api/sys/dict/list')
        data = assert_success(resp)
        assert 'list' in data['data']

    def test_log_list(self, auth_client):
        resp = auth_client.get('/api/sys/log/list')
        data = assert_success(resp)
        assert 'list' in data['data']

    def test_dept_crud(self, auth_client):
        resp = auth_client.post('/api/sys/dept/add', json={
            'dept_name': '测试部门', 'sort_order': 99
        })
        dept_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/sys/dept/update', json={
            'id': dept_id, 'dept_name': '已更新部门'
        })
        assert_success(resp)

        resp = auth_client.post('/api/sys/dept/delete', json={'id': dept_id})
        assert_success(resp)

    def test_dict_crud(self, auth_client):
        resp = auth_client.post('/api/sys/dict/add', json={
            'dict_type': 'test_type', 'dict_label': '测试', 'dict_value': 'test'
        })
        dict_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/sys/dict/update', json={
            'id': dict_id, 'dict_label': '已更新'
        })
        assert_success(resp)

        resp = auth_client.post('/api/sys/dict/delete', json={'id': dict_id})
        assert_success(resp)


def _create_permission_user(app, username, menu_ids):
    with app.app_context():
        db = get_db()
        role = db.execute(
            "INSERT INTO sys_role (role_name, role_key, menu_ids) VALUES (?,?,?)",
            (f'{username}角色', f'{username}_role', menu_ids),
        )
        user = db.execute(
            "INSERT INTO sys_user (username, password, role_id) VALUES (?,?,?)",
            (username, 'not-used-by-this-test', role.lastrowid),
        )
        db.commit()
        return user.lastrowid


def _call_permission_guard(app, user_id, username, *perms):
    protected = permission_required(*perms)(
        lambda: jsonify({'code': 0, 'message': 'allowed'})
    )
    with app.test_request_context('/permission-test'):
        session['user_id'] = user_id
        session['username'] = username
        result = protected()
        if isinstance(result, tuple):
            response, status = result
        else:
            response, status = result, result.status_code
        return status, response.get_json()


SYSTEM_WRITE_CASES = [
    ('/api/sys/user/add', {'username': 'blocked_user', 'password': 'blocked123'}),
    ('/api/sys/user/update', {'id': 999999, 'real_name': 'blocked'}),
    ('/api/sys/user/delete', {'id': 999999}),
    ('/api/sys/role/add', {'role_name': 'blocked', 'role_key': 'blocked_role'}),
    ('/api/sys/role/update', {'id': 999999, 'role_name': 'blocked'}),
    ('/api/sys/role/delete', {'id': 999999}),
    ('/api/sys/dept/add', {'dept_name': 'blocked'}),
    ('/api/sys/dept/update', {'id': 999999, 'dept_name': 'blocked'}),
    ('/api/sys/dept/delete', {'id': 999999}),
    ('/api/sys/menu/add', {'menu_name': 'blocked'}),
    ('/api/sys/menu/update', {'id': 999999, 'menu_name': 'blocked'}),
    ('/api/sys/menu/delete', {'id': 999999}),
    ('/api/sys/dict/add', {
        'dict_type': 'blocked',
        'dict_label': 'blocked',
        'dict_value': 'blocked',
    }),
    ('/api/sys/dict/update', {'id': 999999, 'dict_label': 'blocked'}),
    ('/api/sys/dict/delete', {'id': 999999}),
]

SYSTEM_IMPORT_TABLES = ['sys_user', 'sys_role', 'sys_dept', 'sys_menu', 'sys_dict']


class TestAuthorization:
    def test_plain_user_cannot_write_system_data(self, auth_client, client):
        created = auth_client.post('/api/sys/user/add', json={
            'username': 'plain_operator',
            'password': 'operator123',
            'real_name': '普通操作员',
        }).get_json()
        assert created['code'] == 0

        plain = client.application.test_client()
        login_response = plain.post('/api/login', json={
            'username': 'plain_operator',
            'password': 'operator123',
        })
        assert login_response.get_json()['code'] == 0

        response = plain.post('/api/sys/dept/add', json={'dept_name': '越权部门'})
        assert response.status_code == 403
        assert response.get_json()['code'] == 403

    def test_admin_can_still_write_system_data(self, auth_client):
        response = auth_client.post(
            '/api/sys/dept/add',
            json={'dept_name': '授权部门'},
        )
        assert response.status_code == 200
        assert response.get_json()['code'] == 0

    @pytest.mark.parametrize(('route', 'payload'), SYSTEM_WRITE_CASES)
    def test_all_system_writes_reject_plain_users(
        self,
        plain_auth_client,
        route,
        payload,
    ):
        response = plain_auth_client.post(route, json=payload)

        assert response.status_code == 403
        assert response.get_json()['code'] == 403

    @pytest.mark.parametrize(('route', 'payload'), SYSTEM_WRITE_CASES)
    def test_all_system_writes_reject_unauthenticated_users(
        self,
        client,
        route,
        payload,
    ):
        response = client.post(route, json=payload)

        assert response.status_code == 401
        assert response.get_json()['code'] == 401

    def test_plain_user_can_still_read_system_data(self, plain_auth_client):
        response = plain_auth_client.get('/api/sys/dept/list')

        assert response.status_code == 200
        assert response.get_json()['code'] == 0

    @pytest.mark.parametrize('table', SYSTEM_IMPORT_TABLES)
    def test_plain_user_cannot_import_system_tables(
        self,
        plain_auth_client,
        table,
    ):
        response = plain_auth_client.post(f'/api/import/{table}')

        assert response.status_code == 403
        assert response.get_json()['code'] == 403

    @pytest.mark.parametrize('table', SYSTEM_IMPORT_TABLES)
    def test_admin_reaches_existing_system_import_validation(
        self,
        auth_client,
        table,
    ):
        response = auth_client.post(f'/api/import/{table}')

        assert response.status_code != 403
        assert response.get_json()['code'] == 400

    @pytest.mark.parametrize(
        ('route', 'payload_key'),
        [
            ('/api/sys/user/reset-password', 'user'),
            ('/api/sys/role/permissions', 'role'),
        ],
    )
    def test_plain_user_cannot_reset_passwords_or_change_role_permissions(
        self,
        plain_auth_client,
        route,
        payload_key,
    ):
        payload = (
            {'user_id': plain_auth_client.user_id, 'new_password': 'hackedpass'}
            if payload_key == 'user'
            else {'role_id': plain_auth_client.role_id, 'menu_ids': 'sys:admin'}
        )

        response = plain_auth_client.post(route, json=payload)

        assert response.status_code == 403
        assert response.get_json()['code'] == 403

    @pytest.mark.parametrize(
        ('route', 'payload'),
        [
            ('/api/sys/user/reset-password', {'user_id': 1, 'new_password': 'newpass'}),
            ('/api/sys/role/permissions', {'role_id': 1, 'menu_ids': 'sys:admin'}),
        ],
    )
    def test_admin_only_system_extensions_reject_unauthenticated_users(
        self,
        client,
        route,
        payload,
    ):
        response = client.post(route, json=payload)

        assert response.status_code == 401
        assert response.get_json()['code'] == 401

    def test_plain_user_can_change_own_password(self, plain_auth_client):
        response = plain_auth_client.post('/api/sys/user/change-password', json={
            'old_password': plain_auth_client.password,
            'new_password': 'newplainpass',
        })

        assert response.status_code == 200
        assert response.get_json()['code'] == 0

    def test_plain_user_can_read_role_permissions(self, plain_auth_client):
        response = plain_auth_client.get(
            f'/api/sys/role/permissions/{plain_auth_client.role_id}'
        )

        assert response.status_code == 200
        assert response.get_json()['code'] == 0

    def test_admin_can_reset_password_and_change_role_permissions(
        self,
        auth_client,
        plain_auth_client,
    ):
        reset = auth_client.post('/api/sys/user/reset-password', json={
            'user_id': plain_auth_client.user_id,
            'new_password': 'adminreset',
        })
        permissions = auth_client.post('/api/sys/role/permissions', json={
            'role_id': plain_auth_client.role_id,
            'menu_ids': json.dumps(['sys:admin']),
        })

        assert reset.status_code == 200
        assert reset.get_json()['code'] == 0
        assert permissions.status_code == 200
        assert permissions.get_json()['code'] == 0

    def test_permission_required_fails_closed(self, app):
        user_id = _create_permission_user(
            app,
            'permission_denied_user',
            json.dumps(['sys:user:list']),
        )

        empty_status, empty_body = _call_permission_guard(
            app,
            user_id,
            'permission_denied_user',
        )
        missing_status, missing_body = _call_permission_guard(
            app,
            user_id,
            'permission_denied_user',
            'sys:user:write',
        )

        assert empty_status == 403
        assert empty_body['code'] == 403
        assert missing_status == 403
        assert missing_body['code'] == 403

    @pytest.mark.parametrize(
        ('username', 'stored_permissions'),
        [
            ('permission_corrupt_user', '[not-valid-json'),
            ('permission_empty_user', None),
        ],
    )
    def test_permission_required_rejects_corrupt_or_empty_permissions(
        self,
        app,
        username,
        stored_permissions,
    ):
        user_id = _create_permission_user(app, username, stored_permissions)

        status, body = _call_permission_guard(
            app,
            user_id,
            username,
            'sys:user:write',
        )

        assert status == 403
        assert body['code'] == 403

    def test_permission_required_rejects_missing_user_or_role(self, app):
        missing_user_status, missing_user_body = _call_permission_guard(
            app,
            987654321,
            'missing_user',
            'sys:user:write',
        )
        with app.app_context():
            db = get_db()
            user = db.execute(
                "INSERT INTO sys_user (username, password, role_id) VALUES (?,?,?)",
                ('missing_role_user', 'not-used', 987654321),
            )
            db.commit()
            missing_role_user_id = user.lastrowid
        missing_role_status, missing_role_body = _call_permission_guard(
            app,
            missing_role_user_id,
            'missing_role_user',
            'sys:user:write',
        )

        assert missing_user_status == 403
        assert missing_user_body['code'] == 403
        assert missing_role_status == 403
        assert missing_role_body['code'] == 403

    @pytest.mark.parametrize(
        ('username', 'stored_permissions'),
        [
            ('permission_json_user', json.dumps(['sys:user:list', 'sys:user:write'])),
            ('permission_legacy_user', 'sys:user:list, sys:user:write'),
        ],
    )
    def test_permission_required_accepts_json_and_legacy_formats(
        self,
        app,
        username,
        stored_permissions,
    ):
        user_id = _create_permission_user(app, username, stored_permissions)

        status, body = _call_permission_guard(
            app,
            user_id,
            username,
            'sys:user:write',
        )

        assert status == 200
        assert body['code'] == 0


# ==================== 3. Base Data Tests ====================

class TestBaseData:
    def test_workshop_list(self, auth_client):
        resp = auth_client.get('/api/base/workshop/list')
        assert_success(resp)

    def test_workshop_crud(self, auth_client):
        resp = auth_client.post('/api/base/workshop/add', json={
            'workshop_name': '测试车间', 'code': 'WS_TEST', 'description': '测试'
        })
        ws_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/workshop/update', json={
            'id': ws_id, 'workshop_name': '更新车间'
        })
        assert_success(resp)

        resp = auth_client.post('/api/base/workshop/delete', json={'id': ws_id})
        assert_success(resp)

    def test_workshop_duplicate_code(self, auth_client):
        auth_client.post('/api/base/workshop/add', json={
            'workshop_name': '车间A', 'code': 'WS_DUP'
        })
        resp = auth_client.post('/api/base/workshop/add', json={
            'workshop_name': '车间B', 'code': 'WS_DUP'
        })
        data = resp.get_json()
        assert data.get('code') != 0
        auth_client.post('/api/base/workshop/delete', json={'id': data.get('data', {}).get('id', 0)})

    def test_process_list(self, auth_client):
        resp = auth_client.get('/api/base/process/list')
        assert_success(resp)

    def test_product_list(self, auth_client):
        resp = auth_client.get('/api/base/product/list')
        assert_success(resp)

    def test_product_crud(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '测试产品', 'code': 'PRD_TEST', 'unit': '个',
            'specification': '10x10', 'product_type': '成品'
        })
        prd_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/product/update', json={
            'id': prd_id, 'product_name': '更新产品'
        })
        assert_success(resp)

        resp = auth_client.get('/api/base/product/all')
        data = assert_success(resp)
        names = [p['product_name'] for p in data['data']]
        assert '更新产品' in names

        resp = auth_client.post('/api/base/product/delete', json={'id': prd_id})
        assert_success(resp)

    def test_product_duplicate_code(self, auth_client):
        auth_client.post('/api/base/product/add', json={
            'product_name': '产品X', 'code': 'PRD_DUP', 'unit': '个'
        })
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '产品Y', 'code': 'PRD_DUP', 'unit': '个'
        })
        data = resp.get_json()
        assert data.get('code') != 0

    def test_bom_list(self, auth_client):
        resp = auth_client.get('/api/base/bom/list')
        assert_success(resp)

    def test_defect_list(self, auth_client):
        resp = auth_client.get('/api/base/defect/list')
        assert_success(resp)

    def test_defect_crud(self, auth_client):
        resp = auth_client.post('/api/base/defect/add', json={
            'defect_name': '划伤', 'code': 'DEF_TEST', 'defect_type': '外观'
        })
        def_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/defect/update', json={
            'id': def_id, 'defect_name': '深度划伤'
        })
        assert_success(resp)

        resp = auth_client.post('/api/base/defect/delete', json={'id': def_id})
        assert_success(resp)

    def test_unit_list(self, auth_client):
        resp = auth_client.get('/api/base/unit/list')
        data = assert_success(resp)
        assert 'list' in data['data']

    def test_unit_crud(self, auth_client):
        resp = auth_client.post('/api/base/unit/add', json={
            'unit_name': '测试单位', 'unit_symbol': 'tu'
        })
        unit_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/unit/delete', json={'id': unit_id})
        assert_success(resp)

    def test_route_list(self, auth_client):
        resp = auth_client.get('/api/base/route/list')
        assert_success(resp)

    def test_supplier_list(self, auth_client):
        resp = auth_client.get('/api/base/supplier/list')
        assert_success(resp)

    def test_supplier_crud(self, auth_client):
        resp = auth_client.post('/api/base/supplier/add', json={
            'supplier_name': '测试供应商', 'code': 'SUP_TEST', 'contact': '张三'
        })
        sup_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/supplier/update', json={
            'id': sup_id, 'supplier_name': '更新供应商'
        })
        assert_success(resp)

        resp = auth_client.get('/api/base/supplier/all')
        assert_success(resp)

        resp = auth_client.post('/api/base/supplier/delete', json={'id': sup_id})
        assert_success(resp)

    def test_customer_list(self, auth_client):
        resp = auth_client.get('/api/base/customer/list')
        assert_success(resp)

    def test_customer_crud(self, auth_client):
        resp = auth_client.post('/api/base/customer/add', json={
            'customer_name': '测试客户', 'code': 'CUS_TEST', 'contact': '李四'
        })
        cus_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/customer/update', json={
            'id': cus_id, 'customer_name': '更新客户'
        })
        assert_success(resp)

        resp = auth_client.get('/api/base/customer/all')
        assert_success(resp)

        resp = auth_client.post('/api/base/customer/delete', json={'id': cus_id})
        assert_success(resp)


# ==================== 4. Inventory Tests ====================

class TestInventory:
    def test_inbound_list(self, auth_client):
        resp = auth_client.get('/api/inv/inbound/list')
        assert_success(resp)

    def test_inbound_crud(self, auth_client):
        resp = auth_client.post('/api/inv/inbound/add', json={
            'inbound_type': '采购入库', 'supplier': '供应商A',
            'total_amount': 5000.0, 'remark': '测试入库'
        })
        ib_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/inv/inbound/update', json={
            'id': ib_id, 'total_amount': 6000.0
        })
        assert_success(resp)

        resp = auth_client.post('/api/inv/inbound/delete', json={'id': ib_id})
        assert_success(resp)

    def test_outbound_list(self, auth_client):
        resp = auth_client.get('/api/inv/outbound/list')
        assert_success(resp)

    def test_outbound_crud(self, auth_client):
        resp = auth_client.post('/api/inv/outbound/add', json={
            'outbound_type': '销售出库', 'customer': '客户A',
            'total_amount': 3000.0, 'remark': '测试出库'
        })
        ob_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/inv/outbound/delete', json={'id': ob_id})
        assert_success(resp)

    def test_balance_list(self, auth_client):
        resp = auth_client.get('/api/inv/balance/list')
        assert_success(resp)

    def test_inbound_number_auto_generated(self, auth_client):
        resp = auth_client.post('/api/inv/inbound/add', json={
            'inbound_type': '采购入库', 'supplier': '供应商B'
        })
        data = assert_success(resp)
        assert data['data']['id'] > 0

        resp2 = auth_client.get('/api/inv/inbound/list')
        list_data = assert_success(resp2)
        created = [r for r in list_data['data']['list'] if r['id'] == data['data']['id']]
        assert len(created) == 1
        assert created[0]['inbound_no'].startswith('RK')

        auth_client.post('/api/inv/inbound/delete', json={'id': data['data']['id']})


# ==================== 5. Production Tests ====================

class TestProductionConsistency:
    def test_report_updates_task_and_workorder_progress(self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=10)
        result = auth_client.post('/api/prod/report/add', json={
            'task_id': ids['task_id'],
            'workorder_id': ids['workorder_id'],
            'process_id': ids['process_id'],
            'qualified_qty': 6,
            'defect_qty': 1,
        }).get_json()
        assert result['code'] == 0

        task = find_by_id(
            auth_client.get('/api/prod/task/list?size=1000').get_json(),
            ids['task_id'],
        )
        workorder = find_by_id(
            auth_client.get('/api/prod/workorder/list?size=1000').get_json(),
            ids['workorder_id'],
        )
        assert task['completed_qty'] == 6
        assert task['defect_qty'] == 1
        assert task['status'] == 1
        assert workorder['completed_qty'] == 6
        assert workorder['defect_qty'] == 1
        assert workorder['status'] == 1

        finished = auth_client.post('/api/prod/report/add', json={
            'task_id': ids['task_id'],
            'workorder_id': ids['workorder_id'],
            'process_id': ids['process_id'],
            'qualified_qty': 4,
            'defect_qty': 0,
        }).get_json()
        assert finished['code'] == 0
        task = find_by_id(
            auth_client.get('/api/prod/task/list?size=1000').get_json(),
            ids['task_id'],
        )
        workorder = find_by_id(
            auth_client.get('/api/prod/workorder/list?size=1000').get_json(),
            ids['workorder_id'],
        )
        assert task['completed_qty'] == 10
        assert task['defect_qty'] == 1
        assert task['status'] == 3
        assert workorder['completed_qty'] == 10
        assert workorder['defect_qty'] == 1
        assert workorder['status'] == 3

    def test_workorder_completes_only_after_all_tasks(self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=10)
        suffix = uuid.uuid4().hex[:8]
        second_process = response_id(auth_client.post('/api/base/process/add', json={
            'process_name': f'第二工序-{suffix}',
            'code': f'PS_SECOND_{suffix}',
            'workshop_id': ids['workshop_id'],
        }))
        second_task = response_id(auth_client.post('/api/prod/task/add', json={
            'workorder_id': ids['workorder_id'],
            'process_id': second_process,
            'planned_qty': 10,
        }))

        for task_id, process_id, expected_status in (
            (ids['task_id'], ids['process_id'], 1),
            (second_task, second_process, 3),
        ):
            response = auth_client.post('/api/prod/report/add', json={
                'task_id': task_id,
                'workorder_id': ids['workorder_id'],
                'process_id': process_id,
                'qualified_qty': 10,
                'defect_qty': 0,
            })
            assert response.status_code == 200
            assert response.get_json()['code'] == 0
            workorder = find_by_id(
                auth_client.get('/api/prod/workorder/list?size=1000').get_json(),
                ids['workorder_id'],
            )
            assert workorder['status'] == expected_status

    def test_gps_report_updates_progress_and_stores_coordinates(self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=8)
        response = auth_client.post('/api/prod/report/gps', json={
            'task_id': ids['task_id'],
            'workorder_id': ids['workorder_id'],
            'process_id': ids['process_id'],
            'qualified_qty': 3,
            'defect_qty': 1,
            'latitude': 31.2304,
            'longitude': 121.4737,
        })
        assert response.status_code == 200
        report_id = response_id(response)

        task = find_by_id(
            auth_client.get('/api/prod/task/list?size=1000').get_json(),
            ids['task_id'],
        )
        workorder = find_by_id(
            auth_client.get('/api/prod/workorder/list?size=1000').get_json(),
            ids['workorder_id'],
        )
        report = find_by_id(
            auth_client.get('/api/prod/report/list?size=1000').get_json(),
            report_id,
        )
        assert task['completed_qty'] == 3
        assert task['defect_qty'] == 1
        assert task['status'] == 1
        assert workorder['completed_qty'] == 3
        assert workorder['defect_qty'] == 1
        assert workorder['status'] == 1
        assert report['remark'] == 'GPS: 31.2304,121.4737'

    @pytest.mark.parametrize(
        ('qualified_qty', 'defect_qty'),
        ((0, 0), (-1, 0), (1, -1), ('invalid', 0)),
    )
    def test_invalid_report_quantity_does_not_change_progress(
            self, auth_client, qualified_qty, defect_qty):
        ids = create_production_chain(auth_client, planned_qty=10)
        response = auth_client.post('/api/prod/report/add', json={
            'task_id': ids['task_id'],
            'workorder_id': ids['workorder_id'],
            'process_id': ids['process_id'],
            'qualified_qty': qualified_qty,
            'defect_qty': defect_qty,
        })
        assert response.status_code == 400
        assert response.get_json()['code'] == 400
        self._assert_no_report_or_progress(auth_client, ids)

    def test_missing_task_does_not_insert_report(self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=10)
        response = auth_client.post('/api/prod/report/add', json={
            'task_id': 999999999,
            'workorder_id': ids['workorder_id'],
            'process_id': ids['process_id'],
            'qualified_qty': 1,
            'defect_qty': 0,
        })
        assert response.status_code == 404
        assert response.get_json()['code'] == 404
        self._assert_no_report_or_progress(auth_client, ids)

    def test_task_workorder_mismatch_does_not_insert_report(self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=10)
        other = create_production_chain(auth_client, planned_qty=10)
        response = auth_client.post('/api/prod/report/add', json={
            'task_id': ids['task_id'],
            'workorder_id': other['workorder_id'],
            'process_id': ids['process_id'],
            'qualified_qty': 1,
            'defect_qty': 0,
        })
        assert response.status_code == 400
        assert response.get_json()['code'] == 400
        self._assert_no_report_or_progress(auth_client, ids)
        self._assert_no_report_or_progress(auth_client, other)

    def test_task_process_mismatch_does_not_insert_report(self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=10)
        other = create_production_chain(auth_client, planned_qty=10)
        response = auth_client.post('/api/prod/report/add', json={
            'task_id': ids['task_id'],
            'workorder_id': ids['workorder_id'],
            'process_id': other['process_id'],
            'qualified_qty': 1,
            'defect_qty': 0,
        })
        assert response.status_code == 400
        assert response.get_json()['code'] == 400
        self._assert_no_report_or_progress(auth_client, ids)
        self._assert_no_report_or_progress(auth_client, other)

    def test_workorder_keyword_does_not_fall_back_to_latest(self, auth_client):
        create_production_chain(auth_client, planned_qty=10)
        payload = auth_client.get(
            '/api/prod/workorder/list?keyword=WO_DOES_NOT_EXIST'
        ).get_json()
        assert payload['data']['list'] == []
        assert payload['data']['total'] == 0

    def test_task_keyword_does_not_fall_back_to_latest(self, auth_client):
        create_production_chain(auth_client, planned_qty=10)
        payload = auth_client.get(
            '/api/prod/task/list?keyword=TK_DOES_NOT_EXIST'
        ).get_json()
        assert payload['data']['list'] == []
        assert payload['data']['total'] == 0

    def test_deleting_completed_report_recalculates_partial_progress(
            self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=10)
        first_report = self._add_report(
            auth_client, ids, qualified_qty=6, defect_qty=1
        )
        completed_report = self._add_report(
            auth_client, ids, qualified_qty=4, defect_qty=2
        )
        completed = self._progress_snapshot(auth_client, ids)
        assert completed['task']['status'] == 3
        assert completed['task']['end_time'] is not None

        response = auth_client.post(
            '/api/prod/report/delete',
            json={'id': completed_report},
        )
        assert response.status_code == 200
        assert response.get_json()['code'] == 0
        assert self._report_ids(auth_client, ids) == [first_report]
        progress = self._progress_snapshot(auth_client, ids)
        assert progress['task'] == {
            'completed_qty': 6,
            'defect_qty': 1,
            'status': 1,
            'end_time': None,
        }
        assert progress['workorder'] == {
            'completed_qty': 6,
            'defect_qty': 1,
            'status': 1,
        }

    def test_deleting_last_report_resets_progress(self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=10)
        report_id = self._add_report(
            auth_client, ids, qualified_qty=10, defect_qty=2
        )
        response = auth_client.post(
            '/api/prod/report/delete',
            json={'id': report_id},
        )
        assert response.status_code == 200
        assert response.get_json()['code'] == 0
        assert self._report_ids(auth_client, ids) == []
        progress = self._progress_snapshot(auth_client, ids)
        assert progress['task'] == {
            'completed_qty': 0,
            'defect_qty': 0,
            'status': 0,
            'end_time': None,
        }
        assert progress['workorder'] == {
            'completed_qty': 0,
            'defect_qty': 0,
            'status': 0,
        }

    def test_deleting_missing_report_returns_404(self, auth_client):
        response = auth_client.post(
            '/api/prod/report/delete',
            json={'id': 999999999},
        )
        assert response.status_code == 404
        assert response.get_json()['code'] == 404

    def test_report_delete_rolls_back_when_recalculation_fails(
            self, auth_client, monkeypatch):
        from blueprints import production as production_module

        ids = create_production_chain(auth_client, planned_qty=10)
        report_id = self._add_report(
            auth_client, ids, qualified_qty=6, defect_qty=1
        )
        before = self._report_side_effect_snapshot(auth_client, ids)

        def fail_recalculation(*args, **kwargs):
            raise RuntimeError('forced aggregate failure')

        monkeypatch.setattr(
            production_module,
            '_recalculate_task_and_workorder',
            fail_recalculation,
        )
        with pytest.raises(RuntimeError, match='forced aggregate failure'):
            auth_client.post(
                '/api/prod/report/delete',
                json={'id': report_id},
            )

        assert self._report_side_effect_snapshot(auth_client, ids) == before

    @pytest.mark.parametrize('endpoint', (
        '/api/prod/report/add',
        '/api/prod/report/gps',
    ))
    @pytest.mark.parametrize('field', ('qualified_qty', 'defect_qty'))
    @pytest.mark.parametrize(
        'invalid_value',
        (float('nan'), float('inf'), float('-inf')),
        ids=('nan', 'positive-infinity', 'negative-infinity'),
    )
    def test_non_finite_report_quantity_has_no_side_effects(
            self, auth_client, endpoint, field, invalid_value):
        ids = create_production_chain(auth_client, planned_qty=10)
        before = self._report_side_effect_snapshot(auth_client, ids)
        payload = {
            'task_id': ids['task_id'],
            'workorder_id': ids['workorder_id'],
            'process_id': ids['process_id'],
            'qualified_qty': 1,
            'defect_qty': 0,
            'latitude': 31.2304,
            'longitude': 121.4737,
        }
        payload[field] = invalid_value

        response = auth_client.post(endpoint, json=payload)

        assert response.status_code == 400
        assert response.get_json()['code'] == 400
        assert self._report_side_effect_snapshot(auth_client, ids) == before

    def test_decimal_reports_complete_at_six_digit_precision(
            self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=0.8)
        self._add_report(auth_client, ids, qualified_qty=0.1)
        self._add_report(auth_client, ids, qualified_qty=0.7)

        progress = self._progress_snapshot(auth_client, ids)
        assert progress['task']['completed_qty'] == 0.8
        assert progress['task']['status'] == 3
        assert progress['workorder']['completed_qty'] == 0.8
        assert progress['workorder']['status'] == 3

    def test_many_decimal_reports_persist_normalized_total(
            self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=0.1)
        for _ in range(10):
            self._add_report(auth_client, ids, qualified_qty=0.01)

        progress = self._progress_snapshot(auth_client, ids)
        assert progress['task']['completed_qty'] == 0.1
        assert progress['task']['status'] == 3
        assert progress['workorder']['completed_qty'] == 0.1
        assert progress['workorder']['status'] == 3

    def test_quantity_below_six_digit_precision_remains_incomplete(
            self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=0.8)
        for _ in range(3):
            self._add_report(auth_client, ids, qualified_qty=0.2666664)

        progress = self._progress_snapshot(auth_client, ids)
        assert progress['task']['completed_qty'] == 0.799998
        assert progress['task']['status'] == 1
        assert progress['workorder']['completed_qty'] == 0.799998
        assert progress['workorder']['status'] == 1

    def test_decimal_workorder_completes_only_after_all_tasks(
            self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=0.8)
        suffix = uuid.uuid4().hex[:8]
        second_process = response_id(auth_client.post('/api/base/process/add', json={
            'process_name': f'精度工序-{suffix}',
            'code': f'PS_PRECISION_{suffix}',
            'workshop_id': ids['workshop_id'],
        }))
        second_task = response_id(auth_client.post('/api/prod/task/add', json={
            'workorder_id': ids['workorder_id'],
            'process_id': second_process,
            'planned_qty': 0.8,
        }))

        self._add_report(auth_client, ids, qualified_qty=0.1)
        self._add_report(auth_client, ids, qualified_qty=0.7)
        progress = self._progress_snapshot(auth_client, ids)
        assert progress['task']['status'] == 3
        assert progress['workorder']['status'] == 1

        second_ids = dict(
            ids,
            task_id=second_task,
            process_id=second_process,
        )
        self._add_report(auth_client, second_ids, qualified_qty=0.1)
        self._add_report(auth_client, second_ids, qualified_qty=0.7)
        progress = self._progress_snapshot(auth_client, second_ids)
        assert progress['task']['status'] == 3
        assert progress['workorder']['status'] == 3

    def test_workorder_searches_number_product_name_and_code(
            self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=10)
        workorder = find_by_id(
            auth_client.get('/api/prod/workorder/list?size=1000').get_json(),
            ids['workorder_id'],
        )
        for keyword in (
            workorder['order_no'],
            workorder['product_name'],
            workorder['product_code'],
        ):
            payload = auth_client.get(
                '/api/prod/workorder/list',
                query_string={'keyword': keyword, 'size': 1000},
            ).get_json()
            assert payload['data']['total'] == len(payload['data']['list'])
            assert [row['id'] for row in payload['data']['list']] == [
                ids['workorder_id']
            ]

    def test_task_searches_number_workorder_and_process_name(
            self, auth_client):
        ids = create_production_chain(auth_client, planned_qty=10)
        task = find_by_id(
            auth_client.get('/api/prod/task/list?size=1000').get_json(),
            ids['task_id'],
        )
        for keyword in (
            task['task_no'],
            task['workorder_no'],
            task['process_name'],
        ):
            payload = auth_client.get(
                '/api/prod/task/list',
                query_string={'keyword': keyword, 'size': 1000},
            ).get_json()
            assert payload['data']['total'] == len(payload['data']['list'])
            assert [row['id'] for row in payload['data']['list']] == [
                ids['task_id']
            ]

    @staticmethod
    def _add_report(
            client, ids, qualified_qty, defect_qty=0, endpoint=None):
        endpoint = endpoint or '/api/prod/report/add'
        return response_id(client.post(endpoint, json={
            'task_id': ids['task_id'],
            'workorder_id': ids['workorder_id'],
            'process_id': ids['process_id'],
            'qualified_qty': qualified_qty,
            'defect_qty': defect_qty,
        }))

    @staticmethod
    def _report_ids(client, ids):
        reports = client.get('/api/prod/report/list?size=1000').get_json()
        return sorted(
            report['id']
            for report in reports['data']['list']
            if report['task_id'] == ids['task_id']
        )

    @staticmethod
    def _progress_snapshot(client, ids):
        task = find_by_id(
            client.get('/api/prod/task/list?size=1000').get_json(),
            ids['task_id'],
        )
        workorder = find_by_id(
            client.get('/api/prod/workorder/list?size=1000').get_json(),
            ids['workorder_id'],
        )
        return {
            'task': {
                key: task[key]
                for key in (
                    'completed_qty',
                    'defect_qty',
                    'status',
                    'end_time',
                )
            },
            'workorder': {
                key: workorder[key]
                for key in ('completed_qty', 'defect_qty', 'status')
            },
        }

    @classmethod
    def _report_side_effect_snapshot(cls, client, ids):
        with client.application.app_context():
            row = get_db().execute(
                """SELECT current_no FROM sys_numbering
                   WHERE entity_type='BR'"""
            ).fetchone()
            current_no = row['current_no'] if row else None
        return {
            'report_ids': cls._report_ids(client, ids),
            'numbering': current_no,
            'progress': cls._progress_snapshot(client, ids),
        }

    @staticmethod
    def _assert_no_report_or_progress(client, ids):
        reports = client.get('/api/prod/report/list?size=1000').get_json()
        assert all(
            report['task_id'] != ids['task_id']
            for report in reports['data']['list']
        )
        task = find_by_id(
            client.get('/api/prod/task/list?size=1000').get_json(),
            ids['task_id'],
        )
        workorder = find_by_id(
            client.get('/api/prod/workorder/list?size=1000').get_json(),
            ids['workorder_id'],
        )
        assert task['completed_qty'] == 0
        assert task['defect_qty'] == 0
        assert task['status'] == 0
        assert workorder['completed_qty'] == 0
        assert workorder['defect_qty'] == 0
        assert workorder['status'] == 0


class TestProduction:
    def test_sales_order_list(self, auth_client):
        resp = auth_client.get('/api/prod/sales/list')
        assert_success(resp)

    def test_sales_order_crud(self, auth_client):
        resp = auth_client.post('/api/prod/sales/add', json={
            'customer': '测试客户', 'contact': '王五', 'phone': '13800000000',
            'total_amount': 10000, 'delivery_date': '2026-07-01', 'remark': '测试订单'
        })
        order_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/sales/update', json={
            'id': order_id, 'total_amount': 12000
        })
        assert_success(resp)

        resp = auth_client.post('/api/prod/sales/delete', json={'id': order_id})
        assert_success(resp)

    def test_plan_crud(self, auth_client):
        resp = auth_client.post('/api/prod/plan/add', json={
            'plan_type': '月计划', 'start_date': '2026-06-01',
            'end_date': '2026-06-30', 'remark': '测试计划'
        })
        plan_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/plan/delete', json={'id': plan_id})
        assert_success(resp)

    def test_workorder_list(self, auth_client):
        resp = auth_client.get('/api/prod/workorder/list')
        assert_success(resp)

    def test_workorder_crud(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '工单测试产品', 'code': 'WO_PRD', 'unit': '个'
        })
        prd_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/workorder/add', json={
            'product_id': prd_id, 'planned_qty': 100, 'priority': 1, 'remark': '测试工单'
        })
        wo_id = assert_success(resp)['data']['id']

        resp = auth_client.get('/api/prod/workorder/list')
        data = assert_success(resp)
        wos = [w for w in data['data']['list'] if w['id'] == wo_id]
        assert len(wos) == 1
        assert wos[0]['order_no'].startswith('WO')
        assert wos[0]['planned_qty'] == 100

        resp = auth_client.post('/api/prod/workorder/update', json={
            'id': wo_id, 'planned_qty': 200, 'priority': 2
        })
        assert_success(resp)

        resp = auth_client.post('/api/prod/workorder/delete', json={'id': wo_id})
        assert_success(resp)
        auth_client.post('/api/base/product/delete', json={'id': prd_id})

    def test_task_list(self, auth_client):
        resp = auth_client.get('/api/prod/task/list')
        assert_success(resp)

    def test_report_list(self, auth_client):
        resp = auth_client.get('/api/prod/report/list')
        assert_success(resp)

    def test_workorder_status_flow(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '流程测试产品', 'code': 'FLOW_PRD', 'unit': '个'
        })
        prd_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/workorder/add', json={
            'product_id': prd_id, 'planned_qty': 50, 'status': 0
        })
        wo_id = assert_success(resp)['data']['id']

        for new_status in [1, 2, 3]:
            resp = auth_client.post('/api/prod/workorder/update', json={
                'id': wo_id, 'status': new_status
            })
            assert_success(resp)

        auth_client.post('/api/prod/workorder/delete', json={'id': wo_id})
        auth_client.post('/api/base/product/delete', json={'id': prd_id})

    def test_workorder_with_task_and_report(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '完整流程产品', 'code': 'FULL_PRD', 'unit': '个'
        })
        prd_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/workshop/add', json={
            'workshop_name': '测试车间', 'code': 'FULL_WS'
        })
        ws_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/process/add', json={
            'process_name': '测试工序', 'code': 'FULL_PRC', 'workshop_id': ws_id
        })
        proc_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/workorder/add', json={
            'product_id': prd_id, 'workshop_id': ws_id, 'planned_qty': 100
        })
        wo_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/task/add', json={
            'workorder_id': wo_id, 'process_id': proc_id, 'planned_qty': 100
        })
        task_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/report/add', json={
            'task_id': task_id, 'workorder_id': wo_id, 'process_id': proc_id,
            'qualified_qty': 95, 'defect_qty': 5
        })
        assert_success(resp)

        resp = auth_client.get('/api/prod/report/list')
        data = assert_success(resp)
        reports = [r for r in data['data']['list'] if r['task_id'] == task_id]
        assert len(reports) >= 1
        assert reports[0]['qualified_qty'] == 95

        auth_client.post('/api/prod/workorder/delete', json={'id': wo_id})
        auth_client.post('/api/base/product/delete', json={'id': prd_id})
        auth_client.post('/api/base/workshop/delete', json={'id': ws_id})


# ==================== 6. Quality Management Tests ====================

class TestQuality:
    def test_incoming_inspection_list(self, auth_client):
        resp = auth_client.get('/api/qm/incoming/list')
        assert_success(resp)

    def test_incoming_inspection_crud(self, auth_client):
        resp = auth_client.post('/api/qm/incoming/add', json={
            'supplier': '供应商A', 'result': '合格', 'remark': '测试来料检验'
        })
        insp_id = assert_success(resp)['data']['id']

        resp = auth_client.get('/api/qm/incoming/list')
        data = assert_success(resp)
        items = [i for i in data['data']['list'] if i['id'] == insp_id]
        assert len(items) == 1
        assert items[0]['inspect_no'].startswith('IQC')

        resp = auth_client.post('/api/qm/incoming/update', json={
            'id': insp_id, 'result': '不合格'
        })
        assert_success(resp)

        resp = auth_client.post('/api/qm/incoming/delete', json={'id': insp_id})
        assert_success(resp)

    def test_process_inspection_crud(self, auth_client):
        resp = auth_client.post('/api/qm/process/add', json={
            'workorder_id': 1, 'result': '合格', 'remark': '过程检验'
        })
        insp_id = assert_success(resp)['data']['id']

        resp = auth_client.get('/api/qm/process/list')
        data = assert_success(resp)
        items = [i for i in data['data']['list'] if i['id'] == insp_id]
        assert items[0]['inspect_no'].startswith('PQC')

        auth_client.post('/api/qm/process/delete', json={'id': insp_id})

    def test_outgoing_inspection_crud(self, auth_client):
        resp = auth_client.post('/api/qm/outgoing/add', json={
            'customer': '客户A', 'result': '合格', 'remark': '出货检验'
        })
        insp_id = assert_success(resp)['data']['id']

        resp = auth_client.get('/api/qm/outgoing/list')
        data = assert_success(resp)
        items = [i for i in data['data']['list'] if i['id'] == insp_id]
        assert items[0]['inspect_no'].startswith('OQC')

        auth_client.post('/api/qm/outgoing/delete', json={'id': insp_id})


# ==================== 7. Notification Tests ====================

class TestNotification:
    def test_notification_list(self, auth_client):
        resp = auth_client.get('/api/notification/list')
        assert_success(resp)

    def test_unread_count(self, auth_client):
        resp = auth_client.get('/api/notification/unread/count')
        data = assert_success(resp)
        assert 'count' in data['data']

    def test_mark_all_read(self, auth_client):
        resp = auth_client.post('/api/notification/read', json={'all': True})
        assert_success(resp)

        resp = auth_client.get('/api/notification/unread/count')
        data = assert_success(resp)
        assert data['data']['count'] == 0


# ==================== 8. Dashboard Tests ====================

class TestDashboard:
    def test_dashboard_stats(self, auth_client):
        resp = auth_client.get('/api/dashboard')
        data = assert_success(resp)
        required_keys = ['products', 'workorders', 'inventory', 'equipment', 'users', 'tasks']
        for key in required_keys:
            assert key in data['data'], f"Missing key: {key}"
            assert isinstance(data['data'][key], int)

    def test_dashboard_charts(self, auth_client):
        resp = auth_client.get('/api/dashboard/charts')
        data = assert_success(resp)
        assert 'daily_output' in data['data']
        assert 'wo_stats' in data['data']
        assert 'pass_rate' in data['data']
        assert isinstance(data['data']['daily_output'], list)
        assert len(data['data']['daily_output']) == 7


# ==================== 9. Traceability Tests ====================

class TestTraceability:
    def test_batch_list(self, auth_client):
        resp = auth_client.get('/api/trace/batch/list')
        assert_success(resp)

    def test_batch_crud(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '追溯产品', 'code': 'TRACE_PRD', 'unit': '个'
        })
        prd_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/trace/batch/add', json={
            'batch_no': 'BATCH001', 'product_id': prd_id,
            'supplier': '供应商A', 'quantity': 500,
            'production_date': '2026-06-01', 'expiry_date': '2027-06-01'
        })
        assert_success(resp)

        resp = auth_client.get('/api/trace/batch/list')
        data = assert_success(resp)
        batches = [b for b in data['data']['list'] if b['batch_no'] == 'BATCH001']
        assert len(batches) == 1
        batch_id = batches[0]['id']

        resp = auth_client.get(f'/api/trace/chain/{batch_id}')
        data = assert_success(resp)
        assert data['data']['batch']['batch_no'] == 'BATCH001'
        assert isinstance(data['data']['traces'], list)

        resp = auth_client.post('/api/trace/batch/delete', json={'id': batch_id})
        assert_success(resp)
        auth_client.post('/api/base/product/delete', json={'id': prd_id})

    def test_trace_query(self, auth_client):
        resp = auth_client.get('/api/trace/query')
        data = assert_success(resp)
        assert data['data'] == []

        resp = auth_client.get('/api/trace/query?keyword=test')
        assert_success(resp)


# ==================== 10. Export/Import Tests ====================

class TestExportImport:
    def test_export_product(self, auth_client):
        resp = auth_client.get('/api/export/base_product')
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.content_type

    def test_export_workorder(self, auth_client):
        resp = auth_client.get('/api/export/prod_workorder')
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.content_type

    def test_export_unsupported_table(self, auth_client):
        resp = auth_client.get('/api/export/nonexistent_table')
        data = resp.get_json()
        assert data.get('code') == 400

    def test_download_template(self, auth_client):
        resp = auth_client.get('/api/template/base_product')
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.content_type

    def test_template_unsupported_table(self, auth_client):
        resp = auth_client.get('/api/template/nonexistent_table')
        data = resp.get_json()
        assert data.get('code') == 400


# ==================== 11. Security Tests ====================

class TestSecurity:
    def test_sql_injection_in_login(self, client):
        payloads = [
            "admin' OR '1'='1",
            "admin'; DROP TABLE sys_user; --",
            "1' UNION SELECT * FROM sys_user --",
        ]
        for payload in payloads:
            resp = client.post('/api/login', json={'username': payload, 'password': 'test'})
            data = resp.get_json()
            assert data.get('code') == 400, f"SQL injection not blocked: {payload}"

    def test_sql_injection_in_list(self, auth_client):
        resp = auth_client.get("/api/base/product/list?keyword=' OR '1'='1")
        assert_success(resp)

        resp = auth_client.get("/api/base/product/list?status=1; DROP TABLE base_product; --")
        assert resp.status_code in (200, 400)

    def test_xss_in_input(self, auth_client):
        xss_payload = '<script>alert("xss")</script>'
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': xss_payload, 'code': 'XSS_TEST', 'unit': '个'
        })
        data = assert_success(resp)
        prd_id = data['data']['id']

        resp = auth_client.get('/api/base/product/list')
        products = assert_success(resp)['data']['list']
        p = [x for x in products if x['id'] == prd_id]
        if p:
            assert p[0]['product_name'] == xss_payload

        auth_client.post('/api/base/product/delete', json={'id': prd_id})

    def test_update_without_id(self, auth_client):
        resp = auth_client.post('/api/base/product/update', json={
            'product_name': '无ID更新'
        })
        data = resp.get_json()
        assert data.get('code') == 400
        assert 'id' in data.get('message', '').lower() or '缺少' in data.get('message', '')

    def test_delete_nonexistent(self, auth_client):
        resp = auth_client.post('/api/base/product/delete', json={'id': 999999})
        assert_success(resp)

    def test_duplicate_entry_handling(self, auth_client):
        auth_client.post('/api/base/supplier/add', json={
            'supplier_name': '重复测试', 'code': 'DUP_SUP'
        })
        resp = auth_client.post('/api/base/supplier/add', json={
            'supplier_name': '重复测试2', 'code': 'DUP_SUP'
        })
        data = resp.get_json()
        assert data.get('code') != 0
        assert '重复' in data.get('message', '')

    def test_generate_token(self, auth_client):
        resp = auth_client.post('/api/security/token/generate', json={})
        data = assert_success(resp)
        assert 'token' in data['data']
        assert len(data['data']['token']) == 64

    def test_security_log(self, auth_client):
        resp = auth_client.get('/api/security/log')
        assert_success(resp)


# ==================== 12. Edge Case Tests ====================

class TestEdgeCases:
    def test_empty_json_body(self, auth_client):
        resp = auth_client.post('/api/base/product/add',
                                data='not json',
                                content_type='text/plain')
        assert resp.status_code in (400, 415, 200)

    def test_pagination_params(self, auth_client):
        resp = auth_client.get('/api/base/product/list?page=1&size=5')
        data = assert_success(resp)
        assert data['data']['page'] == 1
        assert data['data']['size'] == 5
        assert len(data['data']['list']) <= 5

    def test_large_page_number(self, auth_client):
        resp = auth_client.get('/api/base/product/list?page=99999&size=20')
        data = assert_success(resp)
        assert data['data']['list'] == []

    def test_zero_size(self, auth_client):
        resp = auth_client.get('/api/base/product/list?page=1&size=0')
        data = assert_success(resp)
        assert data['data']['list'] == []

    def test_negative_page(self, auth_client):
        resp = auth_client.get('/api/base/product/list?page=-1&size=10')
        assert resp.status_code in (200, 400, 500)

    def test_special_characters_in_name(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '产品@#$%^&*()', 'code': 'SPECIAL_PRD', 'unit': '个'
        })
        data = assert_success(resp)
        auth_client.post('/api/base/product/delete', json={'id': data['data']['id']})

    def test_unicode_input(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '日本語テスト製品', 'code': 'UNI_PRD', 'unit': '個'
        })
        data = assert_success(resp)
        auth_client.post('/api/base/product/delete', json={'id': data['data']['id']})

    def test_long_string_input(self, auth_client):
        long_name = 'A' * 1000
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': long_name, 'code': 'LONG_PRD', 'unit': '个'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        if data.get('code') == 0:
            auth_client.post('/api/base/product/delete', json={'id': data['data']['id']})

    def test_missing_required_fields(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={})
        data = resp.get_json()
        assert data.get('code') != 0

    def test_concurrent_number_generation(self, auth_client):
        ids = []
        for i in range(5):
            resp = auth_client.post('/api/prod/workorder/add', json={
                'product_id': 1, 'planned_qty': 10
            })
            data = resp.get_json()
            if data.get('code') == 0:
                ids.append(data['data']['id'])

        if ids:
            resp = auth_client.get('/api/prod/workorder/list?size=100')
            data = assert_success(resp)
            order_nos = [w['order_no'] for w in data['data']['list'] if w['id'] in ids]
            assert len(order_nos) == len(set(order_nos)), "Duplicate order numbers generated"

            for wo_id in ids:
                auth_client.post('/api/prod/workorder/delete', json={'id': wo_id})


# ==================== 13. Business Logic Tests ====================

class TestBusinessLogic:
    def test_full_production_flow(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '流程产品', 'code': 'BIZ_PRD', 'unit': '个'
        })
        prd_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/workshop/add', json={
            'workshop_name': '流程车间', 'code': 'BIZ_WS'
        })
        ws_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/process/add', json={
            'process_name': '切割', 'code': 'BIZ_CUT', 'workshop_id': ws_id
        })
        cut_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/process/add', json={
            'process_name': '焊接', 'code': 'BIZ_WELD', 'workshop_id': ws_id
        })
        weld_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/workorder/add', json={
            'product_id': prd_id, 'workshop_id': ws_id, 'planned_qty': 200, 'priority': 2
        })
        wo_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/task/add', json={
            'workorder_id': wo_id, 'process_id': cut_id, 'planned_qty': 200
        })
        cut_task_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/task/add', json={
            'workorder_id': wo_id, 'process_id': weld_id, 'planned_qty': 200
        })
        weld_task_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/report/add', json={
            'task_id': cut_task_id, 'workorder_id': wo_id, 'process_id': cut_id,
            'qualified_qty': 198, 'defect_qty': 2
        })
        assert_success(resp)

        resp = auth_client.post('/api/prod/report/add', json={
            'task_id': weld_task_id, 'workorder_id': wo_id, 'process_id': weld_id,
            'qualified_qty': 195, 'defect_qty': 3
        })
        assert_success(resp)

        resp = auth_client.get('/api/prod/report/list?size=100')
        data = assert_success(resp)
        reports = [r for r in data['data']['list'] if r['workorder_id'] == wo_id]
        assert len(reports) >= 2

        resp = auth_client.post('/api/prod/workorder/update', json={
            'id': wo_id, 'status': 2, 'completed_qty': 195, 'defect_qty': 5
        })
        assert_success(resp)

        auth_client.post('/api/prod/workorder/delete', json={'id': wo_id})
        auth_client.post('/api/base/product/delete', json={'id': prd_id})
        auth_client.post('/api/base/workshop/delete', json={'id': ws_id})

    def test_inventory_flow(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '库存产品', 'code': 'INV_PRD', 'unit': '个'
        })
        prd_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/inv/inbound/add', json={
            'inbound_type': '采购入库', 'supplier': '供应商A', 'total_amount': 10000
        })
        ib_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/inv/outbound/add', json={
            'outbound_type': '销售出库', 'customer': '客户A', 'total_amount': 5000
        })
        ob_id = assert_success(resp)['data']['id']

        resp = auth_client.get('/api/inv/inbound/list')
        data = assert_success(resp)
        assert any(ib['id'] == ib_id for ib in data['data']['list'])

        resp = auth_client.get('/api/inv/outbound/list')
        data = assert_success(resp)
        assert any(ob['id'] == ob_id for ob in data['data']['list'])

        auth_client.post('/api/inv/inbound/delete', json={'id': ib_id})
        auth_client.post('/api/inv/outbound/delete', json={'id': ob_id})
        auth_client.post('/api/base/product/delete', json={'id': prd_id})

    def test_quality_inspection_flow(self, auth_client):
        resp = auth_client.post('/api/qm/incoming/add', json={
            'supplier': '供应商A', 'result': '待检'
        })
        iq_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/qm/incoming/update', json={
            'id': iq_id, 'result': '合格', 'status': 1
        })
        assert_success(resp)

        resp = auth_client.get('/api/qm/incoming/list')
        data = assert_success(resp)
        item = [i for i in data['data']['list'] if i['id'] == iq_id][0]
        assert item['result'] == '合格'
        assert item['status'] == 1

        auth_client.post('/api/qm/incoming/delete', json={'id': iq_id})

    def test_workorder_priority_levels(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '优先级产品', 'code': 'PRI_PRD', 'unit': '个'
        })
        prd_id = assert_success(resp)['data']['id']

        wo_ids = []
        for priority in [1, 2, 3]:
            resp = auth_client.post('/api/prod/workorder/add', json={
                'product_id': prd_id, 'planned_qty': 10, 'priority': priority
            })
            data = assert_success(resp)
            wo_ids.append(data['data']['id'])

        resp = auth_client.get('/api/prod/workorder/list')
        data = assert_success(resp)
        created = [w for w in data['data']['list'] if w['id'] in wo_ids]
        priorities = {w['id']: w['priority'] for w in created}
        assert priorities[wo_ids[0]] == 1
        assert priorities[wo_ids[2]] == 3

        for wo_id in wo_ids:
            auth_client.post('/api/prod/workorder/delete', json={'id': wo_id})
        auth_client.post('/api/base/product/delete', json={'id': prd_id})


# ==================== 14. CRUD Helper Function Tests ====================

class TestCrudHelpers:
    def test_crud_update_missing_id(self, auth_client):
        resp = auth_client.post('/api/base/product/update', json={
            'product_name': '无ID'
        })
        data = resp.get_json()
        assert data.get('code') == 400

    def test_crud_add_integrity_error(self, auth_client):
        auth_client.post('/api/base/product/add', json={
            'product_name': '重复测试', 'code': 'DUP_CRUD', 'unit': '个'
        })
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '重复测试2', 'code': 'DUP_CRUD', 'unit': '个'
        })
        data = resp.get_json()
        assert data.get('code') != 0
        assert '重复' in data.get('message', '')

    def test_crud_list_keyword_search(self, auth_client):
        auth_client.post('/api/base/product/add', json={
            'product_name': '搜索测试专用', 'code': 'SEARCH_PRD', 'unit': '个'
        })
        resp = auth_client.get('/api/base/product/list?keyword=搜索测试专用')
        data = assert_success(resp)
        names = [p['product_name'] for p in data['data']['list']]
        assert '搜索测试专用' in names

    def test_crud_list_sort_params(self, auth_client):
        resp = auth_client.get('/api/base/product/list?sort=id&order=ASC')
        assert_success(resp)

        resp = auth_client.get('/api/base/product/list?sort=id&order=DESC')
        assert_success(resp)

    def test_crud_list_invalid_sort(self, auth_client):
        resp = auth_client.get('/api/base/product/list?sort=invalid_col&order=DESC')
        assert_success(resp)


# ==================== 15. Pagination and Filtering Tests ====================

class TestPaginationAndFiltering:
    def test_default_pagination(self, auth_client):
        resp = auth_client.get('/api/base/product/list')
        data = assert_success(resp)
        assert data['data']['page'] == 1
        assert data['data']['size'] == 20

    def test_custom_pagination(self, auth_client):
        resp = auth_client.get('/api/base/product/list?page=2&size=5')
        data = assert_success(resp)
        assert data['data']['page'] == 2
        assert data['data']['size'] == 5

    def test_workorder_pagination(self, auth_client):
        resp = auth_client.get('/api/prod/workorder/list?page=1&size=10')
        data = assert_success(resp)
        assert 'list' in data['data']
        assert 'total' in data['data']

    def test_task_pagination(self, auth_client):
        resp = auth_client.get('/api/prod/task/list?page=1&size=5')
        data = assert_success(resp)
        assert 'list' in data['data']

    def test_notification_pagination(self, auth_client):
        resp = auth_client.get('/api/notification/list?page=1&size=10')
        data = assert_success(resp)
        assert 'list' in data['data']
        assert 'total' in data['data']

    def test_notification_unread_filter(self, auth_client):
        resp = auth_client.get('/api/notification/list?unread=1')
        data = assert_success(resp)
        assert 'list' in data['data']


# ==================== 16. Error Handling Tests ====================

class TestErrorHandling:
    def test_invalid_json_content_type(self, auth_client):
        resp = auth_client.post('/api/base/product/add',
                                data='<html>not json</html>',
                                content_type='text/html')
        assert resp.status_code in (400, 415, 200, 500)

    def test_nonexistent_endpoint(self, auth_client):
        resp = auth_client.get('/api/nonexistent/endpoint')
        assert resp.status_code == 404

    def test_wrong_http_method(self, auth_client):
        resp = auth_client.get('/api/base/product/add')
        assert resp.status_code == 405

    def test_delete_with_invalid_id_type(self, auth_client):
        resp = auth_client.post('/api/base/product/delete', json={'id': 'not_a_number'})
        assert resp.status_code in (200, 400, 500)

    def test_update_with_zero_id(self, auth_client):
        resp = auth_client.post('/api/base/product/update', json={
            'id': 0, 'product_name': 'test'
        })
        data = resp.get_json()
        assert data.get('code') == 400

    def test_invalid_page_params(self, auth_client):
        try:
            resp = auth_client.get('/api/base/product/list?page=abc&size=xyz')
            assert resp.status_code in (200, 400, 500)
        except ValueError:
            pass


# ==================== 17. Equipment and Tool Tests ====================

class TestEquipmentAndTools:
    def test_eqp_type_list(self, auth_client):
        resp = auth_client.get('/api/eqp/type/list')
        assert_success(resp)

    def test_eqp_ledger_list(self, auth_client):
        resp = auth_client.get('/api/eqp/ledger/list')
        assert_success(resp)

    def test_eqp_repair_list(self, auth_client):
        resp = auth_client.get('/api/eqp/repair/list')
        assert_success(resp)

    def test_eqp_maintenance_list(self, auth_client):
        resp = auth_client.get('/api/eqp/maintenance/list')
        assert_success(resp)

    def test_eqp_maintenance_overdue(self, auth_client):
        resp = auth_client.get('/api/eqp/maintenance/overdue')
        assert_success(resp)

    def test_eqp_check_list(self, auth_client):
        resp = auth_client.get('/api/eqp/check/list')
        assert_success(resp)

    def test_tool_type_list(self, auth_client):
        resp = auth_client.get('/api/tool/type/list')
        assert_success(resp)

    def test_tool_ledger_list(self, auth_client):
        resp = auth_client.get('/api/tool/ledger/list')
        assert_success(resp)

    def test_tool_borrow_list(self, auth_client):
        resp = auth_client.get('/api/tool/borrow/list')
        assert_success(resp)


# ==================== 18. Schedule Tests ====================

class TestSchedule:
    def test_team_list(self, auth_client):
        resp = auth_client.get('/api/sched/team/list')
        assert_success(resp)

    def test_plan_list(self, auth_client):
        resp = auth_client.get('/api/sched/plan/list')
        assert_success(resp)


# ==================== 19. Flow/Approval Tests ====================

class TestFlow:
    def test_definition_list(self, auth_client):
        resp = auth_client.get('/api/flow/definition/list')
        assert_success(resp)

    def test_instance_list_mine(self, auth_client):
        resp = auth_client.get('/api/flow/instance/list?tab=mine')
        assert_success(resp)

    def test_instance_list_pending(self, auth_client):
        resp = auth_client.get('/api/flow/instance/list?tab=pending')
        assert_success(resp)

    def test_pending_count(self, auth_client):
        resp = auth_client.get('/api/flow/pending/count')
        assert_success(resp)


# ==================== 20. Report and Analytics Tests ====================

class TestReports:
    def test_production_report(self, auth_client):
        resp = auth_client.get('/api/report/production')
        assert_success(resp)

    def test_spc_data(self, auth_client):
        resp = auth_client.get('/api/spc/data')
        assert_success(resp)

    def test_spc_chart(self, auth_client):
        resp = auth_client.get('/api/spc/chart')
        assert_success(resp)

    def test_spc_cpk(self, auth_client):
        resp = auth_client.get('/api/spc/cpk')
        assert_success(resp)

    def test_kanban_production(self, auth_client):
        resp = auth_client.get('/api/kanban/production')
        assert_success(resp)

    def test_kanban_realtime(self, auth_client):
        resp = auth_client.get('/api/kanban/realtime')
        assert_success(resp)


# ==================== 21. Document and Backup Tests ====================

class TestDocumentAndBackup:
    def test_document_list(self, auth_client):
        resp = auth_client.get('/api/document/list')
        assert_success(resp)

    def test_backup_list(self, auth_client):
        resp = auth_client.get('/api/backup/list')
        assert_success(resp)


# ==================== 22. Cost Tests ====================

class TestCost:
    def test_cost_list(self, auth_client):
        resp = auth_client.get('/api/cost/list')
        assert_success(resp)

    def test_cost_summary(self, auth_client):
        resp = auth_client.get('/api/cost/summary')
        assert_success(resp)


# ==================== 23. HTML Page Tests ====================

class TestPages:
    def test_index_page(self, client):
        resp = client.get('/')
        assert resp.status_code == 200


# ==================== 24. gen_no Function Tests ====================

class TestGenNo:
    def test_gen_no_creates_numbering(self, auth_client):
        resp = auth_client.post('/api/prod/workorder/add', json={
            'product_id': 1, 'planned_qty': 1
        })
        data = resp.get_json()
        if data.get('code') == 0:
            wo_id = data['data']['id']
            resp = auth_client.get('/api/prod/workorder/list')
            wos = assert_success(resp)['data']['list']
            created = [w for w in wos if w['id'] == wo_id]
            if created:
                assert created[0]['order_no'].startswith('WO')
                assert len(created[0]['order_no']) > 10
            auth_client.post('/api/prod/workorder/delete', json={'id': wo_id})

    def test_gen_no_increments(self, auth_client):
        ids = []
        for _ in range(3):
            resp = auth_client.post('/api/prod/sales/add', json={
                'customer': '编号测试客户'
            })
            data = resp.get_json()
            if data.get('code') == 0:
                ids.append(data['data']['id'])

        if len(ids) >= 2:
            resp = auth_client.get('/api/prod/sales/list?size=100')
            sales = assert_success(resp)['data']['list']
            order_nos = sorted([s['order_no'] for s in sales if s['id'] in ids])
            assert len(order_nos) == len(set(order_nos))

        for sid in ids:
            auth_client.post('/api/prod/sales/delete', json={'id': sid})


# ==================== 25. Data Integrity Tests ====================

class TestDataIntegrity:
    def test_workorder_product_reference(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '引用测试', 'code': 'REF_PRD', 'unit': '个'
        })
        prd_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/workorder/add', json={
            'product_id': prd_id, 'planned_qty': 50
        })
        wo_id = assert_success(resp)['data']['id']

        resp = auth_client.get('/api/prod/workorder/list')
        data = assert_success(resp)
        wo = [w for w in data['data']['list'] if w['id'] == wo_id][0]
        assert wo['product_name'] == '引用测试'

        auth_client.post('/api/prod/workorder/delete', json={'id': wo_id})
        auth_client.post('/api/base/product/delete', json={'id': prd_id})

    def test_workorder_list_joins(self, auth_client):
        resp = auth_client.post('/api/base/product/add', json={
            'product_name': '联查产品', 'code': 'JOIN_PRD', 'unit': '个'
        })
        prd_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/base/workshop/add', json={
            'workshop_name': '联查车间', 'code': 'JOIN_WS'
        })
        ws_id = assert_success(resp)['data']['id']

        resp = auth_client.post('/api/prod/workorder/add', json={
            'product_id': prd_id, 'workshop_id': ws_id, 'planned_qty': 30
        })
        wo_id = assert_success(resp)['data']['id']

        resp = auth_client.get('/api/prod/workorder/list')
        data = assert_success(resp)
        wo = [w for w in data['data']['list'] if w['id'] == wo_id][0]
        assert wo['product_name'] == '联查产品'
        assert wo['workshop_name'] == '联查车间'

        auth_client.post('/api/prod/workorder/delete', json={'id': wo_id})
        auth_client.post('/api/base/product/delete', json={'id': prd_id})
        auth_client.post('/api/base/workshop/delete', json={'id': ws_id})
