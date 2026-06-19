"""生产看板蓝图 - TV模式"""
import datetime
from flask import Blueprint, request, jsonify, render_template_string
from utils.database import get_db, BASE_DIR
from utils.helpers import login_required

kanban_bp = Blueprint('kanban', __name__)


@kanban_bp.route('/api/kanban/realtime')
@login_required
def kanban_realtime():
    """实时生产看板数据"""
    db = get_db()
    
    # 进行中的工单
    active_orders = db.execute('''SELECT w.order_no, p.product_name, w.planned_qty, w.completed_qty,
        w.status, ws.workshop_name, w.priority
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        WHERE w.status IN (0,1)
        ORDER BY w.priority DESC, w.id ASC LIMIT 10''').fetchall()
    
    # 今日统计
    today = datetime.date.today().strftime('%Y-%m-%d')
    today_report = db.execute('''SELECT COALESCE(SUM(qualified_qty),0) as qualified,
        COALESCE(SUM(defect_qty),0) as defect
        FROM prod_report WHERE DATE(report_time)=?''', (today,)).fetchone()
    
    # 设备状态
    eqp_stats = []
    for st, label in [(1,'运行'),(2,'维修'),(0,'停用')]:
        cnt = db.execute("SELECT COUNT(*) as c FROM eqp_ledger WHERE status=?", (st,)).fetchone()['c']
        eqp_stats.append({'name': label, 'value': cnt})
    
    # 各车间今日产出
    workshop_output = db.execute('''SELECT ws.workshop_name, COALESCE(SUM(r.qualified_qty),0) as qty
        FROM base_workshop ws
        LEFT JOIN base_process p ON ws.id=p.workshop_id
        LEFT JOIN prod_report r ON p.id=r.process_id AND DATE(r.report_time)=?
        GROUP BY ws.id ORDER BY qty DESC''', (today,)).fetchall()
    
    return jsonify({'code': 0, 'data': {
        'active_orders': [dict(r) for r in active_orders],
        'today_qualified': today_report['qualified'],
        'today_defect': today_report['defect'],
        'eqp_stats': eqp_stats,
        'workshop_output': [dict(r) for r in workshop_output]
    }})


KANBAN_HTML = '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>生产看板</title>
<meta http-equiv="refresh" content="30">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Microsoft YaHei",sans-serif;background:#0a1628;color:#fff;height:100vh;overflow:hidden}
.header{height:60px;background:linear-gradient(90deg,#1a3a5c,#0d2137);display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:bold;letter-spacing:4px;border-bottom:2px solid #1890ff}
.grid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:16px;padding:16px;height:calc(100vh - 60px)}
.panel{background:rgba(24,144,255,0.08);border:1px solid rgba(24,144,255,0.3);border-radius:8px;padding:16px;overflow:hidden}
.panel-title{font-size:16px;color:#1890ff;margin-bottom:12px;border-bottom:1px solid rgba(24,144,255,0.3);padding-bottom:8px}
.stats-row{display:flex;gap:20px;margin-bottom:16px}
.stat-box{flex:1;text-align:center;background:rgba(24,144,255,0.1);border-radius:8px;padding:16px}
.stat-val{font-size:36px;font-weight:bold;color:#1890ff}
.stat-label{color:#8cc8ff;font-size:13px;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:rgba(24,144,255,0.2);padding:8px;text-align:left;color:#8cc8ff}
td{padding:8px;border-bottom:1px solid rgba(255,255,255,0.1)}
.tag{padding:2px 8px;border-radius:4px;font-size:11px}
.tag-run{background:#fa8c16;color:#fff}
.tag-done{background:#52c41a;color:#fff}
.tag-wait{background:#1890ff;color:#fff}
</style>
</head><body>
<div class="header">MES 生产看板</div>
<div class="grid">
<div class="panel">
<div class="panel-title">进行中工单</div>
<table><thead><tr><th>工单号</th><th>产品</th><th>计划</th><th>完成</th><th>车间</th><th>状态</th></tr></thead>
<tbody id="orderList"></tbody></table>
</div>
<div class="panel">
<div class="panel-title">今日产出统计</div>
<div class="stats-row">
<div class="stat-box"><div class="stat-val" id="qualified">0</div><div class="stat-label">合格数</div></div>
<div class="stat-box"><div class="stat-val" id="defect" style="color:#f5222d">0</div><div class="stat-label">不良数</div></div>
<div class="stat-box"><div class="stat-val" id="rate">0%</div><div class="stat-label">合格率</div></div>
</div>
<div id="chartOutput" style="height:200px"></div>
</div>
<div class="panel">
<div class="panel-title">设备状态</div>
<div id="chartEqp" style="height:100%"></div>
</div>
<div class="panel">
<div class="panel-title">各车间产出</div>
<div id="chartWS" style="height:100%"></div>
</div>
</div>
<script>
function loadData(){
fetch('/api/kanban/realtime').then(r=>r.json()).then(r=>{
if(r.code!==0)return;
var d=r.data;
var ol=document.getElementById('orderList');
ol.innerHTML=d.active_orders.map(o=>'<tr><td>'+o.order_no+'</td><td>'+o.product_name+'</td><td>'+o.planned_qty+'</td><td>'+o.completed_qty+'</td><td>'+(o.workshop_name||'-')+'</td><td><span class="tag '+(o.status?'tag-run':'tag-wait')+'">'+(o.status?'进行中':'待开始')+'</span></td></tr>').join('');
document.getElementById('qualified').textContent=d.today_qualified;
document.getElementById('defect').textContent=d.today_defect;
var total=d.today_qualified+d.today_defect;
document.getElementById('rate').textContent=total?Math.round(d.today_qualified/total*100)+'%':'0%';
var c1=echarts.init(document.getElementById('chartOutput'));
c1.setOption({tooltip:{trigger:'item'},series:[{type:'pie',radius:['40%','70%'],data:[{name:'合格',value:d.today_qualified,itemStyle:{color:'#52c41a'}},{name:'不良',value:d.today_defect,itemStyle:{color:'#f5222d'}}],label:{formatter:'{b}: {c}',color:'#fff'}}]});
var c2=echarts.init(document.getElementById('chartEqp'));
c2.setOption({tooltip:{trigger:'item'},series:[{type:'pie',radius:['40%','70%'],data:d.eqp_stats,label:{formatter:'{b}: {c}',color:'#fff'}}]});
var c3=echarts.init(document.getElementById('chartWS'));
c3.setOption({tooltip:{trigger:'axis'},xAxis:{type:'category',data:d.workshop_output.map(i=>i.workshop_name),axisLabel:{color:'#8cc8ff'}},yAxis:{type:'value',axisLabel:{color:'#8cc8ff'}},series:[{type:'bar',data:d.workshop_output.map(i=>i.qty),itemStyle:{color:'#1890ff'}}]});
});
}
loadData();
setInterval(loadData,30000);

// 全屏切换
document.addEventListener('keydown', function(e) {
    if(e.key === 'F11') {
        e.preventDefault();
        if(!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }
});

// 看板轮播
var carouselTimer = null;
var carouselPages = ['kanban', 'kanban/stats'];
var carouselIdx = 0;
var carouselInterval = 30000; // 30秒

function startCarousel() {
    if(carouselTimer) clearInterval(carouselTimer);
    carouselTimer = setInterval(function() {
        carouselIdx = (carouselIdx + 1) % carouselPages.length;
        // 重新加载数据实现轮播效果
        loadData();
    }, carouselInterval);
}

function stopCarousel() {
    if(carouselTimer) {
        clearInterval(carouselTimer);
        carouselTimer = null;
    }
}

// 自动启动轮播
startCarousel();
</script></body></html>'''


@kanban_bp.route('/kanban')
def kanban_page():
    return KANBAN_HTML
