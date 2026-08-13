import os
import sqlite3
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import database  # noqa: E402
from app import create_app  # noqa: E402


def valid_event(**overrides):
    data = {
        'schema_version': '1.0',
        'event_id': 'EV-API-001',
        'customer_code': 'CUSTOMER-A',
        'factory_code': 'F01',
        'gateway_code': 'GW-F01-A',
        'device_code': 'D01',
        'event_type': 'device.connected',
        'occurred_at': '2026-08-13T10:30:18+08:00',
        'received_at': None,
        'sequence': 1,
        'correlation_id': None,
        'payload': {'address': '192.168.1.10'},
        'raw_reference': None,
    }
    data.update(overrides)
    return data


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / 'device-platform-api.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='device-platform-test')
    test_client = app.test_client()
    with test_client.session_transaction() as session:
        session['user_id'] = 1
        session['username'] = 'admin'
    return test_client


def test_event_api_accepts_once_and_reports_duplicate(client):
    created = client.post('/api/device-platform/events', json=valid_event())
    duplicate = client.post('/api/device-platform/events', json=valid_event())

    assert created.status_code == 201
    assert created.get_json()['data'] == {
        'accepted': True, 'duplicate': False, 'gap_expected': None,
        'gap_actual': None, 'sequence_conflict': False,
    }
    assert duplicate.status_code == 200
    assert duplicate.get_json()['data']['duplicate'] is True


def test_event_api_rejects_bad_contract_and_requires_login(client):
    bad = client.post('/api/device-platform/events', json=valid_event(sequence=0))
    assert bad.status_code == 400
    assert 'sequence' in bad.get_json()['message']

    anonymous = create_app().test_client()
    assert anonymous.post('/api/device-platform/events', json=valid_event()).status_code == 401
    assert anonymous.get('/api/device-platform/events').status_code == 401
    assert anonymous.get('/api/device-platform/health').status_code == 401


def test_event_list_filters_and_health_reports_real_gaps(client):
    assert client.post('/api/device-platform/events', json=valid_event()).status_code == 201
    second = valid_event(
        event_id='EV-API-003', sequence=3, event_type='quality.completed',
        payload={'sn': 'SN001', 'result': 'NG'},
    )
    assert client.post('/api/device-platform/events', json=second).status_code == 201

    listing = client.get(
        '/api/device-platform/events?factory_code=F01&device_code=D01&event_type=quality.completed'
    ).get_json()['data']
    assert listing['total'] == 1
    assert listing['list'][0]['event_id'] == 'EV-API-003'
    assert listing['list'][0]['payload']['result'] == 'NG'

    health = client.get('/api/device-platform/health').get_json()['data']
    assert health == {
        'total_events': 2,
        'pending_events': 2,
        'open_sequence_gaps': 1,
        'devices_seen': 1,
    }


def test_event_list_paginates_and_bounds_page_size(client):
    for sequence in range(1, 4):
        body = valid_event(event_id=f'EV-{sequence}', sequence=sequence)
        client.post('/api/device-platform/events', json=body)
    data = client.get('/api/device-platform/events?page=2&page_size=2').get_json()['data']
    assert data['page'] == 2
    assert data['page_size'] == 2
    assert data['total'] == 3
    assert len(data['list']) == 1
    assert client.get('/api/device-platform/events?page_size=501').status_code == 400
