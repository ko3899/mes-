"""MQTT QoS1 transport with mandatory mutual TLS."""

import json

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
        self.client.tls_set(ca_certs=ca, certfile=cert, keyfile=key)
        rc = self.client.connect(self.host, self.port, keepalive=60)
        if rc not in (0, None):
            raise RuntimeError(f'MQTT connection failed: {rc}')
        self.client.loop_start()

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
        info = self.client.publish(topic, payload=payload, qos=1, retain=False)
        if getattr(info, 'rc', 0) != 0:
            return DeliveryReceipt(False, False, f'MQTT publish failed: {info.rc}')
        info.wait_for_publish(timeout=self.timeout)
        if not info.is_published():
            return DeliveryReceipt(False, False, 'MQTT PUBACK timeout')
        return DeliveryReceipt(True, False)

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
