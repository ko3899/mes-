import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from edge_gateway.plugins import (  # noqa: E402
    PluginManifest, PluginRegistry, PluginPermissionError, DriverContext,
)


def test_manifest_and_registry_enforce_declared_permissions():
    manifest = PluginManifest.from_dict({
        'plugin_id': 'tcp.line', 'version': '1.0.0', 'entrypoint': 'tests.fake:Driver',
        'platforms': ['windows', 'linux'], 'permissions': ['network'],
    })
    registry = PluginRegistry()
    registry.register(manifest, lambda context: {'context': context})
    assert registry.create('tcp.line', DriverContext({'host': '127.0.0.1'}))['context'].config['host'] == '127.0.0.1'
    try:
        registry.require_permission(manifest, 'serial')
        assert False, 'expected permission failure'
    except PluginPermissionError:
        pass


def test_plugin_manifest_rejects_unknown_permissions():
    try:
        PluginManifest.from_dict({
            'plugin_id': 'bad', 'version': '1', 'entrypoint': 'x:y',
            'platforms': ['linux'], 'permissions': ['database'],
        })
        assert False, 'expected validation failure'
    except ValueError as exc:
        assert 'permission' in str(exc)
