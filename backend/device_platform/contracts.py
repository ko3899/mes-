"""Versioned, transport-neutral device event and command contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import json
from types import MappingProxyType
from typing import Any, Mapping


SCHEMA_VERSION = '1.0'

EVENT_TYPES = frozenset({
    'barcode.scanned',
    'device.connected',
    'device.disconnected',
    'device.state.changed',
    'production.started',
    'production.completed',
    'quality.completed',
    'measurement.sampled',
    'alarm.raised',
    'alarm.cleared',
    'count.changed',
    'energy.sampled',
    'command.acknowledged',
    'command.failed',
})

COMMAND_TYPES = frozenset({
    'production.authorize',
    'recipe.apply',
    'parameter.write',
    'task.control',
})


class ContractError(ValueError):
    """Raised when an event or command violates the published contract."""


def _required_text(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f'{name} must be a non-empty string')
    return value.strip()


def _optional_text(data: Mapping[str, Any], name: str) -> str | None:
    value = data.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f'{name} must be null or a non-empty string')
    return value.strip()


def _timestamp(value: Any, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f'{name} must be an RFC 3339 timestamp')
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ContractError(f'{name} must be an RFC 3339 timestamp') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f'{name} must include a timezone offset')
    return text


def _json_payload(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ContractError('payload must be a JSON object')
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        copied = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ContractError('payload must contain only valid JSON values') from exc
    return copied


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return deepcopy(value)


def _reject_unknown(data: Mapping[str, Any], fields: frozenset[str]) -> None:
    unknown = set(data) - fields
    if unknown:
        raise ContractError(f'unknown fields: {", ".join(sorted(unknown))}')


@dataclass(frozen=True)
class DeviceEvent:
    schema_version: str
    event_id: str
    customer_code: str
    factory_code: str
    gateway_code: str
    device_code: str
    event_type: str
    occurred_at: str
    received_at: str | None
    sequence: int
    correlation_id: str | None
    payload: Mapping[str, Any]
    raw_reference: str | None

    FIELDS = frozenset({
        'schema_version', 'event_id', 'customer_code', 'factory_code',
        'gateway_code', 'device_code', 'event_type', 'occurred_at',
        'received_at', 'sequence', 'correlation_id', 'payload', 'raw_reference',
    })

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'DeviceEvent':
        if not isinstance(data, Mapping):
            raise ContractError('event must be a JSON object')
        _reject_unknown(data, cls.FIELDS)
        schema_version = _required_text(data, 'schema_version')
        if schema_version != SCHEMA_VERSION:
            raise ContractError(f'unsupported schema_version: {schema_version}')
        event_type = _required_text(data, 'event_type')
        if event_type not in EVENT_TYPES:
            raise ContractError(f'unsupported event_type: {event_type}')
        sequence = data.get('sequence')
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ContractError('sequence must be a positive integer')
        return cls(
            schema_version=schema_version,
            event_id=_required_text(data, 'event_id'),
            customer_code=_required_text(data, 'customer_code'),
            factory_code=_required_text(data, 'factory_code'),
            gateway_code=_required_text(data, 'gateway_code'),
            device_code=_required_text(data, 'device_code'),
            event_type=event_type,
            occurred_at=_timestamp(data.get('occurred_at'), 'occurred_at'),
            received_at=_timestamp(data.get('received_at'), 'received_at', optional=True),
            sequence=sequence,
            correlation_id=_optional_text(data, 'correlation_id'),
            payload=_freeze(_json_payload(data.get('payload'))),
            raw_reference=_optional_text(data, 'raw_reference'),
        )

    def to_dict(self) -> dict:
        return {
            'schema_version': self.schema_version,
            'event_id': self.event_id,
            'customer_code': self.customer_code,
            'factory_code': self.factory_code,
            'gateway_code': self.gateway_code,
            'device_code': self.device_code,
            'event_type': self.event_type,
            'occurred_at': self.occurred_at,
            'received_at': self.received_at,
            'sequence': self.sequence,
            'correlation_id': self.correlation_id,
            'payload': _thaw(self.payload),
            'raw_reference': self.raw_reference,
        }


@dataclass(frozen=True)
class DeviceCommand:
    schema_version: str
    command_id: str
    factory_code: str
    gateway_code: str
    device_code: str
    command_type: str
    created_at: str
    expires_at: str
    idempotency_key: str
    config_version: str | None
    payload: Mapping[str, Any]

    FIELDS = frozenset({
        'schema_version', 'command_id', 'factory_code', 'gateway_code',
        'device_code', 'command_type', 'created_at', 'expires_at',
        'idempotency_key', 'config_version', 'payload',
    })

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'DeviceCommand':
        if not isinstance(data, Mapping):
            raise ContractError('command must be a JSON object')
        _reject_unknown(data, cls.FIELDS)
        schema_version = _required_text(data, 'schema_version')
        if schema_version != SCHEMA_VERSION:
            raise ContractError(f'unsupported schema_version: {schema_version}')
        command_type = _required_text(data, 'command_type')
        if command_type not in COMMAND_TYPES:
            raise ContractError(f'unsupported command_type: {command_type}')
        created_at = _timestamp(data.get('created_at'), 'created_at')
        expires_at = _timestamp(data.get('expires_at'), 'expires_at')
        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        if expires <= created:
            raise ContractError('expires_at must be later than created_at')
        return cls(
            schema_version=schema_version,
            command_id=_required_text(data, 'command_id'),
            factory_code=_required_text(data, 'factory_code'),
            gateway_code=_required_text(data, 'gateway_code'),
            device_code=_required_text(data, 'device_code'),
            command_type=command_type,
            created_at=created_at,
            expires_at=expires_at,
            idempotency_key=_required_text(data, 'idempotency_key'),
            config_version=_optional_text(data, 'config_version'),
            payload=_freeze(_json_payload(data.get('payload'))),
        )

    def is_expired(self, now: datetime) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ContractError('now must include a timezone offset')
        expires = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return now >= expires

    def to_dict(self) -> dict:
        return {
            'schema_version': self.schema_version,
            'command_id': self.command_id,
            'factory_code': self.factory_code,
            'gateway_code': self.gateway_code,
            'device_code': self.device_code,
            'command_type': self.command_type,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'idempotency_key': self.idempotency_key,
            'config_version': self.config_version,
            'payload': _thaw(self.payload),
        }
