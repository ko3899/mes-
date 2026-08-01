# MES Collector Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready enterprise-blue collector terminal with personal data semantics, safe barcode handling, camera fallback, and idempotent offline report synchronization.

**Architecture:** Keep Flask and framework-free browser code. Serve focused collector modules from `frontend/static/`; keep DOM construction, API normalization, scanning, offline persistence, and page rendering behind separate interfaces. Extend existing production endpoints compatibly for current-user filtering, barcode resolution, and report idempotency.

**Tech Stack:** Python 3.8+, Flask 2.3+, SQLite, pytest 8.x, HTML5, CSS3, framework-free JavaScript, Node.js built-in test runner, PyWebView.

## Global Constraints

- Preserve `/`, existing business endpoints, SQLite business semantics, `mes_collector_app.py`, and PyInstaller packaging.
- Do not add Vue, React, a runtime build step, an external camera library, or a large UI dependency.
- Use `BarcodeDetector` only after a user gesture and degrade to scanner/keyboard input when unavailable.
- Queue only idempotent writes carrying a user-scoped `client_operation_id`.
- Render all barcode, user, and API text through DOM `textContent` or the shared escaping helper.
- Target 360×600, 420×800, and 390×844 without horizontal page scrolling.
- Write every behavior test first, run it, and confirm the expected failure before production edits.

## File Map

- `frontend/index.html`: collector document skeleton and stable element IDs only.
- `frontend/static/css/collector.css`: tokens, layout, components, responsive and reduced-motion rules.
- `frontend/static/js/core.js`: pure formatting, escaping, barcode classification, response normalization.
- `frontend/static/js/api.js`: fetch wrapper and collector endpoint methods.
- `frontend/static/js/offline_queue.js`: user-scoped persistent queue and replay state machine.
- `frontend/static/js/scanner.js`: scanner input and camera lifecycle.
- `frontend/static/js/pages.js`: six business renderers and safe DOM builders.
- `frontend/static/js/app.js`: authentication, navigation, network state, and module orchestration.
- `backend/app.py`: collector static asset route.
- `backend/blueprints/production.py`: personal filters, collector summary/barcode resolver, idempotent reporting.
- `backend/utils/database.py`: backward-compatible report operation ID migration and index.
- `tests/collector_core.test.js`: pure module, scanner, queue, and controller tests.
- `tests/collector_ui_design.test.js`: document/CSS accessibility and responsive contracts.
- `test_comprehensive.py`: Flask endpoint regression tests.

---

### Task 1: Personal Collector Queries and Barcode Resolution

**Files:**
- Modify: `test_comprehensive.py`
- Modify: `backend/blueprints/production.py`

**Interfaces:**
- Produces: `GET /api/prod/task/list?mine=1`, `GET /api/prod/report/list?mine=1&date=today`, `GET /api/collector/summary`, `GET /api/collector/barcode/<code>`.
- Barcode response: `{code: 0, data: {kind: 'workorder'|'task'|'product', entity: object, tasks: object[]}}`.

- [ ] **Step 1: Write failing Flask tests**

Append focused tests that insert one task/report for the authenticated user and one for another user, then assert:

```python
mine = auth_client.get('/api/prod/task/list?mine=1&size=50').get_json()
assert all(row['assigned_to'] == 1 for row in mine['data']['list'])

summary = auth_client.get('/api/collector/summary').get_json()['data']
assert summary['pending_tasks'] == expected_pending
assert summary['today_reports'] == expected_today

resolved = auth_client.get('/api/collector/barcode/PRODUCT-CODE').get_json()
assert resolved['data']['kind'] == 'product'
assert resolved['data']['entity']['code'] == 'PRODUCT-CODE'
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest test_comprehensive.py -k "collector_personal or collector_summary or collector_barcode" -q`  
Expected: FAIL because `mine`, `date`, summary, and barcode contracts do not exist.

- [ ] **Step 3: Implement compatible query filters and collector endpoints**

In `production.py`, extend only when query parameters are present. Use `session['user_id']`, server-local `datetime.date.today()`, exact `order_no`/`task_no`/product `code` matching, and parameterized SQL. Return empty results for no match; never fall back to the newest row.

```python
mine = request.args.get('mine') == '1'
if mine:
    clauses.append('t.assigned_to=?')
    params.append(session['user_id'])
```

- [ ] **Step 4: Verify GREEN and regression**

Run: `python -m pytest test_comprehensive.py -k "collector_personal or collector_summary or collector_barcode" -q`  
Then: `python -m pytest -q`  
Expected: focused tests PASS; full Python suite PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- test_comprehensive.py backend/blueprints/production.py
git commit -m "feat: add personal collector queries"
```

### Task 2: Idempotent Offline Report Contract

**Files:**
- Modify: `test_comprehensive.py`
- Modify: `backend/utils/database.py`
- Modify: `backend/blueprints/production.py`

**Interfaces:**
- Consumes: existing `POST /api/prod/report/add` request fields.
- Produces: optional `client_operation_id: string`; a repeated ID for the same user returns the original report with `data.duplicate: true` and does not update totals twice.

- [ ] **Step 1: Write the duplicate-report failure test**

```python
payload = {
    'task_id': task_id, 'workorder_id': workorder_id,
    'process_id': process_id, 'qualified_qty': 2,
    'defect_qty': 0, 'client_operation_id': 'offline-op-001',
}
first = auth_client.post('/api/prod/report/add', json=payload).get_json()
second = auth_client.post('/api/prod/report/add', json=payload).get_json()
assert first['data']['id'] == second['data']['id']
assert second['data']['duplicate'] is True
assert report_count == 1
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest test_comprehensive.py -k "report_client_operation" -q`  
Expected: FAIL because duplicate submissions currently create two reports.

- [ ] **Step 3: Add the backward-compatible schema migration**

In `_init_extra_tables()` add `client_operation_id TEXT` to `prod_report` when missing. In `_create_indexes()` add:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_report_user_operation
ON prod_report(user_id, client_operation_id)
WHERE client_operation_id IS NOT NULL
```

Update the test database schema in `test_comprehensive.py` to include the nullable column.

- [ ] **Step 4: Implement idempotency inside the existing transaction**

Validate IDs as 1–80 character strings. Before generating a report number, query by `(user_id, client_operation_id)` and return the existing ID. Insert the operation ID with the report and handle an index race by re-querying after rollback.

- [ ] **Step 5: Verify GREEN and regression**

Run: `python -m pytest test_comprehensive.py -k "report_client_operation or report_updates_task" -q`  
Then: `python -m pytest -q`  
Expected: focused and full suites PASS.

- [ ] **Step 6: Commit**

```powershell
git add -- test_comprehensive.py backend/utils/database.py backend/blueprints/production.py
git commit -m "feat: make collector reports idempotent"
```

### Task 3: Collector Core Modules and Static Delivery

**Files:**
- Create: `tests/collector_core.test.js`
- Create: `frontend/static/js/core.js`
- Create: `frontend/static/js/api.js`
- Modify: `backend/app.py`

**Interfaces:**
- Produces: `MESCollector.escapeHtml(value)`, `classifyBarcode(value)`, `normalizeApiResponse(response, payload)`, and `createApiClient(fetchImpl)`.
- Produces: `GET /frontend/static/<path>`.

- [ ] **Step 1: Write failing Node tests**

Use `vm`/CommonJS-compatible exports and assert:

```javascript
assert.equal(core.escapeHtml('<img onerror=x>'), '&lt;img onerror=x&gt;');
assert.deepEqual(core.classifyBarcode('wo0001'), {kind: 'workorder', code: 'WO0001'});
assert.deepEqual(core.classifyBarcode(' TK0002 '), {kind: 'task', code: 'TK0002'});
assert.deepEqual(core.classifyBarcode('P-100'), {kind: 'product', code: 'P-100'});
```

Also assert the API client distinguishes 401, 4xx business failure, non-JSON response, timeout, and network failure.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/collector_core.test.js`  
Expected: FAIL because collector modules do not exist.

- [ ] **Step 3: Implement the minimal pure modules and route**

Use a UMD-style wrapper so the same files work in a browser and Node tests. Add:

```python
@app.route('/frontend/static/<path:filename>')
def frontend_static(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'static'), filename)
```

- [ ] **Step 4: Verify GREEN**

Run: `node --test tests/collector_core.test.js`  
Run: `python -m pytest test_comprehensive.py -k "page_routes" -q`  
Expected: all selected tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- tests/collector_core.test.js frontend/static/js/core.js frontend/static/js/api.js backend/app.py
git commit -m "feat: add collector core modules"
```

### Task 4: User-Scoped Offline Queue and Scanner Lifecycle

**Files:**
- Modify: `tests/collector_core.test.js`
- Create: `frontend/static/js/offline_queue.js`
- Create: `frontend/static/js/scanner.js`

**Interfaces:**
- Produces: `createOfflineQueue({storage, api, now, makeId})` with `enqueue`, `list`, `sync`, `remove`, `retry`, and `counts`.
- Produces: `createScanner({document, navigator, BarcodeDetector})` with `mount`, `startCamera`, `stopCamera`, and `unmount`.

- [ ] **Step 1: Write failing queue tests**

Assert user separation, FIFO replay, unique operation IDs, removal on success, retention on network/5xx, and `needs_attention` on 4xx. Use an in-memory storage adapter with the same `getItem/setItem/removeItem` interface as `localStorage`.

- [ ] **Step 2: Verify queue RED**

Run: `node --test --test-name-pattern="offline queue" tests/collector_core.test.js`  
Expected: FAIL because `offline_queue.js` is missing.

- [ ] **Step 3: Implement the minimal queue**

Persist under `mes.collector.queue.<userId>`. Replay only the active user's items and stop after a retryable failure to preserve order. Never store passwords or session cookies.

- [ ] **Step 4: Verify queue GREEN**

Run: `node --test --test-name-pattern="offline queue" tests/collector_core.test.js`  
Expected: PASS.

- [ ] **Step 5: Write failing scanner lifecycle tests**

Assert that `mount()` adds one listener, a second `mount()` does not duplicate it, `unmount()` removes it, unsupported camera returns `{supported:false}`, and `stopCamera()` stops every media track.

- [ ] **Step 6: Verify scanner RED**

Run: `node --test --test-name-pattern="scanner" tests/collector_core.test.js`  
Expected: FAIL because `createScanner` does not exist.

- [ ] **Step 7: Implement and verify the scanner lifecycle**

Implement the lifecycle without global permanent listeners. Run: `node --test --test-name-pattern="scanner" tests/collector_core.test.js`  
Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add -- tests/collector_core.test.js frontend/static/js/offline_queue.js frontend/static/js/scanner.js
git commit -m "feat: add collector offline queue and scanner"
```

### Task 5: Enterprise-Blue Collector Shell and Business Pages

**Files:**
- Create: `tests/collector_ui_design.test.js`
- Rewrite: `frontend/index.html`
- Create: `frontend/static/css/collector.css`
- Create: `frontend/static/js/pages.js`
- Create: `frontend/static/js/app.js`
- Modify: `frontend/manifest.json`

**Interfaces:**
- Consumes: Tasks 1–4 APIs and modules.
- Produces: stable DOM hooks `loginView`, `appView`, `networkState`, `syncCount`, `pageContent`, `bottomNav`, `modalRoot`, `toastRoot`, and six `data-page` navigation buttons.

- [ ] **Step 1: Write failing UI contract tests**

Assert the skeleton has no prefilled password, loads only local assets, exposes the stable hooks, and has accessible labels. Assert CSS defines `--navy-950`, `--primary-600`, `.collector-shell`, `.bottom-nav`, `.network-pill`, `.scan-stage`, `:focus-visible`, safe-area padding, `@media (max-height: 680px)`, and reduced motion.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/collector_ui_design.test.js`  
Expected: FAIL because the old inline single-file UI lacks these contracts.

- [ ] **Step 3: Build the shell and visual system**

Replace inline CSS/JS with local module files. Use a compact top status bar, scrollable content, and fixed bottom navigation. Keep touch targets at least 44px and primary actions at least 48px. Use semantic status text with color, not color alone.

- [ ] **Step 4: Implement safe page renderers and orchestration**

Render API text with DOM builders; no record values in HTML strings. Wire personal summary/tasks/reports, barcode resolver, report queue, pending inspections, inventory, and correctly named tool borrowing. Replace all `alert` calls with toast/result/dialog components and prevent duplicate submits.

- [ ] **Step 5: Verify GREEN and JavaScript regression**

Run: `node --test tests/collector_ui_design.test.js tests/collector_core.test.js`  
Then: `node --test tests/*.test.js`  
Expected: collector and full Node suites PASS.

- [ ] **Step 6: Commit**

```powershell
git add -- tests/collector_ui_design.test.js frontend/index.html frontend/manifest.json frontend/static
git commit -m "feat: rebuild MES collector terminal"
```

### Task 6: Collector Browser, Packaging, and Full Regression Acceptance

**Files:**
- Modify: `frontend/run.py`
- Create (ignored): `reports/ui/collector-420x800.png`
- Create (ignored): `reports/ui/collector-390x844.png`

**Interfaces:**
- Consumes: completed collector application.
- Produces: verified local/PyWebView-compatible collector.

- [ ] **Step 1: Run static and automated verification**

```powershell
node --check frontend/static/js/core.js
node --check frontend/static/js/api.js
node --check frontend/static/js/offline_queue.js
node --check frontend/static/js/scanner.js
node --check frontend/static/js/pages.js
node --check frontend/static/js/app.js
node --test tests/*.test.js
python -m pytest -q
python -m compileall backend mes_collector_app.py frontend/run.py
```

Expected: every command exits 0 with no JavaScript syntax error or Python traceback.

- [ ] **Step 2: Verify resource packaging contracts**

Confirm `build_collector.spec` and `mes_collector.spec` include the entire `frontend` directory. Replace the legacy miniature Flask backend in `frontend/run.py` with a launcher that imports `backend.app`, initializes the shared database, starts it without a reloader, and opens `/`; this makes the script use production authentication and APIs.

- [ ] **Step 3: Complete browser acceptance**

At 360×600, 420×800, and 390×844 verify login, all six navigation entries, scanner keyboard input, camera unsupported fallback, personal tasks, online report, simulated offline queue, restored sync, quality, inventory/tool naming, logout, and console cleanliness. Save the two principal screenshots under `reports/ui/`.

- [ ] **Step 4: Commit the launcher correction**

```powershell
git add -- frontend/run.py
git commit -m "fix: align collector packaging with main app"
```

- [ ] **Step 5: Final cleanliness check**

Run: `git status --short`  
Expected: no tracked changes; only deliberately ignored screenshots may exist.
