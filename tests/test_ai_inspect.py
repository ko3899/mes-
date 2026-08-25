# -*- coding: utf-8 -*-
"""AI 智能分析接口测试（mock 外部大模型调用，不消耗真实 Key）。"""
import os
import sys
import sqlite3

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from app import create_app
from blueprints import ai as ai_module
from utils import database


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = str(tmp_path / 'ai.db')
    monkeypatch.setattr(database, 'DB_PATH', path)
    database.init_db()
    database._init_extra_tables()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # admin 角色 init_db 已种子，INSERT OR IGNORE 兜底
    conn.execute(
        "INSERT OR IGNORE INTO sys_role(role_name,role_key,description,menu_ids,status) "
        "VALUES('超级管理员','admin','','',1)"
    )
    role = conn.execute("SELECT id FROM sys_role WHERE role_key='admin'").fetchone()['id']
    uid = conn.execute(
        "INSERT INTO sys_user(username,password,real_name,status,role_id) VALUES('adm','x','管理员',1,?)",
        (role,),
    ).lastrowid
    conn.commit()
    conn.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='ai-test')
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
        s['username'] = 'adm'
    return c


def _set_cfg(db_path, enabled='1', key='sk-test', model='deepseek-chat', provider='deepseek'):
    conn = sqlite3.connect(db_path)
    for k, v in [('ai_enabled', enabled), ('ai_provider', provider),
                 ('ai_api_key', key), ('ai_model', model)]:
        conn.execute(
            "INSERT INTO sys_config(config_key, config_value, config_type) VALUES(?,?,'string')",
            (k, v),
        )
    conn.commit()
    conn.close()


def test_inspect_requires_text(client):
    r = client.post('/api/ai/inspect', json={})
    assert r.status_code == 400


def test_inspect_not_enabled_returns_503(client):
    r = client.post('/api/ai/inspect', json={'text': '检查一下这批物料'})
    assert r.status_code == 503
    assert 'AI' in r.get_json()['message']


def test_inspect_calls_deepseek_success(client, tmp_path, monkeypatch):
    _set_cfg(str(tmp_path / 'ai.db'))

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured['url'] = url
        captured['auth'] = headers.get('Authorization')
        captured['model'] = json['model']

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    'choices': [{'message': {'content': '建议返工处理'}}],
                    'model': 'deepseek-chat',
                    'usage': {'total_tokens': 120},
                }

        return Resp()

    monkeypatch.setattr(ai_module.requests, 'post', fake_post)
    r = client.post('/api/ai/inspect', json={'text': 'SN001 过站检测不合格'})
    assert r.status_code == 200
    data = r.get_json()['data']
    assert data['reply'] == '建议返工处理'
    assert data['provider'] == 'deepseek'
    assert captured['url'] == 'https://api.deepseek.com/chat/completions'
    assert captured['auth'] == 'Bearer sk-test'
    assert captured['model'] == 'deepseek-chat'


def test_inspect_http_error_returns_502(client, tmp_path, monkeypatch):
    _set_cfg(str(tmp_path / 'ai.db'))

    class Resp:
        status_code = 401

        def raise_for_status(self):
            raise ai_module.requests.exceptions.HTTPError(response=self)

    monkeypatch.setattr(ai_module.requests, 'post', lambda *a, **k: Resp())
    r = client.post('/api/ai/inspect', json={'text': 'x'})
    assert r.status_code == 502
    assert 'Key' in r.get_json()['message']


def test_ai_config_roundtrip(client, tmp_path):
    _set_cfg(str(tmp_path / 'ai.db'))
    r = client.get('/api/ai/config')
    data = r.get_json()['data']
    assert data['ai_enabled'] is True
    assert data['ai_api_key_configured'] is True
    assert data['ai_model'] == 'deepseek-chat'
