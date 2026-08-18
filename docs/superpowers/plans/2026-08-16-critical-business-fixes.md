# Critical Business Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven development and review each task before moving on.

**Goal:** Close the four production blockers found in the full business audit: standard event ingestion, controlled mobile reporting, write permissions, and legacy production CRUD bypasses.

**Architecture:** Keep existing domain services as the single write path. Initialize communication tables before any sink selection, make report control a server-side invariant, apply existing permission decorators to mutating routes, and reject legacy writes unless they meet the same domain guards. Preserve all existing records.

**Tech Stack:** Flask, SQLite, Python 3.8, browser JavaScript, pytest, Node test runner.

## Global Constraints

- Do not delete or rewrite existing business data.
- Do not add external runtime dependencies.
- Every behavior change must have a failing regression test first.
- Use existing `permission_required` and domain service functions.

---

### Task 1: Initialize standard event storage before AIM sink selection

**Status:** Verified. The runtime event test now waits for asynchronous dispatch instead of asserting before the dispatcher cycle completes.

**Files:**
- Modify: `backend/services/machine_access.py`
- Modify: `backend/machine_runtime.py`
- Test: `tests/test_machine_runtime.py`

**Behavior:** A fresh database must create standard event tables before `_default_event_sink()` decides whether central ingestion is available. AIM CSV import must create one `iot_device_event` and dispatch its outbox row.

### Task 2: Enforce controlled, idempotent mobile reports

**Status:** Completed and verified.

**Files:**
- Modify: `backend/blueprints/production.py`
- Modify: `frontend/static/js/app.js`
- Modify: `frontend/static/js/api.js`
- Test: `tests/admin_logic_workflows.test.js`
- Test: `tests/test_production_api.py`

**Behavior:** `/api/prod/report/add` rejects requests without an explicit controlled workflow marker; mobile online/offline submissions include `controlled:true` and a stable client operation id. Existing approved/rejected server workflow remains unchanged.

### Task 3: Protect mutating routes with permissions

**Status:** Completed and verified.

**Files:**
- Modify: `backend/blueprints/production.py`
- Modify: `backend/blueprints/base_data.py`
- Modify: `backend/blueprints/warehouse.py`
- Modify: `backend/blueprints/prod_ext.py`
- Test: `tests/test_permissions_api.py`

**Behavior:** Non-admin users require explicit module permissions for production, master data, inventory, and production extensions. Login alone is not sufficient for writes, approval, posting, or deletion.

### Task 4: Remove legacy production write bypasses

**Status:** Completed and verified for legacy add routes.

**Files:**
- Modify: `backend/blueprints/production.py`
- Modify: `backend/blueprints/prod_ext.py`
- Test: `tests/test_production_api.py`

**Behavior:** Legacy add/update/delete routes either delegate to validated domain services or return a clear 410/409 compatibility response. No route may create a production record without parent, quantity, route, and snapshot validation.

### Task 5: Full verification and review

**Status:** Python 215 passed; Node 122 passed; compileall and diff checks passed.

**Files:**
- No new production files.
- Test: all Python and Node suites.

**Behavior:** Focused tests pass, then full suites pass with no new failures. Request a code review before reporting completion.
