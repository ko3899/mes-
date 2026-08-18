"""Small, dependency-free protocol plugin boundary for edge drivers.

Plugins receive a context and emit standard events through callbacks; they never
receive a database connection.  The registry is intentionally strict so a
partner driver cannot silently request database or arbitrary process access.
"""

from dataclasses import dataclass
import multiprocessing
from types import MappingProxyType
from typing import Any, Mapping


ALLOWED_PERMISSIONS = frozenset({'network', 'serial', 'usb', 'filesystem'})
SUPPORTED_PLATFORMS = frozenset({'windows', 'linux', 'darwin'})


class PluginPermissionError(PermissionError):
    pass


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    version: str
    entrypoint: str
    platforms: tuple
    permissions: frozenset

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]):
        if not isinstance(data, Mapping):
            raise ValueError('plugin manifest must be an object')
        required = ('plugin_id', 'version', 'entrypoint')
        for name in required:
            if not isinstance(data.get(name), str) or not data[name].strip():
                raise ValueError(f'{name} is required')
        raw_platforms = data.get('platforms', ())
        raw_permissions = data.get('permissions', ())
        if isinstance(raw_platforms, (str, bytes)) or isinstance(raw_permissions, (str, bytes)):
            raise ValueError('platforms and permissions must be arrays')
        platforms = tuple(str(value).strip().lower() for value in raw_platforms)
        permissions = frozenset(str(value).strip().lower() for value in raw_permissions)
        unknown_platforms = set(platforms) - SUPPORTED_PLATFORMS
        if unknown_platforms:
            raise ValueError(f'unknown plugin platform: {sorted(unknown_platforms)[0]}')
        unknown = permissions - ALLOWED_PERMISSIONS
        if unknown:
            raise ValueError(f'unknown plugin permission: {sorted(unknown)[0]}')
        if not platforms:
            raise ValueError('platforms is required')
        return cls(data['plugin_id'].strip(), data['version'].strip(),
                   data['entrypoint'].strip(), platforms, permissions)


@dataclass
class DriverContext:
    config: Mapping[str, Any]
    emit_event: Any = None
    read_command: Any = None
    log: Any = None

    def __post_init__(self):
        if not isinstance(self.config, Mapping):
            raise TypeError('driver config must be a mapping')
        self.config = MappingProxyType(dict(self.config))


class PluginRegistry:
    def __init__(self):
        self._factories = {}
        self._manifests = {}

    def register(self, manifest, factory):
        if not isinstance(manifest, PluginManifest):
            raise TypeError('manifest must be PluginManifest')
        if manifest.plugin_id in self._factories:
            raise ValueError(f'plugin already registered: {manifest.plugin_id}')
        if not callable(factory):
            raise TypeError('plugin factory must be callable')
        self._manifests[manifest.plugin_id] = manifest
        self._factories[manifest.plugin_id] = factory

    def require_permission(self, manifest, permission):
        if str(permission).lower() not in manifest.permissions:
            raise PluginPermissionError(
                f'plugin {manifest.plugin_id} did not declare {permission} permission'
            )

    def create(self, plugin_id, context, platform=None, required_permissions=()):
        manifest = self._manifests.get(plugin_id)
        if manifest is None:
            raise KeyError(f'unknown plugin: {plugin_id}')
        if not isinstance(context, DriverContext):
            raise TypeError('context must be DriverContext')
        if platform and str(platform).lower() not in manifest.platforms:
            raise ValueError(f'plugin {plugin_id} does not support platform {platform}')
        for permission in required_permissions:
            self.require_permission(manifest, permission)
        return self._factories[plugin_id](context)

    def manifests(self):
        return tuple(self._manifests.values())


class PluginWorker:
    """Run one driver in an isolated process with a stop event."""

    def __init__(self, target, args=()):
        self._stop = multiprocessing.Event()
        self._process = multiprocessing.Process(target=target, args=tuple(args) + (self._stop,))

    def start(self):
        self._process.start()

    def stop(self, timeout=5):
        self._stop.set()
        self._process.join(timeout)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout)

    @property
    def alive(self):
        return self._process.is_alive()

    @property
    def health(self):
        return 'running' if self._process.is_alive() else ('stopped' if self._process.exitcode in (0, None) else 'failed')
