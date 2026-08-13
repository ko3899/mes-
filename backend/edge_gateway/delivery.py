"""Transport-neutral, lease-safe delivery of durable edge events."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryReceipt:
    accepted: bool
    duplicate: bool = False
    message: str = ''
    retryable: bool = True


@dataclass(frozen=True)
class DeliverySummary:
    claimed: int
    sent: int
    failed: int


class DeliveryPump:
    def __init__(self, store, transport, worker_id, lease_seconds=30,
                 base_backoff_seconds=2, max_attempts=10):
        self.store = store
        self.transport = transport
        self.worker_id = str(worker_id)
        self.lease_seconds = int(lease_seconds)
        self.base_backoff_seconds = int(base_backoff_seconds)
        self.max_attempts = int(max_attempts)

    def run_once(self, limit=100):
        events = self.store.claim_pending(
            self.worker_id, limit=limit, lease_seconds=self.lease_seconds
        )
        sent = 0
        failed = 0
        for claim in events:
            event = claim.event
            try:
                receipt = self.transport.send(event)
                if not isinstance(receipt, DeliveryReceipt) or not receipt.accepted:
                    reason = getattr(receipt, 'message', '') or 'central rejected event'
                    self.store.release(
                        event.event_id, self.worker_id, claim.lease_token, reason,
                        backoff_seconds=self.base_backoff_seconds,
                        max_attempts=self.max_attempts,
                        permanent=not getattr(receipt, 'retryable', True),
                    )
                    failed += 1
                    continue
                if self.store.ack(event.event_id, self.worker_id, claim.lease_token):
                    sent += 1
                else:
                    failed += 1
            except Exception as exc:
                self.store.release(
                    event.event_id, self.worker_id, claim.lease_token, exc,
                    backoff_seconds=self.base_backoff_seconds,
                    max_attempts=self.max_attempts,
                )
                failed += 1
        return DeliverySummary(len(events), sent, failed)

    def close(self):
        close = getattr(self.transport, 'close', None)
        if close:
            close()
