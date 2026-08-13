import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from device_platform.contracts import DeviceEvent  # noqa: E402
from edge_gateway.delivery import DeliveryPump, DeliveryReceipt  # noqa: E402
from edge_gateway.event_store import EdgeEventStore  # noqa: E402


def event(device, sequence):
    return DeviceEvent.from_dict({
        'schema_version': '1.0', 'event_id': f'{device}-{sequence}',
        'customer_code': 'C', 'factory_code': 'F', 'gateway_code': 'GW',
        'device_code': device, 'event_type': 'device.connected',
        'occurred_at': '2026-08-13T10:30:18+08:00', 'received_at': None,
        'sequence': sequence, 'correlation_id': None, 'payload': {},
        'raw_reference': None,
    })


class Transport:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.events = []

    def send(self, item):
        self.events.append(item.event_id)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_pump_acknowledges_accepted_and_duplicate_receipts(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1)); store.append(event('D2', 1))
    transport = Transport([
        DeliveryReceipt(accepted=True, duplicate=False),
        DeliveryReceipt(accepted=True, duplicate=True),
    ])
    summary = DeliveryPump(store, transport, 'worker-1').run_once(limit=10)
    assert summary.sent == 2 and summary.failed == 0
    assert store.stats()['pending'] == 0


def test_pump_releases_failed_event_for_retry(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1))
    summary = DeliveryPump(store, Transport([RuntimeError('offline')]), 'worker-1').run_once()
    assert summary.sent == 0 and summary.failed == 1
    assert store.stats()['pending'] == 1
    assert [e.event_id for e in store.claim_pending('worker-2')] == ['D1-1']


def test_pump_sends_only_first_event_per_device_each_cycle(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1)); store.append(event('D1', 2))
    transport = Transport([DeliveryReceipt(True, False), DeliveryReceipt(True, False)])
    first = DeliveryPump(store, transport, 'worker').run_once(limit=10)
    second = DeliveryPump(store, transport, 'worker').run_once(limit=10)
    assert first.claimed == 1 and second.claimed == 1
    assert transport.events == ['D1-1', 'D1-2']


def test_rejected_receipt_is_released_with_reason(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1))
    receipt = DeliveryReceipt(accepted=False, duplicate=False, message='contract rejected')
    summary = DeliveryPump(store, Transport([receipt]), 'worker').run_once()
    assert summary.failed == 1
    assert store.stats()['attempts'] == 1
