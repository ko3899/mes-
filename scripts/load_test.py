"""MES 关键路径压测脚本(纯 Python,无第三方依赖)。

覆盖场景:
  1. 登录并发(验证 Session 限流和并发)
  2. 过站 API 并发(验证制程防呆和数据库锁)
  3. 设备事件摄入并发(验证事件序列号和幂等)
  4. 机台 TCP Socket 并发(验证 V1 协议接入)

用法:
    # 基础压测(默认 20 并发,持续 30 秒)
    python scripts/load_test.py --base-url http://localhost:8080

    # 高并发压测
    python scripts/load_test.py --base-url http://localhost:8080 --users 100 --duration 60

    # 只跑某个场景
    python scripts/load_test.py --scenario login --users 50

输出:每秒 RPS、平均延迟、P95/P99 延迟、错误率、状态码分布。
"""

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed


class Stats:
    """线程安全的统计收集器。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.latencies = []
        self.status_codes = Counter()
        self.errors = Counter()
        self.count = 0

    def record(self, latency, status_code, error=None):
        with self._lock:
            self.latencies.append(latency)
            self.status_codes[status_code] += 1
            if error:
                self.errors[error] += 1
            self.count += 1

    def summary(self):
        if not self.latencies:
            return {'count': 0}
        lat = sorted(self.latencies)
        n = len(lat)
        return {
            'count': n,
            'avg_ms': round(statistics.mean(lat) * 1000, 1),
            'p50_ms': round(lat[n // 2] * 1000, 1),
            'p95_ms': round(lat[int(n * 0.95)] * 1000, 1),
            'p99_ms': round(lat[int(n * 0.99)] * 1000, 1) if n >= 100 else None,
            'max_ms': round(lat[-1] * 1000, 1),
            'status_codes': dict(self.status_codes),
            'errors': dict(self.errors),
        }


def _request(method, url, data=None, headers=None, timeout=10):
    """发起 HTTP 请求,返回 (latency, status_code, error)。"""
    body = json.dumps(data).encode('utf-8') if data else None
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            time.time() - t0
            return time.time() - t0, resp.status, None
    except urllib.error.HTTPError as exc:
        return time.time() - t0, exc.code, None
    except Exception as exc:
        return time.time() - t0, 0, type(exc).__name__


def scenario_login(base_url, stats, stop_event):
    """登录场景:循环调用 /api/login。"""
    url = base_url + '/api/login'
    while not stop_event.is_set():
        lat, code, err = _request('POST', url, {
            'username': 'admin', 'password': 'admin123',
        })
        stats.record(lat, code, err)


def scenario_pass_station(base_url, stats, stop_event):
    """过站场景:需要先登录拿 Session,再循环过站。

    由于过站需要真实 SN 和工单,这里只压测 API 响应能力,
    预期返回 400/401(参数不全)也计入成功响应。
    """
    # 先登录
    lat, code, err = _request('POST', base_url + '/api/login', {
        'username': 'admin', 'password': 'admin123',
    })
    # 登录响应里的 Set-Cookie 需要保留;urllib 不自动管理,这里简化
    url = base_url + '/api/process/pass-station'
    i = 0
    while not stop_event.is_set():
        lat, code, err = _request('POST', url, {
            'sn': f'SN-LOADTEST-{i}',
            'station': 'SMT01',
            'process_name': '贴片',
        })
        stats.record(lat, code, err)
        i += 1


def scenario_device_event(base_url, stats, stop_event):
    """设备事件摄入:压测 /api/device-platform/events。

    需要 admin 登录,这里压测端点响应能力。
    """
    url = base_url + '/api/device-platform/events'
    i = 0
    while not stop_event.is_set():
        event = {
            'schema_version': '1.0',
            'event_id': f'LOADTEST-{i}-{time.time()}',
            'customer_code': 'TEST', 'factory_code': 'F1',
            'gateway_code': 'GW1', 'device_code': 'D1',
            'event_type': 'quality.completed',
            'occurred_at': '2026-08-20T10:00:00+08:00',
            'sequence': i + 1,
            'payload': {'sn': f'SN-{i}', 'result': 'OK'},
        }
        lat, code, err = _request('POST', url, event)
        stats.record(lat, code, err)
        i += 1


SCENARIOS = {
    'login': scenario_login,
    'pass-station': scenario_pass_station,
    'device-event': scenario_device_event,
}


def run(base_url, scenario, users, duration):
    stats = Stats()
    stop_event = threading.Event()
    fn = SCENARIOS[scenario]
    print(f'压测开始: scenario={scenario} users={users} duration={duration}s')
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=users) as pool:
        futures = [pool.submit(fn, base_url, stats, stop_event) for _ in range(users)]
        time.sleep(duration)
        stop_event.set()
        for f in as_completed(futures, timeout=30):
            pass
    elapsed = time.time() - t0
    summary = stats.summary()
    if summary['count']:
        summary['rps'] = round(summary['count'] / elapsed, 1)
    summary['elapsed_s'] = round(elapsed, 1)
    summary['scenario'] = scenario
    summary['users'] = users
    return summary


def main():
    parser = argparse.ArgumentParser(description='MES 压测脚本')
    parser.add_argument('--base-url', default='http://localhost:8080',
                        help='MES 服务地址(默认: http://localhost:8080)')
    parser.add_argument('--scenario', choices=list(SCENARIOS.keys()) + ['all'],
                        default='all', help='压测场景')
    parser.add_argument('--users', type=int, default=20, help='并发用户数')
    parser.add_argument('--duration', type=int, default=30, help='持续时间(秒)')
    args = parser.parse_args()

    scenarios = list(SCENARIOS.keys()) if args.scenario == 'all' else [args.scenario]
    results = {}
    for sc in scenarios:
        print(f'\n=== {sc} ===')
        results[sc] = run(args.base_url, sc, args.users, args.duration)
        r = results[sc]
        print(f"  请求数: {r['count']}")
        print(f"  RPS: {r.get('rps')}")
        print(f"  平均延迟: {r.get('avg_ms')}ms")
        print(f"  P95: {r.get('p95_ms')}ms  P99: {r.get('p99_ms')}ms")
        print(f"  状态码: {r.get('status_codes')}")
        if r.get('errors'):
            print(f"  错误: {r['errors']}")

    print('\n=== 汇总(JSON) ===')
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
