import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from device_platform.contracts import DeviceEvent  # noqa: E402
from edge_gateway.delivery import DeliveryPump, DeliveryReceipt  # noqa: E402
from edge_gateway.event_store import EdgeEventStore  # noqa: E402


def event(device, sequence, lifecycle=None):
    return DeviceEvent.from_dict({
        'schema_version': '1.0', 'event_id': f'{device}-{sequence}' if lifecycle is None else f'{device}-{lifecycle}-{sequence}',
        'customer_code': 'C', 'factory_code': 'F', 'gateway_code': 'GW',
        'device_code': device, 'event_type': 'device.connected',
        'occurred_at': '2026-08-13T10:30:18+08:00', 'received_at': None,
        'sequence': sequence, 'correlation_id': None, 'payload': {},
        'raw_reference': None,
        **({'lifecycle_id': lifecycle} if lifecycle else {}),
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

    def close(self):
        self.closed = True


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
    summary = DeliveryPump(store, Transport([RuntimeError('offline')]), 'worker-1',
                           base_backoff_seconds=0).run_once()
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


def test_permanent_rejection_is_dead_lettered_and_transport_closes(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1))
    transport = Transport([DeliveryReceipt(False, message='invalid', retryable=False)])
    pump = DeliveryPump(store, transport, 'worker')
    assert pump.run_once().failed == 1
    assert store.stats()['dead_letter'] == 1
    pump.close()
    assert transport.closed is True


def test_dead_letter_can_be_replayed_after_manual_fix(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1))
    store.release('D1-1', 'worker', store.claim_pending('worker')[0].lease_token,
                  'bad payload', permanent=True)
    assert store.stats()['dead_letter'] == 1
    assert store.replay_dead_letters(['D1-1']) == 1
    assert store.stats()['dead_letter'] == 0
    assert [item.event_id for item in store.pending()] == ['D1-1']


def test_device_restart_lifecycle_does_not_block_new_sequence(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1, 'old'))
    store.append(event('D1', 2, 'old'))
    store.append(event('D1', 1, 'new'))
    store.append(event('D1', 2, 'new'))
    first = store.claim_pending('worker', limit=10)
    assert [(item.device_code, item.lifecycle_id, item.sequence) for item in first] == [
        ('D1', 'new', 1), ('D1', 'old', 1)
    ]
