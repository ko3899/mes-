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
        tenant_id INTEGER DEFAULT 1,
        status INTEGER DEFAULT 1,
        avatar TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_tenant (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_name TEXT NOT NULL,
        tenant_code TEXT NOT NULL UNIQUE,
        contact TEXT,
        phone TEXT,
        max_users INTEGER DEFAULT 100,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    db.execute('''CREATE TABLE IF NOT EXISTS sys_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT NOT NULL UNIQUE,
        config_value TEXT,
        config_type TEXT DEFAULT 'string',
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    db.execute('''CREATE TABLE IF NOT EXISTS sys_login_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        login_ip TEXT,
        status INTEGER DEFAULT 1,
        login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    db.execute('''CREATE TABLE IF NOT EXISTS base_supplier (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        contact TEXT,
        phone TEXT,
        address TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

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
        client_operation_id TEXT,
        FOREIGN KEY (task_id) REFERENCES prod_task(id),
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_exception (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exception_no TEXT NOT NULL UNIQUE,
        exception_type TEXT,
        station TEXT,
        description TEXT,
        severity TEXT DEFAULT 'medium',
        handler INTEGER,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_defect_receive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receive_no TEXT NOT NULL UNIQUE,
        sn TEXT,
        product_id INTEGER,
        defect_id INTEGER,
        station TEXT,
        quantity INTEGER DEFAULT 1,
        process_type TEXT DEFAULT '待处理',
        operator INTEGER,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    db.execute('''CREATE TABLE IF NOT EXISTS sys_ip_whitelist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT NOT NULL UNIQUE,
        description TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_print_template (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL,
        biz_type TEXT,
        template_content TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS sys_notify_channel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_name TEXT NOT NULL,
        channel_type TEXT NOT NULL,
        config TEXT,
        enabled INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 初始化数据 ====================
    # 使用安全的密码哈希（PBKDF2 + SHA256 + 盐值）
    import secrets
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', 'admin123'.encode(), salt.encode(), 100000)
    pwd = f"{salt}${pwd_hash.hex()}"
    db.execute("""INSERT OR IGNORE INTO sys_tenant
                  (tenant_name, tenant_code, max_users, status)
                  VALUES (?, 'default', 100, 1)""", ('默认租户',))
    db.execute("INSERT OR IGNORE INTO sys_user (username, password, real_name, phone, status) VALUES (?, ?, ?, ?, ?)",
               ('admin', pwd, '系统管理员', '13800000000', 1))

    db.execute("INSERT OR IGNORE INTO sys_role (role_name, role_key, description, menu_ids) VALUES (?, ?, ?, ?)",
               ('超级管理员', 'admin', '拥有所有权限', ''))
    db.execute("INSERT OR IGNORE INTO sys_role (role_name, role_key, description, menu_ids) VALUES (?, ?, ?, ?)",
               ('普通用户', 'user', '普通用户权限', ''))

    # Backfill role references for databases created before role assignment was enforced.
    db.execute("""UPDATE sys_user SET role_id=(SELECT id FROM sys_role WHERE role_key='admin')
                  WHERE username='admin' AND (role_id IS NULL OR role_id=0)""")
    db.execute("""UPDATE sys_user SET role_id=(SELECT id FROM sys_role WHERE role_key='user')
                  WHERE role_id IS NULL OR role_id=0""")

    default_departments = [
        ('总经办', 0, 1),
        ('生产部', 0, 2),
        ('品质部', 0, 3),
        ('仓库部', 0, 4),
        ('设备部', 0, 5),
    ]
    for dept_name, parent_id, sort_order in default_departments:
        exists = db.execute(
            "SELECT id FROM sys_dept WHERE dept_name=? AND parent_id=? ORDER BY id LIMIT 1",
            (dept_name, parent_id),
        ).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO sys_dept (dept_name, parent_id, sort_order) VALUES (?, ?, ?)",
                (dept_name, parent_id, sort_order),
            )

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
    # Legacy menu definitions refer to parents by their 1-based position in the
    # seed list. Resolve those positions to actual IDs so existing databases do
    # not attach children to unrelated rows.
    seeded_menu_ids = {}
    for seed_position, menu in enumerate(menus, start=1):
        menu_name, legacy_parent, path, component, icon, sort_order, menu_type, perms = menu
        parent_id = seeded_menu_ids.get(legacy_parent, 0)
        existing = db.execute(
            "SELECT id FROM sys_menu WHERE path=? ORDER BY id LIMIT 1", (path,)
        ).fetchone()
        if existing:
            menu_id = existing[0]
            db.execute(
                """UPDATE sys_menu
                   SET menu_name=?, parent_id=?, component=?, icon=?, sort_order=?,
                       menu_type=?, perms=? WHERE id=?""",
                (menu_name, parent_id, component, icon, sort_order, menu_type, perms, menu_id),
            )
        else:
            cursor = db.execute(
                """INSERT INTO sys_menu
                   (menu_name, parent_id, path, component, icon, sort_order, menu_type, perms)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (menu_name, parent_id, path, component, icon, sort_order, menu_type, perms),
            )
            menu_id = cursor.lastrowid
        seeded_menu_ids[seed_position] = menu_id

    units = [('个', '个'), ('件', '件'), ('台', '台'), ('套', '套'), ('米', 'm'), ('千克', 'kg'), ('升', 'L'), ('箱', '箱')]
    for u in units:
        db.execute("INSERT OR IGNORE INTO base_unit (unit_name, unit_symbol) VALUES (?,?)", u)

    # ==================== 标准成本 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS base_standard_cost (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        material_cost REAL DEFAULT 0,
        labor_cost REAL DEFAULT 0,
        overhead_cost REAL DEFAULT 0,
        total_cost REAL DEFAULT 0,
        effective_date TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    # ==================== FMEA ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_fmea (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fmea_no TEXT NOT NULL UNIQUE,
        product_id INTEGER,
        process_id INTEGER,
        failure_mode TEXT,
        failure_effect TEXT,
        failure_cause TEXT,
        severity INTEGER DEFAULT 1,
        occurrence INTEGER DEFAULT 1,
        detection INTEGER DEFAULT 1,
        rpn INTEGER DEFAULT 1,
        current_control TEXT,
        recommended_action TEXT,
        responsible TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 线边仓 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS inv_line_warehouse (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        workshop_id INTEGER,
        quantity REAL DEFAULT 0,
        min_quantity REAL DEFAULT 10,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id)
    )''')

    # ==================== 三级库位 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS inv_warehouse (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        warehouse_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        address TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS inv_area (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        warehouse_id INTEGER NOT NULL,
        area_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (warehouse_id) REFERENCES inv_warehouse(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS inv_location (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_id INTEGER NOT NULL,
        location_name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (area_id) REFERENCES inv_area(id)
    )''')

    # ==================== 库存事务 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS inv_transaction_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trans_type TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        warehouse_id INTEGER,
        area_id INTEGER,
        location_id INTEGER,
        batch_no TEXT,
        ref_no TEXT,
        ref_type TEXT,
        operator INTEGER,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 到货通知 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS inv_arrival_notice (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notice_no TEXT NOT NULL UNIQUE,
        supplier_id INTEGER,
        status INTEGER DEFAULT 0,
        expected_date TEXT,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS inv_arrival_notice_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notice_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        FOREIGN KEY (notice_id) REFERENCES inv_arrival_notice(id)
    )''')

    # ==================== 质检方案 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS qm_inspect_template (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL,
        inspect_type TEXT NOT NULL,
        items TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 设备点检项目 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS eqp_check_project (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT NOT NULL,
        check_type TEXT,
        standard TEXT,
        method TEXT,
        status INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ==================== 排班日历 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS sched_calendar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        work_date TEXT NOT NULL,
        shift_type TEXT,
        user_ids TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (plan_id) REFERENCES sched_plan(id)
    )''')

    # ==================== 工序流转卡 ====================
    db.execute('''CREATE TABLE IF NOT EXISTS prod_routing_card (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        product_id INTEGER,
        current_step INTEGER DEFAULT 1,
        total_steps INTEGER DEFAULT 1,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id)
    )''')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_routing_card_step (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id INTEGER NOT NULL,
        step_no INTEGER NOT NULL,
        process_name TEXT,
        station TEXT,
        operator INTEGER,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        result TEXT,
        FOREIGN KEY (card_id) REFERENCES prod_routing_card(id)
    )''')

    db.commit()
    db.close()


def _add_column_if_missing(db, table, column, definition):
    """Add a column without rebuilding a legacy SQLite table."""
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return
    columns = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
    if column not in columns:
        db.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')


def _init_extra_tables():
    """初始化新增功能的表"""
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript('''
        CREATE TABLE IF NOT EXISTS sys_document (
            id INTEGER PRIMARY KEY AUTOINCREMENT, doc_name TEXT NOT NULL,
            doc_type TEXT, category TEXT, file_path TEXT, file_size INTEGER,
            uploader INTEGER, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS prod_cost (
            id INTEGER PRIMARY KEY AUTOINCREMENT, workorder_id INTEGER,
            cost_type TEXT, amount REAL DEFAULT 0, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sys_backup (
            id INTEGER PRIMARY KEY AUTOINCREMENT, backup_name TEXT NOT NULL,
            file_path TEXT, file_size INTEGER, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS base_stage_code (
            id INTEGER PRIMARY KEY AUTOINCREMENT, stage_name TEXT NOT NULL,
            code TEXT UNIQUE, color TEXT, description TEXT,
            sort_order INTEGER DEFAULT 0, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS prod_stage_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT, stage_code TEXT,
            workorder_id INTEGER, product_id INTEGER, quantity REAL DEFAULT 0,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, end_time TIMESTAMP,
            duration REAL DEFAULT 0, operator INTEGER, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS util_energy (
            id INTEGER PRIMARY KEY AUTOINCREMENT, workshop_id INTEGER,
            energy_type TEXT, quantity REAL DEFAULT 0, unit TEXT,
            cost REAL DEFAULT 0, record_date TEXT, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS util_environment (
            id INTEGER PRIMARY KEY AUTOINCREMENT, workshop_id INTEGER,
            temperature REAL, humidity REAL, noise REAL, pm25 REAL,
            voc REAL, recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sys_5s_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, audit_no TEXT UNIQUE,
            workshop_id INTEGER, auditor INTEGER, audit_date TEXT,
            sort_score INTEGER DEFAULT 0, set_in_order_score INTEGER DEFAULT 0,
            shine_score INTEGER DEFAULT 0, standardize_score INTEGER DEFAULT 0,
            sustain_score INTEGER DEFAULT 0, total_score REAL DEFAULT 0,
            issues TEXT, corrective_action TEXT, status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS eqp_mold (
            id INTEGER PRIMARY KEY AUTOINCREMENT, mold_name TEXT, code TEXT UNIQUE,
            product_id INTEGER, specification TEXT, cavity_count INTEGER,
            usage_count INTEGER DEFAULT 0, max_usage INTEGER DEFAULT 0,
            location TEXT, status INTEGER DEFAULT 1, remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS eqp_fixture (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fixture_name TEXT,
            code TEXT UNIQUE, process_id INTEGER, specification TEXT,
            quantity INTEGER DEFAULT 0, location TEXT, status INTEGER DEFAULT 1,
            remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sys_barcode (id INTEGER PRIMARY KEY AUTOINCREMENT, barcode TEXT UNIQUE, biz_type TEXT, biz_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sys_announcement (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, announcement_type TEXT, publisher INTEGER, publish_time TEXT, expire_time TEXT, priority INTEGER DEFAULT 0, status INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS inv_batch (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_no TEXT UNIQUE, product_id INTEGER, supplier TEXT, quantity REAL DEFAULT 0, production_date TEXT, expiry_date TEXT, status INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS inv_trace (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER, trace_type TEXT, biz_no TEXT, operation TEXT, ref_no TEXT, ref_id INTEGER, quantity REAL DEFAULT 0, operator INTEGER, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS hr_training (id INTEGER PRIMARY KEY AUTOINCREMENT, training_name TEXT, training_type TEXT, trainer TEXT, start_date TEXT, end_date TEXT, location TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS hr_training_record (id INTEGER PRIMARY KEY AUTOINCREMENT, training_id INTEGER, user_id INTEGER, score REAL, result TEXT, certificate TEXT, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS hr_skill_matrix (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, process_id INTEGER, skill_level INTEGER DEFAULT 0, certified INTEGER DEFAULT 0, certified_at TEXT, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS spc_data (id INTEGER PRIMARY KEY AUTOINCREMENT, equipment_id INTEGER, process_id INTEGER, item_name TEXT, value REAL, unit TEXT, collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS base_station_config (id INTEGER PRIMARY KEY AUTOINCREMENT, station TEXT UNIQUE, station_name TEXT, process_id INTEGER, sequence_no INTEGER DEFAULT 0, allow_repeat INTEGER DEFAULT 0, previous_station TEXT, status INTEGER DEFAULT 1, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS base_material (id INTEGER PRIMARY KEY AUTOINCREMENT, material_no TEXT UNIQUE, material_name TEXT, specification TEXT, unit TEXT, status INTEGER DEFAULT 1, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS prod_material_lock (id INTEGER PRIMARY KEY AUTOINCREMENT, material_id INTEGER, reason TEXT, operator INTEGER, status INTEGER DEFAULT 1, unlock_time TEXT, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS prod_box (id INTEGER PRIMARY KEY AUTOINCREMENT, box_no TEXT UNIQUE, product_id INTEGER, workorder_id INTEGER, quantity REAL DEFAULT 0, status INTEGER DEFAULT 1, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS prod_outsource (id INTEGER PRIMARY KEY AUTOINCREMENT, outsource_no TEXT UNIQUE, supplier_id INTEGER, product_id INTEGER, quantity REAL DEFAULT 0, unit_price REAL DEFAULT 0, amount REAL DEFAULT 0, delivery_date TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS prod_labor_time (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, task_id INTEGER, workorder_id INTEGER, work_date TEXT, duration REAL DEFAULT 0, overtime REAL DEFAULT 0, quantity REAL DEFAULT 0, amount REAL DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS prod_packing (id INTEGER PRIMARY KEY AUTOINCREMENT, packing_no TEXT UNIQUE, workorder_id INTEGER, package_type TEXT, quantity REAL DEFAULT 0, operator INTEGER, packed_at TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS qm_defect_process (id INTEGER PRIMARY KEY AUTOINCREMENT, defect_no TEXT UNIQUE, workorder_id INTEGER, defect_id INTEGER, quantity REAL DEFAULT 0, disposition TEXT, responsible TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS qm_first_inspect (id INTEGER PRIMARY KEY AUTOINCREMENT, inspect_no TEXT UNIQUE, workorder_id INTEGER, process_id INTEGER, inspector INTEGER, result TEXT, inspect_date TEXT, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS qm_8d_report (id INTEGER PRIMARY KEY AUTOINCREMENT, report_no TEXT UNIQUE, title TEXT, customer TEXT, problem TEXT, root_cause TEXT, corrective_action TEXT, owner TEXT, due_date TEXT, status INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS qm_supplier_eval (id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_id INTEGER, eval_date TEXT, quality_score REAL DEFAULT 0, delivery_score REAL DEFAULT 0, service_score REAL DEFAULT 0, total_score REAL DEFAULT 0, grade TEXT, evaluator INTEGER, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS qm_capa (id INTEGER PRIMARY KEY AUTOINCREMENT, capa_no TEXT UNIQUE, source TEXT, issue TEXT, root_cause TEXT, corrective_action TEXT, preventive_action TEXT, owner TEXT, due_date TEXT, status INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS qm_control_plan (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_no TEXT UNIQUE, product_id INTEGER, process_id INTEGER, control_item TEXT, specification TEXT, method TEXT, frequency TEXT, reaction_plan TEXT, status INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS qm_eco (id INTEGER PRIMARY KEY AUTOINCREMENT, eco_no TEXT UNIQUE, title TEXT, change_reason TEXT, change_content TEXT, applicant INTEGER, effective_date TEXT, status INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS base_workstation (id INTEGER PRIMARY KEY AUTOINCREMENT, station_name TEXT, workstation_name TEXT, code TEXT UNIQUE, workshop_id INTEGER, process_id INTEGER, location TEXT, status INTEGER DEFAULT 1, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS prod_andon (id INTEGER PRIMARY KEY AUTOINCREMENT, andon_no TEXT UNIQUE, workstation_id INTEGER, andon_type TEXT, description TEXT, caller INTEGER, responder INTEGER, response_time TEXT, resolve_time TEXT, close_time TEXT, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS prod_rework (id INTEGER PRIMARY KEY AUTOINCREMENT, rework_no TEXT UNIQUE, workorder_id INTEGER, quantity REAL DEFAULT 0, reason TEXT, disposition TEXT, operator INTEGER, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS svc_complaint (id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_no TEXT UNIQUE, customer_id INTEGER, product_id INTEGER, complaint_type TEXT, severity TEXT DEFAULT 'medium', description TEXT, complaint_date TEXT, handler INTEGER, resolution TEXT, status INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS svc_return (id INTEGER PRIMARY KEY AUTOINCREMENT, return_no TEXT UNIQUE, complaint_id INTEGER, customer_id INTEGER, product_id INTEGER, quantity REAL DEFAULT 0, return_reason TEXT, return_date TEXT, handler INTEGER, status INTEGER DEFAULT 0, remark TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS flow_definition (id INTEGER PRIMARY KEY AUTOINCREMENT, flow_name TEXT NOT NULL, flow_key TEXT NOT NULL UNIQUE, description TEXT, steps TEXT, status INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS flow_instance (id INTEGER PRIMARY KEY AUTOINCREMENT, flow_id INTEGER NOT NULL, biz_type TEXT, biz_id INTEGER, title TEXT, current_step INTEGER DEFAULT 1, status INTEGER DEFAULT 0, creator INTEGER, steps_snapshot TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS flow_task (id INTEGER PRIMARY KEY AUTOINCREMENT, instance_id INTEGER NOT NULL, step_no INTEGER NOT NULL, assignee INTEGER NOT NULL, action TEXT, comment TEXT, status INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, completed_at TIMESTAMP);
    ''')
    _add_column_if_missing(db, 'sys_announcement', 'expire_time', 'TEXT')
    _add_column_if_missing(db, 'sys_announcement', 'priority', 'INTEGER DEFAULT 0')
    _add_column_if_missing(db, 'inv_batch', 'supplier', 'TEXT')
    _add_column_if_missing(db, 'inv_trace', 'ref_no', 'TEXT')
    _add_column_if_missing(db, 'inv_trace', 'ref_id', 'INTEGER')
    _add_column_if_missing(db, 'inv_trace', 'quantity', 'REAL DEFAULT 0')
    _add_column_if_missing(db, 'svc_complaint', 'severity', "TEXT DEFAULT 'medium'")
    _add_column_if_missing(db, 'svc_return', 'complaint_id', 'INTEGER')
    _add_column_if_missing(db, 'flow_instance', 'steps_snapshot', 'TEXT')
    _add_column_if_missing(db, 'prod_labor_time', 'duration', 'REAL DEFAULT 0')
    _add_column_if_missing(db, 'prod_labor_time', 'overtime', 'REAL DEFAULT 0')
    _add_column_if_missing(db, 'base_workstation', 'station_name', 'TEXT')
    _add_column_if_missing(db, 'prod_andon', 'resolve_time', 'TEXT')
    _add_column_if_missing(db, 'prod_andon', 'remark', 'TEXT')
    _add_column_if_missing(db, 'prod_andon', 'priority', 'INTEGER DEFAULT 1')
    _add_column_if_missing(db, 'prod_box', 'box_type', 'TEXT')
    _add_column_if_missing(db, 'prod_box', 'sn_list', 'TEXT')
    _add_column_if_missing(db, 'prod_material_lock', 'lock_no', 'TEXT')
    _add_column_if_missing(db, 'prod_material_lock', 'lock_type', 'TEXT')
    _add_column_if_missing(db, 'prod_material_lock', 'released_at', 'TEXT')
    _add_column_if_missing(db, 'sys_document', 'version', "TEXT DEFAULT '1.0'")
    from services.device_event_ingest import create_device_event_tables
    from services.aim_event_bridge import create_aim_event_outbox
    from services.gateway_auth import create_gateway_auth_tables
    create_device_event_tables(db)
    create_aim_event_outbox(db)
    create_gateway_auth_tables(db)
    _add_column_if_missing(db, 'base_process', 'sort_order', 'INTEGER DEFAULT 0')
    for col in ['required_sn', 'required_material', 'check_sequence', 'prev_station']:
        try:
            db.execute(f"ALTER TABLE base_station_config ADD COLUMN {col} INTEGER DEFAULT 0")
        except:
            pass
    try:
        db.execute("ALTER TABLE base_station_config ADD COLUMN required_process TEXT")
    except:
        pass
    _add_column_if_missing(db, 'prod_report', 'client_operation_id', 'TEXT')

    # 生产主数据版本与车间归属。旧记录允许为空，新业务由服务层强制校验。
    _add_column_if_missing(db, 'base_process_route', 'workshop_id', 'INTEGER')
    _add_column_if_missing(db, 'base_process_route', 'version', 'INTEGER DEFAULT 1')
    _add_column_if_missing(db, 'base_process_route_detail', 'workshop_id', 'INTEGER')
    _add_column_if_missing(
        db, 'base_process_route_detail', 'is_inspection_point', 'INTEGER DEFAULT 0'
    )
    _add_column_if_missing(db, 'prod_sales_order', 'customer_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_plan_item', 'sales_order_item_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_workorder', 'plan_item_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_workorder', 'production_batch_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_workorder', 'route_version', 'INTEGER')
    _add_column_if_missing(db, 'prod_workorder', 'bom_version', 'TEXT')
    _add_column_if_missing(db, 'prod_task', 'route_step_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_report', 'production_batch_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_report', 'approval_status', 'INTEGER DEFAULT 0')
    _add_column_if_missing(db, 'prod_report', 'defect_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_report', 'posted_at', 'TIMESTAMP')

    db.execute('''CREATE TABLE IF NOT EXISTS prod_batch (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_no TEXT NOT NULL,
        plan_id INTEGER,
        plan_item_id INTEGER NOT NULL,
        sales_order_id INTEGER,
        product_id INTEGER NOT NULL,
        workshop_id INTEGER NOT NULL,
        planned_qty REAL NOT NULL,
        completed_qty REAL DEFAULT 0,
        defect_qty REAL DEFAULT 0,
        start_date TEXT,
        end_date TEXT,
        status INTEGER DEFAULT 0,
        remark TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(plan_item_id, batch_no),
        FOREIGN KEY (plan_item_id) REFERENCES prod_plan_item(id),
        FOREIGN KEY (product_id) REFERENCES base_product(id),
        FOREIGN KEY (workshop_id) REFERENCES base_workshop(id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS prod_workorder_route_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workorder_id INTEGER NOT NULL UNIQUE,
        source_route_id INTEGER,
        route_name TEXT NOT NULL,
        route_version INTEGER DEFAULT 1,
        product_id INTEGER NOT NULL,
        workshop_id INTEGER NOT NULL,
        description TEXT,
        frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS prod_workorder_route_step (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        source_detail_id INTEGER,
        process_id INTEGER NOT NULL,
        process_code TEXT,
        process_name TEXT NOT NULL,
        workshop_id INTEGER NOT NULL,
        step_no INTEGER NOT NULL,
        standard_time REAL,
        is_inspection_point INTEGER DEFAULT 0,
        description TEXT,
        UNIQUE(snapshot_id, step_no),
        FOREIGN KEY (snapshot_id) REFERENCES prod_workorder_route_snapshot(id),
        FOREIGN KEY (process_id) REFERENCES base_process(id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS prod_workorder_bom_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workorder_id INTEGER NOT NULL,
        source_bom_id INTEGER,
        material_id INTEGER NOT NULL,
        material_code TEXT,
        material_name TEXT NOT NULL,
        quantity_per_unit REAL NOT NULL,
        required_qty REAL NOT NULL,
        unit TEXT,
        bom_version TEXT,
        frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(workorder_id, material_id),
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id),
        FOREIGN KEY (material_id) REFERENCES base_product(id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS sys_business_status_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        from_status INTEGER,
        to_status INTEGER NOT NULL,
        action TEXT,
        operator_id INTEGER,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS prod_material_req (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        req_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL DEFAULT 0,
        req_type TEXT DEFAULT '领料',
        status INTEGER DEFAULT 0,
        operator INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS prod_transfer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transfer_no TEXT NOT NULL UNIQUE,
        workorder_id INTEGER NOT NULL,
        from_process_id INTEGER NOT NULL,
        to_process_id INTEGER NOT NULL,
        from_route_step_id INTEGER,
        to_route_step_id INTEGER,
        quantity REAL NOT NULL,
        status INTEGER DEFAULT 1,
        operator INTEGER,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id)
    )''')
    _add_column_if_missing(db, 'prod_transfer', 'from_route_step_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_transfer', 'to_route_step_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_transfer', 'remark', 'TEXT')
    material_columns = {
        'production_batch_id': 'INTEGER',
        'bom_snapshot_id': 'INTEGER',
        'required_qty': 'REAL DEFAULT 0',
        'requested_qty': 'REAL DEFAULT 0',
        'issued_qty': 'REAL DEFAULT 0',
        'received_qty': 'REAL DEFAULT 0',
        'returned_qty': 'REAL DEFAULT 0',
        'warehouse_id': 'INTEGER',
        'location_id': 'INTEGER',
        'material_batch_no': 'TEXT',
        'remark': 'TEXT',
        'issued_by': 'INTEGER',
        'received_by': 'INTEGER',
        'issued_at': 'TIMESTAMP',
        'received_at': 'TIMESTAMP',
    }
    for column, definition in material_columns.items():
        _add_column_if_missing(db, 'prod_material_req', column, definition)
    db.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_report_user_operation
           ON prod_report(user_id, client_operation_id)
           WHERE client_operation_id IS NOT NULL"""
    )
    try:
        db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_task_instance_step
                      ON flow_task(instance_id, step_no)''')
    except sqlite3.IntegrityError:
        pass
    try:
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_active_business
                      ON flow_instance(biz_type, biz_id)
                      WHERE status=0 AND biz_type IS NOT NULL AND biz_type<>''""")
    except sqlite3.IntegrityError:
        pass
    db.execute('''CREATE TABLE IF NOT EXISTS sys_table_order (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_key TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        position INTEGER NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(table_key, record_id)
    )''')
    db.execute('''CREATE INDEX IF NOT EXISTS idx_sys_table_order_position
                  ON sys_table_order(table_key, position)''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_machine_endpoint (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id INTEGER NOT NULL,
        protocol_version INTEGER NOT NULL DEFAULT 1,
        transport_mode TEXT NOT NULL DEFAULT 'server',
        bind_ip TEXT NOT NULL,
        allowed_remote_ip TEXT,
        listen_port INTEGER NOT NULL,
        reader_ip TEXT,
        reader_port INTEGER,
        reader_frame_idle_ms INTEGER NOT NULL DEFAULT 80,
        station_code TEXT NOT NULL,
        process_id INTEGER NOT NULL,
        cavity_code TEXT NOT NULL DEFAULT '1',
        encoding TEXT NOT NULL DEFAULT 'utf-8',
        timeout_ms INTEGER NOT NULL DEFAULT 1000,
        heartbeat_seconds INTEGER NOT NULL DEFAULT 30,
        laser_template TEXT,
        inspection_template TEXT,
        shared_secret TEXT,
        csv_input_dir TEXT,
        csv_stable_seconds INTEGER NOT NULL DEFAULT 2,
        enabled INTEGER NOT NULL DEFAULT 1,
        last_seen_at TIMESTAMP,
        last_error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (equipment_id) REFERENCES eqp_ledger(id),
        FOREIGN KEY (process_id) REFERENCES base_process(id)
    )''')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'allowed_remote_ip', 'TEXT')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'transport_mode', "TEXT NOT NULL DEFAULT 'server'")
    _add_column_if_missing(db, 'iot_machine_endpoint', 'reader_ip', 'TEXT')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'reader_port', 'INTEGER')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'reader_frame_idle_ms', 'INTEGER NOT NULL DEFAULT 80')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'csv_input_dir', 'TEXT')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'csv_stable_seconds', 'INTEGER NOT NULL DEFAULT 2')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'listener_status', "TEXT NOT NULL DEFAULT 'stopped'")
    _add_column_if_missing(db, 'iot_machine_endpoint', 'listener_pid', 'INTEGER')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'listener_started_at', 'TIMESTAMP')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'csv_last_scan_at', 'TIMESTAMP')
    _add_column_if_missing(db, 'iot_machine_endpoint', 'csv_last_error', 'TEXT')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_machine_runtime (
        component TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        pid INTEGER,
        started_at TIMESTAMP,
        heartbeat_at TIMESTAMP,
        last_error TEXT
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS prod_serial (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_no TEXT NOT NULL UNIQUE,
        product_id INTEGER NOT NULL,
        workorder_id INTEGER,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES base_product(id),
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS prod_station_flow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flow_no TEXT NOT NULL UNIQUE,
        sn TEXT,
        product_id INTEGER,
        workorder_id INTEGER,
        current_station TEXT,
        current_process TEXT,
        status INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS prod_station_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flow_id INTEGER NOT NULL,
        sn TEXT,
        station TEXT NOT NULL,
        process_name TEXT,
        action TEXT NOT NULL,
        operator INTEGER,
        result TEXT,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (flow_id) REFERENCES prod_station_flow(id)
    )''')
    _add_column_if_missing(db, 'prod_station_record', 'route_step_id', 'INTEGER')
    _add_column_if_missing(db, 'prod_station_record', 'machine_request_id', 'INTEGER')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_machine_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint_id INTEGER NOT NULL,
        remote_address TEXT,
        connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_heartbeat_at TIMESTAMP,
        disconnected_at TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'online',
        request_count INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        FOREIGN KEY (endpoint_id) REFERENCES iot_machine_endpoint(id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_machine_request (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint_id INTEGER NOT NULL,
        session_id INTEGER,
        request_no TEXT NOT NULL,
        protocol_version INTEGER NOT NULL,
        station_code TEXT NOT NULL,
        cavity_code TEXT NOT NULL,
        sn TEXT NOT NULL,
        workorder_id INTEGER,
        task_id INTEGER,
        route_step_id INTEGER,
        decision TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        reason_message TEXT,
        laser_template TEXT,
        inspection_template TEXT,
        elapsed_ms INTEGER NOT NULL DEFAULT 0,
        dedupe_key TEXT NOT NULL,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        report_status TEXT NOT NULL DEFAULT 'pending',
        FOREIGN KEY (endpoint_id) REFERENCES iot_machine_endpoint(id),
        FOREIGN KEY (session_id) REFERENCES iot_machine_session(id),
        FOREIGN KEY (workorder_id) REFERENCES prod_workorder(id),
        FOREIGN KEY (task_id) REFERENCES prod_task(id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_inspection_report (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        endpoint_id INTEGER NOT NULL,
        sn TEXT NOT NULL,
        inspected_at TIMESTAMP NOT NULL,
        result TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        archive_path TEXT,
        file_hash TEXT NOT NULL,
        import_status TEXT NOT NULL DEFAULT 'imported',
        failure_reason TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        prod_report_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (request_id) REFERENCES iot_machine_request(id),
        FOREIGN KEY (endpoint_id) REFERENCES iot_machine_endpoint(id),
        FOREIGN KEY (prod_report_id) REFERENCES prod_report(id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_inspection_value (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        item_code TEXT NOT NULL,
        item_name TEXT,
        measured_value TEXT,
        unit TEXT,
        lower_limit REAL,
        upper_limit REAL,
        result TEXT,
        FOREIGN KEY (report_id) REFERENCES iot_inspection_report(id)
    )''')
    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_prod_batch_plan_item ON prod_batch(plan_item_id)',
        'CREATE INDEX IF NOT EXISTS idx_prod_batch_product ON prod_batch(product_id)',
        'CREATE INDEX IF NOT EXISTS idx_prod_route_step_snapshot ON prod_workorder_route_step(snapshot_id)',
        'CREATE INDEX IF NOT EXISTS idx_prod_route_step_process ON prod_workorder_route_step(process_id)',
        'CREATE INDEX IF NOT EXISTS idx_prod_bom_snapshot_workorder ON prod_workorder_bom_snapshot(workorder_id)',
        'CREATE INDEX IF NOT EXISTS idx_prod_material_workorder ON prod_material_req(workorder_id)',
        'CREATE INDEX IF NOT EXISTS idx_prod_material_snapshot ON prod_material_req(bom_snapshot_id)',
        'CREATE INDEX IF NOT EXISTS idx_business_status_entity ON sys_business_status_log(entity_type, entity_id)',
        'CREATE INDEX IF NOT EXISTS idx_route_detail_route ON base_process_route_detail(route_id)',
        'CREATE INDEX IF NOT EXISTS idx_sales_item_order ON prod_sales_order_item(order_id)',
        'CREATE INDEX IF NOT EXISTS idx_plan_item_plan ON prod_plan_item(plan_id)',
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_iot_machine_endpoint_binding ON iot_machine_endpoint(bind_ip,listen_port,station_code,cavity_code)',
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_iot_machine_request_dedupe ON iot_machine_request(dedupe_key)',
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_iot_machine_pending_step
           ON iot_machine_request(endpoint_id,sn,route_step_id)
           WHERE decision='L1' AND report_status='pending'""",
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_iot_inspection_report_hash ON iot_inspection_report(endpoint_id,file_hash)',
        'CREATE INDEX IF NOT EXISTS idx_iot_machine_request_sn ON iot_machine_request(sn,requested_at)',
        'CREATE INDEX IF NOT EXISTS idx_iot_machine_session_endpoint ON iot_machine_session(endpoint_id,status)',
        'CREATE INDEX IF NOT EXISTS idx_iot_inspection_value_report ON iot_inspection_value(report_id)',
    ]
    for sql in indexes:
        try:
            db.execute(sql)
        except sqlite3.OperationalError:
            pass
    from services.quality_disposition import create_quality_disposition_tables
    create_quality_disposition_tables(db)
    db.commit()
    db.close()


def _create_indexes():
    """创建数据库索引优化查询性能"""
    db = sqlite3.connect(DB_PATH)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_prod_workorder_status ON prod_workorder(status)",
        "CREATE INDEX IF NOT EXISTS idx_prod_task_workorder ON prod_task(workorder_id)",
        "CREATE INDEX IF NOT EXISTS idx_prod_task_status ON prod_task(status)",
        "CREATE INDEX IF NOT EXISTS idx_prod_report_task ON prod_report(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_prod_report_time ON prod_report(report_time)",
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_report_user_operation
           ON prod_report(user_id, client_operation_id)
           WHERE client_operation_id IS NOT NULL""",
        "CREATE INDEX IF NOT EXISTS idx_inv_balance_product ON inv_balance(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_sys_log_time ON sys_log(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_prod_station_flow_sn ON prod_station_flow(sn)",
        "CREATE INDEX IF NOT EXISTS idx_prod_station_record_sn ON prod_station_record(sn)",
        "CREATE INDEX IF NOT EXISTS idx_sys_notification_user ON sys_notification(user_id, is_read)",
    ]
    for sql in indexes:
        try:
            db.execute(sql)
        except:
            pass
    db.commit()
    db.close()
