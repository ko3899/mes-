# 独立边缘网关运行说明

## 运行边界

边缘服务只负责从本地持久队列向中央平台可靠发送标准事件。设备协议驱动必须先将事件写入 `EdgeEventStore`，成功提交后才向设备确认。

HTTP模式用于内网试点和没有MQTT基础设施的客户；必须使用HTTPS。MQTT模式用于正式多工厂部署，固定使用QoS 1和双向TLS，并且必须运行中央消费者。

## HTTP模式配置

```powershell
$env:MES_EDGE_DB='D:\MES-Edge\data\events.edge.db'
$env:MES_EDGE_GATEWAY_ID='GW-F01-A'
$env:MES_EDGE_TRANSPORT='http'
$env:MES_EDGE_HTTP_URL='https://192.168.1.3'
$env:MES_EDGE_HTTP_SECRET='<独立网关密钥>'
$env:MES_EDGE_HTTP_TIMEOUT_SECONDS='5'
$env:MES_EDGE_POLL_SECONDS='2'
$env:MES_EDGE_LEASE_SECONDS='30'
$env:MES_EDGE_BATCH_SIZE='20'
python edge_gateway_service.py --show-config
python edge_gateway_service.py --once
python edge_gateway_service.py --replay-dead-letters
```

`--show-config`不会输出网关密钥。中央MES进程通过环境变量 `MES_GATEWAY_SECRETS_JSON` 保存实际密钥，例如 `{"GW-F01-A":"独立网关密钥"}`；数据库只保存其 SHA-256 指纹，并将凭据绑定客户、工厂和网关。数据库泄露本身不能直接伪造签名。请求签名包含网关ID、Unix时间、随机数和请求体哈希，中央拒绝超过5分钟和重复随机数的请求。旧数据库的 `secret_hash` 字段仅兼容保留，不再用于验签。

网关凭据示例（旧库若要求 `secret_hash` 非空，可同时写入相同指纹）：

```sql
INSERT INTO iot_gateway_credential
(gateway_code, customer_code, factory_code, secret_fingerprint, secret_hash, enabled)
VALUES ('GW-F01-A', 'CUSTOMER-A', 'F01', '<SHA-256指纹>', '<SHA-256指纹>', 1);
```

## MQTT模式配置

```powershell
$env:MES_EDGE_DB='D:\MES-Edge\data\events.edge.db'
$env:MES_EDGE_GATEWAY_ID='GW-F01-A'
$env:MES_EDGE_TRANSPORT='mqtt'
$env:MES_EDGE_MQTT_HOST='mqtt.customer.local'
$env:MES_EDGE_MQTT_PORT='8883'
$env:MES_EDGE_MQTT_CA='D:\MES-Edge\certs\ca.pem'
$env:MES_EDGE_MQTT_CERT='D:\MES-Edge\certs\GW-F01-A.pem'
$env:MES_EDGE_MQTT_KEY='D:\MES-Edge\certs\GW-F01-A.key'
$env:MES_EDGE_CUSTOMER_CODE='CUSTOMER-A'
$env:MES_EDGE_FACTORY_CODE='F01'
$env:MES_EDGE_MQTT_TIMEOUT_SECONDS='10'
$env:MES_EDGE_MQTT_CENTRAL_CONSUMER_CONFIRMED='1'
python edge_gateway_service.py --once
```

发布主题：

```text
mes/v1/{customer}/{factory}/{gateway}/events/{device}
```

Broker必须校验客户证书并使用ACL限制网关只能发布自身主题。中央消费者运行方式：

```powershell
$env:MES_CENTRAL_DB='D:\MES\mes.db'
$env:MES_MQTT_HOST='mqtt.customer.local'
$env:MES_MQTT_PORT='8883'
$env:MES_MQTT_CA='D:\MES\certs\ca.pem'
$env:MES_MQTT_CERT='D:\MES\certs\central-consumer.pem'
$env:MES_MQTT_KEY='D:\MES\certs\central-consumer.key'
python mqtt_event_consumer_service.py
```

消费者按主题和事件内四项身份严格比对后才写入 `iot_device_event`。Broker PUBACK 只有在该消费者已部署并通过验收后，才可作为边缘配置确认条件。

## Windows服务

使用客户认可的服务管理器，以专用低权限账号运行：

```text
python D:\MES\edge_gateway_service.py
```

服务账号只授予边缘数据库目录、证书文件和必要设备网络的访问权限。私钥禁止授予普通用户读取权限。不要使用映射盘符访问共享目录，使用UNC路径和明确服务账号。

## Linux服务

systemd服务使用专用用户、只读程序目录、可写数据目录和EnvironmentFile。EnvironmentFile权限必须为服务用户和管理员可读，不得提交到Git。

## 防火墙

- HTTP模式：边缘到中央TCP 443出站。
- MQTT模式：边缘到Broker TCP 8883出站。
- 不需要从总部向边缘开放入站端口。
- 设备侧端口根据协议插件单独放行，并与办公网络隔离。

## 故障与恢复

- 发送失败：事件释放租约、增加失败次数并保留在本地。
- 重试采用指数退避；达到上限或收到不可重试的4xx拒绝后进入死信，避免坏事件持续占用线路。
- 进程崩溃：租约到期后其他实例重新领取。
- 中央重复接收：按`event_id`返回重复成功，边缘随后确认出队。
- 磁盘恢复：同时恢复`.edge.db`及SQLite WAL文件，或使用SQLite backup API。
- 证书过期：在到期前更换证书并重启网关；旧证书撤销后Broker应立即拒绝。

## 验证

```powershell
python -m pytest -q tests/test_edge_delivery.py
python -m pytest -q tests/test_gateway_http_transport.py
python -m pytest -q tests/test_edge_gateway_runtime.py
python -m pytest -q tests/test_mqtt_transport.py
python -m pytest -q
```

## Application acknowledgement

MQTT QoS1/PUBACK only confirms delivery to the broker. The edge transport now
also waits for `mes/v1/{customer}/{factory}/{gateway}/acks/{event_id}` from
`mqtt_event_consumer_service.py`. The consumer publishes that ACK only after
the event is validated and durably ingested (or explicitly rejected). If the
ACK does not arrive, the edge outbox keeps the event pending and retries it.

For AIM CSV events, set `MES_AIM_EVENT_MODE=edge` and `MES_EDGE_DB` to the
edge outbox database when the independent gateway is used. The MES runtime
periodically scans pending AIM outbox rows, so a failed dispatch is retried
without re-uploading the original CSV.
