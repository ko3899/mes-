"""SN-level quality disposition and rework persistence."""
from contextlib import contextmanager
from uuid import uuid4


QUALITY_NORMAL = 'normal'
QUALITY_HOLD = 'quality_hold'
QUALITY_REWORK = 'rework'
QUALITY_SCRAPPED = 'scrapped'
QUALITY_CONCESSION = 'concession'
OPEN_DISPOSITION_STATUSES = ('pending_review', 'approved', 'task_started')


def _table_exists(db, table):
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _add_column_if_missing(db, table, column, definition):
    if not _table_exists(db, table):
        return
    columns = {row[1] for row in db.execute('PRAGMA table_info("%s")' % table)}
    if column not in columns:
        db.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (table, column, definition))


def create_quality_disposition_tables(db):
    """Apply the additive quality-disposition migration and backfill AIM NG rows."""
    _add_column_if_missing(
        db, 'prod_serial', 'quality_status', "TEXT NOT NULL DEFAULT 'normal'"
    )
    _add_column_if_missing(
        db, 'prod_task', 'task_type', "TEXT NOT NULL DEFAULT 'normal'"
    )
    _add_column_if_missing(db, 'prod_task', 'source_task_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_task', 'quality_disposition_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_task', 'target_sn', 'TEXT')
    _add_column_if_missing(db, 'prod_station_record', 'quality_disposition_id', 'INTEGER')

    db.execute(
        '''CREATE TABLE IF NOT EXISTS prod_quality_disposition (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disposition_no TEXT NOT NULL UNIQUE,
            sn TEXT NOT NULL,
            inspection_report_id INTEGER UNIQUE,
            machine_request_id INTEGER,
            prod_report_id INTEGER,
            workorder_id INTEGER NOT NULL,
            source_task_id INTEGER NOT NULL,
            route_step_id INTEGER NOT NULL,
            action TEXT NOT NULL DEFAULT 'pending',
            status TEXT NOT NULL DEFAULT 'pending_review',
            rework_task_id INTEGER,
            cycle_no INTEGER NOT NULL DEFAULT 1,
            reason TEXT,
            reviewer_id INTEGER,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (inspection_report_id) REFERENCES iot_inspection_report(id),
            FOREIGN KEY (machine_request_id) REFERENCES iot_machine_request(id),
            FOREIGN KEY (prod_report_id) REFERENCES prod_report(id),
            FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id),
            FOREIGN KEY (source_task_id) REFERENCES prod_task(id),
            FOREIGN KEY (route_step_id) REFERENCES prod_workorder_route_step(id),
            FOREIGN KEY (rework_task_id) REFERENCES prod_task(id)
        )'''
    )
    db.execute(
        '''CREATE UNIQUE INDEX IF NOT EXISTS idx_quality_disposition_open_sn_step
           ON prod_quality_disposition(sn, route_step_id)
           WHERE status IN ('pending_review','approved','task_started')'''
    )
    db.execute(
        '''CREATE INDEX IF NOT EXISTS idx_quality_disposition_source_task
           ON prod_quality_disposition(source_task_id, status)'''
    )
    db.execute(
        '''CREATE UNIQUE INDEX IF NOT EXISTS idx_station_record_disposition
           ON prod_station_record(quality_disposition_id)
           WHERE quality_disposition_id IS NOT NULL'''
    )

    required = (
        'prod_serial', 'prod_task', 'prod_workorder', 'prod_workorder_route_step',
        'prod_report', 'iot_machine_request', 'iot_inspection_report',
    )
    if not all(_table_exists(db, table) for table in required):
        return

    rows = db.execute(
        '''SELECT ir.id AS inspection_report_id, ir.request_id AS machine_request_id,
                  ir.prod_report_id, ir.sn, req.workorder_id,
                  req.task_id AS source_task_id, req.route_step_id
           FROM iot_inspection_report ir
           JOIN iot_machine_request req ON req.id=ir.request_id
           JOIN prod_serial serial ON serial.serial_no=ir.sn
           JOIN prod_workorder wo ON wo.id=req.workorder_id
           JOIN prod_task task ON task.id=req.task_id
                              AND task.workorder_id=req.workorder_id
           JOIN prod_workorder_route_step step ON step.id=req.route_step_id
           JOIN prod_report report ON report.id=ir.prod_report_id
                                  AND report.task_id=req.task_id
                                  AND report.workorder_id=req.workorder_id
           WHERE UPPER(ir.result)='NG' AND ir.import_status='imported' '''
    ).fetchall()
    for row in rows:
        cursor = db.execute(
            '''INSERT OR IGNORE INTO prod_quality_disposition
               (disposition_no,sn,inspection_report_id,machine_request_id,prod_report_id,
                workorder_id,source_task_id,route_step_id,action,status,cycle_no)
               VALUES(?,?,?,?,?,?,?,?,?,'pending_review',1)''',
            ('QD-BACKFILL-%s' % row['inspection_report_id'], row['sn'],
             row['inspection_report_id'], row['machine_request_id'], row['prod_report_id'],
             row['workorder_id'], row['source_task_id'], row['route_step_id'], 'pending'),
        )
        if cursor.rowcount or db.execute(
            '''SELECT 1 FROM prod_quality_disposition
               WHERE inspection_report_id=? AND status='pending_review' ''',
            (row['inspection_report_id'],),
        ).fetchone():
            db.execute(
                "UPDATE prod_serial SET quality_status=? WHERE serial_no=?",
                (QUALITY_HOLD, row['sn']),
            )


def _dict(row):
    return dict(row) if row is not None else None


def create_ng_disposition(db, endpoint, request_row, inspection_report_id,
                          prod_report_id, reason=''):
    """Create one pending disposition and hold the SN in the caller transaction."""
    existing = db.execute(
        'SELECT * FROM prod_quality_disposition WHERE inspection_report_id=?',
        (inspection_report_id,),
    ).fetchone()
    if existing:
        return _dict(existing)

    sn = request_row['sn']
    route_step_id = request_row['route_step_id']
    conflict = db.execute(
        '''SELECT * FROM prod_quality_disposition
           WHERE sn=? AND route_step_id=?
             AND status IN ('pending_review','approved','task_started')''',
        (sn, route_step_id),
    ).fetchone()
    if conflict:
        raise ValueError('SN当前工序已存在未完成质量处置单')

    disposition_no = 'QD-%s' % inspection_report_id
    cursor = db.execute(
        '''INSERT OR IGNORE INTO prod_quality_disposition
           (disposition_no,sn,inspection_report_id,machine_request_id,prod_report_id,
            workorder_id,source_task_id,route_step_id,action,status,cycle_no,reason)
           VALUES(?,?,?,?,?,?,?,?,?,'pending_review',1,?)''',
        (disposition_no, sn, inspection_report_id, request_row['id'], prod_report_id,
         request_row['workorder_id'], request_row['task_id'], route_step_id,
         'pending', reason),
    )
    disposition_id = cursor.lastrowid
    if not disposition_id:
        row = db.execute(
            'SELECT * FROM prod_quality_disposition WHERE disposition_no=?',
            (disposition_no,),
        ).fetchone()
        if not row:
            raise ValueError('质量处置单创建冲突')
        disposition_id = row['id']
    updated = db.execute(
        '''UPDATE prod_serial SET quality_status=?
           WHERE serial_no=? AND quality_status IN (?,?)''',
        (QUALITY_HOLD, sn, QUALITY_NORMAL, QUALITY_HOLD),
    ).rowcount
    if updated != 1:
        raise ValueError('SN不存在或当前质量状态不允许转为待审核')
    return _dict(db.execute(
        'SELECT * FROM prod_quality_disposition WHERE id=?', (disposition_id,)
    ).fetchone())


def access_context(db, sn, route_step_id):
    """Return the quality gate and linked rework task for machine admission."""
    if (not _table_exists(db, 'prod_quality_disposition')
            or 'quality_status' not in {
                row[1] for row in db.execute('PRAGMA table_info(prod_serial)')
            }):
        return {
            'quality_status': QUALITY_NORMAL,
            'disposition': None,
            'rework_task': None,
        }
    serial = db.execute(
        'SELECT quality_status FROM prod_serial WHERE serial_no=?', (sn,)
    ).fetchone()
    quality_status = serial['quality_status'] if serial else QUALITY_NORMAL
    disposition = db.execute(
        '''SELECT * FROM prod_quality_disposition
           WHERE sn=? AND route_step_id=?
           ORDER BY cycle_no DESC,id DESC LIMIT 1''',
        (sn, route_step_id),
    ).fetchone()
    rework_task = None
    if disposition and disposition['rework_task_id']:
        rework_task = db.execute(
            'SELECT * FROM prod_task WHERE id=?', (disposition['rework_task_id'],)
        ).fetchone()
    return {
        'quality_status': quality_status or QUALITY_NORMAL,
        'disposition': _dict(disposition),
        'rework_task': _dict(rework_task),
    }


@contextmanager
def _atomic(db):
    nested = db.in_transaction
    if nested:
        db.execute('SAVEPOINT quality_disposition')
    else:
        db.execute('BEGIN IMMEDIATE')
    try:
        yield
        if nested:
            db.execute('RELEASE SAVEPOINT quality_disposition')
        else:
            db.commit()
    except Exception:
        if nested:
            db.execute('ROLLBACK TO SAVEPOINT quality_disposition')
            db.execute('RELEASE SAVEPOINT quality_disposition')
        else:
            db.rollback()
        raise


def _load_disposition(db, disposition_id):
    row = db.execute(
        'SELECT * FROM prod_quality_disposition WHERE id=?', (disposition_id,)
    ).fetchone()
    if not row:
        raise ValueError('质量处置单不存在')
    return row


def approve_disposition(db, disposition_id, action, user_id, reason=''):
    """Approve rework, scrap, or concession exactly once."""
    action = str(action or '').strip().lower()
    if action not in ('rework', 'scrap', 'concession'):
        raise ValueError('处置方式只能是返工、报废或让步接收')
    with _atomic(db):
        row = _load_disposition(db, disposition_id)
        if row['action'] == action and row['status'] in ('approved', 'task_started', 'completed'):
            return _dict(row)
        if row['status'] != 'pending_review':
            raise ValueError('质量处置单已处理，不能重复变更')

        rework_task_id = None
        target_status = 'completed'
        completed_at = 'CURRENT_TIMESTAMP'
        if action == 'rework':
            source_task = db.execute(
                'SELECT * FROM prod_task WHERE id=?', (row['source_task_id'],)
            ).fetchone()
            if not source_task:
                raise ValueError('原生产任务不存在')
            task_no = 'RW-%s' % row['disposition_no']
            db.execute(
                '''INSERT OR IGNORE INTO prod_task
                   (task_no,workorder_id,process_id,route_step_id,planned_qty,
                    completed_qty,defect_qty,status,remark,task_type,source_task_id,
                    quality_disposition_id,target_sn)
                   VALUES(?,?,?,?,1,0,0,0,?,'rework',?,?,?)''',
                (task_no, row['workorder_id'], source_task['process_id'],
                 row['route_step_id'], '质量处置返工：%s' % (reason or ''),
                 row['source_task_id'], row['id'], row['sn']),
            )
            task = db.execute(
                'SELECT * FROM prod_task WHERE task_no=?', (task_no,)
            ).fetchone()
            if not task or int(task['quality_disposition_id'] or 0) != int(row['id']):
                raise ValueError('返工任务编号冲突')
            rework_task_id = task['id']
            target_status = 'approved'
            completed_at = 'NULL'
            db.execute(
                'UPDATE prod_serial SET quality_status=? WHERE serial_no=?',
                (QUALITY_REWORK, row['sn']),
            )
        elif action == 'scrap':
            db.execute(
                'UPDATE prod_serial SET quality_status=? WHERE serial_no=?',
                (QUALITY_SCRAPPED, row['sn']),
            )
        else:
            request_row = db.execute(
                'SELECT * FROM iot_machine_request WHERE id=?', (row['machine_request_id'],)
            ).fetchone()
            step = db.execute(
                'SELECT * FROM prod_workorder_route_step WHERE id=?', (row['route_step_id'],)
            ).fetchone()
            serial = db.execute(
                'SELECT * FROM prod_serial WHERE serial_no=?', (row['sn'],)
            ).fetchone()
            if not request_row or not step or not serial:
                raise ValueError('让步接收缺少原机台请求、工序或SN')
            flow = db.execute(
                'SELECT * FROM prod_station_flow WHERE sn=? ORDER BY id DESC LIMIT 1',
                (row['sn'],),
            ).fetchone()
            if not flow:
                flow_id = db.execute(
                    '''INSERT INTO prod_station_flow
                       (flow_no,sn,product_id,workorder_id,current_station,current_process,status)
                       VALUES(?,?,?,?,?,?,0)''',
                    ('SF%s' % uuid4().hex[:16], row['sn'], serial['product_id'],
                     row['workorder_id'], request_row['station_code'], step['process_name']),
                ).lastrowid
            else:
                flow_id = flow['id']
            db.execute(
                '''INSERT OR IGNORE INTO prod_station_record
                   (flow_id,sn,station,process_name,action,operator,result,remark,
                    route_step_id,machine_request_id,quality_disposition_id)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (flow_id, row['sn'], request_row['station_code'], step['process_name'],
                 '让步接收', user_id, 'PASS', reason, row['route_step_id'],
                 row['machine_request_id'], row['id']),
            )
            db.execute(
                'UPDATE prod_serial SET quality_status=? WHERE serial_no=?',
                (QUALITY_CONCESSION, row['sn']),
            )

        completed_sql = 'CURRENT_TIMESTAMP' if completed_at == 'CURRENT_TIMESTAMP' else 'NULL'
        cursor = db.execute(
            '''UPDATE prod_quality_disposition
               SET action=?,status=?,rework_task_id=?,reason=?,reviewer_id=?,
                   reviewed_at=CURRENT_TIMESTAMP,completed_at=%s
               WHERE id=? AND status='pending_review' ''' % completed_sql,
            (action, target_status, rework_task_id, reason, user_id, row['id']),
        )
        if cursor.rowcount != 1:
            raise ValueError('质量处置单已被其他用户处理')
    return _dict(db.execute(
        'SELECT * FROM prod_quality_disposition WHERE id=?', (disposition_id,)
    ).fetchone())


def reject_disposition(db, disposition_id, user_id, reason):
    reason = str(reason or '').strip()
    if not reason:
        raise ValueError('驳回原因不能为空')
    with _atomic(db):
        row = _load_disposition(db, disposition_id)
        if row['status'] == 'rejected':
            return _dict(row)
        if row['status'] != 'pending_review':
            raise ValueError('质量处置单已处理，不能驳回')
        cursor = db.execute(
            '''UPDATE prod_quality_disposition
               SET status='rejected',reason=?,reviewer_id=?,reviewed_at=CURRENT_TIMESTAMP
               WHERE id=? AND status='pending_review' ''',
            (reason, user_id, disposition_id),
        )
        if cursor.rowcount != 1:
            raise ValueError('质量处置单已被其他用户处理')
    return _dict(db.execute(
        'SELECT * FROM prod_quality_disposition WHERE id=?', (disposition_id,)
    ).fetchone())


def validate_rework_task_start(db, task_id):
    task = db.execute(
        '''SELECT t.*,d.status AS disposition_status,d.action AS disposition_action,
                  s.quality_status
           FROM prod_task t
           JOIN prod_quality_disposition d ON d.id=t.quality_disposition_id
           JOIN prod_serial s ON s.serial_no=t.target_sn
           WHERE t.id=?''',
        (task_id,),
    ).fetchone()
    if not task or task['task_type'] != 'rework':
        raise ValueError('返工任务不存在')
    if int(task['status']) != 0:
        raise ValueError('只有草稿返工任务可以启动')
    if task['disposition_status'] != 'approved' or task['disposition_action'] != 'rework':
        raise ValueError('质量处置单尚未批准返工')
    if task['quality_status'] != QUALITY_REWORK:
        raise ValueError('SN当前不处于返工状态')
    return _dict(task)
