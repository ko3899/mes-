import os
import sys
import json

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from device_platform.contracts import DeviceEvent  # noqa: E402
from edge_gateway.config import EdgeConfig, EdgeConfigError  # noqa: E402
from edge_gateway.mqtt_transport import MqttEventTransport  # noqa: E402


def event():
    return DeviceEvent.from_dict({
        'schema_version': '1.0', 'event_id': 'E1', 'customer_code': 'C',
        'factory_code': 'F01', 'gateway_code': 'GW1', 'device_code': 'D1',
        'event_type': 'device.connected', 'occurred_at': '2026-08-13T10:30:18+08:00',
        'received_at': None, 'sequence': 1, 'correlation_id': None,
        'payload': {}, 'raw_reference': None,
    })


class Info:
    rc = 0
    def __init__(self, published=True): self.published = published
    def wait_for_publish(self, timeout): self.timeout = timeout
    def is_published(self): return self.published


class Client:
    def __init__(self, info=None): self.info = info or Info(); self.calls = []; self.on_message = None
    def tls_set(self, **kwargs): self.calls.append(('tls', kwargs))
    def connect(self, host, port, keepalive): self.calls.append(('connect', host, port, keepalive)); return 0
    def subscribe(self, topic, qos): self.calls.append(('subscribe', topic, qos))
    def loop_start(self): self.calls.append(('start',))
    def publish(self, topic, payload, qos, retain):
        self.calls.append(('publish', topic, payload, qos, retain))
        if '/events/' in topic and self.on_message:
            event_id = json.loads(payload)['event_id']
            message = type('AckMessage', (), {
                'topic': topic.replace('/events/', '/acks/'),
                'payload': json.dumps({'event_id': event_id, 'accepted': True}).encode(),
            })()
            self.on_message(self, None, message)
        return self.info
    def loop_stop(self): self.calls.append(('stop',))
    def disconnect(self): self.calls.append(('disconnect',))


def mqtt_env(tmp_path, **overrides):
    for name in ('ca.pem', 'client.pem', 'client.key'):
        (tmp_path / name).write_text('test')
    values = {
        'MES_EDGE_DB': str(tmp_path / 'edge.db'), 'MES_EDGE_GATEWAY_ID': 'GW1',
        'MES_EDGE_TRANSPORT': 'mqtt', 'MES_EDGE_MQTT_HOST': 'broker.local',
        'MES_EDGE_MQTT_PORT': '8883', 'MES_EDGE_MQTT_CA': str(tmp_path / 'ca.pem'),
        'MES_EDGE_MQTT_CERT': str(tmp_path / 'client.pem'),
        'MES_EDGE_MQTT_KEY': str(tmp_path / 'client.key'),
        'MES_EDGE_CUSTOMER_CODE': 'C', 'MES_EDGE_FACTORY_CODE': 'F01',
        'MES_EDGE_MQTT_CENTRAL_CONSUMER_CONFIRMED': '1',
    }
    values.update(overrides); return values


def test_mqtt_publishes_exact_topic_with_qos1_and_tls(tmp_path):
    config = EdgeConfig.from_env(mqtt_env(tmp_path))
    client = Client()
    transport = MqttEventTransport.from_config(config, client_factory=lambda: client)
    receipt = transport.send(event())
    assert receipt.accepted and not receipt.duplicate
    publish = next(call for call in client.calls if call[0] == 'publish')
    assert publish[1] == 'mes/v1/C/F01/GW1/events/D1'
    assert publish[3:] == (1, False)
    assert any(call[0] == 'tls' for call in client.calls)


def test_mqtt_requires_existing_tls_files(tmp_path):
    values = mqtt_env(tmp_path, MES_EDGE_MQTT_CA=str(tmp_path / 'missing.pem'))
    with pytest.raises(EdgeConfigError): EdgeConfig.from_env(values)


def test_mqtt_puback_timeout_returns_failed_receipt(tmp_path):
    config = EdgeConfig.from_env(mqtt_env(tmp_path))
    transport = MqttEventTransport.from_config(
        config, client_factory=lambda: Client(Info(published=False))
    )
    receipt = transport.send(event())
    assert not receipt.accepted and 'PUBACK' in receipt.message


def test_mqtt_rejects_payload_identity_outside_configured_scope(tmp_path):
    config = EdgeConfig.from_env(mqtt_env(tmp_path))
    client = Client()
    transport = MqttEventTransport.from_config(config, client_factory=lambda: client)
    item = event().to_dict(); item['factory_code'] = 'OTHER'
    receipt = transport.send(DeviceEvent.from_dict(item))
    assert not receipt.accepted and receipt.retryable is False
    assert not any(call[0] == 'publish' for call in client.calls)


def test_mqtt_requires_central_consumer_confirmation(tmp_path):
    values = mqtt_env(tmp_path)
    values.pop('MES_EDGE_MQTT_CENTRAL_CONSUMER_CONFIRMED')
    with pytest.raises(EdgeConfigError, match='consumer'):
        EdgeConfig.from_env(values)
