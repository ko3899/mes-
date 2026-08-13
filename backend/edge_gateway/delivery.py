"""Transport-neutral, lease-safe delivery of durable edge events."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryReceipt:
    accepted: bool
    duplicate: bool = False
    message: str = ''


@dataclass(frozen=True)
class DeliverySummary:
    claimed: int
    sent: int
    failed: int


class DeliveryPump:
    def __init__(self, store, transport, worker_id, lease_seconds=30):
        self.store = store
        self.transport = transport
        self.worker_id = str(worker_id)
        self.lease_seconds = int(lease_seconds)

    def run_once(self, limit=100):
        events = self.store.claim_pending(
            self.worker_id, limit=limit, lease_seconds=self.lease_seconds
        )
        sent = 0
        failed = 0
        for event in events:
            try:
                receipt = self.transport.send(event)
                if not isinstance(receipt, DeliveryReceipt) or not receipt.accepted:
                    reason = getattr(receipt, 'message', '') or 'central rejected event'
                    self.store.release(event.event_id, self.worker_id, reason)
                    failed += 1
                    continue
                if self.store.ack(event.event_id, worker_id=self.worker_id):
                    sent += 1
                else:
                    failed += 1
            except Exception as exc:
                self.store.release(event.event_id, self.worker_id, exc)
                failed += 1
        return DeliverySummary(len(events), sent, failed)
