# MES工厂管家 API 文档

## 基础信息
- Base URL: `http://localhost:8080`
- 认证方式: Cookie Session（先调用 /api/login 获取）
- 响应格式: `{"code": 0, "data": {...}, "message": "success"}`

## 认证接口

### POST /api/login
登录获取 Session
```json
{"username": "admin", "password": "admin123"}
```

### POST /api/logout
退出登录

### GET /api/user/info
获取当前用户信息

## 基础数据

### GET /api/base/workshop/list
车间列表，支持 ?page=1&size=20&keyword=xxx

### POST /api/base/workshop/add
新增车间

### GET /api/base/process/list
工序列表（按排序号排列）

### POST /api/base/process/add
新增工序（自动分配排序号）

### POST /api/base/process/reorder
工序调序 `{"id": 1, "direction": "up"}`

### GET /api/base/product/all
产品下拉列表

### GET /api/base/supplier/all
供应商下拉列表

### GET /api/base/customer/all
客户下拉列表

## 生产管理

### GET /api/prod/workorder/list
工单列表

### POST /api/prod/workorder/add
新增工单（自动生成工单号）

### GET /api/prod/task/list
任务列表

### POST /api/prod/report/add
报工 `{"task_id": 1, "qualified_qty": 10, "defect_qty": 1}`

## 制程管控

### POST /api/process/pass-station
过站（含防呆校验）
```json
{"sn": "SN001", "station": "SMT01", "process_name": "贴片"}
```

### POST /api/process/skip-station
跳站 `{"sn": "SN001", "station": "SMT01", "reason": "..."}`

### POST /api/process/exit-station
出站

### POST /api/process/rework
重工 `{"sn": "SN001", "target_station": "SMT01"}`

### POST /api/process/close-box
关箱 `{"sn_list": ["SN001", "SN002"]}`

### POST /api/process/open-box
拆箱 `{"box_no": "BOX001"}`

### POST /api/process/lock-material
锁料 `{"material_id": 1, "reason": "..."}`

### POST /api/process/unlock-material
解料 `{"id": 1}`

### POST /api/process/return-to-line
返线 `{"sn": "SN001", "station": "SMT01"}`

### POST /api/process/defect-receive
不良品接收

### GET /api/process/record/sn/{sn}
按SN查询过站记录

### GET /api/process/statistics
制程统计

### GET /api/process/station-config/list
站点配置列表（防呆规则）

## 数据分析

### GET /api/analytics/yield
良率统计 `?days=30&process_id=1`

### GET /api/analytics/oee
OEE分析

### GET /api/analytics/data-dashboard
数据看板

### GET /api/analytics/delivery-alert
交期预警

### GET /api/analytics/inventory-turnover
库存周转率

### GET /api/search/global?q=xxx
全局搜索

### GET /api/query/production
生产查询（支持 start_date/end_date/status 等参数）

### GET /api/query/statistics
综合统计

## 系统管理

### GET /api/sys/monitor
系统监控（CPU/内存/磁盘）

### GET /api/sys/online/list
在线用户

### POST /api/sys/user/change-password
修改密码

### GET /api/notification/unread/count
未读通知数

### GET /api/backup/list
备份列表

### POST /api/backup/create
创建备份
