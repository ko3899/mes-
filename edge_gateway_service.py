"""Standalone MES factory edge event delivery service."""

import argparse
import json
import os
import sys
import time


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'backend'))

from edge_gateway.config import EdgeConfig, EdgeConfigError  # noqa: E402
from edge_gateway.delivery import DeliveryPump  # noqa: E402
from edge_gateway.event_store import EdgeEventStore  # noqa: E402
from edge_gateway.http_transport import HttpEventTransport  # noqa: E402


def load_config():
    return EdgeConfig.from_env(os.environ)


def build_pump(config):
    store = EdgeEventStore(config.database_path)
    if config.transport == 'http':
        transport = HttpEventTransport(
            config.http_url, config.gateway_id, config.http_secret,
            timeout=config.transport_timeout_seconds,
        )
    else:
        from edge_gateway.mqtt_transport import MqttEventTransport
        transport = MqttEventTransport.from_config(config)
    worker_id = f'{config.gateway_id}:{os.getpid()}'
    return DeliveryPump(store, transport, worker_id, config.lease_seconds)


def main(argv=None):
    parser = argparse.ArgumentParser(description='MES边缘网关事件传输服务')
    parser.add_argument('--once', action='store_true', help='执行一次发送后退出')
    parser.add_argument('--show-config', action='store_true', help='显示脱敏配置后退出')
    parser.add_argument('--replay-dead-letters', action='store_true', help='将边缘死信全部重新放回发送队列')
    args = parser.parse_args(argv)
    try:
        config = load_config()
    except EdgeConfigError as exc:
        print(f'配置错误: {exc}', file=sys.stderr)
        return 2
    if args.show_config:
        print(json.dumps(config.safe_summary(), ensure_ascii=False, indent=2))
        return 0
    if args.replay_dead_letters:
        store = EdgeEventStore(config.database_path)
        print(json.dumps({'replayed': store.replay_dead_letters()}, ensure_ascii=False))
        return 0
    pump = None
    try:
        pump = build_pump(config)
        while True:
            summary = pump.run_once(limit=config.batch_size)
            print(json.dumps(summary.__dict__, ensure_ascii=False))
            if args.once:
                return 0 if summary.failed == 0 else 1
            time.sleep(config.poll_seconds)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f'edge gateway failed: {exc}', file=sys.stderr)
        return 1
    finally:
        if pump is not None:
            pump.close()


if __name__ == '__main__':
    raise SystemExit(main())
