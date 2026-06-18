"""PDF 报表生成器"""
import os
from datetime import datetime


def generate_production_report_html(data):
    """生成生产报表 HTML"""
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>生产报表</title>
<style>
body {{ font-family: 'Microsoft YaHei', sans-serif; padding: 40px; }}
h1 {{ text-align: center; color: #1890ff; }}
.info {{ text-align: center; color: #999; margin-bottom: 30px; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
th, td {{ border: 1px solid #ddd; padding: 12px; text-align: center; }}
th {{ background: #1890ff; color: white; }}
tr:nth-child(even) {{ background: #f5f5f5; }}
.stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 30px 0; }}
.stat-item {{ background: #f0f5ff; border-radius: 8px; padding: 20px; text-align: center; }}
.stat-value {{ font-size: 28px; font-weight: bold; color: #1890ff; }}
.stat-label {{ color: #666; margin-top: 8px; }}
</style>
</head>
<body>
<h1>MES工厂管家 - 生产报表</h1>
<p class="info">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<div class="stat-grid">
    <div class="stat-item">
        <div class="stat-value">{data.get('total_orders', 0)}</div>
        <div class="stat-label">工单总数</div>
    </div>
    <div class="stat-item">
        <div class="stat-value">{data.get('completed', 0)}</div>
        <div class="stat-label">已完成</div>
    </div>
    <div class="stat-item">
        <div class="stat-value">{data.get('in_progress', 0)}</div>
        <div class="stat-label">进行中</div>
    </div>
    <div class="stat-item">
        <div class="stat-value">{data.get('defect_rate', 0)}%</div>
        <div class="stat-label">不良率</div>
    </div>
</div>

<h2>各车间产量统计</h2>
<table>
<tr><th>车间</th><th>产量</th></tr>
"""
    for ws in data.get('workshop_stats', []):
        html += f"<tr><td>{ws.get('workshop_name', '-')}</td><td>{ws.get('qty', 0)}</td></tr>\n"

    html += """</table>
</body>
</html>"""
    return html


def save_report_html(html_content, filename):
    """保存报表为 HTML 文件"""
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    filepath = os.path.join(reports_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return filepath
