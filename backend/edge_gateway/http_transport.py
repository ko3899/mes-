"""Authenticated HTTPS transport for edge event delivery."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import uuid

from edge_gateway.delivery import DeliveryReceipt
from services.gateway_auth import build_signature


class HttpEventTransport:
    def __init__(self, base_url, gateway_id, secret, timeout=5, opener=urlopen,
                 clock=time.time, nonce_factory=None):
        if urlparse(str(base_url)).scheme.lower() != 'https':
            raise ValueError('gateway HTTP transport requires https')
        if not str(gateway_id).strip() or not str(secret):
            raise ValueError('gateway_id and secret are required')
        self.url = str(base_url).rstrip('/') + '/api/device-platform/gateway-events'
        self.gateway_id = str(gateway_id)
        self.secret = str(secret)
        self.timeout = float(timeout)
        self.opener = opener
        self.clock = clock
        self.nonce_factory = nonce_factory or (lambda: uuid.uuid4().hex)

    def send(self, event):
        body = json.dumps(
            event.to_dict(), ensure_ascii=False, separators=(',', ':'), allow_nan=False
        ).encode('utf-8')
        timestamp = str(int(self.clock()))
        nonce = str(self.nonce_factory())
        signature = build_signature(self.gateway_id, timestamp, nonce, body, self.secret)
        request = Request(self.url, data=body, method='POST', headers={
            'Content-Type': 'application/json',
            'X-Gateway-Id': self.gateway_id,
            'X-Gateway-Time': timestamp,
            'X-Gateway-Nonce': nonce,
            'X-Gateway-Signature': signature,
        })
        try:
            with self.opener(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            return DeliveryReceipt(False, False, f'HTTP {exc.code}')
        except (URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f'gateway HTTP delivery failed: {exc}') from exc
        result = data.get('data') or {}
        return DeliveryReceipt(
            bool(result.get('accepted')), bool(result.get('duplicate')),
            str(data.get('message') or ''),
        )
