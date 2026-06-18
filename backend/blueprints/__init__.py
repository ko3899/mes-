"""MES工厂管家 - 蓝图模块"""
from .auth import auth_bp
from .system import system_bp
from .base_data import base_data_bp
from .inventory import inventory_bp
from .production import production_bp
from .quality import quality_bp
from .equipment import equipment_bp
from .tool import tool_bp
from .schedule import schedule_bp
from .flow import flow_bp
from .dashboard import dashboard_bp
from .report import report_bp

__all__ = [
    'auth_bp', 'system_bp', 'base_data_bp', 'inventory_bp',
    'production_bp', 'quality_bp', 'equipment_bp', 'tool_bp',
    'schedule_bp', 'flow_bp', 'dashboard_bp', 'report_bp'
]
