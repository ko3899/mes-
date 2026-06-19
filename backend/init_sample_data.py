"""示例数据初始化"""
import sqlite3
import os
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'database', 'mes.db')


def init_sample_data():
    """初始化示例数据"""
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    
    # 检查是否已有数据
    count = db.execute("SELECT COUNT(*) as c FROM base_product").fetchone()[0]
    if count > 0:
        print("已有数据，跳过初始化")
        db.close()
        return
    
    print("正在初始化示例数据...")
    
    # 车间
    workshops = [('注塑车间', 'WS01'), ('SMT车间', 'WS02'), ('组装车间', 'WS03'), ('包装车间', 'WS04')]
    for name, code in workshops:
        db.execute("INSERT OR IGNORE INTO base_workshop (workshop_name, code) VALUES (?,?)", (name, code))
    
    # 工序
    processes = [
        ('注塑成型', 'P001', 1, 5.0), ('SMT贴片', 'P002', 2, 2.0),
        ('回流焊', 'P003', 2, 3.0), ('DIP插件', 'P004', 2, 4.0),
        ('组装', 'P005', 3, 8.0), ('质检', 'P006', 3, 3.0),
        ('包装', 'P007', 4, 2.0)
    ]
    for i, (name, code, ws, time) in enumerate(processes):
        db.execute("INSERT OR IGNORE INTO base_process (process_name, code, workshop_id, standard_time, sort_order) VALUES (?,?,?,?,?)",
                   (name, code, ws, time, i+1))
    
    # 产品
    products = [
        ('智能手表', 'PROD001', '标准版', '个', '成品'),
        ('手机壳', 'PROD002', '透明款', '个', '成品'),
        ('充电器', 'PROD003', '65W快充', '个', '成品'),
        ('数据线', 'PROD004', 'Type-C 1m', '条', '成品'),
        ('PCB主板', 'PROD005', 'V2.0', '块', '半成品'),
        ('塑料外壳', 'PROD006', 'ABS材质', '个', '原材料'),
    ]
    for name, code, spec, unit, ptype in products:
        db.execute("INSERT OR IGNORE INTO base_product (product_name, code, specification, unit, product_type) VALUES (?,?,?,?,?)",
                   (name, code, spec, unit, ptype))
    
    # 工位
    stations = [
        ('SMT01', 'SMT贴片区', 2), ('SMT02', '回流焊区', 2),
        ('DIP01', 'DIP插件区', 2), ('ASM01', '组装区', 3),
        ('QC01', '质检站', 3), ('PKG01', '包装区', 4)
    ]
    for code, name, ws in stations:
        db.execute("INSERT OR IGNORE INTO base_workstation (station_name, code, workshop_id) VALUES (?,?,?)",
                   (name, code, ws))
    
    # 设备
    equipments = [
        ('贴片机01', 'EQP001', 'SMT', 'Yamaha', 2),
        ('回流焊01', 'EQP002', '焊接', 'Heller', 2),
        ('注塑机01', 'EQP003', '注塑', '海天', 1),
        ('组装台01', 'EQP004', '组装', '自制', 3),
    ]
    for name, code, etype, mfr, ws in equipments:
        db.execute("INSERT OR IGNORE INTO eqp_ledger (equipment_name, code, model, manufacturer, workshop_id) VALUES (?,?,?,?,?)",
                   (name, code, etype, mfr, ws))
    
    # 工具
    tools = [
        ('电批01', 'TL001', '电动工具', '10N.m', 5),
        ('万用表01', 'TL002', '测量工具', 'Fluke', 3),
    ]
    for name, code, ttype, spec, qty in tools:
        db.execute("INSERT OR IGNORE INTO tool_ledger (tool_name, code, type_id, specification, quantity) VALUES (?,?,?,?,?)",
                   (name, code, 1, spec, qty))
    
    # 站点配置（防呆）
    station_configs = [
        ('SMT01', 'SMT贴片区', 0, 1, 1, 0, '', 0, ''),
        ('SMT02', '回流焊区', 0, 1, 1, 0, '', 1, 'SMT01'),
        ('DIP01', 'DIP插件区', 0, 1, 1, 0, '', 1, 'SMT02'),
        ('ASM01', '组装区', 0, 1, 1, 0, '', 1, 'DIP01'),
        ('QC01', '质检站', 0, 1, 1, 0, '', 1, 'ASM01'),
        ('PKG01', '包装区', 0, 1, 1, 0, '', 1, 'QC01'),
    ]
    for station, name, repeat, max_pass, req_sn, req_mat, req_proc, seq, prev in station_configs:
        db.execute("INSERT OR IGNORE INTO base_station_config (station, station_name, allow_repeat, max_pass_count, required_sn, required_material, required_process, check_sequence, prev_station) VALUES (?,?,?,?,?,?,?,?,?)",
                   (station, name, repeat, max_pass, req_sn, req_mat, req_proc, seq, prev))
    
    # 不良品项
    defects = [
        ('外观划伤', 'DEF001', '外观'), ('尺寸超差', 'DEF002', '尺寸'),
        ('功能异常', 'DEF003', '功能'), ('焊接不良', 'DEF004', '外观'),
        ('漏贴元件', 'DEF005', '功能'),
    ]
    for name, code, dtype in defects:
        db.execute("INSERT OR IGNORE INTO base_defect (defect_name, code, defect_type) VALUES (?,?,?)",
                   (name, code, dtype))
    
    # 阶段码
    stages = [
        ('切割', 'CUT', '#1890ff', '材料切割'), ('焊接', 'WELD', '#fa8c16', '焊接工序'),
        ('组装', 'ASM', '#52c41a', '产品组装'), ('测试', 'TEST', '#722ed1', '功能测试'),
        ('包装', 'PACK', '#13c2c2', '成品包装'),
    ]
    for i, (name, code, color, desc) in enumerate(stages):
        db.execute("INSERT OR IGNORE INTO base_stage_code (stage_name, code, color, description, sort_order) VALUES (?,?,?,?,?)",
                   (name, code, color, desc, i+1))
    
    # 系统配置
    configs = [
        ('company_name', 'MES工厂管家', 'string', '公司名称'),
        ('version', '1.0.0', 'string', '系统版本'),
        ('default_password', '123456', 'string', '默认密码'),
    ]
    for key, val, ctype, desc in configs:
        db.execute("INSERT OR IGNORE INTO sys_config (config_key, config_value, config_type, description) VALUES (?,?,?,?)",
                   (key, val, ctype, desc))
    
    db.commit()
    db.close()
    print("示例数据初始化完成!")


if __name__ == '__main__':
    init_sample_data()
