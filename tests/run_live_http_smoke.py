"""对运行中的本地服务执行库存闭环，并清理所有测试业务数据。"""
import argparse
import http.cookiejar
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'database', 'mes.db')


def api(opener, base_url, path, method='GET', data=None):
    body = None if data is None else json.dumps(data).encode('utf-8')
    request = urllib.request.Request(
        base_url + path,
        data=body,
        method=method,
        headers={'Content-Type': 'application/json'} if body is not None else {},
    )
    try:
        with opener.open(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode('utf-8'))


def run(base_url, username, password):
    suffix = str(int(time.time() * 1000))
    code = f'LIVE-SMOKE-{suffix}'
    product_id = inbound_id = outbound_id = None
    inbound_no = outbound_no = None
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    try:
        status, payload = api(opener, base_url, '/api/login', 'POST', {
            'username': username,
            'password': password,
        })
        assert status == 200 and payload['code'] == 0, (status, payload)

        status, payload = api(opener, base_url, '/api/base/product/add', 'POST', {
            'product_name': '线上闭环临时产品',
            'code': code,
            'unit': '个',
            'status': 1,
        })
        assert status == 200 and payload['code'] == 0, (status, payload)
        product_id = payload['data']['id']

        status, payload = api(opener, base_url, '/api/inv/inbound/add', 'POST', {
            'product_id': product_id,
            'quantity': 10,
            'unit_price': 2.5,
            'supplier': '线上闭环测试',
            'remark': code,
        })
        assert status == 200 and payload['code'] == 0, (status, payload)
        inbound_id = payload['data']['id']
        inbound_no = payload['data']['inbound_no']
        status, payload = api(opener, base_url, f'/api/inv/inbound/{inbound_id}/post', 'POST', {})
        assert status == 200 and payload['code'] == 0, (status, payload)
        status, payload = api(opener, base_url, f'/api/inv/inbound/{inbound_id}/post', 'POST', {})
        assert status == 409, (status, payload)

        status, payload = api(opener, base_url, '/api/inv/outbound/add', 'POST', {
            'product_id': product_id,
            'quantity': 10,
            'unit_price': 4,
            'customer': '线上闭环测试',
            'remark': code,
        })
        assert status == 200 and payload['code'] == 0, (status, payload)
        outbound_id = payload['data']['id']
        outbound_no = payload['data']['outbound_no']
        status, payload = api(opener, base_url, f'/api/inv/outbound/{outbound_id}/post', 'POST', {})
        assert status == 200 and payload['code'] == 0, (status, payload)

        status, payload = api(opener, base_url, '/api/inv/balance/list')
        assert status == 200 and payload['code'] == 0, (status, payload)
        balance = next(row for row in payload['data'] if row['product_id'] == product_id)
        assert balance['quantity'] == 0 and balance['amount'] == 0, balance
        print(f'PASS live HTTP: {inbound_no} inbound 10 -> {outbound_no} outbound 10 -> balance 0')
    finally:
        db = sqlite3.connect(DB_PATH)
        try:
            db.execute('BEGIN IMMEDIATE')
            ref_numbers = [number for number in (inbound_no, outbound_no) if number]
            for ref_no in ref_numbers:
                db.execute('DELETE FROM inv_transaction WHERE ref_no=?', (ref_no,))
                db.execute('DELETE FROM inv_transaction_log WHERE ref_no=?', (ref_no,))
            if inbound_id:
                db.execute('DELETE FROM inv_inbound_item WHERE inbound_id=?', (inbound_id,))
                db.execute('DELETE FROM inv_inbound WHERE id=?', (inbound_id,))
            if outbound_id:
                db.execute('DELETE FROM inv_outbound_item WHERE outbound_id=?', (outbound_id,))
                db.execute('DELETE FROM inv_outbound WHERE id=?', (outbound_id,))
            if product_id:
                db.execute('DELETE FROM inv_balance WHERE product_id=?', (product_id,))
                db.execute('DELETE FROM base_product WHERE id=?', (product_id,))
            else:
                db.execute('DELETE FROM base_product WHERE code=?', (code,))
            db.commit()
            integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
            assert integrity == 'ok', integrity
            print('PASS cleanup: temporary documents, transactions, balance and product removed')
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8081')
    parser.add_argument('--username', default='admin')
    parser.add_argument('--password', default='admin123')
    args = parser.parse_args()
    run(args.base_url.rstrip('/'), args.username, args.password)
