# MES Manual Record Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 MES 全部记录型业务列表增加可持久化的上移、下移和移动到全局指定位置功能。

**Architecture:** 新增独立 `sys_table_order` 表和白名单驱动的统一排序服务，不修改各业务表结构。前端在已有统一表格增强器中识别记录 ID、加载位置映射、增加顺序列与操作按钮；通用 CRUD 和自定义业务表共享同一套交互。

**Tech Stack:** Flask、SQLite、原生 JavaScript、Node `node:test`、Python `unittest`、in-app browser。

## Global Constraints

- 不删除、不清理现有业务记录和已保留测试数据。
- 只覆盖具有稳定整数主键的记录型业务列表；统计、图表、看板和摘要表排除。
- `table_key` 必须经过服务端固定白名单映射，禁止客户端提供原始 SQL 表名。
- 手工位置为模块全量位置，从 1 开始且连续。
- 字段升降序激活时禁止手工调整，恢复默认顺序后才能操作。
- 不引入新的前端框架或运行时依赖。

---

### Task 1: 顺序表与纯排序服务

**Files:**
- Modify: `backend/utils/database.py`
- Create: `backend/utils/table_order.py`
- Test: `tests/test_table_order.py`

**Interfaces:**
- Produces `ORDERABLE_TABLES: dict[str, str]`，将页面键映射到固定业务表。
- Produces `ordered_ids(db, table_key) -> list[int]`、`move_record(db, table_key, record_id, target_position) -> list[int]`、`step_record(db, table_key, record_id, direction) -> list[int]`。

- [ ] **Step 1: Write the failing test**

```python
def test_move_ninth_record_to_sixth():
    ids = list(range(1, 11))
    result = reorder_ids(ids, 9, 6)
    assert result == [1, 2, 3, 4, 5, 9, 6, 7, 8, 10]

def test_target_position_is_clamped():
    assert reorder_ids([1, 2, 3], 2, 99) == [1, 3, 2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_table_order -v`
Expected: FAIL because `backend.utils.table_order` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `reorder_ids(ids, record_id, target_position)` as a pure function; create `sys_table_order` with unique `(table_key, record_id)` and index `(table_key, position)` in database initialization. `ordered_ids` reads valid IDs from the whitelisted table, uses stored positions first and appends unpositioned IDs by descending ID.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_table_order -v`
Expected: PASS for move, step, clamping, missing record and consecutive positions.

- [ ] **Step 5: Commit**

```powershell
git add backend/utils/database.py backend/utils/table_order.py tests/test_table_order.py
git commit -m "feat: add persistent table order service"
```

### Task 2: 统一手工排序 API

**Files:**
- Create: `backend/blueprints/table_order.py`
- Modify: `backend/app.py`
- Test: `tests/test_table_order_api.py`

**Interfaces:**
- `GET /api/table-order/<path:table_key>` returns `{positions, total}`.
- `POST /api/table-order/move` consumes `{table_key, record_id, target_position}`.
- `POST /api/table-order/step` consumes `{table_key, record_id, direction}` where direction is `up|down`.

- [ ] **Step 1: Write the failing test**

Create a temporary application database, log in with the test client, seed ten workorders, call move with record 9 and target 6, then assert the returned ID sequence is `[10, 8, 7, 6, 5, 9, 4, 3, 2, 1]` for the default descending-ID list. Assert an unknown `table_key` returns 400.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_table_order_api -v`
Expected: FAIL with 404 for the missing endpoints.

- [ ] **Step 3: Write minimal implementation**

Register `table_order_bp`; validate JSON integer fields and direction; call the service inside SQLite transactions; return 400 for invalid module/position/direction and 404 for a missing record. Include `positions` as string-keyed JSON mapping and `ordered_ids` in successful responses.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_table_order_api -v`
Expected: PASS for authentication, whitelist, move, step and boundary behavior.

- [ ] **Step 5: Commit**

```powershell
git add backend/blueprints/table_order.py backend/app.py tests/test_table_order_api.py
git commit -m "feat: expose manual table order API"
```

### Task 3: 列表接口应用手工默认顺序

**Files:**
- Modify: `backend/utils/helpers.py`
- Modify: `backend/blueprints/production.py`
- Modify: `backend/utils/table_order.py`
- Test: `tests/test_table_order.py`

**Interfaces:**
- Produces `manual_order_clause(table_key, id_expression='id') -> str` for whitelisted SQL queries.
- Generic `crud_list` receives an optional `table_key`; custom production lists use `manual_order_clause` only when `sort` is empty.

- [ ] **Step 1: Write the failing test**

Seed stored positions, request the workorder list without `sort`, and assert it follows manual order. Request `sort=planned_qty&order=ASC` and assert field sorting overrides manual order.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_table_order -v`
Expected: FAIL because list queries still use `id DESC`.

- [ ] **Step 3: Write minimal implementation**

For default ordering use a correlated `COALESCE((SELECT position FROM sys_table_order WHERE table_key=? AND record_id=<id>), 2147483647), <id> DESC` expression with a bound `table_key`. Keep existing allowlisted field sorting unchanged when `sort` is present. Pass stable page keys from generic and core production endpoints.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_table_order -v` and `node --test tests/production_sort_api.test.js`
Expected: PASS; explicit field sorting remains unchanged.

- [ ] **Step 5: Commit**

```powershell
git add backend/utils/helpers.py backend/blueprints/production.py backend/utils/table_order.py tests/test_table_order.py
git commit -m "feat: apply manual order to default list queries"
```

### Task 4: 全部记录表的顺序列与操作

**Files:**
- Modify: `admin/static/js/ui_utils.js`
- Modify: `admin/static/js/crud.js`
- Modify: `admin/static/js/app.js`
- Modify: `admin/static/css/style.css`
- Test: `tests/admin_manual_table_order.test.js`

**Interfaces:**
- `MESUI.manualOrderRegistry` maps current page key to service `table_key` and record-ID column index.
- `MESUI.enableManualTableOrder(root, pageKey, options)` adds the position column and buttons.
- Global `moveTableRecord(tableKey, recordId, targetPosition)` and `stepTableRecord(tableKey, recordId, direction)` call the API and reload the current page.

- [ ] **Step 1: Write the failing test**

```js
test('manual order registry covers every record page', () => {
  assert.equal(MESUI.manualOrderRegistry['prod/workorder'].tableKey, 'prod/workorder');
  assert.equal(typeof MESUI.enableManualTableOrder, 'function');
});

test('field sorting disables manual movement', () => {
  assert.equal(MESUI.canAdjustManualOrder({field: 'planned_qty', order: 'ASC'}), false);
  assert.equal(MESUI.canAdjustManualOrder({field: '', order: ''}), true);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/admin_manual_table_order.test.js`
Expected: FAIL because the registry and enhancer do not exist.

- [ ] **Step 3: Write minimal implementation**

Add a compact “顺序” cell showing `#6`, `↑`, `↓`, and “移到”. For generic CRUD rows use existing `row.id`; for custom tables add `data-record-id` by reading the configured ID cell. Fetch the position map once per rendered page. Clicking “移到” opens a numeric prompt labeled “全局位置”; successful move reloads the same page. Disable controls while `sortField` is non-empty and show the required explanation in `title` and alert.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/admin_manual_table_order.test.js tests/admin_table_sort.test.js tests/admin_custom_tables_sort.test.js`
Expected: PASS for rendering, API payloads, disabled state and XSS escaping.

- [ ] **Step 5: Commit**

```powershell
git add admin/static/js/ui_utils.js admin/static/js/crud.js admin/static/js/app.js admin/static/css/style.css tests/admin_manual_table_order.test.js
git commit -m "feat: add manual order controls to record tables"
```

### Task 5: 文档、回归与无删除浏览器验收

**Files:**
- Modify: `docs/MES工厂管家_使用手册.md`
- Test: all existing test suites and browser checklist

- [ ] **Step 1: Write the failing test**

Extend `tests/admin_manual_table_order.test.js` to assert the manual contains “移动到全局位置” and explains that field sorting must first be restored to default.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/admin_manual_table_order.test.js`
Expected: FAIL until documentation is updated.

- [ ] **Step 3: Write minimal implementation**

Document the three controls, global position semantics, pagination, persistence and interaction with field sorting. In the browser, use existing retained workorder rows only: move one record to another position, refresh and verify persistence; do not delete or create records.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/*.test.js`, `python -m unittest discover -s tests -p 'test*.py'`, `python -m py_compile backend/blueprints/table_order.py backend/utils/table_order.py`.
Expected: all automated tests pass; browser confirms position persistence after refresh.

- [ ] **Step 5: Commit**

```powershell
git add docs/MES工厂管家_使用手册.md tests/admin_manual_table_order.test.js
git commit -m "docs: explain manual record ordering"
```

## Self-review checklist

- [x] The ninth-to-sixth example is covered by a pure unit test and browser acceptance.
- [x] Persistence, global pagination position, whitelist security and field-sort conflict are covered.
- [x] No task deletes or cleans existing data.
- [x] Function names and JSON fields are consistent across backend and frontend tasks.
- [x] Charts, dashboards and summary tables are explicitly excluded.
