# MES 工厂管家稳定化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复已复现的权限、生产业务链路和管理端交互缺陷，接通八个已有后端基础的管理页面，并让未实现的外部集成返回真实状态。

**Architecture:** 保持 Flask + SQLite + 原生 JavaScript 架构。后端把报工、权限和外部能力状态收敛到可独立测试的函数；前端增加一个无 DOM 依赖的 UI 工具模块供浏览器和 Node 测试共用，并在现有渲染体系中补齐页面映射。

**Tech Stack:** Python 3.8、Flask 3.x、SQLite、pytest 8.x、原生 JavaScript、Node.js 内置测试运行器。

## Global Constraints

- 不引入新的前端框架。
- 不修改或删除现有业务表和历史数据。
- 所有行为修改必须先增加失败测试并确认失败原因正确。
- 后端测试只使用临时 SQLite 数据库。
- AI、ERP 和通知渠道没有真实适配器时不得返回业务成功。
- APS 本次只提供经过验证的预览，不持久化排程结果。
- 每个任务完成后运行该任务的聚焦测试，再运行完整 pytest。

---

## 文件结构

- `pytest.ini`：限定 pytest 只收集真正的 pytest 测试模块。
- `test_comprehensive.py`：后端和 API 回归测试。
- `tests/admin_ui_utils.test.js`：纯前端工具函数回归测试。
- `tests/admin_api.test.js`：管理端 API 缓存和错误归一化测试。
- `admin/static/js/ui_utils.js`：HTML 转义、状态文案和菜单目标等纯函数。
- `admin/static/js/api.js`：请求、缓存失效和错误归一化。
- `admin/static/js/crud.js`、`modal.js`、`menu.js`、`app.js`：通用管理端交互。
- `admin/static/js/pages/warehouse_schedule.js`：八个补齐页面的渲染和表单。
- `backend/utils/helpers.py`：认证、管理员授权和通用排序。
- `backend/blueprints/production.py`：搜索和报工事务。
- `backend/blueprints/warehouse.py`、`eqp_schedule.py`、`svc.py`：补齐 CRUD。
- `backend/blueprints/ai.py`、`erp.py`、`erp_deep.py`、`aps.py`、`sys_ext.py`、`update.py`：真实的未配置/未实现响应。

---

### Task 1: 建立稳定测试入口和纯前端工具

**Files:**
- Create: `pytest.ini`
- Create: `admin/static/js/ui_utils.js`
- Create: `tests/admin_ui_utils.test.js`
- Modify: `admin/index.html:69-73`
- Test: `test_comprehensive.py`

**Interfaces:**
- Produces: `MESUI.escapeHtml(value) -> string`
- Produces: `MESUI.menuPage(menu) -> string`
- Produces: `MESUI.statusHtml(field, value) -> string`
- Produces: `MESUI.errorMessage(error, fallback) -> string`

- [ ] **Step 1: 写 pytest 收集失败的基线说明测试**

在 `pytest.ini` 创建前运行：

```powershell
python -m pytest --collect-only -q
```

Expected: 收集阶段因 `test_all_apis.py` 连接 8080，以及四个 Playwright 脚本缺少依赖而失败。

- [ ] **Step 2: 创建 pytest 收集配置**

创建：

```ini
[pytest]
python_files = test_comprehensive.py
test_classes = Test*
test_functions = test_*
```

运行：

```powershell
python -m pytest --collect-only -q
```

Expected: 成功收集 138 条现有测试，不导入截图和外部服务脚本。

- [ ] **Step 3: 写纯前端工具失败测试**

创建 `tests/admin_ui_utils.test.js`：

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { escapeHtml, menuPage, statusHtml } =
  require('../admin/static/js/ui_utils.js');

test('escapeHtml renders business input as text', () => {
  assert.equal(
    escapeHtml('<img src=x onerror=alert(1)>'),
    '&lt;img src=x onerror=alert(1)&gt;'
  );
});

test('menuPage preserves each top-level destination', () => {
  assert.equal(menuPage({k: 'analytics/dashboard', home: true}), 'analytics/dashboard');
  assert.equal(menuPage({k: 'notifications', home: true}), 'notifications');
});

test('statusHtml prefers configured business labels', () => {
  const field = {k: 'status', s: [{v: 0, t: '待检'}, {v: 1, t: '已检'}]};
  assert.match(statusHtml(field, 0), /待检/);
  assert.doesNotMatch(statusHtml(field, 0), /禁用/);
});
```

运行：

```powershell
node --test tests/admin_ui_utils.test.js
```

Expected: FAIL，因为 `ui_utils.js` 尚不存在。

- [ ] **Step 4: 实现纯前端工具**

创建 `admin/static/js/ui_utils.js`：

```javascript
(function(root, factory) {
    var api = factory();
    root.MESUI = api;
    if(typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function menuPage(menu) {
        return menu.k;
    }

    function statusHtml(field, value) {
        var label = null;
        if(field && field.s) {
            field.s.forEach(function(option) {
                if(String(option.v) === String(value)) label = option.t;
            });
        }
        if(label == null) {
            var numeric = Number(value);
            label = numeric === 1 ? '启用' : (numeric === 0 ? '禁用' : '未知');
        }
        var cls = Number(value) === 1 ? 'tag-ok' : (Number(value) === 0 ? 'tag-draft' : 'tag-no');
        return '<span class="tag ' + cls + '">' + escapeHtml(label) + '</span>';
    }

    function errorMessage(error, fallback) {
        return error && error.message ? error.message : fallback;
    }

    return {
        escapeHtml: escapeHtml,
        menuPage: menuPage,
        statusHtml: statusHtml,
        errorMessage: errorMessage
    };
});
```

在 `admin/index.html` 的 `api.js` 前加入：

```html
<script src="/admin/static/js/ui_utils.js"></script>
```

- [ ] **Step 5: 验证并提交**

运行：

```powershell
node --test tests/admin_ui_utils.test.js
python -m pytest -q
```

Expected: Node 3 tests PASS；pytest 138 tests PASS。

提交：

```powershell
git add pytest.ini admin/index.html admin/static/js/ui_utils.js tests/admin_ui_utils.test.js
git commit -m "test: stabilize MES test entrypoints"
```

---

### Task 2: 修复管理员授权和动态内容转义

**Files:**
- Modify: `backend/utils/helpers.py:25-55`
- Modify: `backend/blueprints/system.py:1-170`
- Modify: `admin/static/js/crud.js:74-93`
- Modify: `admin/static/js/modal.js:21-45`
- Modify: `admin/static/js/app.js:99-109`
- Test: `test_comprehensive.py`
- Test: `tests/admin_ui_utils.test.js`

**Interfaces:**
- Produces: `admin_required(function) -> decorated function`
- Consumes: `MESUI.escapeHtml`
- Consumes: `MESUI.statusHtml`

- [ ] **Step 1: 写普通用户越权失败测试**

在 `test_comprehensive.py` 增加：

```python
class TestAuthorization:
    def test_plain_user_cannot_write_system_data(self, auth_client, client):
        created = auth_client.post('/api/sys/user/add', json={
            'username': 'plain_operator',
            'password': 'operator123',
            'real_name': '普通操作员',
        }).get_json()
        assert created['code'] == 0

        plain = client.application.test_client()
        login = plain.post('/api/login', json={
            'username': 'plain_operator',
            'password': 'operator123',
        })
        assert login.get_json()['code'] == 0

        response = plain.post('/api/sys/dept/add', json={'dept_name': '越权部门'})
        assert response.status_code == 403
        assert response.get_json()['code'] == 403

    def test_admin_can_still_write_system_data(self, auth_client):
        response = auth_client.post('/api/sys/dept/add', json={'dept_name': '授权部门'})
        assert response.get_json()['code'] == 0
```

运行：

```powershell
python -m pytest test_comprehensive.py::TestAuthorization -q
```

Expected: 普通用户测试 FAIL，实际返回 200。

- [ ] **Step 2: 实现管理员装饰器并保护系统写接口**

在 `helpers.py` 增加：

```python
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'code': 401, 'message': '请先登录'}), 401
        if session.get('username') != 'admin':
            return jsonify({'code': 403, 'message': '仅管理员可执行此操作'}), 403
        return f(*args, **kwargs)
    return decorated
```

把 `system.py` 中用户、角色、部门、菜单和字典的 `add/update/delete` 路由装饰器从 `@login_required` 改为 `@admin_required`。读取路由保持不变。

修正 `permission_required(*perms)` 为失败关闭：管理员放行；普通用户把 `role['menu_ids']` 按 JSON 数组解析（旧数据解析失败时按逗号分隔），将两侧都规范为字符串后求交集；`perms` 为空、角色不存在、列表解析失败或没有匹配项时均返回 403。该装饰器本批次不用于系统写路由，但不能继续默认放行。

- [ ] **Step 3: 写动态值转义覆盖测试**

在 `tests/admin_ui_utils.test.js` 增加：

```javascript
test('escapeHtml covers all attribute-breaking characters', () => {
  assert.equal(
    escapeHtml(`&<>"'`),
    '&amp;&lt;&gt;&quot;&#39;'
  );
});
```

运行并确认测试先因实现使用位置尚未改变而仅覆盖工具；随后进行浏览器回归时验证 DOM 不出现业务数据创建的标签。

- [ ] **Step 4: 在管理端所有通用输出路径使用转义**

在 `crud.js`：

```javascript
var v = row[f.k] != null ? row[f.k] : '';
if(f.k === 'status') {
    v = MESUI.statusHtml(f, v);
} else if(f.s) {
    f.s.forEach(function(o) {
        if(String(o.v) === String(v)) v = o.t;
    });
    v = MESUI.escapeHtml(v);
} else {
    v = MESUI.escapeHtml(v);
}
```

同时：

- 表格普通字段、创建时间使用 `MESUI.escapeHtml`。
- `modal.js` 的 label、option 文本和 value 使用转义。
- `showCompareResult` 的字段名和值使用转义。
- 用 `currentRowsById` 保存行对象，编辑按钮只传 ID，避免把 JSON 直接拼进 `onclick`。

- [ ] **Step 5: 验证并提交**

运行：

```powershell
python -m pytest test_comprehensive.py::TestAuthorization -q
node --test tests/admin_ui_utils.test.js
python -m pytest -q
```

Expected: 全部 PASS。

提交：

```powershell
git add backend/utils/helpers.py backend/blueprints/system.py admin/static/js/crud.js admin/static/js/modal.js admin/static/js/app.js test_comprehensive.py tests/admin_ui_utils.test.js
git commit -m "fix: enforce admin writes and escape UI data"
```

---

### Task 3: 修复报工事务和扫码搜索

**Files:**
- Modify: `backend/blueprints/production.py:63-178`
- Modify: `backend/utils/helpers.py:58-84`
- Test: `test_comprehensive.py`

**Interfaces:**
- Produces: `_create_report(data: dict, user_id: int) -> dict`
- Produces: `_recalculate_task_and_workorder(db, task_id: int, workorder_id: int) -> None`
- Existing API: `POST /api/prod/report/add`
- Existing API: `POST /api/prod/report/gps`

- [ ] **Step 1: 写报工进度失败测试**

在 `test_comprehensive.py` 顶部增加 `import uuid`，并在测试类之前增加以下辅助函数：

```python
def response_id(response):
    payload = response.get_json()
    assert payload['code'] == 0, payload
    return payload['data']['id']


def create_production_chain(client, planned_qty=10):
    suffix = uuid.uuid4().hex[:8]
    workshop_id = response_id(client.post('/api/base/workshop/add', json={
        'workshop_name': f'报工车间-{suffix}',
        'code': f'WS_{suffix}',
    }))
    process_id = response_id(client.post('/api/base/process/add', json={
        'process_name': f'报工工序-{suffix}',
        'code': f'PS_{suffix}',
        'workshop_id': workshop_id,
    }))
    product_id = response_id(client.post('/api/base/product/add', json={
        'product_name': f'报工产品-{suffix}',
        'code': f'PD_{suffix}',
        'unit': '件',
    }))
    workorder_id = response_id(client.post('/api/prod/workorder/add', json={
        'product_id': product_id,
        'workshop_id': workshop_id,
        'planned_qty': planned_qty,
    }))
    task_id = response_id(client.post('/api/prod/task/add', json={
        'workorder_id': workorder_id,
        'process_id': process_id,
        'planned_qty': planned_qty,
    }))
    return {
        'workshop_id': workshop_id,
        'process_id': process_id,
        'product_id': product_id,
        'workorder_id': workorder_id,
        'task_id': task_id,
    }


def find_by_id(payload, row_id):
    return next(row for row in payload['data']['list'] if row['id'] == row_id)
```

再创建 `class TestProductionConsistency:`，把以下测试方法放在类中：

```python
def test_report_updates_task_and_workorder_progress(self, auth_client):
    ids = create_production_chain(auth_client, planned_qty=10)
    result = auth_client.post('/api/prod/report/add', json={
        'task_id': ids['task_id'],
        'workorder_id': ids['workorder_id'],
        'process_id': ids['process_id'],
        'qualified_qty': 6,
        'defect_qty': 1,
    }).get_json()
    assert result['code'] == 0

    task = find_by_id(auth_client.get('/api/prod/task/list?size=100').get_json(), ids['task_id'])
    workorder = find_by_id(
        auth_client.get('/api/prod/workorder/list?size=100').get_json(),
        ids['workorder_id'],
    )
    assert task['completed_qty'] == 6
    assert task['status'] == 1
    assert workorder['completed_qty'] == 6
    assert workorder['defect_qty'] == 1
    assert workorder['status'] == 1

    finished = auth_client.post('/api/prod/report/add', json={
        'task_id': ids['task_id'],
        'workorder_id': ids['workorder_id'],
        'process_id': ids['process_id'],
        'qualified_qty': 4,
        'defect_qty': 0,
    }).get_json()
    assert finished['code'] == 0
    task = find_by_id(
        auth_client.get('/api/prod/task/list?size=100').get_json(),
        ids['task_id'],
    )
    workorder = find_by_id(
        auth_client.get('/api/prod/workorder/list?size=100').get_json(),
        ids['workorder_id'],
    )
    assert task['completed_qty'] == 10
    assert task['status'] == 3
    assert workorder['completed_qty'] == 10
    assert workorder['status'] == 3


def test_workorder_completes_only_after_all_tasks(self, auth_client):
    ids = create_production_chain(auth_client, planned_qty=10)
    suffix = uuid.uuid4().hex[:8]
    second_process = response_id(auth_client.post('/api/base/process/add', json={
        'process_name': f'第二工序-{suffix}',
        'code': f'PS_SECOND_{suffix}',
        'workshop_id': ids['workshop_id'],
    }))
    second_task = response_id(auth_client.post('/api/prod/task/add', json={
        'workorder_id': ids['workorder_id'],
        'process_id': second_process,
        'planned_qty': 10,
    }))
    for task_id, process_id, expected_status in (
        (ids['task_id'], ids['process_id'], 1),
        (second_task, second_process, 3),
    ):
        result = auth_client.post('/api/prod/report/add', json={
            'task_id': task_id,
            'workorder_id': ids['workorder_id'],
            'process_id': process_id,
            'qualified_qty': 10,
            'defect_qty': 0,
        })
        assert result.status_code == 200
        workorder = find_by_id(
            auth_client.get('/api/prod/workorder/list?size=100').get_json(),
            ids['workorder_id'],
        )
        assert workorder['status'] == expected_status
```

运行：

```powershell
python -m pytest test_comprehensive.py -k "report_updates_task" -q
```

Expected: FAIL，完成数量仍为 0。

- [ ] **Step 2: 实现事务内编号生成**

在 `backend/utils/helpers.py` 中抽出以下函数，并让现有 `gen_no` 在自己的 `BEGIN IMMEDIATE` 和 `commit` 之间调用它：

```python
def gen_no_in_transaction(db, prefix):
    row = db.execute(
        "SELECT * FROM sys_numbering WHERE entity_type=?",
        (prefix,),
    ).fetchone()
    if not row:
        db.execute(
            """INSERT INTO sys_numbering
               (prefix, entity_type, current_no, digit_count)
               VALUES (?,?,1,6)""",
            (prefix, prefix),
        )
        no = 1
        digits = 6
    else:
        no = row['current_no'] + 1
        digits = row['digit_count']
        db.execute(
            "UPDATE sys_numbering SET current_no=? WHERE entity_type=?",
            (no, prefix),
        )
    today = datetime.datetime.now().strftime('%Y%m%d')
    return f"{prefix}{today}{str(no).zfill(digits)}"
```

`gen_no(prefix)` 的公开接口不变；只有已经开启事务的报工逻辑直接调用 `gen_no_in_transaction`。

- [ ] **Step 3: 实现单事务报工**

在 `production.py` 实现 `_create_report`：

```python
def _create_report(data, user_id):
    db = get_db()
    try:
        task_id = int(data.get('task_id'))
        workorder_id = int(data.get('workorder_id'))
        process_id = int(data.get('process_id'))
        qualified = float(data.get('qualified_qty') or 0)
        defect = float(data.get('defect_qty') or 0)
    except (TypeError, ValueError):
        return {'code': 400, 'message': '报工参数不合法'}
    if qualified <= 0 or defect < 0:
        return {'code': 400, 'message': '报工数量不合法'}

    try:
        db.execute("BEGIN IMMEDIATE")
        task = db.execute(
            "SELECT * FROM prod_task WHERE id=?", (task_id,)
        ).fetchone()
        if not task:
            db.rollback()
            return {'code': 404, 'message': '任务不存在'}
        if int(task['workorder_id']) != workorder_id:
            db.rollback()
            return {'code': 400, 'message': '任务与工单不匹配'}
        if int(task['process_id']) != process_id:
            db.rollback()
            return {'code': 400, 'message': '任务与工序不匹配'}

        report_no = gen_no_in_transaction(db, 'BR')
        cursor = db.execute(
            """INSERT INTO prod_report
               (report_no, task_id, workorder_id, process_id, user_id,
                qualified_qty, defect_qty, remark)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                report_no,
                task_id,
                workorder_id,
                process_id,
                user_id,
                qualified,
                defect,
                data.get('remark'),
            ),
        )
        _recalculate_task_and_workorder(
            db, task_id, workorder_id
        )
        db.commit()
        return {
            'code': 0,
            'data': {'id': cursor.lastrowid},
            'message': '报工成功',
        }
    except Exception:
        db.rollback()
        raise
```

实现 `_recalculate_task_and_workorder`：

```python
def _progress_status(completed, defect, planned):
    if completed >= planned:
        return 3
    if completed > 0 or defect > 0:
        return 1
    return 0


def _report_totals(db, column, row_id):
    assert column in ('task_id', 'workorder_id')
    return db.execute(
        f"""SELECT COALESCE(SUM(qualified_qty), 0) AS completed,
                   COALESCE(SUM(defect_qty), 0) AS defect
            FROM prod_report WHERE {column}=?""",
        (row_id,),
    ).fetchone()


def _recalculate_task_and_workorder(db, task_id, workorder_id):
    task = db.execute(
        "SELECT planned_qty FROM prod_task WHERE id=?", (task_id,)
    ).fetchone()
    task_totals = _report_totals(db, 'task_id', task_id)
    task_status = _progress_status(
        task_totals['completed'], task_totals['defect'], task['planned_qty']
    )
    db.execute(
        """UPDATE prod_task
           SET completed_qty=?, defect_qty=?, status=?,
               start_time=CASE
                   WHEN ? > 0 THEN COALESCE(start_time, CURRENT_TIMESTAMP)
                   ELSE start_time
               END,
               end_time=CASE
                   WHEN ? = 3 THEN COALESCE(end_time, CURRENT_TIMESTAMP)
                   ELSE NULL
               END
           WHERE id=?""",
        (
            task_totals['completed'],
            task_totals['defect'],
            task_status,
            task_totals['completed'] + task_totals['defect'],
            task_status,
            task_id,
        ),
    )

    workorder_totals = _report_totals(db, 'workorder_id', workorder_id)
    task_counts = db.execute(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(CASE WHEN status=3 THEN 1 ELSE 0 END), 0)
                      AS finished
           FROM prod_task WHERE workorder_id=?""",
        (workorder_id,),
    ).fetchone()
    has_progress = (
        workorder_totals['completed'] > 0 or workorder_totals['defect'] > 0
    )
    workorder_status = (
        3 if task_counts['total'] > 0
             and task_counts['finished'] == task_counts['total']
        else 1 if has_progress
        else 0
    )
    db.execute(
        """UPDATE prod_workorder
           SET completed_qty=?, defect_qty=?, status=?,
               updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (
            workorder_totals['completed'],
            workorder_totals['defect'],
            workorder_status,
            workorder_id,
        ),
    )
```

两个更新和报工插入必须使用同一个 `db` 连接，辅助函数内部不得提交。`prod_report_add` 与 `prod_report_gps` 都调用 `_create_report`；GPS 路由只负责把坐标规范化进 `remark`。

把 `production.py` 的导入改为包含 `gen_no_in_transaction`。两个报工路由根据结果码返回正确 HTTP 状态：

```python
result = _create_report(data, session.get('user_id'))
status = result['code'] if result.get('code', 0) >= 400 else 200
return jsonify(result), status
```

- [ ] **Step 4: 写扫码搜索失败测试**

把下面两个方法加入 `TestProductionConsistency`：

```python
def test_workorder_keyword_does_not_fall_back_to_latest(self, auth_client):
    create_production_chain(auth_client, planned_qty=10)
    payload = auth_client.get(
        '/api/prod/workorder/list?keyword=WO_DOES_NOT_EXIST'
    ).get_json()
    assert payload['data']['list'] == []

def test_task_keyword_does_not_fall_back_to_latest(self, auth_client):
    create_production_chain(auth_client, planned_qty=10)
    payload = auth_client.get(
        '/api/prod/task/list?keyword=TK_DOES_NOT_EXIST'
    ).get_json()
    assert payload['data']['list'] == []
```

Expected: 两条测试 FAIL，当前均返回最新记录。

- [ ] **Step 5: 实现列表搜索**

工单列表增加：

```sql
WHERE (? = '' OR w.order_no LIKE ? OR p.product_name LIKE ? OR p.code LIKE ?)
```

任务列表增加：

```sql
WHERE (? = '' OR t.task_no LIKE ? OR w.order_no LIKE ? OR pr.process_name LIKE ?)
```

总数查询和列表查询必须使用完全相同的 WHERE 参数。

- [ ] **Step 6: 验证并提交**

运行：

```powershell
python -m pytest test_comprehensive.py -k "report_updates_task or keyword_does_not_fall_back" -q
python -m pytest -q
```

Expected: 全部 PASS。

提交：

```powershell
git add backend/blueprints/production.py backend/utils/helpers.py test_comprehensive.py
git commit -m "fix: make reporting and barcode lookup consistent"
```

---

### Task 4: 修复管理端共享交互

**Files:**
- Modify: `admin/static/js/api.js`
- Modify: `admin/static/js/crud.js`
- Modify: `admin/static/js/modal.js`
- Modify: `admin/static/js/menu.js`
- Modify: `admin/static/js/app.js`
- Modify: `backend/utils/helpers.py:119-130`
- Modify: `backend/blueprints/svc.py:35-41`
- Create: `tests/admin_api.test.js`
- Test: `test_comprehensive.py`

**Interfaces:**
- Produces: `api(url, opts) -> Promise<object>`
- Produces: `currentRowsById: Map<string, object>`
- Adds API: `POST /api/svc/complaint/delete`

- [ ] **Step 1: 写 API 缓存失效失败测试**

创建 `tests/admin_api.test.js`，用 Node `vm` 加载真实 `api.js`：

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function loadApi(responses) {
  let calls = 0;
  const context = {
    console,
    Date,
    JSON,
    doLogout() {},
    fetch: async () => {
      const data = responses[Math.min(calls, responses.length - 1)];
      calls += 1;
      return {
        ok: true,
        headers: {get: () => 'application/json'},
        json: async () => data,
      };
    },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('admin/static/js/api.js', 'utf8'), context);
  return {context, calls: () => calls};
}

test('successful write invalidates cached GET data', async () => {
  const loaded = loadApi([
    {code: 0, data: ['old']},
    {code: 0},
    {code: 0, data: ['new']},
  ]);
  await loaded.context.api('/api/items');
  await loaded.context.api('/api/items', {method: 'POST', body: {id: 1}});
  const refreshed = await loaded.context.api('/api/items');
  assert.deepEqual(refreshed.data, ['new']);
  assert.equal(loaded.calls(), 3);
});
```

运行：

```powershell
node --test tests/admin_api.test.js
```

Expected: FAIL，第三次请求仍返回缓存数据或调用次数不是 3。

- [ ] **Step 2: 实现缓存失效和统一错误对象**

`api.js` 在成功 POST 后调用 `clearApiCache()`。解析前检查 `response.ok` 和 `content-type`；HTML 404 转为：

```javascript
{
    code: response.status,
    message: '请求失败（HTTP ' + response.status + '）'
}
```

删除重复的 `escapeJson` 和 `doExport2` 定义。

- [ ] **Step 3: 写后端排序和客诉删除失败测试**

创建 `class TestAdminInteractionBackend:`，把以下两个方法放在类中：

```python
def test_lowercase_sort_order_is_honored(self, auth_client):
    suffix = uuid.uuid4().hex[:8]
    first = response_id(auth_client.post('/api/base/workshop/add', json={
        'workshop_name': '排序一',
        'code': f'SORT_1_{suffix}',
    }))
    second = response_id(auth_client.post('/api/base/workshop/add', json={
        'workshop_name': '排序二',
        'code': f'SORT_2_{suffix}',
    }))
    asc = auth_client.get('/api/base/workshop/list?sort=id&order=asc&size=100').get_json()
    desc = auth_client.get('/api/base/workshop/list?sort=id&order=desc&size=100').get_json()
    asc_ids = [row['id'] for row in asc['data']['list'] if row['id'] in (first, second)]
    desc_ids = [row['id'] for row in desc['data']['list'] if row['id'] in (first, second)]
    assert asc_ids == [first, second]
    assert desc_ids == [second, first]

def test_complaint_can_be_deleted(self, auth_client):
    created = auth_client.post('/api/svc/complaint/add', json={
        'complaint_type': '质量',
        'description': '删除测试',
    }).get_json()
    deleted = auth_client.post(
        '/api/svc/complaint/delete',
        json={'id': created['data']['id']},
    )
    assert deleted.status_code == 200
    assert deleted.get_json()['code'] == 0
```

Expected: 排序测试 FAIL；删除返回 404。

- [ ] **Step 4: 实现排序和删除**

`helpers.py`：

```python
order = str(params.get('order', 'DESC')).upper()
if order not in ('ASC', 'DESC'):
    order = 'DESC'
```

`svc.py`：

```python
@svc_bp.route('/api/svc/complaint/delete', methods=['POST'])
@login_required
def complaint_delete():
    return jsonify(crud_delete('svc_complaint', request.json.get('id')))
```

- [ ] **Step 5: 修复比较、菜单和状态显示**

- `crudLoad` 每次加载建立 `currentRowsById`。
- `crudEditById(id)` 从映射取对象。
- `compareRecords` 从映射取两个对象；任何对象缺失时显示错误而不是永久加载。
- `buildMenu` 对 `home:true` 使用 `MESUI.menuPage(m)`。
- 状态输出统一调用 `MESUI.statusHtml(f, value)`。
- `csDel` 只在 `r && r.code === 0` 时刷新，否则显示错误。

- [ ] **Step 6: 验证并提交**

运行：

```powershell
node --test tests/admin_ui_utils.test.js tests/admin_api.test.js
python -m pytest test_comprehensive.py -k "lowercase_sort or complaint_can_be_deleted" -q
python -m pytest -q
```

Expected: 全部 PASS。

提交：

```powershell
git add admin/static/js/api.js admin/static/js/crud.js admin/static/js/modal.js admin/static/js/menu.js admin/static/js/app.js backend/utils/helpers.py backend/blueprints/svc.py tests/admin_api.test.js test_comprehensive.py
git commit -m "fix: repair shared admin interactions"
```

---

### Task 5: 补齐八个页面所需后端 CRUD

**Files:**
- Modify: `backend/blueprints/warehouse.py`
- Modify: `backend/blueprints/eqp_schedule.py`
- Test: `test_comprehensive.py`

**Interfaces:**
- Adds: `POST /api/area/update`
- Adds: `POST /api/area/delete`
- Adds: `POST /api/location/update`
- Adds: `POST /api/location/delete`
- Adds: `POST /api/arrival/delete`
- Adds: `POST /api/qm/template/delete`
- Adds: `POST /api/sched/calendar/update`
- Adds: `POST /api/sched/calendar/delete`

- [ ] **Step 1: 写缺失 CRUD 路由失败测试**

创建 `class TestWarehouseScheduleCrud:` 并增加下列生命周期测试。每个测试使用 `uuid.uuid4().hex[:8]` 生成唯一的 `code` 或名称，避免会话级测试数据库中的唯一键冲突：

```python
def test_area_update_and_delete(self, auth_client):
    suffix = uuid.uuid4().hex[:8]
    warehouse = auth_client.post('/api/warehouse/add', json={
        'warehouse_name': '成品仓',
        'code': f'WH_{suffix}',
    }).get_json()['data']['id']
    area = auth_client.post('/api/area/add', json={
        'warehouse_id': warehouse,
        'area_name': 'A区',
        'code': f'AREA_{suffix}',
    }).get_json()['data']['id']

    updated = auth_client.post('/api/area/update', json={
        'id': area,
        'area_name': 'A1区',
    })
    assert updated.status_code == 200
    assert updated.get_json()['code'] == 0

    deleted = auth_client.post('/api/area/delete', json={'id': area})
    assert deleted.status_code == 200
    assert deleted.get_json()['code'] == 0


def test_location_update_and_delete(self, auth_client):
    suffix = uuid.uuid4().hex[:8]
    warehouse = response_id(auth_client.post('/api/warehouse/add', json={
        'warehouse_name': '库位测试仓',
        'code': f'WH_LOC_{suffix}',
    }))
    area = response_id(auth_client.post('/api/area/add', json={
        'warehouse_id': warehouse,
        'area_name': '库位测试区',
        'code': f'AREA_LOC_{suffix}',
    }))
    location = response_id(auth_client.post('/api/location/add', json={
        'area_id': area,
        'location_name': 'L01',
        'code': f'LOC_{suffix}',
    }))
    updated = auth_client.post('/api/location/update', json={
        'id': location,
        'location_name': 'L02',
    }).get_json()
    assert updated['code'] == 0
    assert auth_client.post(
        '/api/location/delete', json={'id': location}
    ).get_json()['code'] == 0


def test_arrival_delete(self, auth_client):
    arrival = response_id(auth_client.post('/api/arrival/add', json={
        'expected_date': '2026-07-29',
        'remark': '删除测试',
    }))
    deleted = auth_client.post('/api/arrival/delete', json={'id': arrival})
    assert deleted.status_code == 200
    assert deleted.get_json()['code'] == 0


def test_qm_template_delete(self, auth_client):
    template = response_id(auth_client.post('/api/qm/template/add', json={
        'template_name': f'来料模板-{uuid.uuid4().hex[:8]}',
        'inspect_type': 'incoming',
        'items': '[]',
    }))
    deleted = auth_client.post('/api/qm/template/delete', json={'id': template})
    assert deleted.status_code == 200
    assert deleted.get_json()['code'] == 0


def test_calendar_update_and_delete(self, auth_client):
    suffix = uuid.uuid4().hex[:8]
    team = response_id(auth_client.post('/api/sched/team/add', json={
        'team_name': f'日历班组-{suffix}',
        'code': f'TEAM_{suffix}',
    }))
    plan = response_id(auth_client.post('/api/sched/plan/add', json={
        'plan_name': f'白班-{uuid.uuid4().hex[:8]}',
        'team_id': team,
        'start_date': '2026-07-01',
        'end_date': '2026-07-31',
        'shift_type': 'day',
    }))
    calendar = response_id(auth_client.post('/api/sched/calendar/add', json={
        'plan_id': plan,
        'work_date': '2026-07-29',
        'shift_type': 'day',
    }))
    updated = auth_client.post('/api/sched/calendar/update', json={
        'id': calendar,
        'shift_type': 'night',
    }).get_json()
    assert updated['code'] == 0
    assert auth_client.post(
        '/api/sched/calendar/delete', json={'id': calendar}
    ).get_json()['code'] == 0
```

运行：

```powershell
python -m pytest test_comprehensive.py -k "area_update or location_update or arrival_delete or template_delete or calendar_update" -q
```

Expected: 所有缺失路由返回 404。

- [ ] **Step 2: 实现缺失 CRUD**

在 `warehouse.py` 增加：

```python
@warehouse_bp.route('/api/area/update', methods=['POST'])
@login_required
def area_update():
    return jsonify(crud_update('inv_area', request.json))

@warehouse_bp.route('/api/area/delete', methods=['POST'])
@login_required
def area_delete():
    return jsonify(crud_delete('inv_area', request.json.get('id')))


@warehouse_bp.route('/api/location/update', methods=['POST'])
@login_required
def location_update():
    return jsonify(crud_update('inv_location', request.json))


@warehouse_bp.route('/api/location/delete', methods=['POST'])
@login_required
def location_delete():
    return jsonify(crud_delete('inv_location', request.json.get('id')))


@warehouse_bp.route('/api/arrival/delete', methods=['POST'])
@login_required
def arrival_delete():
    return jsonify(crud_delete('inv_arrival_notice', request.json.get('id')))
```

在 `eqp_schedule.py` 增加：

```python
@eqp_schedule_bp.route('/api/qm/template/delete', methods=['POST'])
@login_required
def qm_template_delete():
    return jsonify(crud_delete('qm_inspect_template', request.json.get('id')))


@eqp_schedule_bp.route('/api/sched/calendar/update', methods=['POST'])
@login_required
def calendar_update():
    return jsonify(crud_update('sched_calendar', request.json))


@eqp_schedule_bp.route('/api/sched/calendar/delete', methods=['POST'])
@login_required
def calendar_delete():
    return jsonify(crud_delete('sched_calendar', request.json.get('id')))
```

库存事务保持只增只读。

- [ ] **Step 3: 验证并提交**

运行：

```powershell
python -m pytest test_comprehensive.py -k "area_update or location_update or arrival_delete or template_delete or calendar_update" -q
python -m pytest -q
```

Expected: 全部 PASS。

提交：

```powershell
git add backend/blueprints/warehouse.py backend/blueprints/eqp_schedule.py test_comprehensive.py
git commit -m "feat: complete warehouse and schedule CRUD APIs"
```

---

### Task 6: 接通八个管理页面

**Files:**
- Create: `admin/static/js/pages/warehouse_schedule.js`
- Modify: `admin/index.html:74-91`
- Modify: `admin/static/js/app.js:267-385`
- Modify: `admin/static/js/crud.js:13-16`
- Modify: `tests/admin_ui_utils.test.js`

**Interfaces:**
- Produces: `renderWarehousePage(el)`
- Produces: `renderAreaPage(el)`
- Produces: `renderLocationPage(el)`
- Produces: `renderArrivalPage(el)`
- Produces: `renderTransactionPage(el)`
- Produces: `renderQualityTemplatePage(el)`
- Produces: `renderCheckProjectPage(el)`
- Produces: `renderScheduleCalendarPage(el)`
- Extends: `renderCrud(el, path, cfg)` accepts `cfg.apiBase`
- Extends: `renderCrud(el, path, cfg)` accepts `cfg.actions`

- [ ] **Step 1: 写页面映射失败测试**

在 `tests/admin_ui_utils.test.js` 增加源契约测试：

```javascript
const fs = require('node:fs');

test('all announced pages have render mappings', () => {
  const app = fs.readFileSync('admin/static/js/app.js', 'utf8');
  [
    'warehouse/list',
    'warehouse/area',
    'warehouse/location',
    'warehouse/arrival',
    'warehouse/transaction',
    'qm/template',
    'eqp/check-project',
    'sched/calendar',
  ].forEach((key) => {
    assert.match(app, new RegExp(`['"]${key.replace('/', '\\/')}['"]\\s*:`));
  });
});
```

运行：

```powershell
node --test tests/admin_ui_utils.test.js
```

Expected: FAIL，八个键均缺少映射。

- [ ] **Step 2: 扩展通用渲染器显式 API 基址**

`crud.js`：

```javascript
function renderCrud(el, path, cfg) {
    curFields = cfg.f;
    curApiBase = cfg.apiBase || ('/api/' + path.split('/')[0] + '/' + path.split('/')[1]);
    curCrudActions = Object.assign(
        {add: true, edit: true, delete: true, import: true, export: true},
        cfg.actions || {}
    );
}
```

- 在 `modal.js` 顶部声明 `var curCrudActions = {};`。
- 标题栏只在相应 action 为 `true` 时生成新增、导入和导出按钮，绑定事件前检查元素是否存在。
- 表格“操作”列只生成允许的编辑、删除按钮；两者都不允许时不生成操作列及单元格。
- `crudLoad` 仍维护 Task 4 引入的 `currentRowsById`，编辑按钮使用 `crudEditById(row.id)`。

- [ ] **Step 3: 创建页面渲染模块**

`warehouse_schedule.js` 使用以下完整配置；所有 `apiBase` 必须与 Flask 路由完全一致：

```javascript
function renderWarehousePage(el) {
    renderCrud(el, 'warehouse/list', {
        t: '仓库设置',
        apiBase: '/api/warehouse',
        f: [
            {k: 'warehouse_name', l: '仓库名称', r: 1},
            {k: 'code', l: '仓库编码', r: 1},
            {k: 'address', l: '地址'},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]},
        ],
    });
}

function renderAreaPage(el) {
    renderCrud(el, 'warehouse/area', {
        t: '库区设置',
        apiBase: '/api/area',
        f: [
            {k: 'warehouse_id', l: '仓库', r: 1, type: 'select',
             api: '/api/warehouse/list?size=1000', vk: 'id', tk: 'warehouse_name'},
            {k: 'area_name', l: '库区名称', r: 1},
            {k: 'code', l: '库区编码', r: 1},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]},
        ],
    });
}

function renderLocationPage(el) {
    renderCrud(el, 'warehouse/location', {
        t: '库位设置',
        apiBase: '/api/location',
        f: [
            {k: 'area_id', l: '库区', r: 1, type: 'select',
             api: '/api/area/list', vk: 'id', tk: 'area_name'},
            {k: 'location_name', l: '库位名称', r: 1},
            {k: 'code', l: '库位编码', r: 1},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]},
        ],
    });
}

function renderArrivalPage(el) {
    renderCrud(el, 'warehouse/arrival', {
        t: '到货通知',
        apiBase: '/api/arrival',
        f: [
            {k: 'notice_no', l: '通知单号', generated: true},
            {k: 'supplier_id', l: '供应商', type: 'select',
             api: '/api/base/supplier/list?size=1000', vk: 'id', tk: 'supplier_name'},
            {k: 'expected_date', l: '预计到货日', type: 'date'},
            {k: 'status', l: '状态', s: [
                {v: 0, t: '待到货'}, {v: 1, t: '部分到货'}, {v: 2, t: '已完成'}
            ]},
            {k: 'remark', l: '备注'},
        ],
    });
}

function renderTransactionPage(el) {
    renderCrud(el, 'warehouse/transaction', {
        t: '库存事务',
        apiBase: '/api/transaction',
        actions: {edit: false, delete: false, import: false},
        f: [
            {k: 'trans_type', l: '事务类型', r: 1, s: [
                {v: 'IN', t: '入库'}, {v: 'OUT', t: '出库'},
                {v: 'MOVE', t: '移库'}, {v: 'ADJUST', t: '调整'}
            ]},
            {k: 'product_id', l: '产品', r: 1, type: 'select',
             api: '/api/base/product/all', vk: 'id', tk: 'product_name'},
            {k: 'quantity', l: '数量', r: 1, type: 'number'},
            {k: 'warehouse_id', l: '仓库', type: 'select',
             api: '/api/warehouse/list?size=1000', vk: 'id', tk: 'warehouse_name'},
            {k: 'area_id', l: '库区', type: 'select',
             api: '/api/area/list', vk: 'id', tk: 'area_name'},
            {k: 'location_id', l: '库位', type: 'select',
             api: '/api/location/list', vk: 'id', tk: 'location_name'},
            {k: 'batch_no', l: '批次号'},
            {k: 'ref_no', l: '关联单号'},
            {k: 'remark', l: '备注'},
        ],
    });
}

function renderQualityTemplatePage(el) {
    renderCrud(el, 'qm/template', {
        t: '质检模板',
        apiBase: '/api/qm/template',
        f: [
            {k: 'template_name', l: '模板名称', r: 1},
            {k: 'inspect_type', l: '检验类型', r: 1, s: [
                {v: 'incoming', t: '来料'}, {v: 'process', t: '过程'},
                {v: 'outgoing', t: '出货'}
            ]},
            {k: 'items', l: '检验项目 JSON'},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]},
        ],
    });
}

function renderCheckProjectPage(el) {
    renderCrud(el, 'eqp/check-project', {
        t: '设备点检项目',
        apiBase: '/api/eqp/check-project',
        f: [
            {k: 'project_name', l: '项目名称', r: 1},
            {k: 'check_type', l: '点检类型'},
            {k: 'standard', l: '点检标准'},
            {k: 'method', l: '点检方法'},
            {k: 'status', l: '状态', s: [{v: 1, t: '启用'}, {v: 0, t: '禁用'}]},
        ],
    });
}

function renderScheduleCalendarPage(el) {
    renderCrud(el, 'sched/calendar', {
        t: '排班日历',
        apiBase: '/api/sched/calendar',
        f: [
            {k: 'plan_id', l: '排班计划', r: 1, type: 'select',
             api: '/api/sched/plan/list', vk: 'id', tk: 'plan_name'},
            {k: 'work_date', l: '工作日期', r: 1, type: 'date'},
            {k: 'shift_type', l: '班次类型', s: [
                {v: 'day', t: '白班'}, {v: 'night', t: '夜班'}
            ]},
            {k: 'user_ids', l: '人员 ID（逗号分隔）'},
        ],
    });
}
```

`notice_no` 是后端生成字段：在 `openModalSync` 中跳过带 `generated: true` 的字段，表格中仍显示该字段。库存事务只允许新增、查询和导出，不生成编辑、删除及导入按钮。

- [ ] **Step 4: 注册脚本和页面映射**

在 `admin/index.html` 的 `app.js` 前加载：

```html
<script src="/admin/static/js/pages/warehouse_schedule.js"></script>
```

在 `app.js` 的 `special` 中加入八个键，对应调用八个渲染函数。

- [ ] **Step 5: 验证并提交**

运行：

```powershell
node --test tests/admin_ui_utils.test.js tests/admin_api.test.js
python -m pytest -q
```

启动临时数据库服务后，用浏览器逐个点击八个菜单，Expected: 标题和表格正确，页面不包含“页面建设中”。

提交：

```powershell
git add admin/index.html admin/static/js/app.js admin/static/js/crud.js admin/static/js/pages/warehouse_schedule.js tests/admin_ui_utils.test.js
git commit -m "feat: connect warehouse quality and schedule pages"
```

---

### Task 7: 让外部集成和 APS 返回真实状态

**Files:**
- Modify: `backend/blueprints/ai.py`
- Modify: `backend/blueprints/erp.py`
- Modify: `backend/blueprints/erp_deep.py`
- Modify: `backend/blueprints/aps.py`
- Modify: `backend/blueprints/sys_ext.py:389-393`
- Modify: `backend/blueprints/update.py:21-24`
- Test: `test_comprehensive.py`

**Interfaces:**
- AI 未配置: HTTP 503 / `code: 503`
- ERP 未实现: HTTP 501 / `code: 501`
- 通知测试未实现: HTTP 501 / `code: 501`
- 更新下载未实现: HTTP 501 / `code: 501`
- APS 预览: HTTP 200 / `mode: preview`

- [ ] **Step 1: 写外部模块状态失败测试**

```python
class TestIntegrationStatus:
    def test_ai_inspection_is_not_fake_success(self, auth_client):
        response = auth_client.post('/api/ai/inspect', json={})
        assert response.status_code == 503
        assert response.get_json()['code'] == 503

    def test_erp_sync_is_not_fake_success(self, auth_client):
        endpoints = [
            '/api/erp/sync/products',
            '/api/erp/sync/orders',
            '/api/erp/sync/inventory',
            '/api/erp/yonyou/sync',
            '/api/erp/kingdee/sync',
            '/api/erp/sap/sync',
        ]
        for endpoint in endpoints:
            response = auth_client.post(endpoint, json={
                'app_key': 'public-id',
                'app_secret': 'must-not-echo',
            })
            assert response.status_code == 501, endpoint
            payload = response.get_json()
            assert payload['code'] == 501
            assert 'must-not-echo' not in json.dumps(payload)

    def test_notification_channel_test_is_not_fake_success(self, auth_client):
        response = auth_client.post('/api/sys/notify-channel/test', json={'id': 1})
        assert response.status_code == 501

    def test_update_download_is_not_fake_success(self, client):
        response = client.get('/api/update/download')
        assert response.status_code == 501
        payload = response.get_json()
        assert payload['code'] == 501
        assert payload['data']['manual_url']
```

运行：

```powershell
python -m pytest test_comprehensive.py::TestIntegrationStatus -q
```

Expected: 全部 FAIL，当前返回 200 和 `code: 0`。

- [ ] **Step 2: 实现诚实错误响应**

未实现适配器统一响应形状：

```python
return jsonify({
    'code': 501,
    'message': '该集成适配器尚未实现',
}), 501
```

普通 ERP、用友、金蝶和 SAP 的六个同步路由使用 501 响应；通知渠道测试也使用 501。更新下载使用：

```python
return jsonify({
    'code': 501,
    'message': '自动下载尚未实现，请前往项目仓库手动下载',
    'data': {'manual_url': 'https://github.com/ko3899/mes-'},
}), 501
```

AI 配置 GET 从 `sys_config` 读取 `ai_enabled`、`ai_provider`、`ai_api_key` 和 `ai_model`；响应使用 `ai_api_key_configured: bool`，不返回原文。没有已实现适配器时检测接口返回 503。ERP 深度同步响应不再构造或回显 `app_secret`。

- [ ] **Step 3: 写 APS 预览失败测试**

把以下两个方法加入 `TestIntegrationStatus`：

```python
def test_aps_rejects_invalid_dates(self, auth_client):
    response = auth_client.post('/api/aps/schedule', json={
        'start_date': 'bad-date',
        'end_date': 'also-bad',
    })
    assert response.status_code == 400

def test_aps_returns_non_persistent_preview(self, auth_client):
    ids = create_production_chain(auth_client, planned_qty=10)
    before = auth_client.get('/api/prod/workorder/list?size=100').get_json()
    response = auth_client.post('/api/aps/schedule', json={
        'start_date': '2026-07-28',
        'end_date': '2026-07-31',
    })
    assert response.get_json()['data']['mode'] == 'preview'
    assert response.get_json()['data']['details'][0]['status'] == '待排程'
    after = auth_client.get('/api/prod/workorder/list?size=100').get_json()
    assert find_by_id(before, ids['workorder_id'])['status'] == find_by_id(
        after, ids['workorder_id']
    )['status']
```

Expected: 无效日期测试 FAIL；预览缺少 mode 且谎称已排程。

- [ ] **Step 4: 实现 APS 预览**

用 `datetime.date.fromisoformat` 校验日期；开始日期晚于结束日期返回 400。响应：

```python
return jsonify({'code': 0, 'data': {
    'mode': 'preview',
    'start_date': start_date.isoformat(),
    'end_date': end_date.isoformat(),
    'scheduled': 0,
    'candidates': len(details),
    'details': details,
}})
```

每个详情项状态为“待排程”，函数不执行 INSERT 或 UPDATE。

- [ ] **Step 5: 验证并提交**

运行：

```powershell
python -m pytest test_comprehensive.py::TestIntegrationStatus -q
python -m pytest test_comprehensive.py -k "aps_" -q
python -m pytest -q
```

Expected: 全部 PASS。

提交：

```powershell
git add backend/blueprints/ai.py backend/blueprints/erp.py backend/blueprints/erp_deep.py backend/blueprints/aps.py backend/blueprints/sys_ext.py backend/blueprints/update.py test_comprehensive.py
git commit -m "fix: report honest integration capability states"
```

---

### Task 8: 全量验证和浏览器回归

**Files:**
- Modify only if verification exposes a regression in files already in scope.

**Interfaces:**
- Consumes all prior task outputs.
- Produces a clean, fully tested stabilization branch.

- [ ] **Step 1: 运行完整自动化测试**

```powershell
python -m pytest -q
node --test tests/admin_ui_utils.test.js tests/admin_api.test.js
python -m compileall -q backend
```

Expected: pytest 全部 PASS；Node 全部 PASS；Python 编译退出码 0。

- [ ] **Step 2: 检查所有 JavaScript 语法**

```powershell
$node='C:\Users\huang\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
Get-ChildItem -LiteralPath 'admin\static\js' -Recurse -Filter '*.js' |
    ForEach-Object { & $node --check $_.FullName }
```

Expected: 所有文件退出码 0，无语法错误。

- [ ] **Step 3: 临时数据库浏览器冒烟测试**

使用测试数据库启动 18080 端口，验证：

1. 普通用户系统写操作显示 403。
2. 插入 `<b>HTML_INJECTION</b>` 后表格显示字面文本，不创建 `<b>` 元素。
3. 报工后任务和工单进度立即更新。
4. 扫描不存在的 WO/TK 显示“未找到”，不显示其他记录。
5. 新增后列表立即出现新记录。
6. 两条记录比较显示对比表。
7. 数据看板和消息通知进入正确页面。
8. 八个补齐菜单均显示可操作页面。
9. 客诉删除后记录消失。

- [ ] **Step 4: 检查工作树和提交历史**

```powershell
git diff --check
git status --short
git log --oneline -10
```

Expected: 无空白错误；没有测试产生的数据库、日志或截图进入 Git；提交按任务边界清晰。

- [ ] **Step 5: 请求独立代码审查**

使用 `requesting-code-review`，范围从设计提交 `9508021` 的父提交到当前 HEAD。审查重点：

- 权限是否存在绕过路径。
- 报工事务是否可能重复累计或产生嵌套事务。
- XSS 转义是否覆盖值、属性和事件处理。
- 八个页面的 API 基址是否与 Flask 路由一致。
- 501/503 状态是否被前端正确展示。

- [ ] **Step 6: 处理审查问题并最终提交**

对 Critical 和 Important 问题补失败测试后修复，重新运行步骤 1-4。最终状态必须是测试全绿且工作树干净。
