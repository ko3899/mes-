# Existing AIM Workorder Test Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind two identifiable software-simulation serial numbers to existing workorder 13 and verify that both reach the AIM V2 production access decision.

**Architecture:** Reuse the existing released workorder, frozen route, active task, equipment and endpoint. Add only idempotent `prod_serial` rows inside one SQLite transaction, then exercise the real socket server and simulator without directly changing production counters.

**Tech Stack:** Python 3.8, SQLite, AIM V2 TCP simulator.

## Global Constraints

- Do not create a new workorder, route, task, equipment or endpoint.
- Do not directly update workorder or task production counters.
- Preserve all generated test records and identify them with the `SIM-AIM-20260816` or `SOFT-SIM-20260816` prefix.
- Do not modify any workorder other than workorder ID 13.
- Repeat execution must not create duplicate serial numbers.

---

### Task 1: Bind two test serial numbers

**Files:**
- Read/Write: `database/mes.db`

**Interfaces:**
- Consumes: `prod_workorder.id=13`, its `product_id`, released route and active task.
- Produces: two `prod_serial` rows with serial numbers `SIM-AIM-20260816-001` and `SIM-AIM-20260816-002`.

- [ ] **Step 1: Validate the existing workorder chain**

Run a read-only query that asserts workorder 13 is status 1 or 2, has one frozen route step matching endpoint process 12, and has an active task with status 1.

- [ ] **Step 2: Insert serial numbers transactionally**

Within `BEGIN IMMEDIATE`, read the workorder product ID and execute `INSERT OR IGNORE INTO prod_serial(serial_no,product_id,workorder_id,status) VALUES(?,?,13,0)` for both serial numbers. Roll back if either existing row is bound to another workorder/product or has a nonzero status.

- [ ] **Step 3: Verify persisted bindings**

Query both rows and require exactly two results, `workorder_id=13`, the workorder product ID, and `status=0`.

### Task 2: Verify AIM V2 access

**Files:**
- Read/Write: `database/mes.db`
- Execute: `machine_simulator.py`
- Execute: `backend/machine_socket_server.py`

**Interfaces:**
- Consumes: the two serial numbers from Task 1 and endpoint ID 1 configuration.
- Produces: persisted `iot_machine_request` audit rows and captured AIM ACK responses.

- [ ] **Step 1: Start an isolated in-process socket listener**

Create `MachineSocketServer(('127.0.0.1', 0), endpoint_id=1, db_path='database/mes.db')` so Windows assigns a temporary test port; stop it in a `finally` block.

- [ ] **Step 2: Send signed V2 requests**

Run `machine_simulator.py` once per SN using endpoint device code, station, cavity and shared secret. Use request numbers `SOFT-SIM-20260816-001` and `SOFT-SIM-20260816-002`.

- [ ] **Step 3: Verify responses and audit rows**

Require both simulator processes to exit 0, capture their ACK responses, and query the matching `iot_machine_request` rows. A result other than L1 must be reported with its exact business reason before any CSV result is generated.

- [ ] **Step 4: Record the checkpoint**

Report the two SN bindings, ACK decisions and database request IDs. Do not generate OK/NG CSV until both requests return L1.
