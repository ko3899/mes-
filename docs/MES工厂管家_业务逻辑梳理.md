# MES工厂管家 业务逻辑梳理

> 梳理对象：`backend/` 目录（约 1.97 万行 Python，Flask + SQLite）
> 梳理时间：2026-08-25
> 覆盖范围：49 个注册蓝图、`services/` 领域服务层、`utils/` 基础设施层、机台接入与边缘网关
> 说明：本文件仅做代码阅读与业务逻辑梳理，未修改任何业务代码。

---

## 1. 系统总览与分层架构

```
┌────────────────────────────────────────────────────────────┐
│  前端：admin/（PC 管理后台） + frontend/（采集终端/看板）        │
├────────────────────────────────────────────────────────────┤
│  Blueprints 层（51 个蓝图，约 300+ 路由）                     │
│  按业务域注册到 Flask app，多数使用 crud_* 通用模式             │
├────────────────────────────────────────────────────────────┤
│  Services 层（backend/services/，事务化领域服务）              │
│  production_flow / quality_disposition / procurement_flow   │
│  machine_access / device_event_* / mqtt_event_consumer ...  │
├────────────────────────────────────────────────────────────┤
│  Utils 层（database / helpers / db_errors / 限流 / 日志）      │
├────────────────────────────────────────────────────────────┤
│  存储层：SQLite mes.db（157 张表，支持 PostgreSQL 迁移）        │
│  机台接入：machine_socket_server / machine_reader_client     │
│  边缘网关：edge_gateway/（独立进程，事件箱 + 传输）              │
└────────────────────────────────────────────────────────────┘
```

**入口**：`backend/app.py` 的 `create_app()` 注册全部蓝图、静态路由、Excel 导入导出、物料追溯 API；启动时 `init_db()` + `_init_extra_tables()` 初始化库表，随后启动 `MachineCommunicationRuntime`（Socket 网关管理 + CSV 采集 + AIM 事件派发）。

**主要依赖**（`requirements.txt`）：flask、openpyxl、waitress、psutil、paho-mqtt、flask-limiter、psycopg2-binary。

---

## 2. 模块职责地图（按业务域归类）

### 2.1 认证与系统管理域

| 蓝图 | 核心职责 | 代表接口 |
|---|---|---|
| `auth.py` | 验证码、登录/登出、会话、用户信息 | `/api/login`、`/api/captcha`、`/api/user/info` |
| `system.py` | 用户/角色/部门/菜单/字典 CRUD | `/api/sys/user/*`、`/api/sys/role/*`、`/api/sys/menu/*` |
| `sys_ext.py` | 密码、权限目录、在线用户、登录日志、系统配置、公告、审计、监控、IP白名单、打印模板、通知渠道 | `/api/sys/permissions/catalog`、`/api/sys/role/permissions`、`/api/sys/online/*`、`/api/sys/config/*`、`/api/sys/monitor` |
| `tenant.py` | 多租户 CRUD | `/api/tenant/*` |
| `backup.py` | 数据库备份/恢复/下载 | `/api/backup/*` |
| `security.py` | API Token 生成/校验、内存限流、安全日志 | `/api/security/token/*` |
| `update.py` | 版本检查/下载 | `/api/update/check`、`/api/version` |
| `notification.py` | 站内通知 | `/api/notification/*` |
| `table_order.py` | 表格自定义排序（sys_table_order） | `/api/table-order/*` |

### 2.2 基础数据域

| 蓝图 | 核心职责 | 代表接口 |
|---|---|---|
| `base_data.py` | 车间、工序、产品、BOM、不良项、单位、工艺路线 CRUD | `/api/base/workshop/*`、`/api/base/process/*`、`/api/base/product/*`、`/api/base/bom/*`、`/api/base/route/save` |
| `supplier.py` | 供应商 | `/api/base/supplier/*` |
| `customer.py` | 客户 | `/api/base/customer/*` |
| `barcode.py` | 条码生成/扫描 | `/api/barcode/*` |
| `document.py` | 文档上传下载（含 SOP） | `/api/document/*` |

### 2.3 生产管理域（核心）

| 蓝图 | 核心职责 | 代表接口 |
|---|---|---|
| `production.py` | 销售订单→计划→批次→工单→任务→报工 全链路（调用 `production_flow`） | `/api/prod/sales/save`、`/api/prod/plan/save`、`/api/prod/batch/save`、`/api/prod/workorder/save`、`/api/prod/workorder/<id>/release`、`/api/prod/workorder/<id>/generate-tasks`、`/api/prod/report/*/approve|post|reject` |
| `prod_ext.py` | 工序转移、生产领料（申请/发料/收料/退料）、委外、序列号、工时、包装（调用 `production_flow`） | `/api/prod/transfer/add`、`/api/prod/material/<id>/request|issue|receive|return`、`/api/prod/serial/generate` |
| `process_ctrl.py` | 过站/跳站/离站、返工、装箱、物料锁定、不良接收、异常、工序流 | `/api/process/pass-station`、`/api/process/rework`、`/api/process/close-box`、`/api/process/defect-receive` |
| `schedule.py` | 班组、排班计划 | `/api/sched/team/*`、`/api/sched/plan/*` |
| `aps.py` | APS 排程预览、资源负荷、甘特图 | `/api/aps/schedule`、`/api/aps/resource`、`/api/aps/gantt` |
| `stage.py` | 阶段码、阶段记录 | `/api/stage/*` |
| `site.py` | 工位、安灯（呼叫/响应/解决）、返工报废处置（调用 quality_disposition） | `/api/site/andon/*`、`/api/site/rework/<id>/approve|reject|start-task` |

### 2.4 质量管理域

| 蓝图 | 核心职责 | 代表接口 |
|---|---|---|
| `quality.py` | IQC 来料 / PQC 过程 / OQC 出货 检验单 CRUD | `/api/qm/incoming/*`、`/api/qm/process/*`、`/api/qm/outgoing/*` |
| `qm_ext.py` | 不良品处理、首件检验、8D 报告、供应商评审、质量统计 | `/api/qm/defect/*`、`/api/qm/first/*`、`/api/qm/8d/*`、`/api/qm/supplier-eval/*` |
| `qm_plus.py` | CAPA、控制计划、ECO 变更 | `/api/qm/capa/*`、`/api/qm/control-plan/*`、`/api/qm/eco/*` |
| `fmea.py` | FMEA 分析与统计 | `/api/fmea/*` |
| `eqp_schedule.py` | 点检项目、质检模板、排班日历、路由卡 | `/api/eqp/check-project/*`、`/api/qm/template/*`、`/api/routing-card/generate` |
| `ai.py` | AI 质检（当前无适配器，返回 503） | `/api/ai/inspect`、`/api/ai/config` |

### 2.5 库存与供应链域

| 蓝图 | 核心职责 | 代表接口 |
|---|---|---|
| `inventory.py` | 入库/出库单据（草稿→过账）、库存余额、库存事务 | `/api/inv/inbound/*`、`/api/inv/outbound/*`、`/api/inv/inbound/<id>/post`、`/api/inv/balance/list` |
| `warehouse.py` | 三级库位（仓库/库区/库位）、库存事务日志、到货通知（写入已停用） | `/api/warehouse/*`、`/api/area/*`、`/api/location/*`、`/api/arrival/*` |
| `scm.py` | 采购单列表、供应商评估 | `/api/scm/purchase/list`、`/api/scm/supplier/eval/*` |
| `sop_warehouse.py` | 电子 SOP、线边仓 | `/api/sop/*`、`/api/line-warehouse/*` |

> 注：采购订单的事务化编排（草稿→提交→审核→到货→关闭）在 `services/procurement_flow.py`，但尚未有蓝图直接暴露这些方法（`scm.py` 目前只读采购相关库存），到货/收料服务（`receiving_service`）也未实现，`warehouse.py` 已把到货通知写入口停用（返回 410）。

### 2.6 设备管理域

| 蓝图 | 核心职责 | 代表接口 |
|---|---|---|
| `equipment.py` | 设备类型、台账、维修单、保养计划、点检 | `/api/eqp/type/*`、`/api/eqp/ledger/*`、`/api/eqp/repair/*`、`/api/eqp/maintenance/*`、`/api/eqp/check/*` |
| `eqp_plus.py` | 模具、治具 | `/api/eqp/mold/*`、`/api/eqp/fixture/*` |
| `tool.py` | 工具类型、台账、领用归还 | `/api/tool/type/*`、`/api/tool/ledger/*`、`/api/tool/borrow/*` |

### 2.7 IoT / 机台 / 设备平台域

| 蓝图 | 核心职责 | 代表接口 |
|---|---|---|
| `machine_iot.py` | AIM 机台通讯端点配置/监控、会话/请求/报告查询、检测 CSV 上传/重试 | `/api/iot/machine/endpoints/*`、`/api/iot/machine/reports/upload`、`/api/iot/machine/reports/<id>/retry`、`/api/iot/machine/health` |
| `iot.py` | IoT 设备列表、数据推送、Webhook | `/api/iot/data/push`、`/api/iot/webhook` |
| `device_platform.py` | 标准设备事件接收（管理端 + 网关鉴权端）、命令下发、健康检查 | `/api/device-platform/events`、`/api/device-platform/gateway-events`、`/api/device-platform/commands/*` |

### 2.8 扩展域（ERP/AI/HR/成本/服务/能耗等）

| 蓝图 | 核心职责 | 代表接口 |
|---|---|---|
| `erp.py` | ERP 配置与同步（产品/订单/库存，多为占位） | `/api/erp/config`、`/api/erp/sync/*` |
| `erp_deep.py` | 用友/金蝶/SAP 深度同步（未实现 501） | `/api/erp/yonyou/sync`、`/api/erp/kingdee/sync`、`/api/erp/sap/sync` |
| `hr.py` | 培训、技能矩阵 | `/api/hr/training/*`、`/api/hr/skill-matrix/*` |
| `five_s.py` | 5S 稽核 | `/api/5s/audit/*` |
| `svc.py` | 售后投诉、退货 | `/api/svc/complaint/*`、`/api/svc/return/*` |
| `cost.py` | 成本记录、汇总、差异 | `/api/cost/*` |
| `util.py` | 能源、环境监测 | `/api/util/energy/*`、`/api/util/environment/*` |
| `analytics.py` | OEE、产能、交期预警、库存周转、良率、移动看板 | `/api/analytics/oee`、`/api/analytics/capacity`、`/api/analytics/*` |
| `dashboard.py` | 仪表盘统计与图表 | `/api/dashboard`、`/api/dashboard/charts` |
| `kanban.py` | 生产看板实时快照 | `/api/kanban/realtime` |
| `report.py` | 生产报表、SPC 数据/图/CPK、PDF | `/api/report/production`、`/api/spc/*` |
| `search.py` | 全局搜索、各域查询统计 | `/api/search/global`、`/api/query/*` |
| `trace_ext.py` | 5M1E 追溯、碳排放 | `/api/trace/5m1e/<sn>`、`/api/carbon/emission` |
| `flow.py` | 通用审批流（定义/实例/审批/驳回，可联动工单下达） | `/api/flow/definition/*`、`/api/flow/instance/submit`、`/api/flow/task/approve` |

---

## 3. 核心业务流程（services/ 层）

### 3.1 生产主链：销售订单 → 工单 → 报工（`production_flow.py`）

编排顺序与数量校验链路：

```
销售订单 prod_sales_order (SO)
   │ save_sales_order: 客户校验、明细数量/单价校验、金额汇总
   ▼
生产计划 prod_plan (PL)
   │ save_plan: 计划必须关联"已确认"销售订单；明细必须匹配销售订单产品；计划数量 ≤ 销售剩余
   ▼
生产批次 prod_batch (PB)
   │ save_batch: 批次数量 ≤ 计划明细剩余；已取消/已完成计划不可拆分
   ▼
生产工单 prod_workorder (WO)
   │ save_workorder: 工单数量 ≤ 批次剩余；工艺路线须与产品/车间匹配
   ▼
工单下达 release_workorder
   │ 校验：仅草稿可下达；冻结工艺路线快照（route_snapshot + route_step）
   │ 冻结 BOM 快照（bom_snapshot）；校验每个工序已分配车间
   ▼
生成任务 generate_tasks（每个冻结工序一条 prod_task）
   │ 生成领料需求 generate_material_requirements（每行 BOM 快照一条 prod_material_req）
   ▼
执行：领料申请 → 发料 → 收料 → 退料（request/issue/receive/return_material）
   │ 发料扣减 inv_balance、写 inv_transaction；退料回补库存
   ▼
报工 prod_report（提交 → 审核 → 过账）
   │ 只有"已审核"报工可过账 post_report
   │ 过账累加任务/工单 completed_qty、defect_qty
   ▼
工序转移 create_transfer（相邻工序、量不超过上工序合格-已转移）
```

关键数量规则（均有代码级强校验）：

- **销售→计划→批次→工单**：每一层累计数量不能超过上层剩余数量。
- **任务完成判定**：普通任务 `completed_qty >= planned_qty` 才置为完成（status=3），不良数只保留为历史损失，不能代替合格产出。
- **报工过账**：`approval_status` 0=已提交 → 1=已审核 → 2=已过账；只有已过账报工才影响任务/工单数量。
- **工序转移**：`create_transfer` 只允许冻结路线中相邻工序（step_no 差 1），转移数量 ≤（上工序合格报工 - 已转移）。
- **事务控制**：`_atomic(db)` 使用 SAVEPOINT（嵌套事务）保证中间态一致，任何 BusinessError 回滚。

### 3.2 质量处置主链（`quality_disposition.py`，SN 级）

与 AIM 机台检测联动，形成 NG 闭环：

```
机台检测 NG → create_ng_disposition：创建质量处置单（pending_review）+ SN 置 quality_hold
   ▼
审批 approve_disposition（action ∈ rework / scrap / concession）
   ├─ rework：创建"草稿返工任务"（task_type='rework', source_task_id, target_sn），SN 置 quality_rework
   ├─ scrap：SN 置 quality_scrapped（永久阻断）
   └─ concession：记录 prod_station_record（'让步接收'），SN 置 quality_concession
   ▼
返工任务启动 start-task（validate_rework_task_start + transition_status 1）
   → 返工任务状态 0（草稿）→ 1（运行中）→ 完成/再 NG
   ▼
返工报工过账 apply_posted_rework_result（在 post_report 事务内）
   ├─ OK：补回原任务/工单合格数，SN 恢复 quality_normal，处置单 completed
   └─ NG：record_rework_ng_cycle，关闭本处置单、创建下一轮 pending_review（cycle_no+1），SN 再置 hold
```

关键点：

- **唯一性约束**：`(sn, route_step_id)` 上存在部分唯一索引，同一 SN 同一工序只能有一个未完成处置单（pending_review/approved/task_started）。
- **防重复**：`INSERT OR IGNORE` + 状态条件更新（`WHERE status='pending_review'`）实现幂等。
- **返工报工单件约束**：合格+不良必须等于 1，且不能同时为 1（单件 OK/NG）。
- **NG 即冻结**：NG 检测报告导入时立即把 SN 置 quality_hold，在审批窗口期机台不可再次准入。

### 3.3 采购流程（`procurement_flow.py`）

采购订单状态机（较完整的事务化编排，但蓝图层尚未接入）：

```
draft(0) ──submit──▶ submitted(1) ──approve──▶ approved(2) ──到货──▶ partial_arrival(3)/fully_arrived(4) ──▶ closed(5)
   │                    │                          │
   └──cancel──▶ cancelled(7)  ◀──reject── rejected(6)┘
```

- `save_purchase_order`：供应商启用校验、物料启用校验、数量为正有限值、单价/税率非负；草稿或驳回态可编辑（重建明细）。
- `submit`：仅草稿/驳回可提交；`review`：仅 submitted 可审核；驳回必填原因。
- `cancel`：草稿/提交/审核/驳回可取消，**已发生到货（inv_arrival_notice）不可取消只能关闭**。
- `close`：已审核或到货中可关闭，必填关闭原因。
- 状态变化写入 `scm_procurement_status_log`。

### 3.4 库存单据流程（`inventory.py`）

```
新增 add（草稿，status=0）
   │ 校验产品存在、数量>0、单价≥0；单据号前缀 RK/CK（gen_no_in_transaction）
   ▼
修改 update（仅草稿可改：删除明细重建）
   ▼
删除 delete（仅草稿可删：级联删明细）
   ▼
过账 post
   ├─ 出库：预检库存（缺料则整单回滚 409，返回缺料清单）
   ├─ 入库：库存 += 数量/金额；出库：库存 -= 数量，按移动平均成本扣减金额
   ├─ 写 inv_transaction（余额流水）与 inv_transaction_log
   └─ 单据 status 0→1（不可重复过账）
```

### 3.5 机台准入与检测报告（`machine_access.py`）

```
机台 TCP 请求 → parse_request（V1 纯 SN / V2 带 HMAC 签名+可选 nonce）
   → evaluate_access 逐级校验：
      SN 读取失败 / 端点禁用 / 设备停用 / SN 不存在 / SN 异常状态
      工单存在且状态∈{1,2} / 产品匹配 / 路线已冻结
      按路线步骤找当前应执行工序（无 PASS 过站记录的首个步骤）
      工序必须匹配端点 process_id（否则 WRONG_STEP）
      质量上下文（hold → 拒绝；scrapped → 拒绝；rework → 需已启动返工任务）
      任务存在且状态=1（运行中）
      V2 需配置激光/检测模板
      （防重放：V2 nonce 唯一表；dedupe_key 幂等）
   → 返回 L1（允许，附模板）/ L3（拒绝，附 reason_code）
   ▼
检测 CSV 导入 import_inspection_report
   → 校验表头（2D Barcode/Date/Time/OK(1)/NG(0)）
   → 归档到 machine_archive/YYYY/MM/DD + 文件哈希防重
   → 找到对应的 L1 pending 请求 → 写 iot_inspection_report + iot_inspection_value
   → 生成草稿报工 prod_report（approval_status=0）
   → 写 prod_station_record（过站 PASS / 检测不良 FAIL）
   → NG：创建质量处置单并冻结 SN
   → 入 AIM 事件箱（iot_aim_event_outbox），由运行时常驻线程派发标准事件
```

---

## 4. 状态机汇总

### 4.1 工单（prod_workorder.status）

| 值 | 含义 | 来源 |
|---|---|---|
| 0 | 草稿（draft） | 新建 |
| 1 | 已下达（released） | release_workorder（冻结路线/BOM 后） |
| 2 | 生产中（producing） | 首个报工过账后 |
| 3 | 已完工（completed） | 累计合格数 ≥ 计划数 |
| 4 | 已暂停（paused） | 人工暂停 |
| 5 | 已关闭（closed） | 从已完工关闭 |
| 6 | 已取消（cancelled） | 草稿/已下达/生产中可取消 |

允许流转（`production_flow._TRANSITIONS['workorder']`）：
`0→{1,6}, 1→{2,4,6}, 2→{3,4}, 4→{2,6}, 3→{5}`

### 4.2 任务（prod_task.status）

| 值 | 含义 |
|---|---|
| 0 | 待执行（pending，含草稿返工任务） |
| 1 | 运行中（running） |
| 2 | 已暂停（paused） |
| 3 | 已完成（completed） |

流转：`0→{1}, 1→{2,3}, 2→{1,3}`。普通任务按合格数完成；返工任务（task_type='rework'）由质量处置驱动。

### 4.3 报工（prod_report.approval_status）

| 值 | 含义 |
|---|---|
| 0 | 已提交（submitted） |
| 1 | 已审核（approved） |
| 2 | 已过账/已记账（posted） |
| 3 | 已驳回（rejected） |

流转：`0→{1,3}, 1→{2}`。只有已过账报工才影响任务/工单数量（对应前端标签：已提交/已审核/已记账/已驳回）。

### 4.4 销售订单 / 生产计划 / 生产批次

三者同一套 5 态：`0 草稿 → 1 已确认/已发布/已排产 → 2 生产中 → 3 已完成`，`4 已取消`（草稿/确认/生产中可取消）。计划必须有"已确认"销售订单；批次必须挂在有效计划明细下。

### 4.5 出入库单据（inv_inbound / inv_outbound.status）

| 值 | 含义 |
|---|---|
| 0 | 草稿（可改/可删） |
| 1 | 已过账（锁定，不可改/删/重复过账） |

### 4.6 采购订单（scm_purchase_order.status）

| 值 | 含义 |
|---|---|
| 0 | 草稿 |
| 1 | 已提交（待审核） |
| 2 | 已审核 |
| 3 | 部分到货 |
| 4 | 全部到货 |
| 5 | 已关闭 |
| 6 | 已驳回 |
| 7 | 已取消 |

### 4.7 质量处置单（prod_quality_disposition.status / action）

- status：`pending_review（待审核）→ approved（已批准返工）→ task_started（返工任务已启动）→ completed（已闭环）`；`rejected（驳回）`。
- action：`pending → rework（返工）/ scrap（报废）/ concession（让步接收）`。
- 对应 SN 质量状态（prod_serial.quality_status）：`normal / quality_hold / rework / scrapped / concession`。

### 4.8 机台请求与检测报告（iot_*）

- `iot_machine_request.decision`：`L1`（允许加工）/ `L3`（拒绝，带 reason_code）。
- `iot_machine_request.report_status`：`pending`（已准入待报告）/ `received`（已收报告）/ `not_required`。
- `iot_inspection_report.import_status`：`imported` / `failed` / `retrying`；`result`：OK / NG。
- `iot_device_event.processing_status`：`pending`（待处理），处理失败可重试。
- `iot_device_command.status`：`queued / leased / acknowledged / failed / expired`。

### 4.9 其它

| 单据 | 状态 |
|---|---|
| eqp_repair_order | 0 待维修 → 1 维修中 → 2 已完成（联动 eqp_ledger 1运行/2维修） |
| eqp_ledger | 0 停用 / 1 运行 / 2 维修 |
| prod_andon | 0 已呼叫 → 1 已响应 → 2 已解决 |
| flow_instance | 0 审批中 → 1 通过 → 2 驳回；flow_task 0 待办 → 1 通过 → 2 驳回 |
| eqp_maintenance_plan | 1 启用；next_date 逾期判断 |

所有核心业务状态变化写入 `sys_business_status_log`（entity_type/entity_id/from_status/to_status/action/operator_id），为审计追溯提供依据。

---

## 5. 权限模型

### 5.1 装饰器机制（`utils/helpers.py`）

- **`login_required`**：`_load_session_user()` 从 session 取 user_id，**每次请求实时查库**（避免 session 过期/停用/删除的缓存逃逸）；用户不存在/停用则清会话并返回 401/403。
- **`admin_required`**：在登录基础上校验 `role_key == 'admin'` 且角色启用，同时校验 session username 与库中一致（防篡改）。
- **`permission_required(*perms)`**：管理员（role_key=admin 且启用）直接放行；普通用户从 `sys_role.menu_ids` 读取权限列表（JSON 数组或逗号分隔），要求请求所需权限与用户权限集合有交集；并带**遗留读权限别名**（如 `base:read` 可命中 `base:product:list` 等）。

权限判定顺序：登录 → 管理员短路 → 取角色 menu_ids → 解析（JSON 或逗号）→ 交集判断 → 放行/403。

### 5.2 权限目录（`blueprints/sys_ext.py` 的 `ACTION_PERMISSION_CATALOG`）

系统维护一个**动作权限白名单目录**（`/api/sys/permissions/catalog`），角色设置权限时只接受目录内的 key：

```
base:read / base:write
inv:read / inv:write
prod:sales:read / prod:sales:write
prod:plan:read / prod:plan:write
prod:batch:read / prod:batch:write
prod:workorder:read / prod:workorder:write
prod:task:read / prod:task:write
prod:report:read / prod:report:create / prod:report:review / prod:report:post
prod:extension:read / prod:extension:write
eqp:read / eqp:write
doc:read / doc:write
aps:write / cost:write / erp:write / flow:write / flow:approve
hr:write / iot:write / process:write / quality:write
sched:write / site:write / svc:write / tool:write / util:write
```

### 5.3 权限 key 命名规律

`<域>:<资源>:<动作>`，域如 `base/inv/prod/eqp/doc/flow/hr/iot/process/quality/sched/site/svc/tool/util/aps/cost/erp`；动作常用 `read/write`，精细场景用 `create/review/post/approve`。同时存在**菜单级权限 key**（sys_menu.perms），形如 `base:route:list`、`inv:inbound:list`、`prod:sales:list`（资源:list 表示页面可见性），与动作权限目录形成"页面 + 操作"双轨。

---

## 6. 数据模型

### 6.1 表命名规律

| 前缀 | 业务域 | 示例 |
|---|---|---|
| `sys_` | 系统管理 | sys_user、sys_role、sys_menu、sys_dict、sys_log、sys_config、sys_tenant、sys_numbering、sys_business_status_log、sys_notification、sys_table_order |
| `base_` | 基础主数据 | base_product、base_process、base_workshop、base_bom、base_process_route(_detail)、base_defect、base_supplier、base_customer、base_workstation、base_station_config、base_stage_code |
| `prod_` | 生产 | prod_sales_order(_item)、prod_plan(_item)、prod_batch、prod_workorder、prod_task、prod_report、prod_transfer、prod_material_req、prod_serial、prod_station_flow、prod_station_record、prod_quality_disposition、prod_workorder_route_snapshot/route_step/bom_snapshot |
| `inv_` | 库存 | inv_inbound(_item)、inv_outbound(_item)、inv_balance、inv_transaction(_log)、inv_warehouse/area/location、inv_arrival_notice(_item)、inv_batch、inv_trace、inv_stock_balance、inv_receipt_action、inv_receipt_posting、inv_line_warehouse |
| `qm_` | 质量 | qm_incoming_inspection(_item)、qm_process_inspection、qm_outgoing_inspection、qm_inspection_item/template、qm_defect_process、qm_first_inspect、qm_8d_report、qm_capa、qm_control_plan、qm_eco、qm_supplier_eval、qm_fmea |
| `eqp_` | 设备 | eqp_ledger、eqp_type、eqp_repair_order、eqp_maintenance_plan、eqp_check_item、eqp_check_project、eqp_check_workorder、eqp_mold、eqp_fixture |
| `sched_` | 排班 | sched_team、sched_plan、sched_holiday、sched_calendar |
| `tool_` | 工具 | tool_type、tool_ledger、tool_borrow |
| `scm_` | 供应链 | scm_purchase_order(_item)、scm_procurement_status_log |
| `iot_` | IoT/机台 | iot_machine_endpoint、iot_machine_session、iot_machine_request、iot_inspection_report(_value)、iot_device_event(_cursor/_sequence_gap/_conflict/_effect/_state/_alarm/_measurement)、iot_aim_event_outbox、iot_aim_device_sequence、iot_gateway_credential/nonce |
| `flow_` | 审批流 | flow_definition、flow_instance、flow_task |
| `hr_` | 人事 | hr_training(_record)、hr_skill_matrix |
| `svc_` | 售后 | svc_complaint、svc_return |
| `util_` | 能源环境 | util_energy、util_environment |
| 其它 | 单表 | spc_data、sys_barcode、sys_backup、sys_document、sys_announcement、prod_routing_card(_step)、prod_andon、prod_exception、prod_defect_receive、prod_box、prod_outsource、prod_labor_time、prod_packing、prod_rework、prod_cost |

### 6.2 核心表与其业务含义

| 表 | 业务含义 | 关键字段 |
|---|---|---|
| prod_sales_order / _item | 销售订单头/明细 | status、delivered_qty、total_amount |
| prod_plan / _item | 生产计划头/明细（关联销售订单） | sales_order_id、planned_qty、completed_qty、workshop_id |
| prod_batch | 生产批次（计划拆分） | plan_item_id、planned_qty、status |
| prod_workorder | 工单 | order_no、route_id、planned_qty、completed_qty、defect_qty、status、priority |
| prod_workorder_route_snapshot / route_step / bom_snapshot | 下达时冻结的路线/BOM 快照 | step_no、process_id、is_inspection_point、required_qty |
| prod_task | 工序任务（含返工任务） | route_step_id、task_type、source_task_id、quality_disposition_id、target_sn |
| prod_report | 报工（提交/审核/过账） | task_id、qualified_qty、defect_qty、approval_status、client_operation_id |
| prod_serial | SN 序列号与质量状态 | serial_no、workorder_id、quality_status |
| prod_station_flow / station_record | SN 过站流水与记录 | sn、action、result、route_step_id、machine_request_id、quality_disposition_id |
| prod_quality_disposition | SN 级质量处置单 | sn、action、status、cycle_no、rework_task_id |
| prod_material_req | 生产领料需求 | required_qty、requested_qty、issued_qty、received_qty、returned_qty、status |
| prod_transfer | 工序转移单 | from/to_route_step_id、quantity、status |
| inv_balance | 库存余额（按产品） | product_id(UNIQUE)、quantity、amount |
| inv_transaction / _log | 库存事务流水（余额变化） | trans_type、quantity、balance、ref_no |
| inv_inbound/outbound (+item) | 出入库单据 | status、total_amount、supplier/customer |
| inv_arrival_notice(+item) | 采购到货通知（写入口已停用） | purchase_order_id、arrived_qty、accepted_qty、inspection_mode |
| inv_stock_balance / inv_receipt_posting / inv_receipt_action | 三级库位批次库存与受控收料过账（表已建，服务未接） | product_id+warehouse+area+location+batch_no 唯一 |
| qm_incoming/process/outgoing_inspection | IQC/PQC/OQC 检验单 | inspect_no、result、status、template_id |
| iot_machine_endpoint | 机台通讯端点（绑定设备/工序/工站/穴位） | equipment_id、process_id、station_code、protocol_version、shared_secret |
| iot_machine_request | 机台准入请求判定记录 | sn、decision、reason_code、dedupe_key、report_status |
| iot_inspection_report / _value | AIM 检测报告与检验值 | sn、result、file_hash、import_status、prod_report_id |
| iot_device_event | 标准设备事件（中央幂等接收） | event_id(UNIQUE)、sequence、processing_status |
| scm_purchase_order(+item) | 采购订单 | status、arrived_qty、accepted_qty、posted_qty |
| sys_numbering | 单据号生成（原子自增） | prefix、current_no、digit_count |
| sys_business_status_log | 业务状态流转日志 | entity_type、entity_id、from/to_status、action |

---

## 7. 设备接入边界

### 7.1 三层接入架构

```
┌─ 现场机台层 ─────────────────────────────────────────────┐
│  1) 老 AIM 机台：TCP Socket 直连（V1，报文=SN）             │
│  2) 新 AIM 机台：TCP Socket（V2，REQ|2|设备|工站|穴位|请求号│
│     |时间戳|[nonce]|SN|HMAC签名）                          │
│  3) 海康读码器：machine_reader_client 作为 TCP 客户端连接   │
│  4) CSV 目录：机台输出检测 CSV，MachineCsvCollector 轮询采集 │
│  5) 边缘网关：edge_gateway_service.py（独立进程，HTTPS/MQTT）│
└──────────────┬────────────────────────────────────────────┘
               ▼
┌─ MES 主服务 ──────────────────────────────────────────────┐
│  machine_runtime.MachineCommunicationRuntime（伴随主进程）：│
│   - MachineGatewayManager：为每个启用的 endpoint 拉起/监管    │
│     machine_socket_server 子进程（按 endpoint 独立监听）      │
│   - MachineCsvCollector：轮询 CSV 目录导入检测报告            │
│   - 常驻事件派发线程：AIM 事件箱 → 标准事件                   │
│  evaluate_access / import_inspection_report（services）     │
│  /api/device-platform/* 接收边缘网关事件                     │
│  MqttEventConsumer（可选独立进程）接收 MQTT QoS1 事件         │
└────────────────────────────────────────────────────────────┘
```

### 7.2 职责边界

| 组件 | 职责 | 不负责 |
|---|---|---|
| `machine_socket_server.py` | 按 endpoint 独立监听 TCP；IP 白名单、连接数上限、心跳、协议解析、准入判定、会话记录 | 业务编排、质检模板维护 |
| `machine_reader_client.py` | 主动连接读码器，按空闲帧切帧，复用 evaluate_access 判定并回送 `<L1>/<L3>` | 不直连主业务库（通过 DB_PATH） |
| `machine_csv_collector.py` | 轮询 CSV 输入目录，稳定后导入检测报告，失败文件隔离到 `_failed` | 不做准入判定 |
| `services/machine_access.py` | **准入判定与检测报告导入的核心业务**：evaluate_access、import_inspection_report、NG 处置联动 | 不监听端口 |
| `services/machine_protocol.py` | V1/V2 报文编解码、HMAC 校验、响应格式化 | 业务规则 |
| `services/aim_event_bridge.py` | 将旧 AIM 检测报告映射为标准事件，写入事件箱并派发 | 事件接收 |
| `edge_gateway/` | 独立边缘进程：本地 SQLite 事件箱（edge_event_outbox）、租约投递（DeliveryPump）、HTTPS HMAC 或 MQTT QoS1/mTLS 传输、死信与重放 | 不持有 MES 业务库 |
| `services/device_event_ingest.py` | 中央幂等接收标准事件：序列号校验、断点续传、冲突隔离 | 业务效果应用 |
| `services/device_event_processor.py` | 应用事件业务效果（quality.completed 等），维护幂等 effect 表 | 事件接收 |
| `services/mqtt_event_consumer.py` | 订阅 `mes/v1/+/+/+/events/+`，解析后交给 ingest，回 ACK 到 `.../acks/` | 业务规则 |
| `services/device_commands.py` | MES→边缘的命令下发队列（production.authorize、recipe.apply 等） | 设备驱动 |

### 7.3 与主业务流程的关系

- 机台准入是**工单/任务/SN 执行链路的"闸门"**：SN 必须挂在有效工单、处于正确冻结工序、任务处于运行中、质量状态允许，才返回 L1。
- 检测报告导入是**报工与质量处置的自动化来源**：OK 生成待审核报工+PASS 过站；NG 生成待审核报工 + 质量处置单 + SN 冻结。
- 边缘网关与 MQTT 面向**跨厂区/私有化部署**，与主业务（生产/质量/库存）解耦：事件只做幂等落库与效果应用，不参与实时准入。

---

## 8. 核心发现与疑点

1. **状态机数量**：核心业务状态机约 10 套（工单/任务/报工/销售/计划/批次/出入库/采购/质量处置/机台请求报告），核心流转定义集中在 `production_flow._TRANSITIONS` 与 `procurement_flow.PURCHASE` 常量。
2. **采购到货-收料链路未闭环**：`procurement_flow.py` 只实现了采购订单状态流转，到货通知写入口已在 `warehouse.py` 停用（410），`receiving_service` 不存在，`inv_receipt_posting/inv_stock_balance/inv_receipt_action` 表已建但无服务接入（仅测试用例覆盖）。IQC 检验单表虽有 `arrival_item_id/conclusion` 等扩展字段，但蓝图层仍走通用 CRUD，未与到货-入库联动。
3. **ERP/AI 为占位**：`erp.py`/`erp_deep.py` 的同步接口多数返回 501/未实现；`ai.py` 的 AI 质检返回 503。
4. **权限双轨并存**：动作权限目录（ACTION_PERMISSION_CATALOG）与菜单级 perms（`xx:yy:list`）并存；`permission_required` 内置遗留别名映射以兼容旧菜单权限，新老权限体系的统一值得后续关注。
5. **通用 CRUD 与受控服务的边界**：多数域仍使用 `crud_*` 通用模式（不校验业务状态），而核心生产/库存/质量链已迁移到领域服务（显式状态校验）。`prod_ext.py` 已对领料等受控表关闭通用写入口（410），建议逐步推广。
6. **质量处置与报工数量闭环**：返工任务通过 `task_type/source_task_id/quality_disposition_id/target_sn` 与原始任务联动；OK 补数、NG 进入下一轮循环，逻辑完整且幂等约束严格。
7. **事务一致性设计**：services 层普遍使用 `SAVEPOINT` 嵌套事务 + 条件 UPDATE（`WHERE status=...`）防并发覆盖，SQLite 下用 `BEGIN IMMEDIATE` 避免写锁升级死锁，值得在后续开发中保持该模式。

---

## 附：相关文件索引

- 入口：`backend/app.py`
- 业务服务：`backend/services/production_flow.py`、`quality_disposition.py`、`procurement_flow.py`、`machine_access.py`
- 设备接入：`backend/machine_socket_server.py`、`machine_runtime.py`、`machine_gateway_manager.py`、`machine_csv_collector.py`、`machine_reader_client.py`
- 边缘网关：`backend/edge_gateway/*`、根目录 `edge_gateway_service.py`、`mqtt_event_consumer_service.py`
- 基础设施：`backend/utils/database.py`、`helpers.py`、`db_errors.py`、`table_order.py`
- 协议契约：`backend/device_platform/contracts.py`
