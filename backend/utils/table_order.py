"""Persistent manual ordering for whitelisted MES record lists."""


ORDERABLE_TABLES = {
    'prod/workorder': 'prod_workorder',
    'prod/task': 'prod_task',
    'prod/report': 'prod_report',
    'prod/sales': 'prod_sales_order',
    'prod/plan': 'prod_plan',
    'prod/batch': 'prod_batch',
    'base/workshop': 'base_workshop',
    'base/process': 'base_process',
    'base/product': 'base_product',
    'base/bom': 'base_bom',
    'base/defect': 'base_defect',
    'base/unit': 'base_unit',
    'base/route': 'base_process_route',
    'base/supplier': 'base_supplier',
    'base/customer': 'base_customer',
    'inv/inbound': 'inv_inbound',
    'inv/outbound': 'inv_outbound',
    'inv/balance': 'inv_balance',
    'qm/incoming': 'qm_incoming_inspection',
    'qm/process': 'qm_process_inspection',
    'qm/outgoing': 'qm_outgoing_inspection',
    'eqp/ledger': 'eqp_ledger',
    'eqp/repair': 'eqp_repair_order',
    'eqp/maintenance': 'eqp_maintenance_plan',
    'eqp/check': 'eqp_check_workorder',
    'tool/ledger': 'tool_ledger',
    'tool/borrow': 'tool_borrow',
    'sched/team': 'sched_team',
    'sched/plan': 'sched_plan',
    'sys/user': 'sys_user',
    'sys/role': 'sys_role',
    'sys/dept': 'sys_dept',
    'sys/dict': 'sys_dict',
    'doc/list': 'sys_document',
    'notifications': 'sys_notification',
    'warehouse/list': 'inv_warehouse',
    'warehouse/area': 'inv_area',
    'warehouse/location': 'inv_location',
    'warehouse/arrival': 'inv_arrival_notice',
    'warehouse/transaction': 'inv_transaction_log',
    'qm/template': 'qm_inspect_template',
    'eqp/check-project': 'eqp_check_project',
    'sched/calendar': 'sched_calendar',
    'process/station-config': 'base_station_config',
    'process/flow': 'prod_station_flow',
    'process/record': 'prod_station_record',
    'process/material': 'base_material',
    'process/box': 'prod_box',
    'process/lock': 'prod_material_lock',
    'process/defect': 'prod_defect_receive',
    'process/exception': 'prod_exception',
    'stage/code': 'base_stage_code',
    'stage/record': 'prod_stage_record',
    'prod/transfer': 'prod_transfer',
    'prod/material': 'prod_material_req',
    'prod/outsource': 'prod_outsource',
    'prod/serial': 'prod_serial',
    'prod/labor': 'prod_labor_time',
    'prod/packing': 'prod_packing',
    'site/workstation': 'base_workstation',
    'site/andon': 'prod_andon',
    'site/rework': 'prod_rework',
    'qm/first': 'qm_first_inspect',
    'qm/defect': 'qm_defect_process',
    'qm/8d': 'qm_8d_report',
    'qm/supplier-eval': 'qm_supplier_eval',
    'qm/capa': 'qm_capa',
    'qm/control-plan': 'qm_control_plan',
    'qm/eco': 'qm_eco',
    'eqp/mold': 'eqp_mold',
    'eqp/fixture': 'eqp_fixture',
    'util/energy': 'util_energy',
    'util/environment': 'util_environment',
    'hr/training': 'hr_training',
    'hr/skill-matrix': 'hr_skill_matrix',
    '5s/audit': 'sys_5s_audit',
    'svc/complaint': 'svc_complaint',
    'svc/return': 'svc_return',
    'trace/batch': 'inv_batch',
    'flow/def': 'flow_definition',
    'flow/instance': 'flow_instance',
    'flow/pending': 'flow_task',
    'sys/log': 'sys_log',
    'sys/login-log': 'sys_login_log',
    'sys/config': 'sys_config',
    'sys/announcement': 'sys_announcement',
    'sys/ip-whitelist': 'sys_ip_whitelist',
    'sys/print-template': 'sys_print_template',
    'sys/notify-channel': 'sys_notify_channel',
}


def reorder_ids(ids, record_id, target_position):
    """Return ids with record_id inserted at a clamped one-based position."""
    ordered = list(ids)
    if record_id not in ordered:
        raise LookupError('记录不存在')
    ordered.remove(record_id)
    target = max(1, min(int(target_position), len(ordered) + 1))
    ordered.insert(target - 1, record_id)
    return ordered


def _table_for(table_key):
    table = ORDERABLE_TABLES.get(table_key)
    if not table:
        raise ValueError('该模块不支持手工排序')
    return table


def ordered_ids(db, table_key):
    table = _table_for(table_key)
    try:
        rows = db.execute(
            f'''SELECT source.id,
                ordering.position
                FROM "{table}" source
                LEFT JOIN sys_table_order ordering
                  ON ordering.table_key=? AND ordering.record_id=source.id
                ORDER BY CASE WHEN ordering.position IS NULL THEN 1 ELSE 0 END,
                         ordering.position ASC,
                         source.id DESC''',
            (table_key,),
        ).fetchall()
    except Exception as exc:
        raise ValueError('该模块的数据表不可用') from exc
    return [int(row['id'] if hasattr(row, 'keys') else row[0]) for row in rows]


def _persist(db, table_key, ids):
    db.execute('DELETE FROM sys_table_order WHERE table_key=?', (table_key,))
    db.executemany(
        '''INSERT INTO sys_table_order(table_key, record_id, position, updated_at)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)''',
        [(table_key, record_id, index) for index, record_id in enumerate(ids, 1)],
    )


def move_record(db, table_key, record_id, target_position):
    ids = ordered_ids(db, table_key)
    reordered = reorder_ids(ids, int(record_id), int(target_position))
    _persist(db, table_key, reordered)
    return reordered


def step_record(db, table_key, record_id, direction):
    ids = ordered_ids(db, table_key)
    record_id = int(record_id)
    if record_id not in ids:
        raise LookupError('记录不存在')
    if direction not in ('up', 'down'):
        raise ValueError('移动方向无效')
    current = ids.index(record_id) + 1
    target = current - 1 if direction == 'up' else current + 1
    return move_record(db, table_key, record_id, target)


def positions_for(ids):
    return {str(record_id): position for position, record_id in enumerate(ids, 1)}
