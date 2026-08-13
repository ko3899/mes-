import os
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from edge_gateway.config import EdgeConfig, EdgeConfigError  # noqa: E402


def env(**overrides):
    values = {
        'MES_EDGE_DB': r'D:\MES-Edge\data\events.db',
        'MES_EDGE_GATEWAY_ID': 'GW-F01-A',
        'MES_EDGE_TRANSPORT': 'http',
        'MES_EDGE_HTTP_URL': 'https://mes.local',
        'MES_EDGE_HTTP_SECRET': 'secret-value',
        'MES_EDGE_POLL_SECONDS': '2',
        'MES_EDGE_LEASE_SECONDS': '30',
        'MES_EDGE_BATCH_SIZE': '20',
    }
    values.update(overrides)
    return values


def test_http_config_is_strict_and_secret_safe():
    config = EdgeConfig.from_env(env())
    assert config.gateway_id == 'GW-F01-A'
    assert config.transport == 'http'
    assert config.safe_summary()['http_secret_configured'] is True
    assert 'secret-value' not in str(config.safe_summary())
    with pytest.raises(EdgeConfigError):
        EdgeConfig.from_env(env(MES_EDGE_HTTP_URL='http://mes.local'))


@pytest.mark.parametrize('key,value', [
    ('MES_EDGE_DB', ''), ('MES_EDGE_GATEWAY_ID', ''),
    ('MES_EDGE_TRANSPORT', 'unknown'), ('MES_EDGE_POLL_SECONDS', '0'),
    ('MES_EDGE_LEASE_SECONDS', '3'), ('MES_EDGE_BATCH_SIZE', '0'),
])
def test_config_rejects_missing_or_unsafe_values(key, value):
    with pytest.raises(EdgeConfigError):
        EdgeConfig.from_env(env(**{key: value}))


def test_cli_once_runs_one_bounded_cycle(monkeypatch, tmp_path):
    import edge_gateway_service as cli
    config = EdgeConfig.from_env(env(MES_EDGE_DB=str(tmp_path / 'events.db')))
    calls = []
    class Pump:
        def run_once(self, limit):
            calls.append(limit)
            return type('Summary', (), {'claimed': 0, 'sent': 0, 'failed': 0})()
    monkeypatch.setattr(cli, 'load_config', lambda: config)
    monkeypatch.setattr(cli, 'build_pump', lambda cfg: Pump())
    assert cli.main(['--once']) == 0
    assert calls == [20]
