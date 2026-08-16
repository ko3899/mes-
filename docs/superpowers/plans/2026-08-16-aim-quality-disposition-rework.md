# AIM Quality Disposition and Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn AIM NG inspection results into an approved SN-level disposition and executable rework flow while making task completion depend on qualified output.

**Architecture:** A new `quality_disposition` service owns all disposition state transitions and rework-task linkage. AIM import and access services call it inside their existing transactions; production posting delegates rework accounting to it. Flask routes expose guarded commands and the existing rework page becomes the operator UI.

**Tech Stack:** Python 3.8, Flask, SQLite, vanilla JavaScript, pytest.

## Global Constraints

- Python 3.8 compatibility is mandatory.
- Ordinary tasks complete only when `completed_qty >= planned_qty`.
- Defect history is never decremented or overwritten by a rework success.
- A quality-held or scrapped SN must fail closed at machine access.
- Quality approval creates a draft rework task; it never starts the task automatically.
- Every command is transactional and idempotent under retries and concurrent requests.
- Existing AIM V1/V2, ordinary reporting and current table APIs remain compatible.

---

### Task 1: Add disposition persistence and migration

**Files:**
- Create: `backend/services/quality_disposition.py`
- Modify: `backend/utils/database.py:1063-1075`
- Test: `tests/test_quality_disposition_migration.py`

**Interfaces:**
- Produces: `create_quality_disposition_tables(db) -> None`.
- Produces tables/columns described in the approved design, including a partial unique index for one open disposition per SN and route step.

- [ ] **Step 1: Write migration tests**

Create a legacy in-memory schema containing `prod_serial`, `prod_task`, AIM reports and requests. Assert migration adds `prod_serial.quality_status`, rework columns on `prod_task`, creates `prod_quality_disposition`, and can run twice. Insert an existing NG report and assert a unique `pending_review` disposition is backfilled with `quality_status='quality_hold'`.

- [ ] **Step 2: Run the migration test and verify RED**

Run: `python -m pytest -q tests/test_quality_disposition_migration.py`

Expected: import or missing-table failure.

- [ ] **Step 3: Implement additive migration**

Implement `create_quality_disposition_tables` using `CREATE TABLE IF NOT EXISTS`, `_add_column_if_missing`-equivalent PRAGMA checks local to the service, and these public constants:

```python
QUALITY_NORMAL = 'normal'
QUALITY_HOLD = 'quality_hold'
QUALITY_REWORK = 'rework'
QUALITY_SCRAPPED = 'scrapped'
QUALITY_CONCESSION = 'concession'
OPEN_DISPOSITION_STATUSES = ('pending_review', 'approved', 'task_started')
```

Backfill imported NG reports only when their request, SN, workorder, task and route step still exist. Use `QD-BACKFILL-{report_id}` as the deterministic disposition number.

- [ ] **Step 4: Wire migration and verify GREEN**

Call the new migration from `_init_extra_tables()`. Run the migration test twice and assert no duplicate dispositions.

- [ ] **Step 5: Commit**

Commit message: `feat: add quality disposition persistence`.

### Task 2: Freeze NG serials and fail closed at access

**Files:**
- Modify: `backend/services/quality_disposition.py`
- Modify: `backend/services/machine_access.py:75-170,261-425`
- Modify: `tests/test_machine_access_service.py`
- Test: `tests/test_quality_disposition_service.py`

**Interfaces:**
- Produces: `create_ng_disposition(db, endpoint, request_row, inspection_report_id, prod_report_id, reason='') -> dict`.
- Produces: `access_context(db, sn, route_step_id) -> dict` with `quality_status`, `disposition`, and optional `rework_task`.

- [ ] **Step 1: Add failing NG and access tests**

Assert NG import atomically creates one disposition, sets the SN to `quality_hold`, and duplicate CSV retains one row. Assert a new request for the held SN returns L3 `QUALITY_HOLD`, while existing normal and OK access tests remain L1.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_quality_disposition_service.py tests/test_machine_access_service.py`

- [ ] **Step 3: Implement NG disposition creation**

Call `create_ng_disposition` before the AIM import transaction commits. The service must use deterministic `QD-{inspection_report_id}` numbering and `INSERT OR IGNORE`; it must reject a conflicting open disposition rather than silently changing links.

- [ ] **Step 4: Implement access-state decisions**

In `evaluate_access`, check disposition state after locating the serial and current route step but before selecting an ordinary task. Map states exactly:

```python
quality_hold -> QUALITY_HOLD
scrapped -> SN_SCRAPPED
rework with draft task -> REWORK_TASK_NOT_STARTED
rework with active linked task -> use that rework task
```

- [ ] **Step 5: Run focused and socket tests**

Run: `python -m pytest -q tests/test_quality_disposition_service.py tests/test_machine_access_service.py tests/test_machine_socket_server.py`

- [ ] **Step 6: Commit**

Commit message: `feat: hold AIM NG serials for disposition`.

### Task 3: Add controlled disposition commands

**Files:**
- Modify: `backend/services/quality_disposition.py`
- Modify: `backend/blueprints/site.py:91-122`
- Modify: `backend/services/production_flow.py:591-614`
- Test: `tests/test_quality_disposition_service.py`
- Test: `tests/test_quality_disposition_api.py`

**Interfaces:**
- Produces: `approve_disposition(db, disposition_id, action, user_id, reason='') -> dict`.
- Produces: `reject_disposition(db, disposition_id, user_id, reason) -> dict`.
- Produces: `validate_rework_task_start(db, task_id) -> None`.

- [ ] **Step 1: Write failing command tests**

Cover rework approval creating exactly one draft task (`task_type='rework'`, planned quantity 1, target SN set), duplicate approval returning the same task, scrap setting `quality_status='scrapped'`, concession creating one PASS station record, and rejecting an already decided disposition.

- [ ] **Step 2: Add failing API authorization tests**

Register `site_bp` in a test app. Verify anonymous requests return 401; users without `qm:process:list` cannot approve; admin can list and approve; production task permission is required to start a rework task.

- [ ] **Step 3: Implement service commands**

Use `BEGIN IMMEDIATE` via a shared atomic helper. Rework approval inserts task number `RW-{disposition_no}` with status 0. Scrap completes the disposition without a task. Concession creates an idempotent PASS record keyed through a new `quality_disposition_id` column on `prod_station_record`.

- [ ] **Step 4: Replace CRUD routes**

Keep `GET /api/site/rework/list`, but source it from `prod_quality_disposition`. Add:

```text
POST /api/site/rework/<id>/approve
POST /api/site/rework/<id>/reject
POST /api/site/rework/<id>/start-task
```

Apply `permission_required('qm:process:list')` to approve/reject and `permission_required('prod:task:list')` to start-task. The start route calls `validate_rework_task_start` and then the existing task transition.

- [ ] **Step 5: Run service and API tests**

Run: `python -m pytest -q tests/test_quality_disposition_service.py tests/test_quality_disposition_api.py`

- [ ] **Step 6: Commit**

Commit message: `feat: approve AIM rework disposition`.

### Task 4: Correct production accounting and complete rework

**Files:**
- Modify: `backend/services/production_flow.py:485-509`
- Modify: `backend/services/quality_disposition.py`
- Modify: `backend/services/machine_access.py:350-425`
- Test: `tests/test_production_flow_service.py`
- Test: `tests/test_quality_disposition_service.py`

**Interfaces:**
- Produces: `apply_posted_rework_result(db, report, task) -> None` called inside `post_report`'s transaction.
- Produces: `record_rework_ng_cycle(...) -> dict` for repeated NG.

- [ ] **Step 1: Write failing accounting tests**

Assert an ordinary task with planned 2, qualified 1 and defect 1 remains active. For a linked rework task, assert OK posting completes the rework task, increments the source task and workorder qualified quantities once, retains defect history, restores SN to `normal`, and completes the disposition. Assert duplicate posting changes no counters.

- [ ] **Step 2: Write repeated-NG tests**

Assert rework NG increments the rework task defect count without completing it, completes the current cycle, creates exactly one next-cycle pending disposition, and returns the SN to `quality_hold`.

- [ ] **Step 3: Implement qualified-output completion rule**

Change ordinary task completion to compare the post-update `completed_qty` with `planned_qty`; never add `defect_qty` for completion. Preserve task-limit protection for direct ordinary reporting, but allow rework results through the linked disposition path only.

- [ ] **Step 4: Implement rework posting**

Branch on `task.task_type`. For rework OK, update the rework task, source task, workorder, serial, disposition and PASS record inside the existing transaction. For rework NG, call `record_rework_ng_cycle`. Condition every update on its expected prior state.

- [ ] **Step 5: Run production regressions**

Run: `python -m pytest -q tests/test_production_flow_service.py tests/test_quality_disposition_service.py tests/test_machine_csv_flow.py tests/test_production_chain_api.py`

- [ ] **Step 6: Commit**

Commit message: `fix: complete production by qualified output`.

### Task 5: Upgrade rework and serial user interfaces

**Files:**
- Modify: `admin/static/js/pages/final1.js:99-140`
- Modify: `admin/static/js/pages/prod_ext.js:188-220`
- Modify: `admin/static/js/pages/machine_iot.js:104-133`
- Modify: `admin/static/css/style.css`
- Test: `tests/test_admin_ui_assets.py`

**Interfaces:**
- Consumes the Task 3 list and command APIs.
- Produces operator controls with no inline JSON/onclick interpolation of database text.

- [ ] **Step 1: Add failing static UI assertions**

Assert the rework page contains SN, report, process, cycle, disposition and task columns; has action controls for rework, scrap, concession and start task; and the serial page maps all five quality statuses to Chinese labels.

- [ ] **Step 2: Implement the rework list and modal**

Render rows using DOM APIs or escaped text. Approval modal requires an action and reason. Only show start-task for approved rework with a draft task. Refresh the row after commands and display server errors.

- [ ] **Step 3: Add status indicators**

Show quality status in the serial list and disposition state in AIM report rows. Add compact hold, rework, scrap and concession tag styles consistent with the current admin theme.

- [ ] **Step 4: Run UI asset tests**

Run: `python -m pytest -q tests/test_admin_ui_assets.py`

- [ ] **Step 5: Commit**

Commit message: `feat: manage SN rework disposition in admin`.

### Task 6: Migrate the live test case and verify end to end

**Files:**
- Modify: `docs/AIM机台接入操作手册.md`
- Test data: `database/mes.db` (not committed)

**Interfaces:**
- Consumes report ID 4 and SN `SIM-AIM-20260816-002`.
- Produces one backfilled pending disposition and an end-to-end verified rework cycle.

- [ ] **Step 1: Run the complete suite before live migration**

Run: `python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run project migration against the live database**

Invoke `_init_extra_tables()` and verify report ID 4 produces one pending disposition, the SN becomes `quality_hold`, and task 10 is recalculated to active because qualified quantity is 1 of planned 2.

- [ ] **Step 3: Exercise the approved flow**

Approve rework, verify the draft task blocks scanning, start it, verify L1, import an OK CSV with a new deterministic test request, approve and post it, then verify source task qualified 2/2, historical defect 1, workorder qualified 2, disposition completed and SN PASS.

- [ ] **Step 4: Document operations**

Add the quality approval, production start, re-scan, report and recovery procedure to the AIM guide. State that test data is retained.

- [ ] **Step 5: Run final verification and commit**

Run: `python -m pytest -q` and `git diff --check`.

Commit message: `docs: add AIM rework operating procedure`.
