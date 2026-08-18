import json
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from services.mqtt_event_consumer import MqttEventConsumer  # noqa: E402
from services.device_event_ingest import create_device_event_tables  # noqa: E402


class Info:
    rc = 0


class Client:
    def __init__(self):
        self.calls = []
        self.on_message = None

    def tls_set(self, **kwargs): self.calls.append(('tls', kwargs))
    def connect(self, *args, **kwargs): self.calls.append(('connect', args, kwargs)); return 0
    def subscribe(self, topic, qos): self.calls.append(('subscribe', topic, qos))
    def publish(self, topic, payload, qos, retain): self.calls.append(('publish', topic, payload, qos, retain)); return Info()
    def loop_start(self): self.calls.append(('start',))
    def loop_stop(self): self.calls.append(('stop',))
    def disconnect(self): self.calls.append(('disconnect',))


class Message:
    topic = 'mes/v1/C/F1/GW1/events/D1'
    payload = json.dumps({
        'schema_version': '1.0', 'event_id': 'MQ1', 'customer_code': 'C',
        'factory_code': 'F1', 'gateway_code': 'GW1', 'device_code': 'D1',
        'event_type': 'device.connected', 'occurred_at': '2026-08-16T10:00:00+08:00',
        'received_at': None, 'sequence': 1, 'correlation_id': None,
        'payload': {}, 'raw_reference': None,
    }).encode()


def test_consumer_subscribes_and_ingests_matching_topic(tmp_path):
    db = sqlite3.connect(tmp_path / 'central.db'); db.row_factory = sqlite3.Row
    create_device_event_tables(db)
    client = Client()
    consumer = MqttEventConsumer('broker', 8883, 'ca', 'cert', 'key', db,
                                 client_factory=lambda: client)
    consumer.start()
    assert any(call[0] == 'subscribe' for call in client.calls)
    client.on_message(client, None, Message())
    assert db.execute('SELECT event_id FROM iot_device_event').fetchone()[0] == 'MQ1'
    consumer.close()


def test_consumer_quarantines_topic_identity_mismatch(tmp_path):
    db = sqlite3.connect(tmp_path / 'central.db'); db.row_factory = sqlite3.Row
    create_device_event_tables(db)
    client = Client()
    consumer = MqttEventConsumer('broker', 8883, 'ca', 'cert', 'key', db,
                                 client_factory=lambda: client)
    bad = Message()
    bad.topic = 'mes/v1/C/F1/GW1/events/OTHER'
    client.on_message(client, None, bad)
    assert db.execute('SELECT COUNT(*) FROM iot_mqtt_rejected_event').fetchone()[0] == 1
