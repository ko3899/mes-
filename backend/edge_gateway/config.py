"""Strict environment configuration for the standalone edge service."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class EdgeConfigError(ValueError):
    pass


def _required(values, key):
    value = str(values.get(key, '')).strip()
    if not value:
        raise EdgeConfigError(f'{key} is required')
    return value


def _integer(values, key, default, minimum, maximum):
    try:
        value = int(str(values.get(key, default)).strip())
    except ValueError as exc:
        raise EdgeConfigError(f'{key} must be an integer') from exc
    if not minimum <= value <= maximum:
        raise EdgeConfigError(f'{key} must be between {minimum} and {maximum}')
    return value


@dataclass(frozen=True)
class EdgeConfig:
    database_path: str
    gateway_id: str
    transport: str
    poll_seconds: int
    lease_seconds: int
    batch_size: int
    transport_timeout_seconds: int
    http_url: str = None
    http_secret: str = None
    mqtt_host: str = None
    mqtt_port: int = None
    mqtt_ca: str = None
    mqtt_cert: str = None
    mqtt_key: str = None
    customer_code: str = None
    factory_code: str = None
    mqtt_central_consumer_confirmed: bool = False

    @classmethod
    def from_env(cls, values):
        database_path = str(Path(_required(values, 'MES_EDGE_DB')).resolve())
        gateway_id = _required(values, 'MES_EDGE_GATEWAY_ID')
        transport = _required(values, 'MES_EDGE_TRANSPORT').lower()
        if transport not in ('http', 'mqtt'):
            raise EdgeConfigError('MES_EDGE_TRANSPORT must be http or mqtt')
        poll = _integer(values, 'MES_EDGE_POLL_SECONDS', 2, 1, 300)
        lease = _integer(values, 'MES_EDGE_LEASE_SECONDS', 30, 5, 3600)
        batch = _integer(values, 'MES_EDGE_BATCH_SIZE', 20, 1, 500)
        timeout_key = ('MES_EDGE_HTTP_TIMEOUT_SECONDS' if transport == 'http'
                       else 'MES_EDGE_MQTT_TIMEOUT_SECONDS')
        timeout = _integer(values, timeout_key, 5 if transport == 'http' else 10, 1, 300)
        if lease < timeout + 5:
            raise EdgeConfigError(f'MES_EDGE_LEASE_SECONDS must be at least {timeout + 5}')
        http_url = http_secret = None
        if transport == 'http':
            http_url = _required(values, 'MES_EDGE_HTTP_URL')
            if urlparse(http_url).scheme.lower() != 'https':
                raise EdgeConfigError('MES_EDGE_HTTP_URL must use https')
            http_secret = _required(values, 'MES_EDGE_HTTP_SECRET')
        mqtt_host = mqtt_port = mqtt_ca = mqtt_cert = mqtt_key = None
        customer_code = factory_code = None
        if transport == 'mqtt':
            confirmed = str(values.get(
                'MES_EDGE_MQTT_CENTRAL_CONSUMER_CONFIRMED', '0'
            )).strip().lower() in ('1', 'true', 'yes')
            if not confirmed:
                raise EdgeConfigError(
                    'MQTT central consumer confirmation is required before production use'
                )
            mqtt_host = _required(values, 'MES_EDGE_MQTT_HOST')
            mqtt_port = _integer(values, 'MES_EDGE_MQTT_PORT', 8883, 1, 65535)
            mqtt_ca = _required(values, 'MES_EDGE_MQTT_CA')
            mqtt_cert = _required(values, 'MES_EDGE_MQTT_CERT')
            mqtt_key = _required(values, 'MES_EDGE_MQTT_KEY')
            for key, path in (('MES_EDGE_MQTT_CA', mqtt_ca), ('MES_EDGE_MQTT_CERT', mqtt_cert),
                              ('MES_EDGE_MQTT_KEY', mqtt_key)):
                if not Path(path).is_file():
                    raise EdgeConfigError(f'{key} file does not exist')
            customer_code = _required(values, 'MES_EDGE_CUSTOMER_CODE')
            factory_code = _required(values, 'MES_EDGE_FACTORY_CODE')
        return cls(database_path, gateway_id, transport, poll, lease, batch, timeout,
                   http_url, http_secret, mqtt_host, mqtt_port, mqtt_ca,
                   mqtt_cert, mqtt_key, customer_code, factory_code,
                   transport != 'mqtt' or confirmed)

    def safe_summary(self):
        return {
            'database_path': self.database_path,
            'gateway_id': self.gateway_id,
            'transport': self.transport,
            'poll_seconds': self.poll_seconds,
            'lease_seconds': self.lease_seconds,
            'batch_size': self.batch_size,
            'transport_timeout_seconds': self.transport_timeout_seconds,
            'http_url': self.http_url,
            'http_secret_configured': bool(self.http_secret),
            'mqtt_host': self.mqtt_host,
            'mqtt_port': self.mqtt_port,
            'mqtt_tls_configured': bool(self.mqtt_ca and self.mqtt_cert and self.mqtt_key),
            'customer_code': self.customer_code,
            'factory_code': self.factory_code,
            'mqtt_central_consumer_confirmed': self.mqtt_central_consumer_confirmed,
        }
