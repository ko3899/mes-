"""Central MQTT consumer completing the edge-to-MES event path."""

import json
import re
import sqlite3
from urllib.parse import quote

from device_platform.contracts import ContractError, DeviceEvent
from services.device_event_ingest import ingest_device_event


TOPIC = re.compile(r'^mes/v1/([^/]+)/([^/]+)/([^/]+)/events/([^/]+)$')


class MqttEventConsumer:
    def __init__(self, host, port, ca, cert, key, db, client_factory=None):
        if client_factory is None:
            try:
                import paho.mqtt.client as mqtt
            except ImportError as exc:
                raise RuntimeError('paho-mqtt is required for MQTT consumer') from exc
            client_factory = mqtt.Client
        self.db = db
        self.client = client_factory()
        self.client.tls_set(ca_certs=ca, certfile=cert, keyfile=key)
        self.host, self.port = str(host), int(port)
        self.client.on_message = self._on_message
        self.db.execute('''CREATE TABLE IF NOT EXISTS iot_mqtt_rejected_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            payload TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        self.db.commit()

    def start(self):
        rc = self.client.connect(self.host, self.port, keepalive=60)
        if rc not in (0, None):
            raise RuntimeError(f'MQTT consumer connection failed: {rc}')
        self.client.subscribe('mes/v1/+/+/+/events/+', qos=1)
        self.client.loop_start()

    def _on_message(self, _client, _userdata, message):
        match = TOPIC.match(str(message.topic))
        if not match:
            self._reject(message, 'invalid topic')
            return
        customer, factory, gateway, device = match.groups()
        event_id = ''
        try:
            event = DeviceEvent.from_dict(json.loads(bytes(message.payload).decode('utf-8')))
            event_id = event.event_id
            if (event.customer_code, event.factory_code, event.gateway_code, event.device_code) != (
                    customer, factory, gateway, device):
                raise ContractError('MQTT topic and event identity mismatch')
            result = ingest_device_event(self.db, event)
            if not result.accepted:
                raise ContractError('MQTT event sequence conflict')
            self._ack(customer, factory, gateway, event.device_code, event.event_id,
                      accepted=True, duplicate=result.duplicate)
        except Exception as exc:
            if not event_id:
                try:
                    event_id = str(json.loads(bytes(message.payload).decode('utf-8')).get('event_id') or '')
                except Exception:
                    event_id = ''
            if event_id:
                self._ack(customer, factory, gateway, device, event_id,
                          accepted=False, ack_message=str(exc),
                          retryable=isinstance(exc, sqlite3.OperationalError))
            try:
                self._reject(message, str(exc))
            except sqlite3.Error:
                # A locked/unavailable database must not tear down the MQTT
                # callback thread; the edge will retry after the non-accepted ACK.
                pass
            return

    def _ack(self, customer, factory, gateway, device, event_id, accepted,
             duplicate=False, ack_message='', retryable=True):
        topic = (f'mes/v1/{customer}/{factory}/{gateway}/acks/'
                 f'{quote(str(event_id), safe="")}')
        payload = json.dumps({
            'event_id': str(event_id), 'device_code': str(device),
            'accepted': bool(accepted), 'duplicate': bool(duplicate),
            'message': str(ack_message), 'retryable': bool(retryable),
        }, separators=(',', ':'))
        info = self.client.publish(topic, payload=payload, qos=1, retain=False)
        if getattr(info, 'rc', 0) not in (0, None):
            # ACK failure is itself auditable, but never turns a valid event
            # into a second ingestion attempt.
            self.db.execute(
                'INSERT INTO iot_mqtt_rejected_event(topic,payload,reason) VALUES(?,?,?)',
                (topic, payload, 'application ACK publish failed'),
            )
            self.db.commit()

    def _reject(self, message, reason):
        self.db.execute(
            'INSERT INTO iot_mqtt_rejected_event(topic,payload,reason) VALUES(?,?,?)',
            (str(message.topic), bytes(message.payload)[:512 * 1024].decode('utf-8', errors='replace'),
             str(reason)[:500]),
        )
        self.db.commit()

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
