# 通用设备接入平台底座操作说明

## 当前交付范围

当前版本已提供第一期的可运行数据底座：

- 版本化的标准设备事件和设备命令契约。
- 边缘网关 SQLite 持久事件队列。
- 中央 MES 幂等事件接收、设备序号游标和缺号记录。
- 需要登录的事件写入、查询和健康 API。
- AIM 检测报告到标准质量事件的兼容桥。

当前 HTTP 接口用于本机开发和业务验证。正式网关跨网络接入所需的 MQTT、双向 TLS、PostgreSQL 和网关证书鉴权属于下一实施计划，不能把当前登录会话接口直接暴露到设备网络或公网。

## 标准事件

事件模型位于 `backend/device_platform/contracts.py`。所有适配器必须先构造并验证 `DeviceEvent`，再写入边缘持久队列。

```python
from device_platform.contracts import DeviceEvent

event = DeviceEvent.from_dict({
    'schema_version': '1.0',
    'event_id': 'F01-D01-000001',
    'customer_code': 'CUSTOMER-A',
    'factory_code': 'F01',
    'gateway_code': 'GW-F01-A',
    'device_code': 'D01',
    'event_type': 'quality.completed',
    'occurred_at': '2026-08-13T10:30:18+08:00',
    'received_at': None,
    'sequence': 1,
    'correlation_id': 'REQ-001',
    'payload': {'sn': 'SN001', 'result': 'OK'},
    'raw_reference': None,
})
```

事件时间必须带时区；序号必须是正整数；`payload` 必须是 JSON 对象。未知事件类型和未知顶层字段会被拒绝。

## 边缘持久队列

边缘网关使用独立数据库，不能指向中央 MES 的 `database/mes.db`：

```python
from edge_gateway.event_store import EdgeEventStore

store = EdgeEventStore(r'D:\MES-Edge\data\edge-events.db')
created = store.append(event)
print(created, store.stats())
```

正常发送顺序：

1. 设备插件构造标准事件。
2. `store.append(event)` 成功提交后才允许向设备确认已接收。
3. 发送程序读取 `store.pending(limit=100)`。
4. 中央平台明确返回接收成功或重复成功后调用 `store.ack(event.event_id)`。
5. 网络、超时或中央错误调用 `store.fail(event.event_id, error)`，事件继续保留等待重传。

不能在发送前调用 `ack`，也不能因为单次发送失败删除本地数据库。

## 中央接收 API

开发环境启动 MES 并登录后：

```text
POST /api/device-platform/events
Content-Type: application/json
```

新事件返回 HTTP `201`；相同 `event_id` 再次提交返回 HTTP `200` 且 `duplicate=true`。两种响应均表示边缘队列可以确认该事件。

查询接口：

```text
GET /api/device-platform/events?page=1&page_size=20
GET /api/device-platform/events?factory_code=F01&device_code=D01
GET /api/device-platform/events?event_type=quality.completed
```

健康接口：

```text
GET /api/device-platform/health
```

字段含义：

- `total_events`：中央已保存的标准事件数量。
- `pending_events`：尚未被 MES 业务处理器消费的事件数量。
- `open_sequence_gaps`：发现但尚未补齐的设备序号缺口。
- `devices_seen`：已经产生标准事件的工厂与设备身份数量。

## 序号与补传

中央平台按照 `(factory_code, device_code)` 分别维护游标。收到序号 `1` 后直接收到序号 `3` 时，会记录缺失序号 `2`；序号 `2` 后续补传成功后，单点缺口变为已解决。

重复的 `event_id` 不会生成第二条事件。同一设备相同序号但不同 `event_id` 会保留并标记序号冲突，方便排查设备重置计数器或错误生成事件的问题。

## AIM 兼容桥

现有 AIM CSV 流程继续正常运行。报告成功导入后会生成：

```text
event_type = quality.completed
event_id   = AIM:{endpoint_id}:REPORT:{report_id}
sequence   = report_id
```

事件写入失败不会撤销已经成功保存的 AIM 原始报告和生产记录，系统会记录错误供后续补偿。旧端点、请求、报告和页面均保留。

## 备份与恢复

当前需要分别备份：

- 中央数据库：`database/mes.db`
- 每台边缘网关的 `edge-events.db` 及其 `-wal`、`-shm` 文件
- AIM 和其他协议的原始文件归档

SQLite 在线备份必须使用 SQLite backup API 或先停止对应服务，不能在运行时只复制主 `.db` 文件而遗漏 WAL。

恢复前验证目标绝对路径，停止对应服务，将现有数据库移动到隔离目录，再恢复数据库和原始文件。恢复后先检查健康接口和边缘 `stats()`，确认积压数据后再恢复设备写入。

## 验证命令

```powershell
python -m pytest -q tests/test_device_platform_contracts.py
python -m pytest -q tests/test_edge_event_store.py
python -m pytest -q tests/test_device_event_ingest.py
python -m pytest -q tests/test_device_platform_api.py
python -m pytest -q tests/test_aim_event_bridge.py
python -m pytest -q
```

完整测试必须全部通过，才能进入 MQTT、双向 TLS、PostgreSQL 和真实设备插件实施。
