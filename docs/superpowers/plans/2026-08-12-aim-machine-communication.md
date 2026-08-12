# AIM Machine Communication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有MES增加兼容PPT V1协议和增强V2协议的机台准入、检测报告接收、Socket服务、模拟器与管理页面。

**Architecture:** 独立的TCP Socket进程负责连接和报文边界，调用无框架依赖的机台准入业务服务；Flask只提供配置、监控和CSV上传API。所有准入判定、报告幂等与SN状态更新集中在服务层，避免Socket和HTTP产生两套规则。

**Tech Stack:** Python 3、Flask、SQLite、标准库 `socketserver`/`csv`/`hashlib`、原生JavaScript、pytest、Node test runner。

## Global Constraints

- V1保持 `SN\r\n -> <L1>/<L3>\r\n` 兼容。
- V2使用 `REQ|2|设备|工站|穴位|请求号|SN`，响应包含请求号、L1/L3、原因、模板和说明。
- 响应目标1秒；数据库或状态不确定时必须L3失败关闭。
- L1不增加产量；有效报告到达后才创建过站和待审核报工。
- 原始报告落盘归档，SHA-256和业务去重键共同防重复。
- 第一期不实现OPC UA、Modbus、机械动作或安全控制。
- 所有生产代码遵循测试先行的红—绿—重构流程。

---

## File Structure

- `backend/services/machine_protocol.py`：V1/V2报文解析、响应格式化和消息帧限制。
- `backend/services/machine_access.py`：设备识别、SN/工序准入、幂等请求和报告导入业务。
- `backend/machine_socket_server.py`：独立TCP服务器、连接会话与逐行报文处理。
- `backend/blueprints/machine_iot.py`：配置、监控、日志、报告上传及重试API。
- `backend/utils/database.py`：通讯相关表、索引和菜单迁移。
- `machine_simulator.py`：V1/V2机台模拟客户端。
- `admin/static/js/pages/machine_iot.js`：通讯配置、在线监控、准入和报告页面。
- `tests/test_machine_protocol.py`：协议单元测试。
- `tests/test_machine_access_service.py`：准入和报告业务测试。
- `tests/test_machine_iot_api.py`：管理与上传API测试。
- `tests/test_machine_socket_server.py`：真实本地Socket集成测试。
- `tests/admin_machine_iot.test.js`：菜单与前端渲染测试。

### Task 1: Database migration and domain fixtures

**Files:**
- Modify: `backend/utils/database.py`
- Modify: `tests/test_production_chain_migration.py`

**Interfaces:**
- Produces: tables `iot_machine_endpoint`, `iot_machine_session`, `iot_machine_request`, `iot_inspection_report`, `iot_inspection_value`; indexes and additive migration.

- [ ] **Step 1: Write failing migration assertions**

Add assertions that all five tables exist, endpoint contains `equipment_id,protocol_version,bind_ip,listen_port,station_code,process_id,cavity_code,enabled`, request contains `request_no,sn,decision,reason_code,dedupe_key`, and report contains `file_hash,archive_path,import_status`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_production_chain_migration.py -q`
Expected: FAIL because `iot_machine_endpoint` is absent.

- [ ] **Step 3: Implement additive schema**

Create the five tables using `CREATE TABLE IF NOT EXISTS`, foreign keys to `eqp_ledger`, `base_process`, `prod_workorder`, `prod_task` and request/report parent rows, plus unique indexes for endpoint binding, request dedupe and report hash.

- [ ] **Step 4: Verify GREEN and idempotence**

Run: `python -m pytest tests/test_production_chain_migration.py -q`
Expected: all migration tests pass twice against a legacy database.

- [ ] **Step 5: Commit**

Run: `git add backend/utils/database.py tests/test_production_chain_migration.py && git commit -m "feat: add AIM communication schema"`

### Task 2: V1/V2 protocol codec

**Files:**
- Create: `backend/services/machine_protocol.py`
- Create: `tests/test_machine_protocol.py`

**Interfaces:**
- Produces: `MachineRequest`, `ProtocolError`, `parse_request(frame, endpoint)`, `format_response(request, decision)`.
- `parse_request` returns normalized `protocol_version,device_code,station_code,cavity_code,request_no,sn`.

- [ ] **Step 1: Write failing codec tests**

Cover V1 SN, `NoRead`, V2 valid request, wrong version, wrong field count, empty SN, forbidden CR/LF/pipe, UTF-8 decoding and 4096-byte maximum.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_machine_protocol.py -q`
Expected: collection fails because module is absent.

- [ ] **Step 3: Implement immutable request/decision codec**

Use dataclasses and pure functions. V1 identity comes from the endpoint; V2 identity must match the configured endpoint. Format V1 as exactly `<L1>\r\n` or `<L3>\r\n`; format V2 as pipe-delimited ACK with sanitized text.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_machine_protocol.py -q`
Expected: all protocol tests pass.

- [ ] **Step 5: Commit**

Run: `git add backend/services/machine_protocol.py tests/test_machine_protocol.py && git commit -m "feat: add AIM V1 and V2 protocol codec"`

### Task 3: Admission and report business service

**Files:**
- Create: `backend/services/machine_access.py`
- Create: `tests/test_machine_access_service.py`

**Interfaces:**
- Consumes: protocol `MachineRequest` and new database tables.
- Produces: `evaluate_access(db, endpoint, request, now=None) -> AccessDecision`; `import_inspection_report(db, endpoint, csv_bytes, filename, archive_root, now=None) -> dict`.

- [ ] **Step 1: Write failing admission tests**

Seed one released workorder with frozen route, tasks, SN and endpoint. Assert L1 for the current available step; L3 for unknown SN, disabled/repair equipment, wrong step, missing upstream transfer, completed duplicate step and missing laser/CCD template. Assert duplicate request number returns the original decision and one database row.

- [ ] **Step 2: Verify admission RED**

Run: `python -m pytest tests/test_machine_access_service.py -q`
Expected: FAIL because `evaluate_access` is absent.

- [ ] **Step 3: Implement minimal admission service**

Resolve SN from `prod_serial`, join workorder/task/frozen route, use existing transfer/report states, persist elapsed milliseconds and a stable reason code. Catch no database exceptions inside the service; the transport converts unexpected failures to L3.

- [ ] **Step 4: Verify admission GREEN**

Run: `python -m pytest tests/test_machine_access_service.py -q`
Expected: admission tests pass.

- [ ] **Step 5: Write failing report tests**

Cover valid PPT headers, dynamic measurement columns, OK and NG, incomplete header, SN mismatch, no prior L1, duplicate hash, same file renamed, atomic archive, rejected quarantine and creation of one pending report/station record only.

- [ ] **Step 6: Verify report RED**

Run: `python -m pytest tests/test_machine_access_service.py -q`
Expected: FAIL because report import is absent.

- [ ] **Step 7: Implement report import**

Decode UTF-8/UTF-8-SIG then configured fallback GBK, validate required first four columns, store arbitrary remaining measurements, write to a temporary file and atomically replace into `archive_root/YYYY/MM/DD`, persist hash and create pending `prod_report` without posting it.

- [ ] **Step 8: Verify service GREEN and commit**

Run: `python -m pytest tests/test_machine_access_service.py -q`
Expected: all service tests pass.

Run: `git add backend/services/machine_access.py tests/test_machine_access_service.py && git commit -m "feat: validate AIM access and inspection reports"`

### Task 4: Flask management and upload API

**Files:**
- Create: `backend/blueprints/machine_iot.py`
- Modify: `backend/app.py`
- Create: `tests/test_machine_iot_api.py`

**Interfaces:**
- Produces: `/api/iot/machine/endpoints`, `/save`, `/toggle`, `/sessions`, `/requests`, `/reports`, `/reports/upload`, `/reports/<id>/retry`, `/health`.

- [ ] **Step 1: Write failing authenticated API tests**

Assert endpoint validation and uniqueness, list enrichment with equipment/process names, toggle audit, paginated request/report filters, multipart CSV upload, report download authorization, retry of failed imports and health summary.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_machine_iot_api.py -q`
Expected: API paths return 404.

- [ ] **Step 3: Implement blueprint**

Use `login_required`, existing JSON envelope, parameterized SQL, bounded pagination and configurable archive root `MES_MACHINE_ARCHIVE_DIR`. Never accept archive paths from clients.

- [ ] **Step 4: Verify GREEN and regression**

Run: `python -m pytest tests/test_machine_iot_api.py tests/test_production_flow_service.py -q`
Expected: all selected tests pass.

- [ ] **Step 5: Commit**

Run: `git add backend/blueprints/machine_iot.py backend/app.py tests/test_machine_iot_api.py && git commit -m "feat: add AIM communication APIs"`

### Task 5: Independent Socket server and simulator

**Files:**
- Create: `backend/machine_socket_server.py`
- Create: `machine_simulator.py`
- Create: `tests/test_machine_socket_server.py`
- Modify: `start_production.bat`

**Interfaces:**
- Consumes: active endpoints, protocol codec and admission service.
- Produces: `MachineSocketServer`, `serve_endpoints(stop_event=None)`, CLI simulator with `--host --port --protocol --device --station --cavity --sn`.

- [ ] **Step 1: Write failing real-socket tests**

Start a server on port 0 and assert V1/V2 framing, split packets, two frames in one packet, NoRead L3, identity mismatch L3, database exception L3, idle timeout and clean shutdown.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_machine_socket_server.py -q`
Expected: module is absent.

- [ ] **Step 3: Implement threaded bounded server**

Use `socketserver.ThreadingTCPServer`, `StreamRequestHandler.readline(4097)`, per-connection SQLite connections, daemon threads, timeouts and deterministic close. Bind only enabled endpoints and refuse duplicate address/port configuration.

- [ ] **Step 4: Implement simulator and startup integration**

Simulator sends one request and prints raw response plus parsed decision. Production launcher starts web and Socket processes separately and preserves existing web startup behavior when no endpoint is configured.

- [ ] **Step 5: Verify GREEN and compile**

Run: `python -m pytest tests/test_machine_socket_server.py -q && python -m compileall backend machine_simulator.py`
Expected: tests pass and no syntax errors.

- [ ] **Step 6: Commit**

Run: `git add backend/machine_socket_server.py machine_simulator.py tests/test_machine_socket_server.py start_production.bat && git commit -m "feat: run AIM socket gateway and simulator"`

### Task 6: Admin communication center

**Files:**
- Create: `admin/static/js/pages/machine_iot.js`
- Modify: `admin/index.html`
- Modify: `admin/static/js/menu.js`
- Modify: `admin/static/js/app.js`
- Modify: `admin/static/js/ui_utils.js`
- Create: `tests/admin_machine_iot.test.js`

**Interfaces:**
- Consumes: Task 4 APIs.
- Produces: `eqp/machine-iot` page with endpoint configuration, online monitoring, request logs, report logs and retry action.

- [ ] **Step 1: Write failing DOM/source tests**

Assert the equipment menu exposes “机台通讯”, router invokes `renderMachineIot`, all dynamic values pass through `MESUI.escapeHtml`, protocol/status labels and request/report filters exist, and save/retry calls use the intended APIs.

- [ ] **Step 2: Verify RED**

Run: `node --test tests/admin_machine_iot.test.js`
Expected: FAIL because page script and route are absent.

- [ ] **Step 3: Implement page**

Follow current card/table/modal styles. Provide tabs for endpoints, online sessions,准入日志 and检测报告; endpoint modal loads equipment/process options and validates V1 IP/port uniqueness cues.

- [ ] **Step 4: Verify GREEN**

Run: `node --test tests/admin_machine_iot.test.js tests/admin_ui_design.test.js tests/admin_api.test.js`
Expected: all selected tests pass.

- [ ] **Step 5: Commit**

Run: `git add admin tests/admin_machine_iot.test.js && git commit -m "feat: add AIM communication admin center"`

### Task 7: End-to-end acceptance, documentation and regression

**Files:**
- Modify: `README.md`
- Create: `docs/AIM机台接入操作手册.md`
- Create: `examples/aim/ok.csv`
- Create: `examples/aim/ng.csv`

**Interfaces:**
- Produces: operator setup, network rules, V1/V2 examples, CSV specification, simulator commands, fault recovery and rollout checklist.

- [ ] **Step 1: Add executable acceptance test**

Extend Socket/API integration tests to execute: V2 request L1, upload OK CSV, inspect request/report/SN trace, repeat request/file, verify one business update; execute L3 wrong-step flow and verify no report/quantity update.

- [ ] **Step 2: Run acceptance RED if any boundary is missing**

Run: `python -m pytest tests/test_machine_socket_server.py tests/test_machine_iot_api.py -q`
Expected: any uncovered integration boundary fails before its final implementation.

- [ ] **Step 3: Complete only missing integration glue and documentation**

Document fixed MES IP, firewall port, endpoint binding, timeout, encoding, backup path, simulator command, CSV fields, L3 reason handling, rollback and one-machine pilot checklist. Mark all example data as test data.

- [ ] **Step 4: Run full verification**

Run: `python -m pytest -q`
Expected: all Python tests pass.

Run: `node --test tests/*.test.js`
Expected: all Node tests pass.

Run: `git diff --check && git status --short`
Expected: no whitespace errors; only intended documentation/example changes remain.

- [ ] **Step 5: Commit**

Run: `git add README.md docs/AIM机台接入操作手册.md examples/aim tests && git commit -m "docs: add AIM machine rollout guide"`

