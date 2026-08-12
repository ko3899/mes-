# AIM CSV Directory Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自动采集 AIM 输出目录中的稳定 CSV，成功归档并写入生产追溯，失败隔离后可由管理员原记录重试。

**Architecture:** 新增独立 `MachineCsvCollector` 轮询器，每轮从数据库同步已启用且配置目录的端点，以“连续两轮元数据不变 + 达到稳定秒数”判定写完。报告服务负责失败记录和原记录重试，Flask 蓝图提供受控接口，生产入口管理采集线程生命周期。

**Tech Stack:** Python 3、Flask、SQLite、`pathlib`/`shutil`、Node.js 源码契约测试。

## Global Constraints

- 仅支持本机或 Windows 已挂载的绝对目录，不新增第三方依赖。
- 单文件最大 5 MB，每轮每端点最多处理 20 个 CSV，默认轮询 2 秒。
- 成功报告只生成待审核报工，不自动过账；失败不得更新生产数量。
- 测试数据以 `TEST-AIM-` 开头并保留，不执行清理。

---

### Task 1: 端点目录配置和数据库迁移

**Files:**
- Modify: `backend/utils/database.py`
- Modify: `backend/blueprints/machine_iot.py`
- Modify: `tests/test_production_chain_migration.py`
- Modify: `tests/test_machine_iot_api.py`

**Interfaces:**
- Produces: endpoint fields `csv_input_dir: TEXT`, `csv_stable_seconds: INTEGER DEFAULT 2`.

- [ ] **Step 1: Write failing migration and API tests**

断言迁移后两列存在；保存相对目录返回 400；稳定秒数小于 1 或大于 60 返回 400；两个启用端点绑定相同规范化目录返回 409；列表返回目录是否存在。

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_production_chain_migration.py tests/test_machine_iot_api.py`
Expected: FAIL because columns and validation are absent.

- [ ] **Step 3: Implement minimal schema and validation**

用 `_add_column_if_missing` 增加字段。`endpoint_save` 使用 `Path.resolve()` 校验绝对路径和目录唯一性，保存规范化路径；目录可暂时不存在。

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest -q tests/test_production_chain_migration.py tests/test_machine_iot_api.py`
Expected: PASS.

Commit: `feat: configure AIM CSV input directories`

### Task 2: 失败报告记录与原记录重试

**Files:**
- Modify: `backend/services/machine_access.py`
- Modify: `tests/test_machine_access_service.py`

**Interfaces:**
- Produces: `record_failed_inspection(db, endpoint, csv_bytes, filename, failure_path, reason) -> dict`.
- Produces: `retry_inspection_report(db, endpoint, report_id, archive_root) -> dict`.

- [ ] **Step 1: Write failing service tests**

断言坏表头和无 L1 可记录一条 `failed` 报告，原路径与原因存在且不创建 `prod_report`；业务条件修复后重试更新同一 report ID 为 `imported`，`retry_count=1`，只创建一个生产报工。

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_machine_access_service.py`
Expected: FAIL because failure/retry functions are absent.

- [ ] **Step 3: Refactor import into parse and persist phases**

提取纯解析器与“将已解析报告写入指定 report ID”的事务函数。失败占位字段使用 `sn='UNKNOWN'`、当前时间、`result='UNKNOWN'`，哈希仍按原字节计算。重试必须验证记录为 `failed` 且文件路径位于允许根目录。

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest -q tests/test_machine_access_service.py`
Expected: PASS.

Commit: `feat: isolate and retry AIM inspection reports`

### Task 3: CSV 目录轮询采集器

**Files:**
- Create: `backend/machine_csv_collector.py`
- Create: `tests/test_machine_csv_collector.py`

**Interfaces:**
- Produces: `MachineCsvCollector(db_path, archive_root, interval=2, max_files=20)` with `scan_once()`, `start()`, `stop()`.
- Consumes: `import_inspection_report` and `record_failed_inspection`.

- [ ] **Step 1: Write failing collector tests**

使用真实临时 SQLite 和目录断言：首轮仅记忆元数据；未达到稳定时间不导入；稳定后移动到 `_processing` 并导入；坏文件进入 `_failed`；同哈希重复文件不产生第二条业务数据；缺失目录只更新端点错误且扫描继续。

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_machine_csv_collector.py`
Expected: FAIL because module is absent.

- [ ] **Step 3: Implement bounded collector**

只枚举输入目录顶层、非隐藏 `.csv`，每端点最多 20 个。缓存键为 `(endpoint_id, resolved_path)`，值为 `(size, mtime_ns, first_stable_at)`。稳定后安全移动到 `_processing`；成功由报告服务归档，失败移动到 `_failed` 并持久化失败记录。跨卷使用临时复制、哈希校验、`os.replace` 后删除来源。

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest -q tests/test_machine_csv_collector.py tests/test_machine_access_service.py`
Expected: PASS.

Commit: `feat: collect AIM CSV result directories`

### Task 4: 重试 API、健康状态和管理页面

**Files:**
- Modify: `backend/blueprints/machine_iot.py`
- Modify: `admin/static/js/pages/machine_iot.js`
- Modify: `tests/test_machine_iot_api.py`
- Modify: `tests/admin_machine_iot.test.js`

**Interfaces:**
- Produces: `POST /api/iot/machine/reports/<id>/retry` (admin only).
- Extends: `GET /api/iot/machine/health` with `collector_directories`, `missing_directories`, `unstable_files`, `last_collection_at`.

- [ ] **Step 1: Write failing API and UI tests**

断言管理员可重试失败记录、普通用户返回 403、客户端不能提交文件路径；端点编辑器包含目录和稳定秒数字段；失败报告行出现事件监听式“重试”按钮；页面显示采集健康字段且动态值经过转义。

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_machine_iot_api.py && node --test tests/admin_machine_iot.test.js`
Expected: FAIL because retry route and UI controls are absent.

- [ ] **Step 3: Implement endpoints and UI**

重试接口只使用数据库 `archive_path`，调用服务层并返回同一记录。健康接口只统计配置和数据库状态。前端使用 `data-id` + 事件监听，禁止内联拼接用户数据。

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest -q tests/test_machine_iot_api.py && node --test tests/admin_machine_iot.test.js`
Expected: PASS.

Commit: `feat: manage AIM CSV retries and health`

### Task 5: 生产生命周期、操作手册和保留测试流程

**Files:**
- Modify: `production.py`
- Modify: `docs/AIM机台接入操作手册.md`
- Create: `tests/test_machine_csv_flow.py`

**Interfaces:**
- Production startup creates one `MachineCsvCollector`, calls `start()` after DB initialization, and always calls `stop()` in `finally`.

- [ ] **Step 1: Write failing lifecycle and end-to-end tests**

端到端测试创建 `TEST-AIM-CSV-OK` 与 `TEST-AIM-CSV-NG`，执行 L1、目录投放、两轮稳定扫描，断言报告、待审核报工、PASS/FAIL 工序记录和归档文件完整关联。启动契约测试断言采集器在生产入口启动和停止。

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_machine_csv_flow.py`
Expected: FAIL because production lifecycle is not wired.

- [ ] **Step 3: Wire lifecycle and update manual**

生产入口使用环境变量 `MES_MACHINE_ARCHIVE_DIR` 和 `MES_MACHINE_SCAN_SECONDS`。手册增加 Windows 共享目录映射、权限、端点配置、成功归档、失败重试和现场验收步骤。

- [ ] **Step 4: Run full regression**

Run: `python -m pytest -q`
Expected: all Python tests pass.

Run: `node --test tests/*.test.js`
Expected: all Node tests pass.

Run: `git diff --check`
Expected: no errors.

- [ ] **Step 5: Commit and start locally**

Commit: `feat: complete AIM CSV collection workflow`

启动 `python production.py`，验证 `/admin` 返回 200、未登录 `/api/iot/machine/health` 返回 401，并在浏览器打开“设备管理 → 机台通讯”供人工核对。

