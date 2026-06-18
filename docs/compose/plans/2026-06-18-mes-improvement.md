# MES工厂管家 全面完善计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task.

**Goal:** 全面完善 MES 工厂管家系统，包括 UI 优化、代码重构、新功能、采集终端增强

**Architecture:** 将单体应用拆分为模块化结构，后端使用 Flask Blueprint，前端使用模块化 JS

**Tech Stack:** Flask, SQLite, HTML/CSS/JavaScript, ECharts

---

## 阶段 1：UI 优化 + 代码重构

### Task 1: 后端重构 - 拆分 app.py 为 Blueprint

**Files:**
- Create: `backend/blueprints/__init__.py`
- Create: `backend/blueprints/auth.py`
- Create: `backend/blueprints/system.py`
- Create: `backend/blueprints/base_data.py`
- Create: `backend/blueprints/inventory.py`
- Create: `backend/blueprints/production.py`
- Create: `backend/blueprints/quality.py`
- Create: `backend/blueprints/equipment.py`
- Create: `backend/blueprints/tool.py`
- Create: `backend/blueprints/schedule.py`
- Create: `backend/blueprints/flow.py`
- Create: `backend/blueprints/dashboard.py`
- Create: `backend/blueprints/report.py`
- Create: `backend/utils/__init__.py`
- Create: `backend/utils/database.py`
- Create: `backend/utils/helpers.py`
- Modify: `backend/app.py` (简化为主入口)

- [ ] **Step 1: 创建 utils 模块**

```python
# backend/utils/__init__.py
from .database import get_db, close_db, init_db
from .helpers import gen_no, login_required, crud_list, crud_add, crud_update, crud_delete
```

```python
# backend/utils/database.py
import sqlite3
import os
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
    # 从原 app.py 复制 init_db 函数内容
    pass
```

```python
# backend/utils/helpers.py
import datetime
from functools import wraps
from flask import session, jsonify, request
from .database import get_db

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'code': 401, 'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated

def gen_no(prefix):
    db = get_db()
    row = db.execute("SELECT * FROM sys_numbering WHERE entity_type=?", (prefix,)).fetchone()
    if not row:
        db.execute("INSERT INTO sys_numbering (prefix, entity_type, current_no, digit_count) VALUES (?,?,1,6)", (prefix, prefix))
        db.commit()
        no = 1
        digits = 6
    else:
        no = row['current_no'] + 1
        db.execute("UPDATE sys_numbering SET current_no=? WHERE entity_type=?", (no, prefix))
        db.commit()
        digits = row['digit_count']
    today = datetime.datetime.now().strftime('%Y%m%d')
    return f"{prefix}{today}{str(no).zfill(digits)}"

def crud_list(table, params):
    db = get_db()
    page = int(params.get('page', 1))
    size = int(params.get('size', 20))
    offset = (page - 1) * size
    where = " WHERE 1=1"
    args = []
    keyword = params.get('keyword', '')
    for key, val in params.items():
        if key in ('page', 'size', 'sort', 'order', 'keyword'):
            continue
        if val is not None and val != '':
            where += f" AND {key}=?"
            args.append(val)
    if keyword:
        try:
            cols_info = db.execute(f"PRAGMA table_info({table})").fetchall()
            text_cols = [c[1] for c in cols_info if c[2] == 'TEXT']
            if text_cols:
                like_parts = [f"{col} LIKE ?" for col in text_cols[:5]]
                where += f" AND ({' OR '.join(like_parts)})"
                like_val = f"%{keyword}%"
                args.extend([like_val] * len(like_parts))
        except:
            pass
    total = db.execute(f"SELECT COUNT(*) as cnt FROM {table}{where}", args).fetchone()['cnt']
    sort = params.get('sort', 'id')
    order = params.get('order', 'DESC')
    if sort not in ('id', 'created_at', 'updated_at', 'sort_order'):
        sort = 'id'
    if order not in ('ASC', 'DESC'):
        order = 'DESC'
    rows = db.execute(f"SELECT * FROM {table}{where} ORDER BY {sort} {order} LIMIT ? OFFSET ?",
                      args + [size, offset]).fetchall()
    return {'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total, 'page': page, 'size': size}}

def crud_add(table, data):
    db = get_db()
    keys = [k for k in data.keys() if k != 'id']
    vals = [data[k] for k in keys]
    placeholders = ','.join(['?'] * len(keys))
    columns = ','.join(keys)
    cursor = db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", vals)
    db.commit()
    return {'code': 0, 'data': {'id': cursor.lastrowid}, 'message': '添加成功'}

def crud_update(table, data):
    db = get_db()
    id = data.get('id')
    if not id:
        return {'code': 400, 'message': '缺少id'}
    keys = [k for k in data.keys() if k != 'id']
    vals = [data[k] for k in keys]
    sets = ','.join([f"{k}=?" for k in keys])
    db.execute(f"UPDATE {table} SET {sets} WHERE id=?", vals + [id])
    db.commit()
    return {'code': 0, 'message': '修改成功'}

def crud_delete(table, id):
    db = get_db()
    db.execute(f"DELETE FROM {table} WHERE id=?", (id,))
    db.commit()
    return {'code': 0, 'message': '删除成功'}
```

- [ ] **Step 2: 创建 auth blueprint**

```python
# backend/blueprints/auth.py
from flask import Blueprint, request, jsonify, session
import hashlib
from ..utils.database import get_db
from ..utils.helpers import login_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    pwd_hash = hashlib.md5(password.encode()).hexdigest()
    db = get_db()
    user = db.execute("SELECT * FROM sys_user WHERE username=? AND password=?", (username, pwd_hash)).fetchone()
    if not user:
        return jsonify({'code': 400, 'message': '用户名或密码错误'})
    session['user_id'] = user['id']
    session['username'] = user['username']
    return jsonify({
        'code': 0,
        'data': {
            'id': user['id'],
            'username': user['username'],
            'real_name': user['real_name'],
            'phone': user['phone'],
            'avatar': user['avatar']
        }
    })

@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'code': 0, 'message': '已退出'})

@auth_bp.route('/api/user/info')
@login_required
def user_info():
    from flask import session as sess
    db = get_db()
    user = db.execute("SELECT id, username, real_name, phone, email, dept_id, role_id, avatar FROM sys_user WHERE id=?",
                      (sess['user_id'],)).fetchone()
    return jsonify({'code': 0, 'data': dict(user)})
```

- [ ] **Step 3: 创建其他 blueprint 模块**

按照相同模式创建 system.py, base_data.py, inventory.py, production.py, quality.py, equipment.py, tool.py, schedule.py, flow.py, dashboard.py, report.py

- [ ] **Step 4: 重构 app.py 为入口文件**

```python
# backend/app.py (简化版)
from flask import Flask
from .utils.database import close_db, init_db, _init_extra_tables
from .blueprints.auth import auth_bp
from .blueprints.system import system_bp
from .blueprints.base_data import base_data_bp
from .blueprints.inventory import inventory_bp
from .blueprints.production import production_bp
from .blueprints.quality import quality_bp
from .blueprints.equipment import equipment_bp
from .blueprints.tool import tool_bp
from .blueprints.schedule import schedule_bp
from .blueprints.flow import flow_bp
from .blueprints.dashboard import dashboard_bp
from .blueprints.report import report_bp

def create_app():
    app = Flask(__name__, static_folder=None)
    app.secret_key = 'mes-factory-2026-secret-key'
    
    # 注册 teardown
    app.teardown_appcontext(close_db)
    
    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(base_data_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(quality_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(tool_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(flow_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(report_bp)
    
    return app

app = create_app()

if __name__ == '__main__':
    init_db()
    _init_extra_tables()
    app.run(host='0.0.0.0', port=8080, debug=False)
```

- [ ] **Step 5: 测试重构后的应用**

```bash
cd D:\MES工厂管家
python -c "from backend.app import app; print('Import OK')"
python backend/app.py
```

- [ ] **Step 6: 提交代码**

```bash
git add backend/
git commit -m "refactor: split app.py into blueprints"
```

---

### Task 2: 前端重构 - 拆分 admin/index.html

**Files:**
- Create: `admin/static/js/app.js`
- Create: `admin/static/js/api.js`
- Create: `admin/static/js/modal.js`
- Create: `admin/static/js/menu.js`
- Create: `admin/static/js/pages/home.js`
- Create: `admin/static/js/pages/base.js`
- Create: `admin/static/js/pages/inventory.js`
- Create: `admin/static/js/pages/production.js`
- Create: `admin/static/js/pages/quality.js`
- Create: `admin/static/js/pages/equipment.js`
- Create: `admin/static/js/pages/tool.js`
- Create: `admin/static/js/pages/schedule.js`
- Create: `admin/static/js/pages/flow.js`
- Create: `admin/static/js/pages/report.js`
- Create: `admin/static/js/pages/system.js`
- Create: `admin/static/css/style.css`
- Modify: `admin/index.html` (简化为入口)

- [ ] **Step 1: 创建 static 目录结构**

```bash
mkdir -p admin/static/js/pages
mkdir -p admin/static/css
```

- [ ] **Step 2: 提取 CSS 到独立文件**

将 `admin/index.html` 中的 `<style>` 内容复制到 `admin/static/css/style.css`

- [ ] **Step 3: 提取 JS 模块**

```javascript
// admin/static/js/api.js
function api(url, opts) {
    opts = opts || {};
    var o = {headers: {'Content-Type': 'application/json'}};
    if (opts.method) o.method = opts.method;
    if (opts.body) o.body = JSON.stringify(opts.body);
    return fetch(url, o).then(function(r) { return r.json(); }).then(function(d) {
        if (d.code === 401) { doLogout(); return null; }
        return d;
    }).catch(function(e) { console.error('API Error:', e); return null; });
}
```

```javascript
// admin/static/js/modal.js
var editId = null;
var curFields = null;
var curApiBase = '';
var modalSaveHandler = null;

function openModal(title, fields, data) {
    // 从原代码复制
}

function closeModal() {
    document.getElementById('modal').classList.remove('show');
    modalSaveHandler = null;
}
```

- [ ] **Step 4: 更新 index.html 引用新模块**

```html
<link rel="stylesheet" href="/admin/static/css/style.css">
<script src="/admin/static/js/api.js"></script>
<script src="/admin/static/js/modal.js"></script>
<script src="/admin/static/js/menu.js"></script>
<script src="/admin/static/js/pages/home.js"></script>
<!-- ... 其他页面模块 -->
<script src="/admin/static/js/app.js"></script>
```

- [ ] **Step 5: 测试前端重构**

```bash
python admin/run.py
# 访问 http://localhost:8081/admin 验证功能正常
```

- [ ] **Step 6: 提交代码**

```bash
git add admin/
git commit -m "refactor: split admin frontend into modules"
```

---

### Task 3: UI 优化 - 改善界面样式

**Files:**
- Modify: `admin/static/css/style.css`
- Modify: `frontend/index.html`

- [ ] **Step 1: 优化配色方案**

```css
/* 使用更现代的配色 */
:root {
    --primary: #1890ff;
    --success: #52c41a;
    --warning: #faad14;
    --danger: #f5222d;
    --text: #262626;
    --text-secondary: #8c8c8c;
    --border: #f0f0f0;
    --bg: #f5f5f5;
    --card-bg: #ffffff;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Microsoft YaHei', sans-serif;
    color: var(--text);
    background: var(--bg);
}
```

- [ ] **Step 2: 改善表格样式**

```css
table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}

th {
    background: #fafafa;
    padding: 12px 16px;
    text-align: left;
    font-weight: 600;
    color: var(--text);
    border-bottom: 1px solid var(--border);
}

td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    transition: background 0.2s;
}

tr:hover td {
    background: #f5f7fa;
}
```

- [ ] **Step 3: 改善按钮样式**

```css
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 32px;
    padding: 0 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
    gap: 6px;
}

.btn:hover {
    opacity: 0.85;
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.btn:active {
    transform: translateY(0);
}
```

- [ ] **Step 4: 改善卡片样式**

```css
.card {
    background: #fff;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    border: 1px solid var(--border);
    transition: box-shadow 0.2s;
}

.card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
```

- [ ] **Step 5: 改善表单样式**

```css
.form-item input,
.form-item select,
.form-item textarea {
    height: 36px;
    border: 1px solid #d9d9d9;
    border-radius: 6px;
    padding: 0 12px;
    font-size: 14px;
    transition: all 0.2s;
    width: 100%;
}

.form-item input:focus,
.form-item select:focus,
.form-item textarea:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(24,144,255,0.2);
    outline: none;
}
```

- [ ] **Step 6: 提交代码**

```bash
git add admin/static/css/
git commit -m "style: improve UI design and responsiveness"
```

---

## 阶段 2：新功能

### Task 4: 消息通知系统

**Files:**
- Create: `backend/blueprints/notification.py`
- Create: `admin/static/js/pages/notification.js`
- Modify: `backend/app.py`

- [ ] **Step 1: 创建通知表**

```python
# 在 init_db 中添加
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
```

- [ ] **Step 2: 创建通知 API**

```python
# backend/blueprints/notification.py
from flask import Blueprint, request, jsonify, session
from ..utils.database import get_db
from ..utils.helpers import login_required

notification_bp = Blueprint('notification', __name__)

@notification_bp.route('/api/notification/list')
@login_required
def notification_list():
    db = get_db()
    user_id = session.get('user_id')
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    unread_only = request.args.get('unread', '0') == '1'
    
    where = "WHERE user_id=?"
    args = [user_id]
    if unread_only:
        where += " AND is_read=0"
    
    total = db.execute(f"SELECT COUNT(*) as cnt FROM sys_notification {where}", args).fetchone()['cnt']
    rows = db.execute(f"SELECT * FROM sys_notification {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                      args + [size, (page-1)*size]).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})

@notification_bp.route('/api/notification/unread/count')
@login_required
def unread_count():
    db = get_db()
    user_id = session.get('user_id')
    cnt = db.execute("SELECT COUNT(*) as c FROM sys_notification WHERE user_id=? AND is_read=0", (user_id,)).fetchone()['c']
    return jsonify({'code': 0, 'data': {'count': cnt}})

@notification_bp.route('/api/notification/read', methods=['POST'])
@login_required
def mark_read():
    db = get_db()
    user_id = session.get('user_id')
    data = request.json
    if data.get('all'):
        db.execute("UPDATE sys_notification SET is_read=1 WHERE user_id=?", (user_id,))
    else:
        db.execute("UPDATE sys_notification SET is_read=1 WHERE id=? AND user_id=?", (data['id'], user_id))
    db.commit()
    return jsonify({'code': 0})
```

- [ ] **Step 3: 添加通知到前端**

```javascript
// 在 header 添加通知图标
function loadNotifications() {
    api('/api/notification/unread/count').then(function(r) {
        if (r && r.code === 0) {
            var badge = document.getElementById('notifBadge');
            if (badge) {
                badge.textContent = r.data.count;
                badge.style.display = r.data.count > 0 ? 'block' : 'none';
            }
        }
    });
}
```

- [ ] **Step 4: 测试通知功能**

- [ ] **Step 5: 提交代码**

```bash
git add backend/blueprints/notification.py admin/static/js/pages/notification.js
git commit -m "feat: add notification system"
```

---

### Task 5: 数据导出增强 - PDF 报表

**Files:**
- Create: `backend/utils/pdf_generator.py`
- Modify: `backend/blueprints/report.py`

- [ ] **Step 1: 安装依赖**

```bash
pip install reportlab
```

- [ ] **Step 2: 创建 PDF 生成器**

```python
# backend/utils/pdf_generator.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# 注册中文字体
font_path = os.path.join(os.path.dirname(__file__), '..', '..', 'resource', 'font', 'simhei.ttf')
if os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont('SimHei', font_path))

def generate_production_report(data, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    
    # 标题
    title = Paragraph("生产报表", styles['Title'])
    elements.append(title)
    
    # 统计数据
    stats_data = [
        ['指标', '数值'],
        ['工单总数', str(data['total_orders'])],
        ['完成数', str(data['completed'])],
        ['进行中', str(data['in_progress'])],
        ['合格率', f"{data.get('pass_rate', 0)}%"],
    ]
    
    stats_table = Table(stats_data)
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'SimHei'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(stats_table)
    
    doc.build(elements)
    return output_path
```

- [ ] **Step 3: 添加 PDF 导出 API**

```python
@report_bp.route('/api/report/production/pdf')
@login_required
def export_production_pdf():
    # 获取数据
    data = get_production_stats()
    output_path = '/tmp/production_report.pdf'
    generate_production_report(data, output_path)
    return send_file(output_path, as_attachment=True, download_name='production_report.pdf')
```

- [ ] **Step 4: 测试 PDF 导出**

- [ ] **Step 5: 提交代码**

```bash
git add backend/utils/pdf_generator.py backend/blueprints/report.py
git commit -m "feat: add PDF report export"
```

---

## 阶段 3：采集终端增强

### Task 6: 采集终端功能增强

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: 增加扫码功能**

```javascript
// 添加扫码输入支持
function setupBarcodeScanner() {
    var scanInput = document.getElementById('scanInput');
    if (scanInput) {
        scanInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                var code = this.value.trim();
                if (code) {
                    handleBarcodeScan(code);
                    this.value = '';
                }
            }
        });
    }
}

function handleBarcodeScan(code) {
    // 根据条码前缀判断类型
    if (code.startsWith('WO')) {
        // 工单条码
        loadWorkorderDetail(code);
    } else if (code.startsWith('TK')) {
        // 任务条码
        loadTaskDetail(code);
    } else if (code.startsWith('PR')) {
        // 产品条码
        loadProductDetail(code);
    } else {
        showToast('未知条码格式: ' + code);
    }
}
```

- [ ] **Step 2: 增加快捷报工**

```javascript
function quickReport(taskId) {
    document.getElementById('mTitle').textContent = '快捷报工';
    document.getElementById('mBody').innerHTML =
        '<div class="form-group"><label class="form-label">数量<span style="color:red">*</span></label>'
        + '<input id="f_qty" class="form-input" type="number" placeholder="输入数量" autofocus></div>'
        + '<div class="numpad">'
        + '<button onclick="numpadInput(1)">1</button><button onclick="numpadInput(2)">2</button><button onclick="numpadInput(3)">3</button>'
        + '<button onclick="numpadInput(4)">4</button><button onclick="numpadInput(5)">5</button><button onclick="numpadInput(6)">6</button>'
        + '<button onclick="numpadInput(7)">7</button><button onclick="numpadInput(8)">8</button><button onclick="numpadInput(9)">9</button>'
        + '<button onclick="numpadClear()">C</button><button onclick="numpadInput(0)">0</button><button class="confirm" onclick="numpadConfirm()">OK</button>'
        + '</div>';
    document.getElementById('modal').classList.add('show');
}
```

- [ ] **Step 3: 增加实时统计**

```javascript
function loadRealtimeStats() {
    api('/api/prod/task/list?size=100').then(function(r) {
        if (r && r.data) {
            var list = r.data.list || r.data;
            var pending = list.filter(function(t) { return t.status === 0; }).length;
            var running = list.filter(function(t) { return t.status === 1; }).length;
            var completed = list.filter(function(t) { return t.status === 3; }).length;
            
            document.getElementById('st_pending').textContent = pending;
            document.getElementById('st_running').textContent = running;
            document.getElementById('st_completed').textContent = completed;
        }
    });
}
```

- [ ] **Step 4: 测试采集终端**

- [ ] **Step 5: 提交代码**

```bash
git add frontend/index.html
git commit -m "feat: enhance collector terminal with barcode scanning"
```

---

## 执行顺序

1. Task 1: 后端重构 (代码重构)
2. Task 2: 前端重构 (代码重构)
3. Task 3: UI 优化 (UI优化)
4. Task 4: 消息通知 (新功能)
5. Task 5: PDF 报表 (新功能)
6. Task 6: 采集终端增强 (采集终端增强)

每个 Task 完成后运行测试并提交代码。
