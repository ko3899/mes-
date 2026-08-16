"""SN-level quality disposition and rework persistence."""


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
