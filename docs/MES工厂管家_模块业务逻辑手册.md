# MES工厂管家 模块业务逻辑手册

> 适用对象：车间班组长、计划员、质检员、仓管员、采购员、设备管理员、系统管理员等业务人员
> 编制依据：`docs/MES工厂管家_业务逻辑梳理.md`（代码级梳理）与 `backend/` 现行实现
> 版本：2026-08-25
> 说明：本手册按业务域分模块讲解"业务目标 → 数据 → 流转 → 接口 → 操作步骤"，帮助员工理解系统怎么用、为什么这么设计。所有状态流转均有系统强校验，人工无法越级操作。

---

## 0. 系统总体认识

MES 工厂管家是一个 **订单驱动、批次追溯、质量闭环** 的制造执行系统，后端为 Flask + SQLite，分为 8 大业务域：

```
①生产管理 ──▶ ②质量管理 ──▶ ③库存管理
     │              │              │
     └──▶ ④设备与工具管理 ◀── ⑤基础数据
                                  │
⑥系统管理 ◀── ⑦采购与供应链 ◀───┘
     │
     └──▶ ⑧设备接入与边缘网关（机台/读码器/CSV/网关）
```

常用概念速记：

| 概念 | 含义 |
|---|---|
| 单据状态 | 大多数单据是"草稿 → 确认/过账"两段式，草稿可改可删，过账后锁定 |
| 数量约束 | 从销售订单到工单，每一层数量都不能超过上一层的剩余量，系统自动校验 |
| 报工三态 | 报工需"提交 → 审核 → 过账"三步，只有过账才真正计入产量 |
| 批次追溯 | 关键物料/成品按批次管理，可查"哪个订单、哪个工序、哪个操作员、哪台机" |
| 权限 | 登录后才能操作；写操作需对应权限 key；管理员拥有全部权限 |

---

## 1. 生产管理域

### 1.1 业务目标
把"客户要什么"一步步拆成"车间做什么、谁来做、做了多少"，实现销售订单 → 生产计划 → 生产批次 → 工单 → 工序任务 → 报工的全链路数字化，每一层数量受控、可追溯。

### 1.2 核心数据表

| 表 | 作用 | 关键字段 |
|---|---|---|
| prod_sales_order(_item) | 销售订单头/明细 | status、delivered_qty、total_amount |
| prod_plan(_item) | 生产计划头/明细 | sales_order_id、planned_qty、completed_qty、workshop_id |
| prod_batch | 生产批次（计划拆分） | plan_item_id、planned_qty、status |
| prod_workorder | 工单 | order_no、route_id、planned_qty、completed_qty、defect_qty、status、priority |
| prod_workorder_route_snapshot / route_step / bom_snapshot | 工单下达时冻结的工艺路线/BOM 快照 | step_no、process_id、is_inspection_point、required_qty |
| prod_task | 工序任务（含返工任务） | route_step_id、task_type、source_task_id、quality_disposition_id、target_sn |
| prod_report | 报工单 | task_id、qualified_qty、defect_qty、approval_status、client_operation_id |
| prod_transfer | 工序转移单 | from/to_route_step_id、quantity、status |
| prod_material_req | 生产领料需求 | required_qty、requested_qty、issued_qty、received_qty、returned_qty、status |
| prod_serial | SN 序列号与质量状态 | serial_no、workorder_id、quality_status |

### 1.3 数据流

```
销售订单(SO) → 生产计划(PL) → 生产批次(PB) → 工单(WO) → 工单下达(冻结路线+BOM)
    → 生成工序任务(每工序一条) + 领料需求(每BOM行一条)
    → 领料：申请 → 发料(扣库存) → 收料 → 退料(回补库存)
    → 报工：提交 → 审核 → 过账(累加工单/任务完成数)
    → 工序转移(相邻工序，量不超上工序合格-已转移)
```

### 1.4 状态流转

- 销售订单/计划/批次：`0草稿 → 1已确认/已发布/已排产 → 2生产中 → 3已完成`，`4已取消`。
- 工单：`0草稿 → 1已下达 → 2生产中 → 3已完工`；`4已暂停`（可回生产）、`5已关闭`（从完工关闭）、`6已取消`（草稿/已下达/生产中可取消）。
- 任务：`0待执行 → 1运行中 → 2已暂停 → 3已完成`；普通任务按"合格数 ≥ 计划数"判定完成。
- 报工：`0已提交 → 1已审核 → 2已过账`，`3已驳回`；**只有已过账报工才影响任务/工单数量**。

### 1.5 关键接口

| 接口 | 说明 |
|---|---|
| `/api/prod/sales/save`、`/api/prod/plan/save`、`/api/prod/batch/save` | 销售/计划/批次保存（草稿） |
| `/api/prod/workorder/save` | 工单保存（草稿） |
| `/api/prod/workorder/<id>/release` | 工单下达（冻结路线/BOM 快照） |
| `/api/prod/workorder/<id>/generate-tasks` | 生成工序任务与领料需求 |
| `/api/prod/material/<id>/request\|issue\|receive\|return` | 领料申请/发料/收料/退料 |
| `/api/prod/report/*/approve\|post\|reject` | 报工审核/过账/驳回 |
| `/api/prod/transfer/add` | 工序转移 |

### 1.6 典型操作步骤（面向业务人员）

1. 计划员录入**销售订单**（选客户、填产品、数量、单价）并保存为草稿 → 确认订单。
2. 计划员创建**生产计划**，选择"已确认"销售订单，明细自动带出产品与剩余数量，保存并发布。
3. 计划员把计划拆成**生产批次**，批次数量不能超过计划剩余。
4. 计划员建**工单**（选产品/批次/工艺路线/数量），数量不能超过批次剩余。
5. 下达工单：系统自动冻结工艺路线和 BOM 快照，校验每个工序已分配车间。
6. 点击"生成任务"，每个冻结工序生成一条工序任务，同时生成领料需求。
7. 仓库按领料申请发料（扣减库存）、车间收料；多余退料回补库存。
8. 车间完成每道工序后**报工**：填写合格数/不良数 → 提交 → 班组长审核 → 过账。
9. 上工序合格产出可**转移**到下工序（只允许相邻工序、量不超剩余）。
10. 所有工序合格数达到计划数后工单自动"已完工"，可关闭。

---

## 2. 质量管理域

### 2.1 业务目标
在来料、过程、出货三个关口把住质量，配合 SPC 统计、不良品处置（返工/报废/让步）形成闭环，让"检验 → 判定 → 处置"全程留痕、责任到人。

### 2.2 核心数据表

| 表 | 作用 |
|---|---|
| qm_incoming_inspection(_item) | IQC 来料检验单（支持 arrival_item_id 与到货收料联动） |
| qm_process_inspection | PQC 过程检验单 |
| qm_outgoing_inspection | OQC 出货检验单 |
| qm_inspect_template | 检验模板（按检验类型配置检验项目） |
| qm_defect_process / qm_first_inspect / qm_8d_report | 不良品处理 / 首件检验 / 8D 报告 |
| qm_capa / qm_control_plan / qm_eco | 纠正预防 / 控制计划 / 工程变更 |
| qm_supplier_eval | 供应商评审 |
| spc_data | SPC 过程统计样本 |
| prod_quality_disposition | SN 级质量处置单（返工/报废/让步） |

### 2.3 数据流

```
来料：到货 → IQC 检验(合格/让步/退货) → 合格品收料入库
过程：首件检验 → 巡检(PQC) → SPC 采集 → 异常触发处置
出货：成品 → OQC 检验 → 合格放行/不合格拦截
不良：机台NG/检验NG → 质量处置单(SN冻结) → 审批(返工/报废/让步)
      → 返工任务 → 返工报工 OK(SN恢复)/NG(进入下一轮处置)
```

### 2.4 状态流转

- 检验单：`0 待检 → 1 合格/不合格/让步接收`（由检验结论决定）。
- 质量处置单：`pending_review 待审核 → approved 已批准返工 → task_started 返工任务已启动 → completed 已闭环`；`rejected 已驳回`。
- SN 质量状态：`normal 正常 / quality_hold 待处理 / rework 返工中 / scrapped 已报废 / concession 让步接收`。
- **SN 一旦 NG 立即冻结（quality_hold）**，在审批完成前机台不允许再次准入。

### 2.5 关键接口

| 接口 | 说明 |
|---|---|
| `/api/qm/incoming/*`、`/api/qm/process/*`、`/api/qm/outgoing/*` | 三类检验单 CRUD |
| `/api/qm/defect/*`、`/api/qm/first/*`、`/api/qm/8d/*` | 不良品/首件/8D |
| `/api/qm/capa/*`、`/api/qm/control-plan/*`、`/api/qm/eco/*` | CAPA/控制计划/ECO |
| `/api/qm/supplier-eval/*` | 供应商评审 |
| `/api/spc/*` | SPC 数据/图/CPK |
| `/api/site/rework/<id>/approve\|reject\|start-task` | 返工处置审批与启动 |

### 2.6 典型操作步骤

1. IQC：供应商到货 → 检验员按模板逐项检验 → 录入实测值 → 判定合格/不合格/让步 → 合格才允许收料。
2. PQC：首件检验确认后批量生产 → 按频次巡检并记录 → 超出控制限触发异常。
3. OQC：成品出货前按抽样方案检验 → 合格放行、不合格拦截。
4. 不良处置：发现不良 → 系统创建处置单并冻结 SN → 质量负责人审批（返工/报废/让步）→ 返工任务执行 → 返工报工过账后 SN 恢复正常或进入下一轮。

---

## 3. 库存管理域

### 3.1 业务目标
管好"仓库-库区-库位"三级货位、按批次管理库存，出入库单据从草稿到过账全流程受控，任何库存变动都有流水可查。

### 3.2 核心数据表

| 表 | 作用 |
|---|---|
| inv_warehouse / inv_area / inv_location | 三级库位（仓库/库区/库位） |
| inv_inbound(_item) / inv_outbound(_item) | 入库/出库单据（草稿→过账） |
| inv_balance | 库存余额（按产品汇总） |
| inv_stock_balance | 批次库存余额（产品+仓库+库区+库位+批次 唯一，累加） |
| inv_transaction / inv_transaction_log | 库存事务流水与日志 |
| inv_batch / inv_trace | 批次档案与追溯记录 |
| inv_receipt_posting | 收料过账记录（采购收料闭环专用） |
| inv_arrival_notice(_item) | 到货通知单与明细 |

### 3.3 数据流

```
入库/出库：
  新增(草稿) → 修改(仅草稿) → 删除(仅草稿) → 过账
  过账：入库 库存+=数量/金额；出库 预检库存(缺料整单回滚) → 库存-=数量，按移动平均扣金额
        → 写 inv_transaction 流水 → 单据 status 0→1（锁定）
批次库存：
  采购收料 → inv_receipt_posting → inv_stock_balance 同库位批次累加
生产领料：
  领料申请 → 发料(扣 inv_balance) → 退料(回补)
```

### 3.4 状态流转

- 出入库单据：`0 草稿（可改可删）→ 1 已过账（锁定，不可改/删/重复过账）`。
- 库存流水只能由入库、出库、领料、退料、收料过账自动生成，**不允许手工新增**（接口返回 409）。

### 3.5 关键接口

| 接口 | 说明 |
|---|---|
| `/api/inv/inbound/add\|update\|delete`、`/api/inv/inbound/<id>/post` | 入库单增删改 + 过账 |
| `/api/inv/outbound/*`、`/api/inv/outbound/<id>/post` | 出库单增删改 + 过账 |
| `/api/inv/balance/list` | 库存余额列表 |
| `/api/warehouse/*`、`/api/area/*`、`/api/location/*` | 三级库位维护 |
| `/api/transaction/list` | 库存事务日志 |
| `/api/trace/batch/*`、`/api/trace/query` | 批次与追溯 |
| `/api/scm/receiving/*` | 采购到货/收料（见第 7 章） |

### 3.6 典型操作步骤

1. 库管员先维护**仓库 → 库区 → 库位**三级结构。
2. 收料/采购到货后按第 7 章流程做**到货登记与收料过账**，自动累计批次库存。
3. 其它入库（退货、调拨等）：新建入库单（选类型/供应商/明细）→ 保存草稿 → 过账。
4. 出库：新建出库单 → 过账时系统自动预检库存，缺料会整单拒绝并提示缺料清单。
5. 任何库存疑问，查**库存事务日志**即可定位是哪张单据、谁在什么时间改动了库存。

---

## 4. 设备与工具管理域

### 4.1 业务目标
管好设备台账、点检保养、维修、模具治具与工具的领用归还，保证设备状态受控、工装可追溯。

### 4.2 核心数据表

| 表 | 作用 |
|---|---|
| eqp_type / eqp_ledger | 设备类型 / 设备台账 |
| eqp_repair_order | 维修单 |
| eqp_maintenance_plan / eqp_check_workorder | 保养计划 / 点检工单 |
| eqp_check_item / eqp_check_project | 点检项目 |
| eqp_mold / eqp_fixture | 模具 / 治具 |
| tool_type / tool_ledger / tool_borrow | 工具类型 / 台账 / 领用归还 |

### 4.3 状态流转

- 设备台账：`0 停用 / 1 运行 / 2 维修`。
- 维修单：`0 待维修 → 1 维修中 → 2 已完成`，维修中会联动设备状态为"维修"。
- 工具领用：`borrow_qty`（领用数）与 `return_qty`（归还数），归还后可再次领用。

### 4.4 关键接口

| 接口 | 说明 |
|---|---|
| `/api/eqp/type/*`、`/api/eqp/ledger/*` | 设备类型/台账 |
| `/api/eqp/repair/*`、`/api/eqp/maintenance/*`、`/api/eqp/check/*` | 维修/保养/点检 |
| `/api/eqp/mold/*`、`/api/eqp/fixture/*` | 模具/治具 |
| `/api/tool/type/*`、`/api/tool/ledger/*`、`/api/tool/borrow/*` | 工具管理 |

### 4.5 典型操作步骤

1. 设备管理员建立设备台账（选类型/车间/位置）。
2. 按保养计划定期生成点检工单并执行点检。
3. 设备故障 → 开维修单 → 维修 → 完工 → 设备状态自动恢复。
4. 员工领用工具 → 登记领用 → 归还时登记归还数量。

---

## 5. 基础数据域

### 5.1 业务目标
统一维护车间、工序、产品、BOM、工艺路线、供应商、客户、单位、不良项等基础主数据，是其它所有业务模块的"字典"，数据必须规范、唯一、可启用/停用。

### 5.2 核心数据表

| 表 | 作用 |
|---|---|
| base_workshop | 车间 |
| base_process | 工序（可关联车间/标准工时） |
| base_product | 产品（编码唯一、含单位/规格/类型） |
| base_bom | 物料清单（产品 → 子件用量） |
| base_process_route(_detail) | 工艺路线（产品 → 工序顺序） |
| base_supplier / base_customer | 供应商 / 客户 |
| base_defect / base_unit | 不良项 / 计量单位 |

### 5.3 数据流

```
产品/工艺/BOM 是源头：
  产品 → 工艺路线(顺序工序) → BOM(子件清单)
  工单下达时把"工艺路线 + BOM"冻结成快照，后续生产按快照执行，
  主数据后续修改不影响已下达工单。
```

### 5.4 关键接口

| 接口 | 说明 |
|---|---|
| `/api/base/workshop/*`、`/api/base/process/*` | 车间/工序 |
| `/api/base/product/*`、`/api/base/bom/*` | 产品/BOM |
| `/api/base/route/save` | 工艺路线保存 |
| `/api/base/supplier/*`、`/api/base/customer/*` | 供应商/客户 |
| `/api/base/defect/*`、`/api/base/unit/*` | 不良项/单位 |

### 5.5 典型操作步骤

1. 先建车间、工序，再建产品（编码全局唯一）。
2. 为产品配置 BOM（哪些子件、用量多少）。
3. 为产品配置工艺路线（按顺序添加工序）。
4. 维护供应商、客户主数据（采购/销售单据都会引用）。
5. 主数据启用后才可在业务单据中选择；停用的主数据不可再被新单据引用。

---

## 6. 系统管理域

### 6.1 业务目标
管好用户、角色、权限、部门、数据字典、审批流、操作审计与系统监控，保证"谁能干什么"清晰受控、操作留痕、系统可运维。

### 6.2 核心数据表

| 表 | 作用 |
|---|---|
| sys_user / sys_role / sys_dept / sys_menu | 用户/角色/部门/菜单 |
| sys_dict | 数据字典 |
| sys_log / sys_login_log | 操作审计 / 登录日志 |
| sys_config | 系统配置 |
| sys_announcement | 系统公告 |
| flow_definition / flow_instance / flow_task | 通用审批流（定义/实例/任务） |
| sys_ip_whitelist / sys_print_template / sys_notify_channel | 安全与工具配置 |
| sys_numbering | 单据号生成（原子自增） |

### 6.3 权限模型

- 三种访问控制：`login_required`（登录即可）、`admin_required`（仅管理员）、`permission_required('域:资源:动作')`（需指定权限 key）。
- 权限 key 目录维护在系统管理"权限目录"中，角色设置权限时只能从目录选择。
- **管理员（role_key=admin）默认拥有全部权限**；普通用户按角色 menu_ids 判定。
- 权限命名规律：`<域>:<资源>:<动作>`，如 `inv:write`（库存维护）、`scm:receipt`（采购收料过账）、`prod:report:post`（报工过账）。

### 6.4 状态流转

- 审批流：实例 `0 审批中 → 1 通过 → 2 驳回`；任务 `0 待办 → 1 通过 → 2 驳回`。
- 登录日志记录登录时间、IP、成功/失败；操作审计记录每次关键操作。
- 在线用户列表超过 30 分钟未活动自动清理；管理员可强制下线。

### 6.5 关键接口

| 接口 | 说明 |
|---|---|
| `/api/login`、`/api/captcha`、`/api/user/info` | 登录/验证码/用户信息 |
| `/api/sys/user/*`、`/api/sys/role/*`、`/api/sys/menu/*` | 用户/角色/菜单 |
| `/api/sys/permissions/catalog`、`/api/sys/role/permissions` | 权限目录与角色授权 |
| `/api/sys/online/*`、`/api/sys/login-log/*`、`/api/sys/audit/*` | 在线/登录日志/审计 |
| `/api/flow/definition/*`、`/api/flow/instance/submit`、`/api/flow/task/approve` | 审批流 |
| `/api/sys/monitor`、`/api/backup/*` | 系统监控/备份恢复 |
| `/api/sys/change-password`、`/api/sys/reset-password` | 修改/重置密码 |

### 6.6 典型操作步骤

1. 管理员创建部门 → 创建角色（如"仓库员""质检员"）→ 给角色勾选权限 → 创建用户并分配角色。
2. 业务人员登录后按角色权限操作系统；忘记密码由管理员重置。
3. 需要多人审批的业务（如工单下达）可配置审批流定义，提交实例后按任务逐级审批。
4. 日常运维查看登录日志、操作审计；定期备份数据库；清理过期日志。

---

## 7. 采购与供应链域（含收料闭环）

### 7.1 业务目标
把"采购下单 → 供应商到货 → 收料过账 → 库存累计 → 采购单状态联动"串成完整闭环，杜绝"采购单下了但到货/收料没有记录"的断链问题，同时支持供应商评估。

### 7.2 核心数据表

| 表 | 作用 |
|---|---|
| scm_purchase_order(_item) | 采购订单头/明细（状态机 0-7） |
| scm_procurement_status_log | 采购状态流转日志 |
| inv_arrival_notice(_item) | 到货通知单与明细 |
| inv_receipt_posting | 收料过账记录（posting_no 唯一） |
| inv_stock_balance | 批次库存余额（同库位批次累加） |
| qm_supplier_eval | 供应商评审 |
| base_supplier | 供应商主数据 |

### 7.3 数据流（收料闭环）

```
采购订单(草稿) → 提交 → 审核 → 到货登记(生成 inv_arrival_notice)
    → 收料过账(写 inv_receipt_posting，指定仓库/库区/库位/批次)
    → 库存累计(inv_stock_balance 同库位批次 upsert 累加)
    → 采购明细 posted_qty 累加 → 采购单状态推进(部分到货/全部到货)
    → 全部过账完成可关闭
```

### 7.4 状态流转

- 采购订单：`0草稿 → 1已提交 → 2已审核 → 3部分到货/4全部到货 → 5已关闭`；`6已驳回`（可改后重新提交）、`7已取消`。
- 规则：
  - 只有草稿/驳回可编辑、提交；只有已提交可审核；驳回必须填原因。
  - **已发生到货的采购单不能取消，只能关闭**（防止到货数据悬空）。
  - 收料过账只允许在"已审核/部分到货/全部到货"状态进行；全部明细过账完成 → 全部到货，否则 → 部分到货。
  - 收料数量不能超过到货明细的"待收数量"；超过采购数量的到货记入超额（excess_qty），但只按正常数量待收。

### 7.5 关键接口

| 接口 | 说明 |
|---|---|
| `/api/scm/purchase/list` | 采购/入库列表 |
| `/api/scm/receiving/arrival/add` | **到货登记**（生成到货通知，权限 scm:write） |
| `/api/scm/receiving/arrival/list`、`/api/scm/receiving/arrival/<id>` | 到货通知列表/详情 |
| `/api/scm/receiving/post` | **收料过账**（写收料记录+库存累计+状态联动，权限 scm:receipt） |
| `/api/scm/receiving/list` | 收料过账列表 |
| `/api/scm/receiving/order/<id>/summary` | 采购单收料进度汇总 |
| `/api/scm/supplier/eval/*`、`/api/scm/supplier/ranking` | 供应商评估与排名 |

> 说明：`procurement_flow.py` 提供采购单事务化编排（保存/提交/审核/取消/关闭）；`receiving_service.py` 提供收料闭环服务；`warehouse.py` 的旧到货通知写入口已停用（返回 410），请统一使用上面的受控接口。

### 7.6 典型操作步骤

1. 采购员**创建采购订单**：选启用状态的供应商，录入物料明细（数量必须大于 0），保存草稿。
2. 提交审核 → 采购主管审核通过（或驳回并填写原因，驳回后可修改重新提交）。
3. 供应商到货时，仓管员在"到货登记"中选择采购单，按采购明细逐行填写**到货数量**（可含送货单号），生成到货通知。
4. 仓管员做**收料过账**：选择到货明细、指定仓库/库区/库位/批次、填写实收数量，系统一次性完成：写收料记录 → 累计批次库存 → 推进采购单状态（部分到货/全部到货）。
5. 重复提交同一收料操作（客户端操作 ID 相同）不会重复入账，系统幂等保护。
6. 全部收料完成后采购单自动变为"全部到货"，可填写原因关闭。
7. 定期查看供应商评估/排名，用于后续采购决策。

---

## 8. 设备接入与边缘网关域

### 8.1 业务目标
把老 AIM 机台、新 AIM 机台、海康读码器、CSV 检测结果、边缘网关/MQTT 统一接入 MES，实现"机台准入闸门 + 检测报告自动回传 + 事件幂等落库"，减少人工录入、保证数据实时准确。

### 8.2 组件与数据表

| 组件/表 | 作用 |
|---|---|
| machine_socket_server.py | 按 endpoint 独立监听 TCP，协议解析、准入判定 |
| machine_reader_client.py | 主动连接读码器，复用准入判定并回送 L1/L3 |
| machine_csv_collector.py | 轮询 CSV 目录导入检测报告，失败隔离到 `_failed` |
| services/machine_access.py | **准入判定与检测报告导入核心** |
| services/aim_event_bridge.py | 旧 AIM 检测报告 → 标准事件 |
| edge_gateway/ | 独立边缘进程：本地事件箱、租约投递、HTTPS/MQTT 传输 |
| services/device_event_ingest.py | 中央幂等接收标准事件（序列号校验、断点续传） |
| services/device_event_processor.py | 应用事件业务效果（quality.completed 等） |
| iot_machine_endpoint / iot_machine_request / iot_inspection_report(_value) | 机台端点/准入请求/检测报告 |
| iot_device_event / iot_aim_event_outbox | 标准事件与 AIM 事件箱 |

### 8.3 数据流

```
机台请求 → evaluate_access 逐级校验(端点/设备/SN/工单/路线/工序/质量/任务)
    → 返回 L1(允许+模板) 或 L3(拒绝+原因码)
检测报告(CSV/读码器) → import_inspection_report
    → 归档+哈希防重 → 写检测报告 → 生成草稿报工 → 写过站记录
    → NG 时创建质量处置单并冻结 SN → 入 AIM 事件箱 → 派发标准事件
边缘/MQTT：设备事件 → 事件箱 → 中央幂等接收 → 业务效果应用
```

### 8.4 关键规则

- 准入是执行链路的"闸门"：SN 必须挂在有效工单、处于正确冻结工序、任务运行中、质量状态允许，才返回 L1。
- 检测报告导入自动生成报工与过站记录；NG 立即冻结 SN，阻断不良流转。
- 标准事件按 event_id 幂等接收，失败可重试；断点续传防漏。
- V2 机台报文带 HMAC 签名与 nonce 防重放。

### 8.5 关键接口

| 接口 | 说明 |
|---|---|
| `/api/iot/machine/endpoints/*`、`/api/iot/machine/reports/upload` | 机台端点配置 / 检测报告上传 |
| `/api/iot/machine/reports/<id>/retry`、`/api/iot/machine/health` | 报告重试 / 健康检查 |
| `/api/iot/data/push`、`/api/iot/webhook` | IoT 数据推送/Webhook |
| `/api/device-platform/events`、`/api/device-platform/gateway-events` | 标准设备事件接收 |
| `/api/device-platform/commands/*` | 命令下发 |

### 8.6 典型操作步骤

1. 设备管理员在"机台通讯端点"配置每个机台（绑定设备/工序/工站/穴位/协议版本）。
2. 机台连接后系统拉起独立监听服务；机台请求经准入判定回送 L1/L3。
3. 检测结果通过 CSV 目录或读码器自动回传，系统自动生成报工与过站记录。
4. 质检员在系统查看检测报告；NG 品自动进入质量处置流程（见第 2 章）。
5. 运维查看端点健康、报告导入状态；失败报告可手动重试。

---

## 9. 附录：权限 key 参考（新增 scm 权限）

系统管理"权限目录"现包含以下采购相关权限（新增于收料闭环）：

| 权限 key | 含义 | 用在哪里 |
|---|---|---|
| scm:read | 采购供应链-查看 | 预留只读接口 |
| scm:write | 采购供应链-维护 | 到货登记等写操作 |
| scm:receipt | 采购收料-过账 | 收料过账（库存+状态联动） |

> 给角色授权时，可在系统管理 → 角色权限中勾选以上 key；收料过账与到货登记建议分别授权给仓管/采购人员。

---

## 10. 常见问题速查

| 现象 | 原因与处理 |
|---|---|
| 报工不能过账 | 报工必须先"审核"，只有已审核报工可过账 |
| 出库单过账提示缺料 | 库存不足，系统整单拒绝；先补库存或分批出库 |
| 采购单不能取消 | 已发生到货，只能"关闭"（填写关闭原因） |
| 收料过账提示超待收数量 | 到货明细待收量不足；重新登记到货或核对数量 |
| 重复点了收料 | 系统幂等保护，同一操作不会重复入账 |
| 到货通知写不进去 | 旧写入口已停用（410），请使用受控收料接口 `/api/scm/receiving/*` |
| 机台返回 L3 | 查看原因码：端点/设备/SN/工单/工序/质量/任务任一不满足 |

---

*（手册完。如与系统实际行为不一致，以 `backend/` 代码与交付报告为准。）*

---

## 十、计划控制模块（新增）

> 需求来源：客户 OPPO Trace 配置端「计划控制」（背景：镭雕工站余量多版本共用导致多做返工）。映射到 MES 后按"产品 × 阶段码"维度控制计划数量。

### 业务目标
由计划员按产品（客户品名/料号）+ 阶段码（DVT/PVT/MP）下达/调整"计划镭雕数量"，限制生产上限，减少多做返工。

### 核心数据表
| 表 | 说明 |
|----|------|
| prod_plan_control | 计划控制行：product_id + stage_code 唯一；plan_qty 计划数量 / ok_qty 已完成 / adjust_qty 最近一次增减；余量=plan_qty-ok_qty 为计算值 |

### 业务规则
| ID | 规则 |
|----|------|
| PC-01 | 计划镭雕数量 = 原值 + 增减计划数量（正加负减） |
| PC-02 | 余量 = 计划镭雕数量 − 镭雕OK数量 |
| PC-03 | R1 增加后计划数量 ≤ 9 位数，否则拒绝："增加数量最大不可使计划镭雕数量超过9位数" |
| PC-04 | R2 减少量 ≤ 余量，否则拒绝："减少数量最小不可小于对应栏位的余量" |
| PC-05 | 增减数量为 0 拒绝；产品不存在拒绝；非整数拒绝 |

### 关键接口
| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /api/prod/plan-control/list | plan:control:read | 列表 + TOTAL 合计，支持 product_id/stage_code/keyword 筛选 |
| POST | /api/prod/plan-control/adjust | plan:control:write | 增减计划数量（单事务，校验 R1/R2） |
| POST | /api/prod/plan-control/init | plan:control:write | 从产品档案批量初始化计划行（幂等） |

### 界面（admin 生产管理 → 计划控制）
9 列表格（序号/项目号/客户品名/客户料号/阶段码/计划镭雕数量/镭雕OK数量/余量/增减计划数量）；只读列灰色；仅"增减计划数量"可录入（支持负数）；提交逐行校验，失败行红字标注 + 弹框提示；底部 TOTAL 合计。
