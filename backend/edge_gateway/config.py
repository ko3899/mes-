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
    http_url: str = None
    http_secret: str = None

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
        http_url = http_secret = None
        if transport == 'http':
            http_url = _required(values, 'MES_EDGE_HTTP_URL')
            if urlparse(http_url).scheme.lower() != 'https':
                raise EdgeConfigError('MES_EDGE_HTTP_URL must use https')
            http_secret = _required(values, 'MES_EDGE_HTTP_SECRET')
        return cls(database_path, gateway_id, transport, poll, lease, batch,
                   http_url, http_secret)

    def safe_summary(self):
        return {
            'database_path': self.database_path,
            'gateway_id': self.gateway_id,
            'transport': self.transport,
            'poll_seconds': self.poll_seconds,
            'lease_seconds': self.lease_seconds,
            'batch_size': self.batch_size,
            'http_url': self.http_url,
            'http_secret_configured': bool(self.http_secret),
        }
