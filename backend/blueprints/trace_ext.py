"""5M1E追溯和碳排放蓝图"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required

trace_ext_bp = Blueprint('trace_ext', __name__)


# ==================== 5M1E追溯 ====================
@trace_ext_bp.route('/api/trace/5m1e/<sn>')
@login_required
def trace_5m1e(sn):
    """5M1E全关联追溯"""
    db = get_db()
    
    # 人(Man) - 操作人员
    operators = db.execute('''SELECT DISTINCT u.real_name, r.station, r.created_at
        FROM prod_station_record r
        LEFT JOIN sys_user u ON r.operator=u.id
        WHERE r.sn=?''', (sn,)).fetchall()
    
    # 机(Machine) - 使用设备
    equipment = db.execute('''SELECT DISTINCT e.equipment_name, e.code
        FROM prod_station_record r
        LEFT JOIN eqp_ledger e ON r.station=e.code
        WHERE r.sn=?''', (sn,)).fetchall()
    
    # 料(Material) - 使用物料
    materials = db.execute('''SELECT DISTINCT m.material_name, m.material_no
        FROM prod_station_record r
        LEFT JOIN base_material m ON r.remark LIKE '%'||m.material_no||'%'
        WHERE r.sn=?''', (sn,)).fetchall()
    
    # 法(Method) - 工序方法
    methods = db.execute('''SELECT DISTINCT r.process_name, r.station
        FROM prod_station_record r
        WHERE r.sn=?''', (sn,)).fetchall()
    
    # 环(Environment) - 环境数据
    environment = db.execute('''SELECT DISTINCT env.temperature, env.humidity, ws.workshop_name
        FROM prod_station_record r
        LEFT JOIN base_workshop ws ON r.station=ws.code
        LEFT JOIN util_environment env ON ws.id=env.workshop_id
        WHERE r.sn=?''', (sn,)).fetchall()
    
    return jsonify({'code': 0, 'data': {
        'sn': sn,
        'man': [dict(r) for r in operators],
        'machine': [dict(r) for r in equipment],
        'material': [dict(r) for r in materials],
        'method': [dict(r) for r in methods],
        'environment': [dict(r) for r in environment]
    }})


# ==================== 碳排放 ====================
@trace_ext_bp.route('/api/carbon/emission')
@login_required
def carbon_emission():
    """碳排放核算"""
    db = get_db()
    
    # 电能碳排放 (kWh * 0.5703 kgCO2/kWh)
    electricity = db.execute('''SELECT COALESCE(SUM(quantity),0) as total
        FROM util_energy WHERE energy_type='电' ''').fetchone()['total']
    elec_carbon = electricity * 0.5703
    
    # 天然气碳排放
    gas = db.execute('''SELECT COALESCE(SUM(quantity),0) as total
        FROM util_energy WHERE energy_type='气' ''').fetchone()['total']
    gas_carbon = gas * 2.162
    
    total_carbon = elec_carbon + gas_carbon
    
    return jsonify({'code': 0, 'data': {
        'electricity_kwh': electricity,
        'electricity_carbon_kg': round(elec_carbon, 2),
        'gas_m3': gas,
        'gas_carbon_kg': round(gas_carbon, 2),
        'total_carbon_kg': round(total_carbon, 2),
        'total_carbon_ton': round(total_carbon / 1000, 4)
    }})
