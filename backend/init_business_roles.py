# -*- coding: utf-8 -*-
"""业务角色初始化脚本（幂等）：按岗位创建 sys_role 并配置细粒度权限。

用法:
    py -3.13 backend/init_business_roles.py            # 初始化 database/mes.db
    py -3.13 backend/init_business_roles.py <db_path>  # 指定数据库文件

设计原则:
- 与《MES工厂管家_岗位职责与操作流程手册》附录的岗位-权限对照一致
- 遵循最小权限原则:只授予岗位必需权限
- INSERT OR IGNORE (role_key 唯一),可重复执行
- 不修改已存在的 admin / user 角色
"""
import json
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, 'database', 'mes.db')

# 岗位 -> (role_key, 角色名, 描述, [权限 key])
BUSINESS_ROLES = [
    (
        'planner', '生产计划员',
        '制定生产计划、创建下发工单、跟踪进度',
        ['base:read',
         'prod:sales:read', 'prod:sales:write',
         'prod:plan:read', 'prod:plan:write',
         'prod:batch:read', 'prod:batch:write',
         'prod:workorder:read', 'prod:workorder:write',
         'prod:task:read', 'prod:task:list',
         'prod:report:read',
         'aps:write'],
    ),
    (
        'workshop_leader', '车间主任',
        '任务分配、进度监控、报工审核与过账、审批',
        ['base:read',
         'prod:workorder:read', 'prod:batch:read',
         'prod:task:read', 'prod:task:list', 'prod:task:write',
         'prod:report:read', 'prod:report:review', 'prod:report:post',
         'prod:extension:read',
         'eqp:read',
         'flow:approve'],
    ),
    (
        'operator', '生产操作工',
        '扫码领取任务、执行生产、扫码报工、领料',
        ['base:read',
         'prod:batch:read',
         'prod:task:read', 'prod:task:list',
         'prod:report:read', 'prod:report:create'],
    ),
    (
        'quality_inspector', '质检员',
        'IQC/PQC/OQC 检验、SPC 监控、不良处置',
        ['base:read',
         'quality:write', 'qm:process:list',
         'prod:report:read', 'prod:batch:read',
         'prod:extension:read',
         'inv:read', 'scm:read'],
    ),
    (
        'warehouse_keeper', '仓管员',
        '出入库管理、库存查询、批次追溯、收料过账',
        ['base:read',
         'inv:read', 'inv:write',
         'prod:batch:read',
         'scm:read', 'scm:receipt',
         'doc:read'],
    ),
    (
        'equipment_admin', '设备管理员',
        '设备台账、维修工单、保养计划、IoT 接入',
        ['base:read',
         'eqp:read', 'eqp:write',
         'iot:write', 'tool:write',
         'sched:write', 'site:write',
         'prod:task:read', 'prod:task:list'],
    ),
    (
        'purchaser', '采购员',
        '采购订单、到货登记、收料过账、供应商管理',
        ['base:read',
         'scm:read', 'scm:write', 'scm:receipt',
         'inv:read', 'doc:read'],
    ),
]


def init_business_roles(db_path=None):
    db_path = db_path or DEFAULT_DB
    if not os.path.exists(db_path):
        raise SystemExit(f'数据库不存在: {db_path}')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        created, updated = 0, 0
        for role_key, role_name, desc, perms in BUSINESS_ROLES:
            menu_ids = json.dumps(sorted(set(perms)), ensure_ascii=False)
            existing = conn.execute(
                'SELECT id, menu_ids FROM sys_role WHERE role_key=?', (role_key,)
            ).fetchone()
            if existing:
                # 已存在则更新权限与描述(不覆盖 role_name 人工改名)
                conn.execute(
                    'UPDATE sys_role SET menu_ids=?, description=? WHERE id=?',
                    (menu_ids, desc, existing['id']),
                )
                updated += 1
            else:
                conn.execute(
                    'INSERT INTO sys_role(role_name, role_key, description, menu_ids, status) '
                    'VALUES(?,?,?,?,1)',
                    (role_name, role_key, desc, menu_ids),
                )
                created += 1
        conn.commit()
        print(f'[OK] 业务角色初始化完成: 新建 {created} 个, 更新 {updated} 个 (db={db_path})')
        for role_key, role_name, _d, perms in BUSINESS_ROLES:
            print(f'  - {role_key:20s} {role_name} ({len(set(perms))} 权限)')
    finally:
        conn.close()


if __name__ == '__main__':
    init_business_roles(sys.argv[1] if len(sys.argv) > 1 else None)
