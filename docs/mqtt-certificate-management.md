# MQTT mTLS 证书生命周期管理

边缘网关、MQTT Broker、中央消费者之间的通信使用 MQTT QoS1 + 双向 TLS(mTLS)。
本文档说明证书的签发、分发、轮换、吊销流程。

## 证书链结构

```
            MES-MQTT-CA(自签根证书,10年)
                        |
        +---------------+----------------+
        |                                |
  central-consumer.pem              GW-F01-A.pem / .key
  (中央消费者,2年)                  (各边缘网关,2年)
```

- **CA 根证书**:`certs/mqtt/ca/ca.pem`,所有节点都需要信任它。
- **消费者证书**:`certs/mqtt/central/`,部署在中央 MES 侧,仅消费者使用。
- **网关证书**:`certs/mqtt/gateways/<gateway_id>/`,部署到对应厂区网关。

私钥(`.key`)绝不离开生成机器,只分发证书(`.pem`)。

## 工具脚本

`scripts/gen_mqtt_certs.py` 封装了全部证书操作,依赖系统 `openssl`。

### 1. 初始化(首次部署)

```bash
python scripts/gen_mqtt_certs.py init
```

生成 CA 根证书和中央消费者证书。CA 私钥妥善保管,丢失意味着需要全量重签。

### 2. 为网关签发证书

```bash
python scripts/gen_mqtt_certs.py gateway GW-F01-A
```

生成 `certs/mqtt/gateways/GW-F01-A/` 下的证书和私钥。将该目录内容部署到网关机器:

| 文件 | 网关环境变量 |
|------|------------|
| `ca.pem`(从 `certs/mqtt/ca/` 复制) | `MES_EDGE_MQTT_CA` |
| `GW-F01-A.pem` | `MES_EDGE_MQTT_CERT` |
| `GW-F01-A.key` | `MES_EDGE_MQTT_KEY` |

### 3. Broker 配置

```bash
python scripts/gen_mqtt_certs.py broker-config > /etc/mosquitto/conf.d/mes-mtls.conf
```

生成的配置启用 8883 端口、强制 `require_certificate true`、用证书 CN 作为用户名。
Broker 自身的证书需单独签发(也可用 CA 签一张 `broker.pem`)。

### 4. ACL 限制

`/etc/mosquitto/acl.conf` 限制每个网关只能操作自己的主题:

```
# 网关只能发布自己的事件
pattern write mes/v1/%c/+/+/events/+

# 网关只能订阅自己的 ack
pattern read mes/v1/%c/+/+/acks/+

# 中央消费者可订阅所有事件、发布所有 ack
user central-consumer
topic read mes/v1/#
topic write mes/v1/#
```

`%c` 是客户端的 CN(即网关 ID),确保网关无法伪造其他网关的事件。

## 证书轮换

证书有效期 2 年。到期前 30 天应轮换:

```bash
# 1. 归档旧证书,签发新证书
python scripts/gen_mqtt_certs.py rotate GW-F01-A

# 2. 将新证书部署到网关,重启边缘服务
# 3. 在 broker 侧用 CRL 吊销旧证书(见下文),或等旧证书自然过期
```

轮换期间新旧证书都应被 broker 接受(旧证书未过期前),避免服务中断。

## 证书吊销(CRL)

当网关私钥泄露或设备退役时,需立即吊销其证书:

```bash
# 1. 初始化 CRL(首次)
cd certs/mqtt/ca
openssl ca -gencrl -config openssl.cnf -out crl.pem

# 2. 吊销指定证书
openssl ca -config openssl.cnf -revoke ../gateways/GW-F01-A/GW-F01-A.pem

# 3. 重新生成 CRL
openssl ca -gencrl -config openssl.cnf -out crl.pem

# 4. broker 配置加载 CRL
#    在 mosquitto.conf 加: crlfile /etc/mosquitto/crl.pem
#    重启 mosquitto
```

需先准备 `openssl.cnf` CA 配置文件(含 `[ca]` 段和数据库索引)。首次配置后,
`certs/mqtt/ca/index.txt` 会记录所有已签发和已吊销的证书。

## 安全要点

1. **CA 私钥**(`certs/mqtt/ca/ca.key`)是整个信任链的根,必须离线保存,
   绝不部署到任何服务节点,绝不提交 Git。
2. **网关私钥**只存在网关机器上,文件权限 600,服务账号专用。
3. **证书传输**:网关证书通过带外通道(如运维人员专用 U 盘或加密邮件)分发,
   不走与数据通道相同的网络。
4. **过期监控**:监控 `certs/mqtt/` 下所有证书的 `notAfter`,到期前告警。
   ```bash
   openssl x509 -in certs/mqtt/gateways/GW-F01-A/GW-F01-A.pem -noout -enddate
   ```
5. **审计**:每次签发/轮换/吊销都记录到运维日志,记录操作人、时间、网关 ID。

## 故障排查

| 现象 | 可能原因 |
|------|---------|
| 网关连不上 broker | 证书过期 / CA 不匹配 / 端口不通 |
| broker 拒绝连接 | `require_certificate true` 但网关未提供证书 |
| ACL 拒绝发布 | 网关 CN 与主题中的 gateway 段不匹配 |
| 消费者收不到事件 | broker ACL 限制 / 消费者证书 CN 不是 `central-consumer` |

验证网关证书与 CA 匹配:
```bash
openssl verify -CAfile certs/mqtt/ca/ca.pem certs/mqtt/gateways/GW-F01-A/GW-F01-A.pem
# 应输出: GW-F01-A.pem: OK
```
