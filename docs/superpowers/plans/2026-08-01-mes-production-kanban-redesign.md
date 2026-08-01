# MES Production Kanban Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline, CDN-dependent kanban with a safe, locally packaged production command screen that updates without page reload and preserves stale data on refresh failures.

**Architecture:** Keep the Flask blueprint as the snapshot provider and page router, but move markup, CSS, controller code, and the pinned ECharts runtime into dedicated local files. A pure controller maps snapshots to view models, owns one chart instance per panel, suppresses concurrent refreshes, and tracks online/stale/auth states.

**Tech Stack:** Python 3.8+, Flask 2.3+, SQLite, pytest 8.x, HTML5, CSS3, framework-free JavaScript, Node.js built-in test runner, ECharts 5.4.3 vendored locally.

## Global Constraints

- Preserve `/kanban` and backward compatibility of `/api/kanban/realtime`.
- Keep real-time data protected by the existing login session.
- Do not use `<meta http-equiv="refresh">`, public CDN resources, fake carousel pages, or synthetic business data.
- Refresh every 30 seconds, refresh on visibility restoration, and never overlap requests.
- Preserve the last successful snapshot on failures and mark it stale; zero production displays `--` yield rather than `0%`.
- Target 1920×1080 and 1366×768.
- Write every behavior test first and verify the expected failure before production edits.

## File Map

- `backend/blueprints/kanban.py`: authenticated real-time snapshot and static page route.
- `frontend/kanban.html`: accessible kanban skeleton.
- `frontend/static/css/kanban.css`: command-screen visual system and responsive layouts.
- `frontend/static/js/kanban.js`: pure mapping plus refresh/chart/fullscreen controller.
- `frontend/static/vendor/echarts.min.js`: pinned local ECharts 5.4.3 distribution.
- `tests/kanban_core.test.js`: snapshot mapping and controller lifecycle.
- `tests/kanban_ui_design.test.js`: page/CSS local-resource and layout contracts.
- `test_comprehensive.py`: endpoint fields, authentication, and zero-data tests.

---

### Task 1: Complete the Authenticated Kanban Snapshot

**Files:**
- Modify: `test_comprehensive.py`
- Modify: `backend/blueprints/kanban.py`

**Interfaces:**
- Produces: `/api/kanban/realtime` data fields `server_time`, `active_orders`, `active_order_count`, `today_qualified`, `today_defect`, `equipment`, `workshop_output`, and `quality_alerts`.

- [ ] **Step 1: Write failing endpoint tests**

Assert an unauthenticated request returns 401 and an authenticated response includes a parseable ISO server time, active count matching the list, all three equipment status buckets, and a non-negative quality alert summary. Add a zero-data test that asserts numeric counts are zero and lists are empty.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest test_comprehensive.py -k "kanban_realtime" -q`  
Expected: FAIL because server time, active count, and quality alerts are missing.

- [ ] **Step 3: Implement the snapshot extension**

Use one server-local `today` value and parameterized SQL. Keep existing field names. Add fields rather than renaming old ones:

```python
'server_time': datetime.datetime.now().isoformat(timespec='seconds'),
'active_order_count': len(active_orders),
'quality_alerts': {'pending': pending_count, 'failed_today': failed_count},
```

Calculate `pending_count` from `qm_incoming_inspection.status=0` and `failed_count` from records whose `result='不合格'` and `DATE(created_at)=today`.

- [ ] **Step 4: Verify GREEN and regression**

Run: `python -m pytest test_comprehensive.py -k "kanban_realtime" -q`  
Then: `python -m pytest -q`  
Expected: all selected and full Python tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- test_comprehensive.py backend/blueprints/kanban.py
git commit -m "feat: complete kanban realtime snapshot"
```

### Task 2: Split and Locally Serve the Kanban Page

**Files:**
- Create: `tests/kanban_ui_design.test.js`
- Create: `frontend/kanban.html`
- Create: `frontend/static/css/kanban.css`
- Modify: `backend/blueprints/kanban.py`
- Modify: `backend/app.py` only if Task 3 collector static route is not yet present.

**Interfaces:**
- Produces: `/kanban` served from `frontend/kanban.html` and local `/frontend/static/...` assets.

- [ ] **Step 1: Write failing page/resource contract tests**

Assert `kanban.html` has `kanbanHeader`, `refreshButton`, `fullscreenButton`, `lastUpdated`, `staleState`, five metric hooks, order table, three chart hooks, and local CSS/JS/ECharts URLs. Assert there is no meta refresh and no `http://` or `https://` asset URL.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/kanban_ui_design.test.js`  
Expected: FAIL because the page is still an inline Python string.

- [ ] **Step 3: Create the semantic skeleton and route**

Use `send_from_directory(FRONTEND_DIR, 'kanban.html')` in the blueprint and delete `KANBAN_HTML`. Build header, metric strip, main order panel, and chart panels with visible loading/empty/error regions and accessible button labels.

- [ ] **Step 4: Build the dark command-screen CSS**

Define `--screen-bg`, `--panel-bg`, `--panel-border`, `--accent`, `--success`, `--warning`, and `--danger`; add 1920 and 1366 layouts, focus-visible styles, tabular numbers, progress bars, stale banner, and reduced-motion behavior.

- [ ] **Step 5: Verify GREEN**

Run: `node --test tests/kanban_ui_design.test.js`  
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add -- tests/kanban_ui_design.test.js frontend/kanban.html frontend/static/css/kanban.css backend/blueprints/kanban.py backend/app.py
git commit -m "feat: split production kanban shell"
```

### Task 3: Snapshot Mapper and Refresh Controller

**Files:**
- Create: `tests/kanban_core.test.js`
- Create: `frontend/static/js/kanban.js`

**Interfaces:**
- Produces: `mapSnapshot(data)`, `createKanbanController({fetchImpl, view, charts, clock})`, `refresh`, `start`, `stop`, and `resize`.

- [ ] **Step 1: Write failing mapping tests**

Assert yield is `--` when total is zero, normal yield is rounded, progress is clamped to 0–100, missing names become `-`, and source objects are not converted into HTML strings.

- [ ] **Step 2: Verify mapping RED**

Run: `node --test --test-name-pattern="snapshot" tests/kanban_core.test.js`  
Expected: FAIL because `mapSnapshot` does not exist.

- [ ] **Step 3: Implement and verify the snapshot mapper**

Implement `mapSnapshot` as a pure function, then run: `node --test --test-name-pattern="snapshot" tests/kanban_core.test.js`  
Expected: PASS.

- [ ] **Step 4: Write failing controller tests**

Use controllable promises to assert a second refresh returns the in-flight promise, successful refresh clears stale state, failure after success retains the previous view model and marks stale, initial failure shows retry, 401 shows authentication state, visibility restoration refreshes, and chart factories are called only once.

- [ ] **Step 5: Verify controller RED**

Run: `node --test --test-name-pattern="controller" tests/kanban_core.test.js`  
Expected: FAIL because `createKanbanController` does not exist.

- [ ] **Step 6: Implement and verify the refresh controller**

Implement one 30-second timer, one visibility listener, one resize listener, and reusable chart instances. Run: `node --test --test-name-pattern="controller" tests/kanban_core.test.js`  
Expected: PASS.

- [ ] **Step 7: Wire safe DOM rendering**

Build table rows with `document.createElement` and `textContent`. Connect manual refresh, full-screen API/F11, last-success time, stale banner, loading/empty states, and ECharts `setOption` updates.

- [ ] **Step 8: Run full Node tests and commit**

Run: `node --test tests/kanban_core.test.js tests/kanban_ui_design.test.js`  
Then: `node --test tests/*.test.js`  
Expected: all Node tests PASS.

```powershell
git add -- tests/kanban_core.test.js frontend/static/js/kanban.js frontend/kanban.html
git commit -m "feat: add resilient kanban controller"
```

### Task 4: Vendor ECharts and Verify Offline Packaging

**Files:**
- Create: `frontend/static/vendor/echarts.min.js`
- Modify: `tests/kanban_ui_design.test.js`

**Interfaces:**
- Produces: pinned local ECharts 5.4.3 browser build included through the existing `frontend` data directory.

- [ ] **Step 1: Add a failing local-dependency assertion**

Extend `kanban_ui_design.test.js` to read `frontend/static/vendor/echarts.min.js`, assert the file exists, is non-trivial, and the page references exactly `/frontend/static/vendor/echarts.min.js`.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/kanban_ui_design.test.js`  
Expected: FAIL because the local ECharts file does not exist.

- [ ] **Step 3: Add the pinned official distribution**

Vendor the unmodified ECharts 5.4.3 minified browser distribution and retain its license header. Do not edit the vendored file by hand. Confirm `build_desktop.spec`, `build_collector.spec`, and `mes_factory.spec` already include the entire `frontend` directory; the current inspected specs require no edit.

- [ ] **Step 4: Verify GREEN and static delivery**

Run: `node --test tests/kanban_ui_design.test.js`  
Request: `http://127.0.0.1:8080/frontend/static/vendor/echarts.min.js`  
Expected: test PASS and HTTP 200 without public-network access.

- [ ] **Step 5: Commit**

```powershell
git add -- frontend/static/vendor/echarts.min.js tests/kanban_ui_design.test.js
git commit -m "build: vendor kanban chart runtime"
```

### Task 5: Kanban Browser Acceptance and Full Regression

**Files:**
- Create (ignored): `reports/ui/kanban-1920x1080.png`
- Create (ignored): `reports/ui/kanban-1366x768.png`

**Interfaces:**
- Consumes: completed `/kanban` implementation.
- Produces: verified production command screen.

- [ ] **Step 1: Run automated and static verification**

```powershell
node --check frontend/static/js/kanban.js
node --test tests/*.test.js
python -m pytest -q
python -m compileall backend
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 2: Verify authenticated and unauthenticated states**

Open `/kanban` without a session and confirm the login-required state does not loop or clear the shell. Log in, reopen it, and confirm the complete snapshot renders.

- [ ] **Step 3: Verify refresh resilience**

At 1920×1080 and 1366×768 verify initial load, manual refresh, concurrent-click suppression, 30-second refresh, visibility restoration, simulated 500/network failure with retained stale data, subsequent recovery, full screen/F11, and resize. Confirm chart instances are not duplicated and the console has no unhandled errors.

- [ ] **Step 4: Save acceptance evidence**

Save screenshots to `reports/ui/kanban-1920x1080.png` and `reports/ui/kanban-1366x768.png`.

- [ ] **Step 5: Final repository check**

Run: `git status --short`  
Expected: no tracked changes; only ignored acceptance artifacts may exist.
