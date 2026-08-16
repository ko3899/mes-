import os
import sqlite3
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import database  # noqa: E402
from services.production_flow import (  # noqa: E402
    BusinessError,
    generate_material_requirements,
    generate_tasks,
    post_report,
    release_workorder,
    save_batch,
    save_sales_order,
    transition_status,
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'flow.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    yield connection
    connection.close()


def seed_flow(db):
    workshop_id = db.execute(
        "INSERT INTO base_workshop(workshop_name,code) VALUES('装配车间','WS-A')"
    ).lastrowid
    product_id = db.execute(
        "INSERT INTO base_product(product_name,code,unit) VALUES('测试成品','FG-A','件')"
    ).lastrowid
    material_id = db.execute(
        "INSERT INTO base_product(product_name,code,unit,product_type) VALUES('测试物料','RM-A','个','原材料')"
    ).lastrowid
    process_ids = []
    for index in range(1, 4):
        process_ids.append(db.execute(
            'INSERT INTO base_process(process_name,code,workshop_id) VALUES(?,?,?)',
            (f'工序{index}', f'PROC-{index}', workshop_id),
        ).lastrowid)
    route_id = db.execute(
        '''INSERT INTO base_process_route(product_id,route_name,workshop_id,version)
           VALUES(?,?,?,?)''', (product_id, '装配路线', workshop_id, 2)
    ).lastrowid
    for index, process_id in enumerate(process_ids, 1):
        db.execute(
            '''INSERT INTO base_process_route_detail
               (route_id,process_id,step_no,workshop_id,standard_time)
               VALUES(?,?,?,?,?)''',
            (route_id, process_id, index, workshop_id, index * 10),
        )
    db.execute(
        '''INSERT INTO base_bom(product_id,material_id,quantity,unit,description)
           VALUES(?,?,?,?,?)''', (product_id, material_id, 2, '个', '生产业务链测试')
    )
    plan_id = db.execute(
        "INSERT INTO prod_plan(plan_no,status,remark) VALUES('PLAN-TEST',1,'生产业务链测试')"
    ).lastrowid
    plan_item_id = db.execute(
        '''INSERT INTO prod_plan_item(plan_id,product_id,planned_qty,workshop_id,remark)
           VALUES(?,?,?,?,?)''', (plan_id, product_id, 100, workshop_id, '生产业务链测试')
    ).lastrowid
    workorder_id = db.execute(
        '''INSERT INTO prod_workorder
           (order_no,plan_id,plan_item_id,product_id,route_id,planned_qty,workshop_id,status,remark)
           VALUES(?,?,?,?,?,?,?,?,?)''',
        ('WO-FREEZE', plan_id, plan_item_id, product_id, route_id, 10,
         workshop_id, 0, '生产业务链测试'),
    ).lastrowid
    db.commit()
    return {
        'workshop_id': workshop_id, 'product_id': product_id,
        'material_id': material_id, 'route_id': route_id,
        'plan_item_id': plan_item_id, 'workorder_id': workorder_id,
    }


def test_sales_order_rolls_back_header_when_a_line_is_invalid(db):
    product_id = db.execute(
        "INSERT INTO base_product(product_name,code) VALUES('产品','ROLLBACK-P')"
    ).lastrowid
    db.commit()
    with pytest.raises(BusinessError, match='产品明细数量必须大于0'):
        save_sales_order(db, {
            'customer': '测试客户',
            'delivery_date': '2026-08-20',
            'remark': '生产业务链测试',
            'items': [{'product_id': product_id, 'quantity': 0, 'unit_price': 10}],
        }, 1)
    assert db.execute('SELECT COUNT(*) FROM prod_sales_order').fetchone()[0] == 0


def test_batch_total_cannot_exceed_plan_line_remaining_quantity(db):
    ids = seed_flow(db)
    save_batch(db, {
        'plan_item_id': ids['plan_item_id'], 'planned_qty': 80,
        'remark': '生产业务链测试',
    }, 1)
    with pytest.raises(BusinessError, match='超过计划明细剩余数量'):
        save_batch(db, {
            'plan_item_id': ids['plan_item_id'], 'planned_qty': 21,
            'remark': '生产业务链测试',
        }, 1)


def test_released_workorder_keeps_route_and_bom_snapshots_after_master_changes(db):
    ids = seed_flow(db)
    result = release_workorder(db, ids['workorder_id'], 1, '生产业务链测试')
    before_steps = [tuple(row) for row in db.execute(
        '''SELECT process_name,step_no,standard_time FROM prod_workorder_route_step
           ORDER BY step_no'''
    )]
    before_bom = [tuple(row) for row in db.execute(
        '''SELECT material_name,quantity_per_unit,required_qty
           FROM prod_workorder_bom_snapshot'''
    )]
    db.execute("UPDATE base_process SET process_name='已修改工序'")
    db.execute('UPDATE base_bom SET quantity=99')
    db.commit()
    assert [tuple(row) for row in db.execute(
        'SELECT process_name,step_no,standard_time FROM prod_workorder_route_step ORDER BY step_no'
    )] == before_steps
    assert [tuple(row) for row in db.execute(
        'SELECT material_name,quantity_per_unit,required_qty FROM prod_workorder_bom_snapshot'
    )] == before_bom
    assert result['route_steps'] == 3
    assert result['bom_items'] == 1


def test_snapshot_generates_tasks_and_material_requirements_once(db):
    ids = seed_flow(db)
    release_workorder(db, ids['workorder_id'], 1)
    assert len(generate_tasks(db, ids['workorder_id'], 1)) == 3
    assert len(generate_tasks(db, ids['workorder_id'], 1)) == 3
    requirements = generate_material_requirements(db, ids['workorder_id'], 1)
    assert len(requirements) == 1
    assert requirements[0]['required_qty'] == 20
    assert len(generate_material_requirements(db, ids['workorder_id'], 1)) == 1


def test_invalid_status_transition_rolls_back_and_does_not_log(db):
    ids = seed_flow(db)
    with pytest.raises(BusinessError, match='不允许'):
        transition_status(db, 'workorder', ids['workorder_id'], 3, 1)
    assert db.execute(
        'SELECT status FROM prod_workorder WHERE id=?', (ids['workorder_id'],)
    ).fetchone()[0] == 0
    assert db.execute('SELECT COUNT(*) FROM sys_business_status_log').fetchone()[0] == 0


def test_defect_quantity_does_not_complete_an_ordinary_task(db):
    ids = seed_flow(db)
    release_workorder(db, ids['workorder_id'], 1)
    task = generate_tasks(db, ids['workorder_id'], 1)[0]
    db.execute(
        'UPDATE prod_task SET planned_qty=2,completed_qty=1,defect_qty=0,status=1 WHERE id=?',
        (task['id'],),
    )
    report_id = db.execute(
        '''INSERT INTO prod_report
           (report_no,task_id,workorder_id,process_id,user_id,qualified_qty,
            defect_qty,approval_status)
           VALUES('R-DEFECT',?,?,?,?,0,1,1)''',
        (task['id'], ids['workorder_id'], task['process_id'], 1),
    ).lastrowid
    db.commit()
    post_report(db, report_id, 1)
    row = db.execute('SELECT completed_qty,defect_qty,status FROM prod_task WHERE id=?', (task['id'],)).fetchone()
    assert tuple(row) == (1, 1, 1)
