"""数据库管理模块"""
import os
import sqlite3
from flask import g

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'database', 'mes.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception):
    db = g.pop('db', None)
    if db:
        db.close()


def init_db():
    """初始化数据库表结构和基础数据"""
    import hashlib

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")

    # ==================== 系统管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        real_name TEXT,
        phone TEXT,
        email TEXT,
        dept_id INTEGER,
        role_id INTEGER,
        status INTEGER DEFAULT 1,
        avatar TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_role (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_name TEXT NOT NULL,
        role_key TEXT NOT NULL UNIQUE,
        description TEXT,
        menu_ids TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_dept (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_name TEXT NOT NULL,
        parent_id INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        leader TEXT,
        phone TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_menu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        menu_name TEXT NOT NULL,
        parent_id INTEGER DEFAULT 0,
        path TEXT,
        component TEXT,
        icon TEXT,
        sort_order INTEGER DEFAULT 0,
        menu_type TEXT DEFAULT 'M',
        perms TEXT,
        status INTEGER DEFAULT 1
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_dict (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dict_type TEXT NOT NULL,
        dict_label TEXT NOT NULL,
        dict_value TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        status INTEGER DEFAULT 1
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        operation TEXT,
        method TEXT,
        url TEXT,
        ip TEXT,
        params TEXT,
        result TEXT,
        cost_time INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 基础数据 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS base_workshop (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workshop_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS base_process (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        process_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        workshop_id INTEGER,
        description TEXT,
        standard_time REAL,
        sort_order INTEGER DEFAULT 0,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workshop_id) REFERENCES base_workshop(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS base_product (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        specification TEXT,
        unit TEXT,
        product_type TEXT,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS base_bom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        material_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id),
        FOREIGN KEY (material_id) REFERENCES base_product(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS base_process_route (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        route_name TEXT NOT NULL,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS base_process_route_detail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        route_id INTEGER NOT NULL,
        process_id INTEGER NOT NULL,
        step_no INTEGER NOT NULL,
        standard_time REAL,
        description TEXT,
        FOREIGN KEY (route_id) REFERENCES base_process_route(id),
        FOREIGN KEY (process_id) REFERENCES base_process(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS base_defect (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        defect_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        defect_type TEXT,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS base_unit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unit_name TEXT NOT NULL,
        unit_symbol TEXT NOT NULL,
        status INTEGER DEFAULT 1
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS base_salary_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        process_id INTEGER,
        base_salary REAL DEFAULT 0,
        piece_rate REAL DEFAULT 0,
        overtime_rate REAL DEFAULT 0,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (process_id) REFERENCES base_process(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_notice (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT,
        notice_type TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_numbering (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prefix TEXT NOT NULL,
        entity_type TEXT NOT NULL UNIQUE,
        current_no INTEGER DEFAULT 0,
        digit_count INTEGER DEFAULT 6,
        description TEXT
    )''')

    # ==================== 库存管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS inv_inbound (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inbound_no TEXT NOT NULL UNIQUE,
        inbound_type TEXT,
        supplier TEXT,
        total_amount REAL DEFAULT 0,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS inv_inbound_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inbound_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        remark TEXT,
        FOREIGN KEY (inbound_id) REFERENCES inv_inbound(id),
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS inv_outbound (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        outbound_no TEXT NOT NULL UNIQUE,
        outbound_type TEXT,
        customer TEXT,
        total_amount REAL DEFAULT 0,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS inv_outbound_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        outbound_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        remark TEXT,
        FOREIGN KEY (outbound_id) REFERENCES inv_outbound(id),
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS inv_balance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL UNIQUE,
        quantity REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS inv_transaction (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        trans_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        balance REAL NOT NULL,
        ref_no TEXT,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    # ==================== 生产管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_sales_order (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT NOT NULL UNIQUE,
        customer TEXT NOT NULL,
        contact TEXT,
        phone TEXT,
        total_amount REAL DEFAULT 0,
        delivery_date TEXT,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_sales_order_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        delivered_qty REAL DEFAULT 0,
        remark TEXT,
        FOREIGN KEY (order_id) REFERENCES prod_sales_order(id),
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_no TEXT NOT NULL UNIQUE,
        sales_order_id INTEGER,
        plan_type TEXT,
        start_date TEXT,
        end_date TEXT,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_plan_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        planned_qty REAL NOT NULL,
        completed_qty REAL DEFAULT 0,
        workshop_id INTEGER,
        remark TEXT,
        FOREIGN KEY (plan_id) REFERENCES prod_plan(id),
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_workorder (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT NOT NULL UNIQUE,
        plan_id INTEGER,
        sales_order_id INTEGER,
        product_id INTEGER NOT NULL,
        route_id INTEGER,
        planned_qty REAL NOT NULL,
        completed_qty REAL DEFAULT 0,
        defect_qty REAL DEFAULT 0,
        workshop_id INTEGER,
        priority INTEGER DEFAULT 1,
        status INTEGER DEFAULT 0,
        start_date TEXT,
        end_date TEXT,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_task (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        process_id INTEGER NOT NULL,
        assigned_to INTEGER,
        planned_qty REAL NOT NULL,
        completed_qty REAL DEFAULT 0,
        defect_qty REAL DEFAULT 0,
        status INTEGER DEFAULT 0,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id),
        FOREIGN KEY (process_id) REFERENCES base_process(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_report (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_no TEXT NOT NULL UNIQUE,
        task_id INTEGER NOT NULL,
        workorder_id INTEGER NOT NULL,
        process_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        qualified_qty REAL NOT NULL,
        defect_qty REAL DEFAULT 0,
        report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        remark TEXT,
        FOREIGN KEY (task_id) REFERENCES prod_task(id),
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id)
    )''')

    # ==================== 质量管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_inspection_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        standard TEXT,
        method TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS qm_inspection_template (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        inspection_type TEXT,
        item_ids TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS qm_incoming_inspection (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspect_no TEXT NOT NULL UNIQUE,
        inbound_id INTEGER,
        supplier TEXT,
        template_id INTEGER,
        result TEXT,
        status INTEGER DEFAULT 0,
        inspector INTEGER,
        inspect_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS qm_process_inspection (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspect_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER,
        task_id INTEGER,
        template_id INTEGER,
        result TEXT,
        status INTEGER DEFAULT 0,
        inspector INTEGER,
        inspect_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS qm_outgoing_inspection (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspect_no TEXT NOT NULL UNIQUE,
        outbound_id INTEGER,
        customer TEXT,
        template_id INTEGER,
        result TEXT,
        status INTEGER DEFAULT 0,
        inspector INTEGER,
        inspect_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 排班管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sched_team (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        leader TEXT,
        member_count INTEGER DEFAULT 0,
        workshop_id INTEGER,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sched_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_name TEXT NOT NULL,
        team_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        shift_type TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (team_id) REFERENCES sched_team(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sched_holiday (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        holiday_name TEXT NOT NULL,
        holiday_date TEXT NOT NULL,
        holiday_type TEXT,
        is_workday INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 工具管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS tool_type (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        description TEXT,
        status INTEGER DEFAULT 1
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS tool_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        type_id INTEGER,
        specification TEXT,
        quantity REAL DEFAULT 0,
        location TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (type_id) REFERENCES tool_type(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS tool_borrow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        borrow_no TEXT NOT NULL UNIQUE,
        tool_id INTEGER NOT NULL,
        borrower INTEGER NOT NULL,
        borrow_qty REAL NOT NULL,
        borrow_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        return_time TIMESTAMP,
        return_qty REAL DEFAULT 0,
        status INTEGER DEFAULT 0,
        remark TEXT,
        FOREIGN KEY (tool_id) REFERENCES tool_ledger(id)
    )''')

    # ==================== 设备管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS eqp_type (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        description TEXT,
        status INTEGER DEFAULT 1
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS eqp_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        type_id INTEGER,
        model TEXT,
        manufacturer TEXT,
        purchase_date TEXT,
        workshop_id INTEGER,
        location TEXT,
        status INTEGER DEFAULT 1,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (type_id) REFERENCES eqp_type(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS eqp_check_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        standard TEXT,
        method TEXT,
        check_type TEXT,
        status INTEGER DEFAULT 1
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS eqp_maintenance_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_name TEXT NOT NULL,
        equipment_id INTEGER NOT NULL,
        check_items TEXT,
        frequency TEXT,
        next_date TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS eqp_repair_order (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repair_no TEXT NOT NULL UNIQUE,
        equipment_id INTEGER NOT NULL,
        fault_desc TEXT,
        repair_desc TEXT,
        reporter INTEGER,
        repairer INTEGER,
        status INTEGER DEFAULT 0,
        report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        repair_time TIMESTAMP,
        remark TEXT,
        FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS eqp_check_workorder (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workorder_no TEXT NOT NULL UNIQUE,
        plan_id INTEGER NOT NULL,
        equipment_id INTEGER NOT NULL,
        check_result TEXT,
        status INTEGER DEFAULT 0,
        assigned_to INTEGER,
        check_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (plan_id) REFERENCES eqp_maintenance_plan(id),
        FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id)
    )''')

    # ==================== 审批流程 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS flow_definition (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flow_name TEXT NOT NULL,
        flow_key TEXT NOT NULL UNIQUE,
        description TEXT,
        steps TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS flow_instance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flow_id INTEGER NOT NULL,
        biz_type TEXT,
        biz_id INTEGER,
        title TEXT,
        current_step INTEGER DEFAULT 1,
        status INTEGER DEFAULT 0,
        creator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (flow_id) REFERENCES flow_definition(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS flow_task (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id INTEGER NOT NULL,
        step_no INTEGER NOT NULL,
        assignee INTEGER NOT NULL,
        action TEXT,
        comment TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (instance_id) REFERENCES flow_instance(id)
    )''')

    # ==================== 定时任务 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS job_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_name TEXT NOT NULL,
        job_key TEXT NOT NULL UNIQUE,
        cron_expression TEXT,
        job_class TEXT,
        params TEXT,
        status INTEGER DEFAULT 1,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS job_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        job_name TEXT,
        status INTEGER,
        message TEXT,
        cost_time INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES job_config(id)
    )''')

    # ==================== 版本记录 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_version (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version_no TEXT NOT NULL,
        release_date TEXT,
        changes TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 消息通知 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_notification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        link TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES sys_user(id)
    )''')

    # ==================== 初始化数据 ====================
    pwd = hashlib.md5('admin123'.encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO sys_user (username, password, real_name, phone, status) VALUES (?, ?, ?, ?, ?)",
               ('admin', pwd, '系统管理员', '13800000000', 1))

    db.execute("INSERT OR IGNORE INTO sys_role (role_name, role_key, description, menu_ids) VALUES (?, ?, ?, ?)",
               ('超级管理员', 'admin', '拥有所有权限', ''))
    db.execute("INSERT OR IGNORE INTO sys_role (role_name, role_key, description, menu_ids) VALUES (?, ?, ?, ?)",
               ('普通用户', 'user', '普通用户权限', ''))

    db.execute("INSERT OR IGNORE INTO sys_dept (dept_name, parent_id, sort_order) VALUES (?, ?, ?)",
               ('总经办', 0, 1))
    db.execute("INSERT OR IGNORE INTO sys_dept (dept_name, parent_id, sort_order) VALUES (?, ?, ?)",
               ('生产部', 0, 2))
    db.execute("INSERT OR IGNORE INTO sys_dept (dept_name, parent_id, sort_order) VALUES (?, ?, ?)",
               ('品质部', 0, 3))
    db.execute("INSERT OR IGNORE INTO sys_dept (dept_name, parent_id, sort_order) VALUES (?, ?, ?)",
               ('仓库部', 0, 4))
    db.execute("INSERT OR IGNORE INTO sys_dept (dept_name, parent_id, sort_order) VALUES (?, ?, ?)",
               ('设备部', 0, 5))

    menus = [
        ('基础数据', 0, '/base', '', 'database', 1, 'M', ''),
        ('工艺路线', 1, '/base/route', '', 'route', 1, 'C', 'base:route:list'),
        ('产品定义', 1, '/base/product', '', 'product', 2, 'C', 'base:product:list'),
        ('物料清单', 1, '/base/bom', '', 'bom', 3, 'C', 'base:bom:list'),
        ('工序', 1, '/base/process', '', 'process', 4, 'C', 'base:process:list'),
        ('不良品项', 1, '/base/defect', '', 'defect', 5, 'C', 'base:defect:list'),
        ('单位管理', 1, '/base/unit', '', 'unit', 6, 'C', 'base:unit:list'),
        ('车间设置', 1, '/base/workshop', '', 'workshop', 7, 'C', 'base:workshop:list'),
        ('库存管理', 0, '/inventory', '', 'inventory', 2, 'M', ''),
        ('入库单', 9, '/inv/inbound', '', 'inbound', 1, 'C', 'inv:inbound:list'),
        ('出库单', 9, '/inv/outbound', '', 'outbound', 2, 'C', 'inv:outbound:list'),
        ('库存余额', 9, '/inv/balance', '', 'balance', 3, 'C', 'inv:balance:list'),
        ('生产管理', 0, '/production', '', 'production', 3, 'M', ''),
        ('销售订单', 13, '/prod/sales', '', 'sales', 1, 'C', 'prod:sales:list'),
        ('生产计划', 13, '/prod/plan', '', 'plan', 2, 'C', 'prod:plan:list'),
        ('工单管理', 13, '/prod/workorder', '', 'workorder', 3, 'C', 'prod:workorder:list'),
        ('任务管理', 13, '/prod/task', '', 'task', 4, 'C', 'prod:task:list'),
        ('报工管理', 13, '/prod/report', '', 'report', 5, 'C', 'prod:report:list'),
        ('质量管理', 0, '/quality', '', 'quality', 4, 'M', ''),
        ('来料检验', 19, '/qm/incoming', '', 'incoming', 1, 'C', 'qm:incoming:list'),
        ('过程检验', 19, '/qm/process', '', 'process-inspect', 2, 'C', 'qm:process:list'),
        ('出货检验', 19, '/qm/outgoing', '', 'outgoing', 3, 'C', 'qm:outgoing:list'),
        ('设备管理', 0, '/equipment', '', 'equipment', 5, 'M', ''),
        ('设备台账', 23, '/eqp/ledger', '', 'eqp-ledger', 1, 'C', 'eqp:ledger:list'),
        ('维修单', 23, '/eqp/repair', '', 'repair', 2, 'C', 'eqp:repair:list'),
        ('排班管理', 0, '/schedule', '', 'schedule', 6, 'M', ''),
        ('班组管理', 26, '/sched/team', '', 'team', 1, 'C', 'sched:team:list'),
        ('排班计划', 26, '/sched/plan', '', 'sched-plan', 2, 'C', 'sched:plan:list'),
        ('工具管理', 0, '/tool', '', 'tool', 7, 'M', ''),
        ('工具台账', 29, '/tool/ledger', '', 'tool-ledger', 1, 'C', 'tool:ledger:list'),
        ('工具领用', 29, '/tool/borrow', '', 'borrow', 2, 'C', 'tool:borrow:list'),
        ('报表管理', 0, '/report', '', 'chart', 8, 'M', ''),
        ('生产报表', 32, '/report/production', '', 'prod-report', 1, 'C', 'report:production:list'),
        ('系统管理', 0, '/system', '', 'system', 9, 'M', ''),
        ('用户管理', 34, '/sys/user', '', 'user', 1, 'C', 'sys:user:list'),
        ('角色管理', 34, '/sys/role', '', 'role', 2, 'C', 'sys:role:list'),
        ('部门管理', 34, '/sys/dept', '', 'dept', 3, 'C', 'sys:dept:list'),
        ('菜单管理', 34, '/sys/menu', '', 'menu', 4, 'C', 'sys:menu:list'),
        ('数据字典', 34, '/sys/dict', '', 'dict', 5, 'C', 'sys:dict:list'),
        ('系统日志', 34, '/sys/log', '', 'log', 6, 'C', 'sys:log:list'),
    ]
    for m in menus:
        db.execute("INSERT OR IGNORE INTO sys_menu (menu_name, parent_id, path, component, icon, sort_order, menu_type, perms) VALUES (?,?,?,?,?,?,?,?)", m)

    units = [('个', '个'), ('件', '件'), ('台', '台'), ('套', '套'), ('米', 'm'), ('千克', 'kg'), ('升', 'L'), ('箱', '箱')]
    for u in units:
        db.execute("INSERT OR IGNORE INTO base_unit (unit_name, unit_symbol) VALUES (?,?)", u)

    db.commit()
    db.close()


def _init_extra_tables():
    """初始化新增功能的表"""
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")

    # 给 base_process 表添加 sort_order 字段（如果不存在）
    try:
        db.execute("ALTER TABLE base_process ADD COLUMN sort_order INTEGER DEFAULT 0")
    except:
        pass  # 字段已存在

    db.execute('''CREATE TABLE IF NOT EXISTS inv_batch (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_no TEXT NOT NULL UNIQUE,
        product_id INTEGER NOT NULL,
        supplier TEXT,
        quantity REAL DEFAULT 0,
        production_date TEXT,
        expiry_date TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS inv_trace (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        trace_type TEXT NOT NULL,
        ref_no TEXT,
        ref_id INTEGER,
        quantity REAL,
        operator INTEGER,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES inv_batch(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS spc_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        process_id INTEGER NOT NULL,
        product_id INTEGER,
        measure_value REAL NOT NULL,
        usl REAL,
        lsl REAL,
        measure_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        operator INTEGER,
        remark TEXT,
        FOREIGN KEY (process_id) REFERENCES base_process(id)
    )''')

    # ==================== 供应商管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS base_supplier (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        contact TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        rating INTEGER DEFAULT 5,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 客户管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS base_customer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        contact TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        credit_limit REAL DEFAULT 0,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 文档管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_document (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_name TEXT NOT NULL,
        doc_type TEXT,
        category TEXT,
        file_path TEXT,
        file_size INTEGER,
        version TEXT DEFAULT '1.0',
        uploader INTEGER,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 成本核算 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_cost (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workorder_id INTEGER NOT NULL,
        cost_type TEXT NOT NULL,
        amount REAL DEFAULT 0,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id)
    )''')

    # ==================== 条码记录 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_barcode (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT NOT NULL UNIQUE,
        biz_type TEXT NOT NULL,
        biz_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 数据备份 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_backup (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        backup_name TEXT NOT NULL,
        file_path TEXT,
        file_size INTEGER,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 通知配置 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_notify_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notify_type TEXT NOT NULL,
        webhook_url TEXT,
        enabled INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 工序转移单 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_transfer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transfer_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        from_process_id INTEGER NOT NULL,
        to_process_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        operator INTEGER,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id),
        FOREIGN KEY (from_process_id) REFERENCES base_process(id),
        FOREIGN KEY (to_process_id) REFERENCES base_process(id)
    )''')

    # ==================== 生产领料 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_material_req (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        req_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        req_type TEXT DEFAULT '领料',
        status INTEGER DEFAULT 0,
        operator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id)
    )''')

    # ==================== 委外加工 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_outsource (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        outsource_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER,
        supplier_id INTEGER,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL DEFAULT 0,
        delivery_date TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 产品序列号 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_serial (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_no TEXT NOT NULL UNIQUE,
        product_id INTEGER NOT NULL,
        workorder_id INTEGER,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    # ==================== 不良品处理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_defect_process (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        process_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER,
        task_id INTEGER,
        defect_id INTEGER,
        quantity REAL NOT NULL,
        process_type TEXT DEFAULT '返工',
        result TEXT,
        status INTEGER DEFAULT 0,
        operator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 首件检验 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_first_inspect (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspect_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        process_id INTEGER NOT NULL,
        self_check INTEGER DEFAULT 0,
        mutual_check INTEGER DEFAULT 0,
        special_check INTEGER DEFAULT 0,
        result TEXT,
        status INTEGER DEFAULT 0,
        operator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 8D报告 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_8d_report (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_no TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        problem_desc TEXT,
        root_cause TEXT,
        corrective_action TEXT,
        preventive_action TEXT,
        responsible TEXT,
        due_date TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 供方评审 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_supplier_eval (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL,
        eval_date TEXT NOT NULL,
        quality_score REAL DEFAULT 0,
        delivery_score REAL DEFAULT 0,
        service_score REAL DEFAULT 0,
        total_score REAL DEFAULT 0,
        grade TEXT,
        evaluator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 工时记录 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_labor_time (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        task_id INTEGER,
        workorder_id INTEGER,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        duration REAL DEFAULT 0,
        overtime REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 包装管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_packing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        packing_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER,
        box_count INTEGER DEFAULT 0,
        quantity_per_box INTEGER DEFAULT 0,
        total_quantity REAL DEFAULT 0,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 登录日志 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_login_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        login_ip TEXT,
        login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        logout_time TIMESTAMP,
        status INTEGER DEFAULT 1,
        browser TEXT,
        os TEXT
    )''')

    # ==================== 系统配置 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT NOT NULL UNIQUE,
        config_value TEXT,
        config_type TEXT DEFAULT 'string',
        description TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 系统公告 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_announcement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT,
        notice_type TEXT DEFAULT 'notice',
        priority INTEGER DEFAULT 0,
        status INTEGER DEFAULT 1,
        publisher INTEGER,
        publish_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expire_time TIMESTAMP
    )''')

    # ==================== IP白名单 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_ip_whitelist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT NOT NULL,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 打印模板 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_print_template (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL,
        biz_type TEXT NOT NULL,
        template_content TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 通知渠道配置 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_notify_channel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_name TEXT NOT NULL,
        channel_type TEXT NOT NULL,
        config TEXT,
        enabled INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 阶段码管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS base_stage_code (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stage_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        description TEXT,
        sort_order INTEGER DEFAULT 0,
        color TEXT DEFAULT '#1890ff',
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_stage_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stage_code TEXT NOT NULL,
        workorder_id INTEGER,
        task_id INTEGER,
        product_id INTEGER,
        quantity REAL DEFAULT 0,
        operator INTEGER,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        duration REAL DEFAULT 0,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 工位管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS base_workstation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        workshop_id INTEGER,
        process_id INTEGER,
        equipment_id INTEGER,
        capacity REAL DEFAULT 0,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workshop_id) REFERENCES base_workshop(id),
        FOREIGN KEY (process_id) REFERENCES base_process(id)
    )''')

    # ==================== 安灯系统 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_andon (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        andon_no TEXT NOT NULL UNIQUE,
        workstation_id INTEGER,
        andon_type TEXT NOT NULL,
        description TEXT,
        priority INTEGER DEFAULT 1,
        status INTEGER DEFAULT 0,
        caller INTEGER,
        responder INTEGER,
        call_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        response_time TIMESTAMP,
        resolve_time TIMESTAMP,
        remark TEXT
    )''')

    # ==================== 返工报废 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_rework (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rework_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER,
        task_id INTEGER,
        quantity REAL NOT NULL,
        rework_type TEXT DEFAULT '返工',
        reason TEXT,
        status INTEGER DEFAULT 0,
        operator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== CAPA ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_capa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        capa_no TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        source TEXT,
        problem_desc TEXT,
        root_cause TEXT,
        corrective_action TEXT,
        preventive_action TEXT,
        responsible TEXT,
        due_date TEXT,
        effectiveness TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 控制计划 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_control_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_name TEXT NOT NULL,
        product_id INTEGER,
        process_id INTEGER,
        characteristic TEXT,
        method TEXT,
        frequency TEXT,
        reaction_plan TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 工程变更 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_eco (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        eco_no TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        change_type TEXT,
        description TEXT,
        reason TEXT,
        impact TEXT,
        applicant INTEGER,
        approver INTEGER,
        status INTEGER DEFAULT 0,
        apply_date TEXT,
        effective_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 模具管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS eqp_mold (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mold_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        mold_type TEXT,
        product_id INTEGER,
        manufacturer TEXT,
        purchase_date TEXT,
        total_life INTEGER DEFAULT 0,
        used_life INTEGER DEFAULT 0,
        location TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 工装夹具 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS eqp_fixture (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        fixture_type TEXT,
        process_id INTEGER,
        calibration_date TEXT,
        next_calibration TEXT,
        location TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 能耗管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS util_energy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_date TEXT NOT NULL,
        workshop_id INTEGER,
        energy_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        unit TEXT,
        cost REAL DEFAULT 0,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 环境监控 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS util_environment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workshop_id INTEGER,
        temperature REAL,
        humidity REAL,
        cleanliness TEXT,
        record_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        remark TEXT
    )''')

    # ==================== 培训管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS hr_training (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        training_name TEXT NOT NULL,
        training_type TEXT,
        trainer TEXT,
        trainee_ids TEXT,
        start_date TEXT,
        end_date TEXT,
        content TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS hr_training_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        training_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        score REAL,
        result TEXT,
        remark TEXT,
        FOREIGN KEY (training_id) REFERENCES hr_training(id)
    )''')

    # ==================== 技能矩阵 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS hr_skill_matrix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        process_id INTEGER NOT NULL,
        skill_level INTEGER DEFAULT 0,
        cert_date TEXT,
        expiry_date TEXT,
        evaluator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 5S管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sys_5s_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_no TEXT NOT NULL UNIQUE,
        workshop_id INTEGER,
        audit_date TEXT NOT NULL,
        sort_score INTEGER DEFAULT 0,
        set_in_order_score INTEGER DEFAULT 0,
        shine_score INTEGER DEFAULT 0,
        standardize_score INTEGER DEFAULT 0,
        sustain_score INTEGER DEFAULT 0,
        total_score REAL DEFAULT 0,
        findings TEXT,
        corrective TEXT,
        auditor INTEGER,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 售后管理 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS svc_complaint (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_no TEXT NOT NULL UNIQUE,
        customer_id INTEGER,
        product_id INTEGER,
        complaint_type TEXT,
        description TEXT,
        severity TEXT,
        status INTEGER DEFAULT 0,
        handler INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS svc_return (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        return_no TEXT NOT NULL UNIQUE,
        complaint_id INTEGER,
        customer_id INTEGER,
        product_id INTEGER,
        quantity REAL DEFAULT 0,
        reason TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.commit()
    db.close()
