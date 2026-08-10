# MES Production Business Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an order-driven MES flow from sales-order lines through plans, production batches, frozen work-order routing/BOM snapshots, tasks, material issuing, reporting, transfer, inventory, and traceability.

**Architecture:** Keep the existing Flask/SQLite and vanilla JavaScript application, but move production invariants into a focused `production_flow` service so blueprints only parse requests and serialize responses. Existing route URLs remain compatible. Add idempotent SQLite migrations and render the missing production pages with the current enterprise-blue components.

**Tech Stack:** Python 3, Flask, SQLite, vanilla JavaScript, Node `node:test`, Python `pytest`/`unittest`.

## Global Constraints

- Do not delete, reset, or rewrite existing business or test data.
- Keep real database primary keys stable and hidden; preserve the existing display-order ID behavior.
- New acceptance records must include the remark `生产业务链测试` and remain in the database.
- New and edited processes require a workshop; legacy blank workshop rows remain readable.
- Released work orders use frozen routing and BOM snapshots and cannot be changed by later master-data edits.
- Business transitions use explicit actions and audit logs, not arbitrary status-field edits.
- Existing API URLs used by the admin and collector clients must remain available.
- Every production change follows RED → GREEN → full regression.

---

## File Structure

- Create `backend/services/production_flow.py`: transaction boundaries, validation, snapshot creation, quantity calculations, status transitions, material issue and report posting.
- Create `backend/services/__init__.py`: service package marker.
- Create `admin/static/js/pages/production_chain.js`: missing sales, plan, route, task and report pages plus shared dependent-select and line-editor helpers.
- Modify `backend/utils/database.py`: idempotent schema migrations and indexes.
- Modify `backend/blueprints/base_data.py`: workshop-aware process and versioned route APIs.
- Modify `backend/blueprints/production.py`: order, plan, batch, work-order, task and report endpoints.
- Modify `backend/blueprints/prod_ext.py`: controlled transfer and material issue endpoints.
- Modify `admin/static/js/pages/business.js`: enhanced work-order page.
- Modify `admin/static/js/pages/extensions.js`: required workshop process page.
- Modify `admin/static/js/pages/prod_ext.js`: enhanced material and transfer pages.
- Modify `admin/static/js/app.js`: safe module rendering and production page registration.
- Modify `admin/index.html`: load `production_chain.js` before `app.js`.
- Create focused Python and Node tests listed below.

---

### Task 1: Prevent stale pages and restore the five missing modules

**Files:**
- Create: `tests/admin_production_chain.test.js`
- Create: `admin/static/js/pages/production_chain.js`
- Modify: `admin/static/js/app.js`
- Modify: `admin/index.html`

**Interfaces:**
- Produces global renderers `renderSales(el)`, `renderPlan(el)`, `renderRoute(el)`, `renderTask(el)`, `renderReport2(el)`.
- Produces `renderModuleError(el, title, error)` used by `renderPage` when a renderer throws.

- [ ] **Step 1: Write the failing renderer and stale-page tests**

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('every special production renderer is defined', () => {
  const source = fs.readFileSync(
    path.join(__dirname, '../admin/static/js/pages/production_chain.js'),
    'utf8'
  );
  ['renderSales','renderPlan','renderRoute','renderTask','renderReport2']
    .forEach(name => assert.match(source, new RegExp('function\\s+' + name + '\\s*\\(')));
});

test('renderPage clears stale content and renders an error card on failure', () => {
  const app = fs.readFileSync('admin/static/js/app.js', 'utf8');
  assert.match(app, /el\.replaceChildren\(\)/);
  assert.match(app, /renderModuleError\(el/);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test tests/admin_production_chain.test.js`

Expected: FAIL because `production_chain.js` and all five renderers are absent.

- [ ] **Step 3: Implement safe dispatch and semantic page shells**

Use this dispatch boundary in `renderPage`:

```js
el.replaceChildren();
try {
    if(special[key]) special[key](el);
    else if(configs[key]) renderCrud(el, key, configs[key]);
    else el.innerHTML = '<div class="card"><div class="card-title">页面建设中...</div></div>';
} catch(error) {
    renderModuleError(el, menuTitleFor(key), error);
}
```

Each new renderer must immediately render its own title, toolbar and loading row before starting API calls. Load `/admin/static/js/pages/production_chain.js` immediately before `/admin/static/js/app.js`.

- [ ] **Step 4: Run focused and existing admin tests**

Run: `node --test tests/admin_production_chain.test.js tests/admin_ui_design.test.js tests/admin_ui_utils.test.js`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/admin_production_chain.test.js admin/static/js/pages/production_chain.js admin/static/js/app.js admin/index.html
git commit -m "fix: restore production module pages"
```

### Task 2: Add backward-compatible production-chain schema

**Files:**
- Create: `tests/test_production_chain_migration.py`
- Create: `tests/production_chain_support.py`
- Modify: `backend/utils/database.py`
- Modify: `backend/utils/table_order.py`

**Interfaces:**
- Produces tables `prod_batch`, `prod_workorder_route_snapshot`, `prod_workorder_route_step`, `prod_workorder_bom_snapshot`, `sys_business_status_log`.
- Adds `base_process_route(workshop_id, version)` and `base_process_route_detail(workshop_id, is_inspection_point)`.
- Adds `prod_workorder(production_batch_id, route_version, bom_version)` and `prod_task(route_step_id)`.
- Adds controlled material fields to `prod_material_req` and `approval_status`, `defect_id`, `posted_at` to `prod_report`.
- Test support produces `create_legacy_db(path)`, `column_names(db, table)`, `table_names(db)`, `seed_reference_data(db)`, and `authenticated_test_client(db)` for later tasks.

- [ ] **Step 1: Write failing migration tests against a legacy database**

```python
def test_extra_migration_preserves_legacy_rows_and_adds_snapshots(tmp_db):
    seed_legacy_production_schema(tmp_db)
    tmp_db.execute("INSERT INTO base_process(process_name,code) VALUES('旧工序','OLD')")
    run_extra_migration(tmp_db)
    assert tmp_db.execute("SELECT process_name FROM base_process").fetchone()[0] == '旧工序'
    assert {'prod_batch', 'prod_workorder_route_snapshot',
            'prod_workorder_route_step', 'prod_workorder_bom_snapshot',
            'sys_business_status_log'} <= table_names(tmp_db)
    assert 'production_batch_id' in column_names(tmp_db, 'prod_workorder')
```

- [ ] **Step 2: Run the migration test and verify RED**

Run: `python -m pytest tests/test_production_chain_migration.py -q`

Expected: FAIL because snapshot and batch tables do not exist.

- [ ] **Step 3: Implement idempotent migrations**

Add a reusable helper:

```python
def _add_column_if_missing(db, table, column, definition):
    columns = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
    if column not in columns:
        db.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')
```

Create the five tables with foreign keys, timestamps and these uniqueness rules:

```sql
UNIQUE(prod_batch.plan_item_id, prod_batch.batch_no)
UNIQUE(prod_workorder_route_snapshot.workorder_id)
UNIQUE(prod_workorder_route_step.snapshot_id, prod_workorder_route_step.step_no)
UNIQUE(prod_workorder_bom_snapshot.workorder_id, prod_workorder_bom_snapshot.material_id)
```

Add indexes for all foreign keys and add `prod/batch` to `ORDERABLE_TABLES`.

- [ ] **Step 4: Verify idempotency and full database tests**

Run: `python -m pytest tests/test_production_chain_migration.py tests/test_table_order.py -q`

Expected: PASS when migration runs twice and legacy rows remain.

- [ ] **Step 5: Commit**

```bash
git add tests/test_production_chain_migration.py tests/production_chain_support.py backend/utils/database.py backend/utils/table_order.py
git commit -m "feat: add production chain snapshot schema"
```

### Task 3: Implement production-flow service invariants

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/production_flow.py`
- Create: `tests/test_production_flow_service.py`

**Interfaces:**
- `save_sales_order(db, payload, user_id) -> dict`
- `save_plan(db, payload, user_id) -> dict`
- `save_batch(db, payload, user_id) -> dict`
- `save_workorder(db, payload, user_id) -> dict`
- `release_workorder(db, workorder_id, user_id, remark='') -> dict`
- `generate_tasks(db, workorder_id, user_id) -> list[dict]`
- `generate_material_requirements(db, workorder_id, user_id) -> list[dict]`
- `issue_material(db, request_id, quantity, warehouse_id, location_id, batch_no, user_id) -> dict`
- `post_report(db, report_id, user_id, remark='') -> dict`
- `transition_status(db, entity_type, entity_id, target_status, user_id, remark='') -> dict`

- [ ] **Step 1: Write failing transaction and invariant tests**

```python
def test_sales_order_rolls_back_header_when_a_line_is_invalid(db):
    with pytest.raises(BusinessError, match='产品明细数量必须大于0'):
        save_sales_order(db, {
            'customer_id': 1,
            'delivery_date': '2026-08-20',
            'items': [{'product_id': 1, 'quantity': 0, 'unit_price': 10}],
        }, 1)
    assert db.execute('SELECT COUNT(*) FROM prod_sales_order').fetchone()[0] == 0

def test_released_workorder_keeps_route_and_bom_snapshots_after_master_changes(db):
    result = release_workorder(db, seeded_workorder_id, 1)
    before = frozen_snapshot(db, seeded_workorder_id)
    mutate_route_and_bom_master(db)
    assert frozen_snapshot(db, seeded_workorder_id) == before
    assert result['route_steps'] == 3

def test_batch_total_cannot_exceed_plan_line_remaining_quantity(db):
    with pytest.raises(BusinessError, match='超过计划明细剩余数量'):
        save_batch(db, {'plan_item_id': 1, 'planned_qty': 101}, 1)
```

- [ ] **Step 2: Run service tests and verify RED**

Run: `python -m pytest tests/test_production_flow_service.py -q`

Expected: collection FAIL because the service does not exist.

- [ ] **Step 3: Implement one explicit transaction per operation**

Use `BusinessError(message, status=400, details=None)`. Each public write function executes `BEGIN IMMEDIATE`, validates all foreign keys and quantities, writes header and lines, commits once, and rolls back on every exception.

Define status constants without changing historical semantics silently:

```python
SALES = {'draft': 0, 'confirmed': 1, 'producing': 2, 'completed': 3, 'cancelled': 4}
PLAN = {'draft': 0, 'released': 1, 'producing': 2, 'completed': 3, 'cancelled': 4}
BATCH = {'draft': 0, 'scheduled': 1, 'producing': 2, 'completed': 3, 'cancelled': 4}
WORKORDER = {'draft': 0, 'released': 1, 'producing': 2, 'completed': 3, 'paused': 4, 'closed': 5, 'cancelled': 6}
TASK = {'pending': 0, 'running': 1, 'paused': 2, 'completed': 3}
REPORT = {'submitted': 0, 'approved': 1, 'posted': 2, 'rejected': 3}
```

`release_workorder` copies route header/details and BOM rows using only the selected product, route and workshop. `transition_status` validates an allow-list graph and appends `sys_business_status_log` in the same transaction.

- [ ] **Step 4: Run service tests**

Run: `python -m pytest tests/test_production_flow_service.py -q`

Expected: all PASS, including rollback, snapshot immutability and invalid transition cases.

- [ ] **Step 5: Commit**

```bash
git add backend/services tests/test_production_flow_service.py
git commit -m "feat: add production flow domain service"
```

### Task 4: Make processes and routes workshop-safe

**Files:**
- Create: `tests/test_process_route_api.py`
- Modify: `backend/blueprints/base_data.py`
- Modify: `admin/static/js/pages/extensions.js`
- Modify: `admin/static/js/pages/production_chain.js`

**Interfaces:**
- `GET /api/base/process/list?workshop_id={workshop_id}&status=1`
- `POST /api/base/process/add|update` requires `workshop_id`.
- `GET /api/base/route/list?product_id={product_id}&workshop_id={workshop_id}` returns headers with ordered `steps`.
- `POST /api/base/route/save` accepts `{id?, route_name, product_id, workshop_id, version, status, description, steps:[{process_id, workshop_id, standard_time, is_inspection_point, description}]}`.

- [ ] **Step 1: Write failing API tests**

```python
def test_new_process_requires_workshop(client):
    response = client.post('/api/base/process/add', json={'process_name':'测试','code':'P1'})
    assert response.status_code == 400
    assert response.get_json()['message'] == '所属车间必填'

def test_route_rejects_process_from_another_workshop(client):
    response = client.post('/api/base/route/save', json=route_with_cross_workshop_step())
    assert response.status_code == 400
    assert '不属于路线车间' in response.get_json()['message']
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_process_route_api.py -q`

Expected: FAIL because workshop filtering and route save do not exist.

- [ ] **Step 3: Implement validated route transactions and UI**

Reject deletion when `base_process_route_detail.process_id` references a process. Render filters for workshop, keyword and status. Route editor uses a line table with step number, workshop, filtered process, standard time and inspection-point checkbox; every dynamic value passes through `MESUI.escapeHtml`.

- [ ] **Step 4: Run Python and Node focused tests**

Run: `python -m pytest tests/test_process_route_api.py -q`

Run: `node --test tests/admin_production_chain.test.js tests/admin_ui_utils.test.js`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_process_route_api.py backend/blueprints/base_data.py admin/static/js/pages/extensions.js admin/static/js/pages/production_chain.js
git commit -m "feat: enforce workshop-safe process routes"
```

### Task 5: Complete sales orders, plans and production batches

**Files:**
- Create: `tests/test_sales_plan_batch_api.py`
- Modify: `backend/blueprints/production.py`
- Modify: `admin/static/js/pages/production_chain.js`
- Modify: `admin/static/js/menu.js`
- Modify: `admin/static/js/ui_utils.js`

**Interfaces:**
- `GET /api/prod/sales/list` returns joined `customer_name`, `line_count`, `total_amount`.
- `GET /api/prod/sales/{sales_order_id}` returns `{header, items}`.
- `POST /api/prod/sales/save` calls `save_sales_order`; an optional positive `id` updates a draft order in the same header-line transaction.
- Equivalent `/api/prod/plan/list`, `/api/prod/plan/{plan_id}`, `/api/prod/plan/save` endpoints.
- `GET/POST /api/prod/batch/list|save` and `POST /api/prod/batch/status`.

- [ ] **Step 1: Write failing header-line and carry-forward tests**

```python
def test_confirmed_sales_lines_can_be_carried_to_plan(client):
    sales_id = create_confirmed_sales_order(client, quantity=100)
    response = client.get(f'/api/prod/plan/source/{sales_id}')
    line = response.get_json()['data']['items'][0]
    assert line['remaining_qty'] == 100

def test_two_batches_may_split_but_not_exceed_plan_line(client):
    plan_item = create_plan_line(client, quantity=100)
    assert save_batch(client, plan_item, 40).status_code == 200
    assert save_batch(client, plan_item, 60).status_code == 200
    assert save_batch(client, plan_item, 1).status_code == 400
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_sales_plan_batch_api.py -q`

Expected: FAIL because detail and batch endpoints are absent.

- [ ] **Step 3: Implement list/detail/save/status endpoints and line editors**

Use one wide modal with header fields and an editable items table. Product change selects the product ID; quantity and unit price recalculate line amount and footer total with `Number(value || 0)`. Plan source loading copies only positive remaining quantities. Add menu key `prod/batch` after production plan and register it for manual display ordering.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_sales_plan_batch_api.py -q`

Run: `node --test tests/admin_production_chain.test.js`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_sales_plan_batch_api.py backend/blueprints/production.py admin/static/js/pages/production_chain.js admin/static/js/menu.js admin/static/js/ui_utils.js
git commit -m "feat: complete sales planning and batch flow"
```

### Task 6: Release work orders and generate frozen-route tasks

**Files:**
- Create: `tests/test_workorder_task_flow_api.py`
- Modify: `backend/blueprints/production.py`
- Modify: `admin/static/js/pages/business.js`
- Modify: `admin/static/js/pages/production_chain.js`
- Modify: `backend/blueprints/dashboard.py`

**Interfaces:**
- `GET /api/prod/workorder/options?plan_item_id={plan_item_id}` returns product, remaining quantity, workshop and matching routes.
- `POST /api/prod/workorder/save` validates batch/product/workshop/route.
- `POST /api/prod/workorder/{workorder_id}/release` freezes route/BOM and records status log.
- `POST /api/prod/workorder/{workorder_id}/generate-tasks` is idempotent.
- `GET /api/prod/workorder/{workorder_id}/executable-steps` returns step, upstream quantity, reported quantity and available quantity.

- [ ] **Step 1: Write failing snapshot, idempotency and filtering tests**

```python
def test_task_generation_uses_only_frozen_route_steps(client):
    workorder = release_seeded_workorder(client)
    first = client.post(f'/api/prod/workorder/{workorder}/generate-tasks').get_json()
    second = client.post(f'/api/prod/workorder/{workorder}/generate-tasks').get_json()
    assert [x['process_id'] for x in first['data']] == seeded_route_process_ids
    assert [x['id'] for x in second['data']] == [x['id'] for x in first['data']]

def test_workorder_rejects_route_for_other_product(client):
    response = client.post('/api/prod/workorder/save', json=mismatched_workorder())
    assert response.status_code == 400
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_workorder_task_flow_api.py -q`

Expected: FAIL because release and task generation endpoints are absent.

- [ ] **Step 3: Implement work-order form, release and task generation**

The work-order modal selects plan → batch → product/workshop → matching route. Released rows show snapshot version and expose “生成任务”; editable fields become read-only after release. Update dashboard active status queries to include released and producing work orders explicitly rather than relying on `status IN (0,1)` assumptions.

- [ ] **Step 4: Run focused and collector compatibility tests**

Run: `python -m pytest tests/test_workorder_task_flow_api.py tests/test_table_order_api.py -q`

Run: `node --test tests/admin_production_chain.test.js tests/collector_core.test.js`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_workorder_task_flow_api.py backend/blueprints/production.py backend/blueprints/dashboard.py admin/static/js/pages/business.js admin/static/js/pages/production_chain.js
git commit -m "feat: release workorders with frozen route tasks"
```

### Task 7: Generate BOM requirements and control inventory issue/return

**Files:**
- Create: `tests/test_material_issue_flow_api.py`
- Modify: `backend/services/production_flow.py`
- Modify: `backend/blueprints/prod_ext.py`
- Modify: `admin/static/js/pages/prod_ext.js`

**Interfaces:**
- `POST /api/prod/workorder/{workorder_id}/generate-materials` returns frozen requirements idempotently.
- `POST /api/prod/material/{material_request_id}/request` records requested quantity.
- `POST /api/prod/material/{material_request_id}/issue` validates and decrements `inv_balance`.
- `POST /api/prod/material/{material_request_id}/receive` records workshop receipt.
- `POST /api/prod/material/{material_request_id}/return` increments inventory and `returned_qty`.

- [ ] **Step 1: Write failing inventory transaction tests**

```python
def test_material_issue_is_atomic_and_rejects_short_stock(client, db):
    request_id = seed_requirement(required=10, stock=6)
    response = client.post(f'/api/prod/material/{request_id}/issue', json={'quantity': 10, 'warehouse_id': 1})
    assert response.status_code == 409
    assert response.get_json()['data']['shortage_qty'] == 4
    assert stock_of(db, material_id) == 6

def test_return_restores_stock_and_writes_reverse_transaction(client, db):
    request_id = issue_seeded_material(quantity=10)
    client.post(f'/api/prod/material/{request_id}/return', json={'quantity': 2})
    assert stock_of(db, material_id) == 2
    assert latest_inventory_transaction(db)['trans_type'] == '生产退料'
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_material_issue_flow_api.py -q`

Expected: FAIL because controlled issue/return endpoints are absent.

- [ ] **Step 3: Implement material state actions and UI**

Lock the inventory row with `BEGIN IMMEDIATE`, verify stock before mutation, update `inv_balance`, insert `inv_transaction` with the work-order number as `ref_no`, update material quantities/status, and commit once. The UI shows requirement, requested, issued, returned, shortage and action buttons appropriate to the current state.

- [ ] **Step 4: Run material and inventory regression tests**

Run: `python -m pytest tests/test_material_issue_flow_api.py tests/test_table_order_api.py -q`

Run: `node --test tests/admin_production_chain.test.js`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_material_issue_flow_api.py backend/services/production_flow.py backend/blueprints/prod_ext.py admin/static/js/pages/prod_ext.js
git commit -m "feat: link production material issues to inventory"
```

### Task 8: Enforce executable quantities, report posting and adjacent transfer

**Files:**
- Create: `tests/test_report_transfer_flow_api.py`
- Modify: `backend/services/production_flow.py`
- Modify: `backend/blueprints/production.py`
- Modify: `backend/blueprints/prod_ext.py`
- Modify: `admin/static/js/pages/production_chain.js`
- Modify: `admin/static/js/pages/prod_ext.js`

**Interfaces:**
- `POST /api/prod/report/add` creates a submitted record without changing totals.
- `POST /api/prod/report/{report_id}/approve`, `/post`, `/reject` control reporting.
- `GET /api/prod/task/{task_id}/availability` returns `{planned_qty, upstream_qty, posted_qty, available_qty}`.
- `POST /api/prod/transfer/add` validates adjacent frozen steps and available quantity.

- [ ] **Step 1: Write failing quantity and posting tests**

```python
def test_submitted_report_does_not_change_task_until_posted(client, db):
    report_id = submit_report(client, qualified=8, defect=2)
    assert task_totals(db) == (0, 0)
    client.post(f'/api/prod/report/{report_id}/approve')
    client.post(f'/api/prod/report/{report_id}/post')
    assert task_totals(db) == (8, 2)

def test_second_step_cannot_report_more_than_transferred(client):
    transfer_between_first_two_steps(client, quantity=8)
    response = submit_second_step_report(client, qualified=9)
    assert response.status_code == 409
    assert '可执行数量为 8' in response.get_json()['message']

def test_transfer_rejects_non_adjacent_route_steps(client):
    assert transfer_step_one_to_three(client, 1).status_code == 400
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/test_report_transfer_flow_api.py -q`

Expected: FAIL because approval/posting and availability rules are absent.

- [ ] **Step 3: Implement report and transfer state machines**

Posting must be idempotent: reject an already posted report, update task/work-order totals once, calculate task completion status, and write the status log in one transaction. Transfer uses snapshot step numbers, verifies `target.step_no == source.step_no + 1`, and computes available transfer as posted qualified quantity minus prior completed transfers.

- [ ] **Step 4: Run focused, collector and production regression tests**

Run: `python -m pytest tests/test_report_transfer_flow_api.py tests/test_table_order_api.py -q`

Run: `node --test tests/admin_production_chain.test.js tests/collector_core.test.js`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_report_transfer_flow_api.py backend/services/production_flow.py backend/blueprints/production.py backend/blueprints/prod_ext.py admin/static/js/pages/production_chain.js admin/static/js/pages/prod_ext.js
git commit -m "feat: control reporting and process transfer quantities"
```

### Task 9: Add end-to-end API acceptance coverage and documentation

**Files:**
- Create: `tests/test_production_chain_e2e.py`
- Modify: `docs/MES工厂管家_使用手册.md`
- Modify: `docs/MES_端到端验收案例.md`

**Interfaces:**
- The E2E fixture creates records with remark `生产业务链测试` using public HTTP endpoints only.
- The manual documents exact module order, required fields, state actions and expected inventory/quantity results.

- [ ] **Step 1: Write the failing end-to-end test**

```python
def test_complete_order_driven_production_chain(authenticated_client):
    sales = save_sales(authenticated_client, qty=100, remark='生产业务链测试')
    plan = save_plan_from_sales(authenticated_client, sales, qty=100)
    batch = save_batch(authenticated_client, plan, qty=100)
    workorder = save_and_release_workorder(authenticated_client, batch)
    tasks = generate_tasks(authenticated_client, workorder)
    materials = generate_materials(authenticated_client, workorder)
    issue_all(authenticated_client, materials)
    post_first_step(authenticated_client, tasks[0], qualified=98, defect=2)
    transfer(authenticated_client, tasks[0], tasks[1], quantity=98)
    assert trace_chain(authenticated_client, workorder)['sales_order_id'] == sales
```

- [ ] **Step 2: Run and verify RED at the first missing integration**

Run: `python -m pytest tests/test_production_chain_e2e.py -q -x`

Expected: FAIL at the first incomplete cross-module response or trace link.

- [ ] **Step 3: Complete response links and write operator instructions**

Every list/detail response exposes upstream IDs and business numbers needed for navigation. Document the exact sample values, expected status after each action, expected stock delta, and recovery instructions for validation errors. Do not delete acceptance data.

- [ ] **Step 4: Run the E2E test and documentation checks**

Run: `python -m pytest tests/test_production_chain_e2e.py -q`

Run: `rg -n "销售订单|生产批次|路线快照|BOM 快照|生产领料|报工审核" docs/MES工厂管家_使用手册.md docs/MES_端到端验收案例.md`

Expected: E2E PASS and every term found.

- [ ] **Step 5: Commit**

```bash
git add tests/test_production_chain_e2e.py docs/MES工厂管家_使用手册.md docs/MES_端到端验收案例.md
git commit -m "test: cover complete production business chain"
```

### Task 10: Full regression, browser acceptance and deployment

**Files:**
- Modify only files required by defects reproduced during acceptance.

**Interfaces:**
- Admin URL: `http://127.0.0.1:8080/admin`.
- Acceptance records remain marked `生产业务链测试`.

- [ ] **Step 1: Run all automated tests**

Run: `node --test tests/*.test.js`

Expected: 100% PASS.

Run: `python -m pytest -q`

Expected: 100% PASS.

- [ ] **Step 2: Run static and syntax verification**

Run: `python -m py_compile backend/app.py backend/blueprints/base_data.py backend/blueprints/production.py backend/blueprints/prod_ext.py backend/services/production_flow.py backend/utils/database.py`

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 3: Restart only the verified MES process**

Resolve the PID listening on port 8080, verify its command line contains `start_app.py`, stop that exact PID, and start `python start_app.py` hidden from `D:\项目代码\MES工厂管家`. Confirm `/admin` returns HTTP 200.

- [ ] **Step 4: Browser-test the complete workflow**

Create and retain one `生产业务链测试` chain. Confirm sales, plan, batch, work order, route tasks, material issue, report posting, transfer and trace pages. Refresh and re-login; verify links, stock and totals persist. Confirm no page displays stale content after navigation and all unrelated workshop processes are absent from dependent selects.

- [ ] **Step 5: Review and final commit**

Inspect `git diff`, ensure the three pre-existing untracked user files remain untouched, and commit any acceptance fixes:

```bash
git add backend/utils/database.py backend/utils/table_order.py backend/services/__init__.py backend/services/production_flow.py backend/blueprints/base_data.py backend/blueprints/production.py backend/blueprints/prod_ext.py backend/blueprints/dashboard.py admin/index.html admin/static/js/app.js admin/static/js/menu.js admin/static/js/ui_utils.js admin/static/js/pages/business.js admin/static/js/pages/extensions.js admin/static/js/pages/prod_ext.js admin/static/js/pages/production_chain.js tests/production_chain_support.py tests/test_production_chain_migration.py tests/test_production_flow_service.py tests/test_process_route_api.py tests/test_sales_plan_batch_api.py tests/test_workorder_task_flow_api.py tests/test_material_issue_flow_api.py tests/test_report_transfer_flow_api.py tests/test_production_chain_e2e.py tests/admin_production_chain.test.js docs/MES工厂管家_使用手册.md docs/MES_端到端验收案例.md
git commit -m "feat: complete order-driven production workflow"
```
