"""MQTT QoS1 transport with mandatory mutual TLS."""

import json
import threading

from edge_gateway.delivery import DeliveryReceipt


class MqttEventTransport:
    def __init__(self, host, port, ca, cert, key, customer_code, factory_code,
                 gateway_id, timeout=10, client_factory=None):
        if client_factory is None:
            try:
                import paho.mqtt.client as mqtt
            except ImportError as exc:
                raise RuntimeError('paho-mqtt is required for MQTT transport') from exc
            client_factory = mqtt.Client
        self.client = client_factory()
        self.host = host; self.port = int(port); self.timeout = float(timeout)
        self.customer_code = customer_code; self.factory_code = factory_code
        self.gateway_id = gateway_id
        self._ack_lock = threading.Lock()
        self._acks = {}
        self.client.on_message = self._on_message
        self.client.tls_set(ca_certs=ca, certfile=cert, keyfile=key)
        rc = self.client.connect(self.host, self.port, keepalive=60)
        if rc not in (0, None):
            raise RuntimeError(f'MQTT connection failed: {rc}')
        subscribe = getattr(self.client, 'subscribe', None)
        if not subscribe:
            raise RuntimeError('MQTT client does not support application ACK subscription')
        subscribe(
            f'mes/v1/{self.customer_code}/{self.factory_code}/{self.gateway_id}/acks/+',
            qos=1,
        )
        self.client.loop_start()

    def _on_message(self, _client, _userdata, message):
        prefix = f'mes/v1/{self.customer_code}/{self.factory_code}/{self.gateway_id}/acks/'
        topic = str(getattr(message, 'topic', ''))
        if not topic.startswith(prefix):
            return
        try:
            body = json.loads(bytes(message.payload).decode('utf-8'))
            event_id = str(body.get('event_id') or topic[len(prefix):])
        except (ValueError, UnicodeDecodeError, TypeError):
            return
        with self._ack_lock:
            waiter = self._acks.get(event_id)
            if waiter:
                waiter['receipt'] = DeliveryReceipt(
                    bool(body.get('accepted')), bool(body.get('duplicate', False)),
                    str(body.get('message') or ''), bool(body.get('retryable', True)),
                )
                waiter['event'].set()

    @classmethod
    def from_config(cls, config, client_factory=None):
        return cls(config.mqtt_host, config.mqtt_port, config.mqtt_ca,
                   config.mqtt_cert, config.mqtt_key, config.customer_code,
                   config.factory_code, config.gateway_id,
                   timeout=config.transport_timeout_seconds,
                   client_factory=client_factory)

    def send(self, event):
        if (event.customer_code, event.factory_code, event.gateway_code) != (
                self.customer_code, self.factory_code, self.gateway_id):
            return DeliveryReceipt(
                False, False, 'MQTT event identity is outside configured scope', False
            )
        topic = (
            f'mes/v1/{self.customer_code}/{self.factory_code}/'
            f'{self.gateway_id}/events/{event.device_code}'
        )
        payload = json.dumps(event.to_dict(), ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False)
        waiter = {'event': threading.Event(), 'receipt': None}
        with self._ack_lock:
            self._acks[event.event_id] = waiter
        info = self.client.publish(topic, payload=payload, qos=1, retain=False)
        if getattr(info, 'rc', 0) != 0:
            with self._ack_lock: self._acks.pop(event.event_id, None)
            return DeliveryReceipt(False, False, f'MQTT publish failed: {info.rc}')
        info.wait_for_publish(timeout=self.timeout)
        if not info.is_published():
            with self._ack_lock: self._acks.pop(event.event_id, None)
            return DeliveryReceipt(False, False, 'MQTT PUBACK timeout')
        if not waiter['event'].wait(timeout=self.timeout):
            with self._ack_lock: self._acks.pop(event.event_id, None)
            return DeliveryReceipt(False, False, 'MQTT central application ACK timeout')
        with self._ack_lock:
            self._acks.pop(event.event_id, None)
        return waiter['receipt'] or DeliveryReceipt(False, False, 'MQTT central application ACK missing')

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
