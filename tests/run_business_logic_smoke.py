"""无需 pytest 的关键业务闭环冒烟测试。"""
import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import create_app  # noqa: E402
from utils import database  # noqa: E402


TEST_DB = os.path.join(PROJECT_ROOT, 'database', 'business_logic_smoke.db')


def assert_status(response, expected, message):
    payload = response.get_json()
    assert response.status_code == expected, (message, response.status_code, payload)
    return payload


def db_one(sql, params=()):
    db = sqlite3.connect(TEST_DB)
    db.row_factory = sqlite3.Row
    row = db.execute(sql, params).fetchone()
    db.close()
    return dict(row) if row else None


def add_inventory_document(client, kind, product_id, quantity, unit_price):
    party = {'supplier': '冒烟供应商'} if kind == 'inbound' else {'customer': '冒烟客户'}
    payload = assert_status(client.post(f'/api/inv/{kind}/add', json={
        'product_id': product_id,
        'quantity': quantity,
        'unit_price': unit_price,
        **party,
    }), 200, f'新增{kind}')
    return payload['data']['id']


def run():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    original_path = database.DB_PATH
    try:
        database.DB_PATH = TEST_DB
        database.init_db()
        database._init_extra_tables()
        db = sqlite3.connect(TEST_DB)
        product_id = db.execute(
            "INSERT INTO base_product(product_name,code,unit) VALUES('冒烟产品','SMOKE-P','个')"
        ).lastrowid
        customer_id = db.execute(
            "INSERT INTO base_customer(customer_name,code,status) VALUES('冒烟客户','SMOKE-C',1)"
        ).lastrowid
        tool_id = db.execute(
            "INSERT INTO tool_ledger(tool_name,code,quantity,status) VALUES('冒烟扳手','SMOKE-T',5,1)"
        ).lastrowid
        workorder_id = db.execute(
            "INSERT INTO prod_workorder(order_no,product_id,planned_qty,status) VALUES('SMOKE-WO',?,10,1)",
            (product_id,),
        ).lastrowid
        db.execute(
            "INSERT INTO base_stage_code(stage_name,code,status) VALUES('冒烟阶段','SMOKE-STAGE',1)"
        )
        db.commit()
        db.close()

        app = create_app()
        app.config.update(TESTING=True, SECRET_KEY='business-logic-smoke')
        client = app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = 1
            session['username'] = 'admin'

        inbound_id = add_inventory_document(client, 'inbound', product_id, 10, 2.5)
        assert db_one('SELECT * FROM inv_balance WHERE product_id=?', (product_id,)) is None
        assert_status(client.post(f'/api/inv/inbound/{inbound_id}/post', json={}), 200, '入库过账')
        assert db_one('SELECT quantity,amount FROM inv_balance WHERE product_id=?', (product_id,)) == {
            'quantity': 10.0,
            'amount': 25.0,
        }
        assert_status(client.post(f'/api/inv/inbound/{inbound_id}/post', json={}), 409, '重复入库过账')

        outbound_id = add_inventory_document(client, 'outbound', product_id, 4, 4)
        assert_status(client.post(f'/api/inv/outbound/{outbound_id}/post', json={}), 200, '出库过账')
        assert db_one('SELECT quantity,amount FROM inv_balance WHERE product_id=?', (product_id,)) == {
            'quantity': 6.0,
            'amount': 15.0,
        }
        shortage_id = add_inventory_document(client, 'outbound', product_id, 7, 4)
        shortage = assert_status(
            client.post(f'/api/inv/outbound/{shortage_id}/post', json={}),
            409,
            '库存不足回滚',
        )
        assert shortage['data'][0]['shortage_qty'] == 1.0
        assert db_one('SELECT quantity,amount FROM inv_balance WHERE product_id=?', (product_id,)) == {
            'quantity': 6.0,
            'amount': 15.0,
        }
        assert_status(client.post('/api/inv/inbound/delete', json={'id': inbound_id}), 409, '已过账单据防删除')

        assert_status(client.post('/api/tool/borrow/add', json={
            'tool_id': tool_id,
            'borrow_qty': 6,
        }), 409, '工具超借')
        borrow = assert_status(client.post('/api/tool/borrow/add', json={
            'tool_id': tool_id,
            'borrow_qty': 4,
        }), 200, '工具借用')
        borrow_id = borrow['data']['id']
        assert_status(client.post('/api/tool/borrow/return', json={
            'id': borrow_id,
            'return_qty': 2,
        }), 200, '工具部分归还')
        assert_status(client.post('/api/tool/borrow/return', json={
            'id': borrow_id,
            'return_qty': 3,
        }), 409, '工具超额归还')
        assert_status(client.post('/api/tool/ledger/update', json={
            'id': tool_id,
            'tool_name': '冒烟扳手',
            'code': 'SMOKE-T',
            'quantity': 1,
            'status': 1,
        }), 409, '台账数量低于未归还数量')
        assert_status(client.post('/api/tool/borrow/return', json={
            'id': borrow_id,
            'return_qty': 2,
        }), 200, '工具全部归还')

        batch = assert_status(client.post('/api/trace/batch/add', json={
            'batch_no': 'SMOKE-BATCH',
            'product_id': product_id,
            'quantity': 10,
            'supplier': '冒烟供应商',
        }), 200, '新增追溯批次')
        batch_id = batch['data']['id']
        assert_status(client.post('/api/trace/batch/add', json={
            'batch_no': 'SMOKE-BATCH',
            'product_id': product_id,
            'quantity': 10,
        }), 409, '重复批次')
        assert_status(client.post('/api/trace/add', json={
            'batch_id': batch_id,
            'trace_type': '入库',
            'ref_no': 'SMOKE-RK',
            'quantity': 10,
        }), 200, '新增追溯记录')
        assert_status(client.post('/api/trace/batch/delete', json={'id': batch_id}), 409, '有追溯记录批次防删除')
        trace_result = assert_status(client.get('/api/trace/query?keyword=SMOKE-BATCH'), 200, '追溯查询')
        assert trace_result['data'][0]['traces'][0]['ref_no'] == 'SMOKE-RK'

        assert_status(client.post('/api/transaction/add', json={
            'trans_type': 'IN',
            'product_id': product_id,
            'quantity': 999,
        }), 409, '禁止手工伪造库存流水')
        stage = assert_status(client.post('/api/stage/record/add', json={
            'stage_code': 'SMOKE-STAGE',
            'workorder_id': workorder_id,
            'quantity': 5,
        }), 200, '新增阶段记录')
        stage_id = stage['data']['id']
        assert_status(client.post('/api/stage/record/complete', json={
            'id': stage_id,
            'remark': '首次完成',
        }), 200, '完成阶段记录')
        first_end_time = db_one('SELECT end_time FROM prod_stage_record WHERE id=?', (stage_id,))['end_time']
        assert_status(client.post('/api/stage/record/complete', json={
            'id': stage_id,
            'remark': '重复完成',
        }), 409, '防止重复完成阶段')
        assert db_one('SELECT end_time FROM prod_stage_record WHERE id=?', (stage_id,))['end_time'] == first_end_time

        complaint = assert_status(client.post('/api/svc/complaint/add', json={
            'customer_id': customer_id,
            'product_id': product_id,
            'complaint_type': '质量',
            'severity': 'high',
            'description': '冒烟客诉',
        }), 200, '新增客诉')
        complaint_id = complaint['data']['id']
        assert db_one('SELECT severity FROM svc_complaint WHERE id=?', (complaint_id,)) == {'severity': 'high'}
        service_return = assert_status(client.post('/api/svc/return/add', json={
            'complaint_id': complaint_id,
            'customer_id': customer_id,
            'product_id': product_id,
            'quantity': 2,
            'return_reason': '尺寸不合格',
        }), 200, '新增退换货')
        return_id = service_return['data']['id']
        assert db_one(
            'SELECT quantity,return_reason FROM svc_return WHERE id=?',
            (return_id,),
        ) == {'quantity': 2.0, 'return_reason': '尺寸不合格'}
        assert_status(client.post('/api/svc/return/add', json={
            'customer_id': customer_id,
            'product_id': product_id,
            'quantity': -1,
            'return_reason': '非法数量',
        }), 400, '退换货负数量')
        assert_status(client.post('/api/sys/user/delete', json={'id': 1}), 409, '防止删除当前账号')
        print('PASS inventory: draft -> inbound 10 -> outbound 4 -> shortage rollback')
        print('PASS tool: over-borrow blocked -> partial return -> over-return blocked')
        print('PASS trace: schema migration -> event -> protected batch')
        print('PASS transaction log: posting-only')
        print('PASS stage: valid reference -> complete once')
        print('PASS service: severity/reason persisted -> negative quantity blocked')
        print('PASS user: current account delete blocked')
    finally:
        database.DB_PATH = original_path
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


if __name__ == '__main__':
    run()
