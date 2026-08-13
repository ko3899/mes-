import json
import os
import sqlite3
import sys
from urllib.error import HTTPError

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import create_app  # noqa: E402
from device_platform.contracts import DeviceEvent  # noqa: E402
from edge_gateway.http_transport import HttpEventTransport  # noqa: E402
from services.gateway_auth import build_signature  # noqa: E402
from utils import database  # noqa: E402


def event():
    return DeviceEvent.from_dict({
        'schema_version': '1.0', 'event_id': 'GW-E1', 'customer_code': 'C',
        'factory_code': 'F01', 'gateway_code': 'GW1', 'device_code': 'D1',
        'event_type': 'device.connected', 'occurred_at': '2026-08-13T10:30:18+08:00',
        'received_at': None, 'sequence': 1, 'correlation_id': None,
        'payload': {}, 'raw_reference': None,
    })


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    path = tmp_path / 'gateway.db'; monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db(); database._init_extra_tables()
    db = sqlite3.connect(path)
    db.execute("""INSERT INTO iot_gateway_credential
               (gateway_code,customer_code,factory_code,secret_fingerprint,enabled)
               VALUES('GW1','C','F01',?,1)""",
               (__import__('hashlib').sha256(b'secret').hexdigest(),))
    db.commit(); db.close()
    monkeypatch.setenv('MES_GATEWAY_SECRETS_JSON', '{"GW1":"secret"}')
    app = create_app(); app.config.update(TESTING=True)
    return app.test_client()


def signed_headers(body, timestamp='1786590000', nonce='nonce-1', secret='secret'):
    return {
        'X-Gateway-Id': 'GW1', 'X-Gateway-Time': timestamp,
        'X-Gateway-Nonce': nonce,
        'X-Gateway-Signature': build_signature('GW1', timestamp, nonce, body, secret),
        'Content-Type': 'application/json',
    }


def test_gateway_endpoint_accepts_valid_signature_and_rejects_replay(app_client, monkeypatch):
    monkeypatch.setattr('services.gateway_auth.time.time', lambda: 1786590000)
    body = json.dumps(event().to_dict(), ensure_ascii=False, separators=(',', ':')).encode()
    first = app_client.post('/api/device-platform/gateway-events', data=body, headers=signed_headers(body))
    replay = app_client.post('/api/device-platform/gateway-events', data=body, headers=signed_headers(body))
    assert first.status_code == 201
    assert replay.status_code == 401


def test_gateway_endpoint_rejects_invalid_and_stale_signatures(app_client, monkeypatch):
    monkeypatch.setattr('services.gateway_auth.time.time', lambda: 1786590000)
    body = json.dumps(event().to_dict(), separators=(',', ':')).encode()
    assert app_client.post('/api/device-platform/gateway-events', data=body,
                           headers=signed_headers(body, secret='wrong')).status_code == 401
    assert app_client.post('/api/device-platform/gateway-events', data=body,
                           headers=signed_headers(body, timestamp='1786589000', nonce='n2')).status_code == 401


def test_gateway_scope_blocks_cross_tenant_and_nonce_rows_expire(app_client, monkeypatch):
    monkeypatch.setattr('services.gateway_auth.time.time', lambda: 1786590000)
    bad = event().to_dict(); bad['customer_code'] = 'OTHER'
    body = json.dumps(bad, separators=(',', ':')).encode()
    assert app_client.post('/api/device-platform/gateway-events', data=body,
                           headers=signed_headers(body, nonce='scope')).status_code == 401
    good = json.dumps(event().to_dict(), separators=(',', ':')).encode()
    assert app_client.post('/api/device-platform/gateway-events', data=good,
                           headers=signed_headers(good, nonce='fresh')).status_code == 201
    db = sqlite3.connect(database.DB_PATH)
    db.execute("UPDATE iot_gateway_nonce SET expires_at=1")
    db.commit(); db.close()
    assert app_client.post('/api/device-platform/gateway-events', data=good,
                           headers=signed_headers(good, nonce='newer')).status_code in (200, 201)
    db = sqlite3.connect(database.DB_PATH)
    assert db.execute('SELECT COUNT(*) FROM iot_gateway_nonce').fetchone()[0] == 1


def test_http_transport_maps_success_and_duplicate_receipts(monkeypatch):
    calls = []
    class Response:
        status = 200
        def read(self): return b'{"code":0,"data":{"accepted":true,"duplicate":true}}'
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def opener(request, timeout): calls.append((request, timeout)); return Response()
    transport = HttpEventTransport('https://mes.local', 'GW1', 'secret', opener=opener,
                                   clock=lambda: 1786590000, nonce_factory=lambda: 'N1')
    receipt = transport.send(event())
    assert receipt.accepted and receipt.duplicate
    request, timeout = calls[0]
    assert request.full_url.endswith('/api/device-platform/gateway-events')
    assert request.headers['X-gateway-signature']
    assert timeout == 5


def test_http_transport_rejects_plain_http_and_maps_errors():
    with pytest.raises(ValueError):
        HttpEventTransport('http://mes.local', 'GW1', 'secret')
    def opener(request, timeout):
        raise HTTPError(request.full_url, 401, 'unauthorized', {}, None)
    receipt = HttpEventTransport('https://mes.local', 'GW1', 'secret', opener=opener).send(event())
    assert not receipt.accepted and '401' in receipt.message and receipt.retryable is False
