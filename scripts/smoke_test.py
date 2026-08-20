"""MES 核心 API 冒烟测试:登录 -> 获取当前用户 -> 访问受保护接口。

用法:
    python scripts/smoke_test.py --base-url http://localhost:8080

返回 0 表示通过,非 0 表示失败。
"""

import argparse
import json
import sys
import urllib.error
import urllib.request


class SmokeTest:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        cookie_handler = urllib.request.HTTPCookieProcessor()
        self.session = urllib.request.build_opener(cookie_handler)

    def _request(self, method, path, data=None):
        url = self.base_url + path
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=body, method=method)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        try:
            with self.session.open(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', 'replace')
            try:
                return exc.code, json.loads(body)
            except Exception:
                return exc.code, {'raw': body[:200]}

    def run(self):
        ok = True

        # 1. 健康检查(无需认证)
        status, body = self._request('GET', '/healthz')
        print(f'[1/5] /healthz -> {status}')
        if status != 200 or body.get('status') != 'ok':
            print('  FAIL', body)
            ok = False

        # 2. 登录
        status, body = self._request('POST', '/api/login', {
            'username': 'admin', 'password': 'admin123',
        })
        print(f'[2/5] /api/login -> {status}')
        if status != 200:
            print('  FAIL', body)
            ok = False

        # 3. 获取当前用户
        status, body = self._request('GET', '/api/user/info')
        print(f'[3/5] /api/user/info -> {status}')
        if status != 200 or not body.get('data', {}).get('username'):
            print('  FAIL', body)
            ok = False

        # 4. 受保护业务接口:工单列表
        status, body = self._request('GET', '/api/prod/workorder/list')
        print(f'[4/5] /api/prod/workorder/list -> {status}')
        if status != 200:
            print('  FAIL', body)
            ok = False

        # 5. 限流:第 51 次 /healthz 应 429
        for _ in range(50):
            self._request('GET', '/healthz')
        status, body = self._request('GET', '/healthz')
        print(f'[5/5] /healthz after 50 req -> {status}')
        if status != 429:
            print('  FAIL: expected 429, got', status, body)
            ok = False

        return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description='MES 核心 API 冒烟测试')
    parser.add_argument('--base-url', default='http://localhost:8080',
                        help='MES 服务地址')
    args = parser.parse_args()
    return SmokeTest(args.base_url).run()


if __name__ == '__main__':
    raise SystemExit(main())
