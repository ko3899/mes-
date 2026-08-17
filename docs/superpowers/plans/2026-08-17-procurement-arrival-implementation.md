# Procurement Arrival Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-usable procurement, arrival, receipt disposition, incoming inspection, return, and inventory posting workflow without deleting or rewriting existing business data.

**Architecture:** Add a focused `procurement_flow` domain service as the only write path, expose it through a dedicated Flask blueprint, and keep legacy arrival CRUD disabled. Add location/batch stock balances while transactionally maintaining the existing product-level `inv_balance` for backward compatibility. Every quantity mutation uses `BEGIN IMMEDIATE`, conditional checks, status logs, RBAC, and client-operation idempotency.

**Tech Stack:** Python 3.8, Flask, SQLite, browser JavaScript, pytest, Node built-in test runner.

## Global Constraints

- Preserve every existing business and test record; no cleanup-based implementation or verification.
- Add no external runtime dependency.
- Continue supporting existing product-level inventory queries and production issue flows.
- Arrival registration records physical facts even when the purchase order is absent, unapproved, mismatched, or over-delivered.
- Receipt does not increase inventory; only exempt, passed, or approved-concession quantities may be posted.
- All new behavior follows test-first red-green-refactor cycles.
- All API permissions are enforced server-side; hiding a button is not authorization.
- SQLite mutations that affect cumulative quantities execute in one transaction.

---

## File Structure

- Create `backend/services/procurement_flow.py`: purchase, arrival, receipt, inspection, return, and posting state machines.
- Create `backend/blueprints/procurement.py`: JSON validation, RBAC, error mapping, read endpoints, and action endpoints.
- Modify `backend/utils/database.py`: additive tables, columns, indexes, status logs, idempotency, and granular stock balance.
- Modify `backend/app.py`: register `procurement_bp`.
- Modify `backend/utils/helpers.py`: no semantic change; only reuse `permission_required`.
- Modify `backend/blueprints/sys_ext.py`: add procurement action permissions to the role catalog.
- Create `admin/static/js/pages/procurement.js`: purchase order, arrival, receipt, inspection, and posting pages.
- Modify `admin/index.html`: load the procurement page module before `app.js`.
- Modify `admin/static/js/menu.js`: add procurement destinations.
- Modify `admin/static/js/app.js`: dispatch procurement destinations.
- Modify `admin/static/js/pages/warehouse_schedule.js`: retire the generic arrival renderer in favor of the controlled page.
- Create `tests/test_procurement_schema.py`: additive migration and index tests.
- Create `tests/test_procurement_flow.py`: domain state, quantity, concurrency, and idempotency tests.
- Create `tests/test_procurement_api.py`: permissions, validation, and endpoint integration tests.
- Create `tests/admin_procurement.test.js`: UI routing and controlled-action source tests.

---

### Task 1: Add Additive Procurement and Granular Inventory Schema

**Files:**
- Modify: `backend/utils/database.py`
- Create: `tests/test_procurement_schema.py`

**Interfaces:**
- Produces tables: `scm_purchase_order`, `scm_purchase_order_item`, `inv_arrival_notice`, `inv_arrival_notice_item`, `inv_receipt_action`, `qm_incoming_inspection`, `qm_incoming_inspection_item`, `inv_receipt_posting`, `inv_stock_balance`, `scm_procurement_status_log`.
- Produces unique idempotency indexes on `(operator_id, client_operation_id)` for receipt actions and postings.
- Preserves existing `inv_balance(product_id, quantity, amount)` as the compatibility aggregate.

- [ ] **Step 1: Write schema tests that describe the additive contract**

```python
def test_procurement_schema_is_additive(db):
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'scm_purchase_order', 'scm_purchase_order_item', 'inv_receipt_action',
            'qm_incoming_inspection', 'inv_receipt_posting', 'inv_stock_balance'} <= names
    assert db.execute('SELECT COUNT(*) FROM inv_arrival_notice').fetchone()[0] >= 0

def test_stock_balance_identity_is_unique(db):
    indexes = {row[1] for row in db.execute("PRAGMA index_list('inv_stock_balance')")}
    assert 'uq_inv_stock_balance_identity' in indexes
```

- [ ] **Step 2: Run the schema tests and verify RED**

Run: `python -m pytest -q tests/test_procurement_schema.py`  
Expected: FAIL because the new tables and `uq_inv_stock_balance_identity` do not exist.

- [ ] **Step 3: Add tables and indexes through idempotent initialization**

Add schemas with these required fields:

```sql
scm_purchase_order(id, order_no UNIQUE, supplier_id, status, expected_date,
                   currency, remark, created_by, submitted_by, submitted_at,
                   approved_by, approved_at, rejected_reason, closed_reason,
                   created_at, updated_at)
scm_purchase_order_item(id, order_id, product_id, ordered_qty, unit_price,
                        tax_rate, arrived_qty, accepted_qty, returned_qty,
                        posted_qty, created_at)
inv_arrival_notice(id, notice_no UNIQUE, purchase_order_id, supplier_id,
                   delivery_note_no, arrived_at, status, exception_code,
                   exception_reason, created_by, created_at, updated_at)
inv_arrival_notice_item(id, notice_id, purchase_order_item_id, product_id,
                        arrived_qty, normal_qty, excess_qty, accepted_qty,
                        returned_qty, pending_qty, inspection_mode, created_at)
inv_receipt_action(id, arrival_item_id, action_type, quantity, reason,
                   operator_id, client_operation_id, created_at)
qm_incoming_inspection(id, inspection_no UNIQUE, arrival_item_id, mode,
                       status, sampled_qty, passed_qty, failed_qty,
                       pending_qty, conclusion, inspector_id, inspected_at,
                       concession_approved_by, concession_reason, created_at)
inv_receipt_posting(id, posting_no UNIQUE, arrival_item_id, inspection_id,
                    product_id, warehouse_id, area_id, location_id, batch_no,
                    quantity, operator_id, client_operation_id, created_at)
inv_stock_balance(id, product_id, warehouse_id, area_id, location_id,
                  batch_no, quantity, updated_at)
scm_procurement_status_log(id, entity_type, entity_id, from_status,
                           to_status, action, operator_id, reason, created_at)
```

Use `CREATE TABLE IF NOT EXISTS`, `_add_column_if_missing`, and `CREATE UNIQUE INDEX IF NOT EXISTS`. Migrate existing arrival rows without altering or deleting their values; new columns remain nullable for legacy records.

- [ ] **Step 4: Run schema tests and database regression tests**

Run: `python -m pytest -q tests/test_procurement_schema.py tests/test_database_seed_idempotency.py`  
Expected: PASS and repeated initialization leaves one copy of every seeded/indexed record.

- [ ] **Step 5: Commit the schema task**

```bash
git add backend/utils/database.py tests/test_procurement_schema.py
git commit -m "feat: add procurement arrival schema"
```

---

### Task 2: Implement Purchase Order State Machine

**Files:**
- Create: `backend/services/procurement_flow.py`
- Create: `tests/test_procurement_flow.py`

**Interfaces:**
- Produces `BusinessError(message: str, status: int = 400, details: Optional[dict] = None)`.
- Produces `save_purchase_order(db, payload, user_id) -> dict`.
- Produces `submit_purchase_order(db, order_id, user_id) -> dict`.
- Produces `review_purchase_order(db, order_id, approved, user_id, reason='') -> dict`.
- Produces `cancel_purchase_order(db, order_id, user_id, reason) -> dict`.
- Produces `close_purchase_order(db, order_id, user_id, reason) -> dict`.

- [ ] **Step 1: Write failing purchase state and quantity tests**

```python
def test_purchase_order_requires_supplier_and_positive_lines(db):
    with pytest.raises(BusinessError):
        save_purchase_order(db, {'supplier_id': 1, 'items': []}, 7)

def test_only_submitted_order_can_be_approved(db, purchase_order):
    with pytest.raises(BusinessError):
        review_purchase_order(db, purchase_order['id'], True, 9)

def test_order_with_arrivals_cannot_be_cancelled(db, arrived_order):
    with pytest.raises(BusinessError):
        cancel_purchase_order(db, arrived_order['id'], 9, 'changed')
```

- [ ] **Step 2: Run the purchase tests and verify RED**

Run: `python -m pytest -q tests/test_procurement_flow.py -k purchase`  
Expected: FAIL because `procurement_flow` and its functions do not exist.

- [ ] **Step 3: Implement minimal purchase services**

Implement `_atomic(db)` with `BEGIN IMMEDIATE`, positive finite quantity validation, server-generated `PO` numbering, item replacement only while draft/rejected, and status constants:

```python
PURCHASE = {'draft': 0, 'submitted': 1, 'approved': 2,
            'partial_arrival': 3, 'fully_arrived': 4,
            'closed': 5, 'rejected': 6, 'cancelled': 7}
```

Each transition must conditionally update the expected old status and append `scm_procurement_status_log`. Reject or close reasons are required when applicable.

- [ ] **Step 4: Run purchase tests and verify GREEN**

Run: `python -m pytest -q tests/test_procurement_flow.py -k purchase`  
Expected: PASS.

- [ ] **Step 5: Commit the purchase service**

```bash
git add backend/services/procurement_flow.py tests/test_procurement_flow.py
git commit -m "feat: add controlled purchase orders"
```

---

### Task 3: Implement Physical Arrival Registration and Matching

**Files:**
- Modify: `backend/services/procurement_flow.py`
- Modify: `tests/test_procurement_flow.py`

**Interfaces:**
- Consumes purchase statuses and line quantities from Task 2.
- Produces `register_arrival(db, payload, user_id) -> dict`.
- Produces `resolve_arrival_exception(db, arrival_id, action, user_id, reason, purchase_order_id=None) -> dict`.

- [ ] **Step 1: Write failing normal, no-order, unapproved, and excess-arrival tests**

```python
def test_unapproved_order_arrival_is_recorded_as_exception(db, draft_order):
    arrival = register_arrival(db, arrival_payload(draft_order, 10), 7)
    assert arrival['status'] == ARRIVAL['exception']
    assert arrival['exception_code'] == 'PURCHASE_NOT_APPROVED'

def test_excess_quantity_is_split_without_losing_physical_arrival(db, approved_order):
    arrival = register_arrival(db, arrival_payload(approved_order, 110), 7)
    item = arrival['items'][0]
    assert item['arrived_qty'] == 110
    assert item['normal_qty'] == 100
    assert item['excess_qty'] == 10
```

- [ ] **Step 2: Run arrival tests and verify RED**

Run: `python -m pytest -q tests/test_procurement_flow.py -k arrival`  
Expected: FAIL because arrival registration is not implemented.

- [ ] **Step 3: Implement registration without inventory mutation**

Generate an `AN` number and persist header/items in one transaction. Match supplier, purchase status, product, order item, and remaining order quantity. Use exception codes `NO_PURCHASE_ORDER`, `PURCHASE_NOT_APPROVED`, `SUPPLIER_MISMATCH`, `PRODUCT_MISMATCH`, and `OVER_DELIVERY`. Always persist physical `arrived_qty`; never update `inv_balance` or `inv_stock_balance` here.

- [ ] **Step 4: Implement exception resolution**

Support exact actions `link_order`, `approve_excess`, and `return`. Require procurement-supervisor permission at the blueprint layer. Re-run matching for `link_order`; move only the approved excess quantity into receivable quantity for `approve_excess`; create receipt-return actions for `return`.

- [ ] **Step 5: Run arrival tests and verify GREEN**

Run: `python -m pytest -q tests/test_procurement_flow.py -k arrival`  
Expected: PASS.

- [ ] **Step 6: Commit the arrival service**

```bash
git add backend/services/procurement_flow.py tests/test_procurement_flow.py
git commit -m "feat: register normal and exceptional arrivals"
```

---

### Task 4: Implement Partial Receipt and Return Disposition

**Files:**
- Modify: `backend/services/procurement_flow.py`
- Modify: `tests/test_procurement_flow.py`

**Interfaces:**
- Produces `record_receipt_action(db, arrival_item_id, action_type, quantity, user_id, reason='', client_operation_id=None) -> dict`.
- Action types are exactly `accept`, `return`, and `hold`.

- [ ] **Step 1: Write failing quantity-conservation tests**

```python
def test_arrival_can_be_partially_accepted_returned_and_held(db, arrival_item):
    record_receipt_action(db, arrival_item['id'], 'accept', 80, 7, client_operation_id='a1')
    record_receipt_action(db, arrival_item['id'], 'return', 15, 7, 'damage', 'r1')
    item = get_arrival_item(db, arrival_item['id'])
    assert (item['accepted_qty'], item['returned_qty'], item['pending_qty']) == (80, 15, 5)

def test_duplicate_receipt_operation_is_idempotent(db, arrival_item):
    first = record_receipt_action(db, arrival_item['id'], 'accept', 10, 7, client_operation_id='same')
    second = record_receipt_action(db, arrival_item['id'], 'accept', 10, 7, client_operation_id='same')
    assert second['id'] == first['id']
    assert get_arrival_item(db, arrival_item['id'])['accepted_qty'] == 10
```

- [ ] **Step 2: Run disposition tests and verify RED**

Run: `python -m pytest -q tests/test_procurement_flow.py -k receipt_action`  
Expected: FAIL because the action service is missing.

- [ ] **Step 3: Implement transaction-safe actions**

Within `BEGIN IMMEDIATE`, load the current item, compute remaining unallocated quantity, reject non-positive/non-finite or excessive quantities, insert the immutable action, and update cumulative fields. A `hold` action records reason and leaves the quantity pending. Handle unique-operation conflicts by returning the existing action.

- [ ] **Step 4: Run disposition and concurrency tests**

Run: `python -m pytest -q tests/test_procurement_flow.py -k "receipt_action or concurrent_receipt"`  
Expected: PASS and the concurrent total never exceeds `arrived_qty`.

- [ ] **Step 5: Commit the disposition service**

```bash
git add backend/services/procurement_flow.py tests/test_procurement_flow.py
git commit -m "feat: add partial receipt and return disposition"
```

---

### Task 5: Implement Incoming Inspection and Concession

**Files:**
- Modify: `backend/services/procurement_flow.py`
- Modify: `tests/test_procurement_flow.py`

**Interfaces:**
- Produces `create_incoming_inspection(db, arrival_item_id, mode, user_id) -> dict`.
- Produces `complete_incoming_inspection(db, inspection_id, payload, user_id) -> dict`.
- Produces `approve_incoming_concession(db, inspection_id, quantity, user_id, reason) -> dict`.

- [ ] **Step 1: Write failing inspection-mode and conservation tests**

```python
@pytest.mark.parametrize('mode', ['required', 'sampling', 'exempt'])
def test_supported_inspection_modes(db, accepted_item, mode):
    inspection = create_incoming_inspection(db, accepted_item['id'], mode, 8)
    assert inspection['mode'] == mode

def test_inspection_results_cannot_exceed_accepted_quantity(db, inspection):
    with pytest.raises(BusinessError):
        complete_incoming_inspection(db, inspection['id'],
                                     {'passed_qty': 80, 'failed_qty': 30}, 8)
```

- [ ] **Step 2: Run inspection tests and verify RED**

Run: `python -m pytest -q tests/test_procurement_flow.py -k inspection`  
Expected: FAIL because inspection functions are absent.

- [ ] **Step 3: Implement inspection transitions**

Use statuses `pending`, `completed`, `concession_pending`, and `closed`. Required and sampling modes require inspector results; exempt mode creates an immediately completed record whose passed quantity equals the available accepted quantity. Failed quantities remain non-postable until returned, reworked/selected, or approved as concession.

- [ ] **Step 4: Implement concession approval**

Require positive quantity not exceeding failed unallocated quantity and a non-empty reason. Store approver and reason; expose approved concession quantity as postable without changing the original failed count.

- [ ] **Step 5: Run inspection tests and verify GREEN**

Run: `python -m pytest -q tests/test_procurement_flow.py -k inspection`  
Expected: PASS.

- [ ] **Step 6: Commit the quality service**

```bash
git add backend/services/procurement_flow.py tests/test_procurement_flow.py
git commit -m "feat: add incoming inspection disposition"
```

---

### Task 6: Post Approved Quantities to Granular and Aggregate Inventory

**Files:**
- Modify: `backend/services/procurement_flow.py`
- Modify: `tests/test_procurement_flow.py`

**Interfaces:**
- Produces `post_receipt_inventory(db, payload, user_id) -> dict`.
- Payload requires `arrival_item_id`, `inspection_id`, `warehouse_id`, `area_id`, `location_id`, `batch_no`, `quantity`, and `client_operation_id`.

- [ ] **Step 1: Write failing authorization-of-quantity and idempotency tests**

```python
def test_only_passed_or_concession_quantity_can_be_posted(db, failed_inspection):
    with pytest.raises(BusinessError):
        post_receipt_inventory(db, posting_payload(failed_inspection, 5, 'p1'), 10)

def test_duplicate_posting_updates_inventory_once(db, passed_inspection):
    first = post_receipt_inventory(db, posting_payload(passed_inspection, 20, 'same-post'), 10)
    second = post_receipt_inventory(db, posting_payload(passed_inspection, 20, 'same-post'), 10)
    assert second['id'] == first['id']
    assert stock_quantity(db, passed_inspection['product_id']) == 20
```

- [ ] **Step 2: Run posting tests and verify RED**

Run: `python -m pytest -q tests/test_procurement_flow.py -k posting`  
Expected: FAIL because posting is absent.

- [ ] **Step 3: Implement one-transaction posting**

Validate warehouse-area-location ownership and remaining postable quantity. In one `BEGIN IMMEDIATE` transaction: insert `inv_receipt_posting`, upsert `inv_stock_balance` by product/warehouse/area/location/batch, update or insert aggregate `inv_balance`, insert existing `inv_transaction` and `inv_transaction_log` rows, update item/order cumulative fields, and append a status log. A duplicate client operation returns the original posting before any balance mutation.

- [ ] **Step 4: Run posting and existing inventory tests**

Run: `python -m pytest -q tests/test_procurement_flow.py -k posting tests/test_material_issue_flow_api.py tests/test_inventory_posting_api.py`  
Expected: PASS with both legacy inventory posting and material issue behavior preserved.

- [ ] **Step 5: Commit inventory posting**

```bash
git add backend/services/procurement_flow.py tests/test_procurement_flow.py
git commit -m "feat: post inspected arrivals to inventory"
```

---

### Task 7: Expose Controlled APIs and RBAC

**Files:**
- Create: `backend/blueprints/procurement.py`
- Modify: `backend/app.py`
- Modify: `backend/blueprints/sys_ext.py`
- Create: `tests/test_procurement_api.py`

**Interfaces:**
- Consumes every domain service from Tasks 2-6.
- Produces `/api/procurement/orders/*`, `/api/procurement/arrivals/*`, `/api/procurement/inspections/*`, and `/api/procurement/postings/*`.
- Produces permissions `procurement:read`, `procurement:order:write`, `procurement:order:review`, `procurement:arrival:write`, `procurement:exception:approve`, `procurement:receipt:write`, `procurement:inspection:write`, `procurement:concession:approve`, and `procurement:inventory:post`.

- [ ] **Step 1: Write failing API permission and workflow tests**

```python
def test_procurement_writer_cannot_approve_order(writer_client, draft_order):
    response = writer_client.post(f"/api/procurement/orders/{draft_order['id']}/review",
                                  json={'approved': True})
    assert response.status_code == 403

def test_warehouse_role_can_post_but_cannot_concede(warehouse_client, inspection):
    assert warehouse_client.post('/api/procurement/postings', json=posting_json(inspection)).status_code == 200
    assert warehouse_client.post(f"/api/procurement/inspections/{inspection['id']}/concession",
                                 json={'quantity': 1, 'reason': 'use as is'}).status_code == 403
```

- [ ] **Step 2: Run API tests and verify RED**

Run: `python -m pytest -q tests/test_procurement_api.py`  
Expected: FAIL because the blueprint and routes do not exist.

- [ ] **Step 3: Implement blueprint routes and error mapping**

Every write route uses the exact permission above and calls one domain service. Read endpoints return paginated headers plus line details and status labels. Map `BusinessError.status` to HTTP status; reject missing/invalid JSON with 400; never pass arbitrary request dictionaries to generic CRUD helpers.

- [ ] **Step 4: Register blueprint and role catalog**

Import and register `procurement_bp` in `backend/app.py`. Add all nine permissions and Chinese labels to `ACTION_PERMISSION_CATALOG` in `backend/blueprints/sys_ext.py`.

- [ ] **Step 5: Run API and existing permission tests**

Run: `python -m pytest -q tests/test_procurement_api.py tests/test_report_transfer_flow_api.py`  
Expected: PASS.

- [ ] **Step 6: Commit API and RBAC**

```bash
git add backend/blueprints/procurement.py backend/app.py backend/blueprints/sys_ext.py tests/test_procurement_api.py
git commit -m "feat: expose procurement workflow APIs"
```

---

### Task 8: Build Procurement, Arrival, Inspection, and Posting UI

**Files:**
- Create: `admin/static/js/pages/procurement.js`
- Modify: `admin/index.html`
- Modify: `admin/static/js/menu.js`
- Modify: `admin/static/js/app.js`
- Modify: `admin/static/js/pages/warehouse_schedule.js`
- Create: `tests/admin_procurement.test.js`

**Interfaces:**
- Consumes Task 7 APIs.
- Produces renderers `renderPurchaseOrders`, `renderProcurementArrivals`, `renderIncomingInspections`, and `renderReceiptPostings`.

- [ ] **Step 1: Write failing source-level UI contract tests**

```javascript
test('procurement pages use controlled action endpoints', () => {
  const source = read('admin/static/js/pages/procurement.js');
  assert.match(source, /\/api\/procurement\/orders/);
  assert.match(source, /\/api\/procurement\/arrivals/);
  assert.match(source, /client_operation_id/);
  assert.doesNotMatch(source, /\/api\/arrival\/(add|update|delete)/);
});
```

- [ ] **Step 2: Run UI tests and verify RED**

Run: `node --test tests/admin_procurement.test.js`  
Expected: FAIL because `procurement.js` and renderers do not exist.

- [ ] **Step 3: Implement four controlled pages**

Use semantic tables, escaped business text, explicit status tags, line-detail modals, and action buttons shown by current status. Generate `client_operation_id` once when opening receipt/posting actions and reuse it on retries. The arrival form permits purchase order selection or “异常无订单到货”. The posting form requires warehouse, area, location, batch, and quantity.

- [ ] **Step 4: Wire scripts, menu, and dispatcher**

Load `procurement.js` before `app.js`. Add menu destinations `procurement/order`, `procurement/arrival`, `procurement/inspection`, and `procurement/posting`. Dispatch each destination to its exact renderer. Replace `warehouse/arrival` with an alias to `renderProcurementArrivals` so existing bookmarks do not reopen generic CRUD.

- [ ] **Step 5: Run focused and complete Node tests**

Run: `node --test tests/admin_procurement.test.js`  
Expected: PASS.  
Run: `node --test tests/*.test.js`  
Expected: all tests PASS.

- [ ] **Step 6: Commit UI**

```bash
git add admin/static/js/pages/procurement.js admin/index.html admin/static/js/menu.js admin/static/js/app.js admin/static/js/pages/warehouse_schedule.js tests/admin_procurement.test.js
git commit -m "feat: add controlled procurement UI"
```

---

### Task 9: Execute End-to-End Acceptance and Final Review

**Files:**
- Modify: `tests/test_procurement_flow.py`
- Modify: `tests/test_procurement_api.py`
- Modify: `docs/superpowers/specs/2026-08-17-procurement-arrival-design.md` only if verified behavior requires clarification, never to weaken an accepted rule.

**Interfaces:**
- Consumes the complete workflow from Tasks 1-8.
- Produces an evidence-backed release gate and preserves all test records.

- [ ] **Step 1: Add the ten accepted end-to-end scenarios**

Cover: 40+60 split arrival; 100+10 excess; 80 accepted/15 returned/5 held; no-order then linked; complete rejection/return; partial quality pass; duplicate posting; concurrent receipt; role matrix; and retained records.

- [ ] **Step 2: Run focused procurement suites**

Run: `python -m pytest -q tests/test_procurement_schema.py tests/test_procurement_flow.py tests/test_procurement_api.py`  
Expected: all procurement tests PASS.

- [ ] **Step 3: Run complete backend and frontend suites**

Run: `python -m pytest -q`  
Expected: all Python tests PASS.  
Run: `node --test tests/*.test.js`  
Expected: all Node tests PASS.

- [ ] **Step 4: Run static and migration checks**

Run: `python -m compileall -q backend`  
Expected: exit code 0.  
Run: `git diff --check`  
Expected: no whitespace errors.  
Start against a copied existing database and verify `GET /healthz` returns HTTP 200 without deleting records.

- [ ] **Step 5: Request code review and close all Critical/Important findings**

Review schema migration safety, state transitions, quantity conservation, concurrent operations, idempotency, RBAC, stored-XSS escaping, and compatibility aggregate inventory. Repeat focused tests after every review fix.

- [ ] **Step 6: Commit final acceptance updates**

```bash
git add tests/test_procurement_flow.py tests/test_procurement_api.py docs/superpowers/specs/2026-08-17-procurement-arrival-design.md
git commit -m "test: verify procurement arrival workflow"
```
