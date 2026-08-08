# MES Unified Table Sorting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 MES 中所有记录型列表提供统一、可持续的升降序排序交互，并保持现有业务默认顺序。

**Architecture:** 在 `MESUI` 增加可测试的排序纯函数和表头渲染工具；通用 CRUD 复用后端 `sort/order`，自定义页面使用页面级状态对已加载数组排序，生产核心分页接口增加排序白名单。通过静态单测、API 测试和浏览器验收覆盖。

**Tech Stack:** 原生 JavaScript、Flask/SQLite、Node `node:test`、Python `unittest`/现有测试、Playwright/in-app browser。

## Global Constraints

- 不删除、清理或重置现有业务数据；新增测试数据必须带“测试”备注并保留。
- 不引入新的前端框架或运行时依赖。
- 未主动排序时保持各页面当前默认顺序。
- 只给记录型表格增加排序，KPI/图表/看板摘要不增加排序按钮。
- 所有服务端排序字段必须经过白名单校验，方向只允许 `ASC` 或 `DESC`。

---

### Task 1: 可测试的统一排序工具

**Files:**
- Modify: `admin/static/js/ui_utils.js`
- Test: `tests/admin_table_sort.test.js`

**Interfaces:**
- Produces `MESUI.sortRows(rows, field, order, type)`、`MESUI.nextSortState(state, field)`、`MESUI.sortHeaderHtml(field, label, state)`。
- `sortRows` 返回新数组；空值始终排在末尾；`type` 支持 `text|number|date|status`。

- [ ] **Step 1: Write the failing test**

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const MESUI = require('../admin/static/js/ui_utils.js');

test('sortRows orders numeric values ascending and keeps nulls last', () => {
  const rows = [{id: 1, qty: null}, {id: 2, qty: 10}, {id: 3, qty: 2}];
  assert.deepEqual(MESUI.sortRows(rows, 'qty', 'ASC', 'number').map(r => r.id), [3, 2, 1]);
});

test('nextSortState cycles field ASC, DESC, then default', () => {
  assert.deepEqual(MESUI.nextSortState({field: '', order: ''}, 'name'), {field: 'name', order: 'ASC'});
  assert.deepEqual(MESUI.nextSortState({field: 'name', order: 'ASC'}, 'name'), {field: 'name', order: 'DESC'});
  assert.deepEqual(MESUI.nextSortState({field: 'name', order: 'DESC'}, 'name'), {field: '', order: ''});
});

test('sortHeaderHtml exposes an accessible button and active direction', () => {
  const html = MESUI.sortHeaderHtml('qty', '计划数', {field: 'qty', order: 'DESC'});
  assert.match(html, /data-sort-field="qty"/);
  assert.match(html, /aria-sort="descending"/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/admin_table_sort.test.js`
Expected: FAIL because the three `MESUI` functions do not exist.

- [ ] **Step 3: Write minimal implementation**

Add the three pure functions to the returned `MESUI` object. Compare normalized values, use `localeCompare` with `zh-CN` for text, and return escaped header labels with a button carrying `data-sort-field` and `aria-sort`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/admin_table_sort.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add admin/static/js/ui_utils.js tests/admin_table_sort.test.js
git commit -m "feat: add shared table sorting helpers"
```

### Task 2: 通用 CRUD 表头和状态

**Files:**
- Modify: `admin/static/js/crud.js`
- Modify: `admin/static/css/style.css`
- Test: `tests/admin_table_sort.test.js`

**Interfaces:** 使用 Task 1 的 `MESUI.sortHeaderHtml` 和 `MESUI.nextSortState`；保留现有 `sortTable(field)` 全局入口。

- [ ] **Step 1: Write the failing test**

在现有静态测试中读取 `crud.js`，断言重置同时清空 `sortField`/`sortOrder`，表头生成包含 `aria-sort` 和方向指示符。

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/admin_table_sort.test.js`
Expected: FAIL against the current CRUD source.

- [ ] **Step 3: Write minimal implementation**

用共享表头生成器输出字段按钮；实现三态切换并在 `crudLoad` 请求中继续传递当前状态；重置同时恢复空字段和默认 `DESC`；增加紧凑、可聚焦的 `.table-sort-button` 样式。

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/admin_table_sort.test.js` and `python -m unittest discover -s tests -p 'test*.py'`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add admin/static/js/crud.js admin/static/css/style.css tests/admin_table_sort.test.js
git commit -m "feat: standardize CRUD table sort controls"
```

### Task 3: 生产核心分页接口

**Files:**
- Modify: `backend/blueprints/production.py`
- Test: `tests/test_table_sort_api.py`

**Interfaces:** `GET /api/prod/workorder/list`, `/api/prod/task/list`, `/api/prod/report/list` accept `sort` and `order`; invalid values fall back to the endpoint default.

- [ ] **Step 1: Write the failing test**

调用三个列表接口，验证 `sort=planned_qty&order=ASC`、`sort=created_at&order=DESC` 改变结果顺序，并验证 `sort=not_a_column&order=DROP` 不报错且不改变默认结果。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_table_sort_api.py -v`
Expected: FAIL because custom production list endpoints ignore sorting.

- [ ] **Step 3: Write minimal implementation**

为每个接口定义固定字段映射（例如 `id`, `order_no`, `product_name`, `planned_qty`, `status`, `priority`, `created_at`），只在映射命中时拼接已验证的列名和 `ASC/DESC`，否则使用现有 `id DESC`。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_table_sort_api.py -v` and the existing production tests.
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/blueprints/production.py tests/test_table_sort_api.py
git commit -m "feat: support safe sorting for production lists"
```

### Task 4: 自定义业务表统一接入

**Files:**
- Modify: `admin/static/js/pages/business.js`, `extensions.js`, `final1.js`, `final2.js`, `final3.js`
- Modify: `admin/static/js/pages/more.js`, `more2.js`, `more3.js`, `process_ctrl.js`
- Modify: `admin/static/js/pages/prod_ext.js`, `qm_ext.js`, `query.js`, `stage.js`, `flow_spc.js`, `sys_ext.js`
- Modify: `admin/static/js/pages/warehouse_schedule.js`
- Test: `tests/admin_custom_tables_sort.test.js`

**Interfaces:** Each record-table renderer keeps a page-local `{field, order}` state, uses `MESUI.sortRows` before rendering, and renders headers with `MESUI.sortHeaderHtml`; dashboard summaries remain unchanged.

- [ ] **Step 1: Write the failing test**

Scan the listed page modules and assert each record-table renderer references `MESUI.sortHeaderHtml` or the shared table sort binding, while summary-only renderers are excluded.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/admin_custom_tables_sort.test.js`
Expected: FAIL with the names of modules still using static sortable-table headers.

- [ ] **Step 3: Write minimal implementation**

Add a small page helper in `ui_utils.js` for binding `[data-sort-field]` buttons, then migrate record tables in groups: production/inventory, quality/equipment, master data/system, and warehouse/process extensions. Keep API payloads unchanged for non-paginated tables and sort the response array locally.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/admin_custom_tables_sort.test.js` and the full static test suite.
Expected: PASS with no summary/card regressions.

- [ ] **Step 5: Commit**

```powershell
git add admin/static/js tests/admin_custom_tables_sort.test.js
git commit -m "feat: add sorting to custom business tables"
```

### Task 5: 文档、回归与浏览器验收

**Files:**
- Modify: `docs/MES工厂管家_使用手册.md`
- Test: existing Node/Python suites and browser acceptance checklist

- [ ] **Step 1: Write the failing test**

Add a documentation assertion that the manual contains the new “表格排序” workflow and default/reset behavior.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/admin_table_sort.test.js tests/admin_custom_tables_sort.test.js`
Expected: FAIL until the manual and all renderers are updated.

- [ ] **Step 3: Write minimal implementation**

Document: click field header once for ASC, twice for DESC, third time restores default; search, refresh and pagination preserve the current sort; reset restores business default. Use the running local server and existing retained test rows for browser checks; do not create or delete data.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/*.test.js`, `python -m unittest discover -s tests -p 'test*.py'`, then browser-check workorder, inventory, quality, equipment and one generic CRUD page.
Expected: all automated tests pass and each page visibly changes row order with the arrow state.

- [ ] **Step 5: Commit**

```powershell
git add docs/MES工厂管家_使用手册.md
git commit -m "docs: document table sorting workflow"
```

## Self-review checklist

- [x] Spec requirements map to Tasks 1-5.
- [x] No destructive data operation is included.
- [x] Sorting APIs and helper names are consistent across tasks.
- [x] Tests are specified before implementation for every behavior change.
- [x] Summary cards and charts are explicitly excluded.
