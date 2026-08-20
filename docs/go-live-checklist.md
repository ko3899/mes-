# MES工厂管家 上线检查清单

本清单汇总从代码到运维的全部上线准备项。按顺序逐项打勾,全部通过即可上线。
每项标注了「负责人」和「验证方式」,便于团队分工。

> 代码侧改动已全部完成并推送(commit `0a941dd`)。剩余为**真实环境验证**项。

---

## 一、代码与测试

### 1.1 测试套件
- [ ] 在干净环境克隆仓库,`pip install -r requirements.txt`
- [ ] 运行 `python -m pytest tests/ -q`,确认 **258 passed, 0 failed**
- [ ] 测试耗时应在 7 分钟以内(本机基准 6:43)
- [ ] 确认 `pytest.ini` 含 `timeout = 30`(防卡死)
- [ ] **负责人**:开发 / **验证**:`pytest` 输出

### 1.2 CI 流水线
- [ ] GitHub 仓库 → Settings → Actions 已启用
- [ ] 推送一次提交,确认 `.github/workflows/ci.yml` 触发
- [ ] CI 在 Python 3.8 和 3.10 矩阵下均绿
- [ ] **负责人**:开发 / **验证**:GitHub Actions 页面

### 1.3 代码质量基线
- [ ] 无未提交改动(`git status` 干净)
- [ ] 本地 master 与 github/master、origin/master 一致
- [ ] **负责人**:开发 / **验证**:`git status -sb`

---

## 二、生产配置

### 2.1 密钥管理
- [ ] `SECRET_KEY` / `FLASK_SECRET_KEY` 通过环境变量注入,**非**硬编码
- [ ] 密钥为强随机字符串(≥32 字节):`python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] `MES_ENV=production` 已设置(强制要求密钥)
- [ ] `.env.production` **不**含真实密钥(仅作模板)
- [ ] **负责人**:运维 / **验证**:`echo $SECRET_KEY | wc -c` ≥ 65

### 2.2 数据库
- [ ] **SQLite 模式**(单机/小规模):确认 `MES_DB_TYPE=sqlite`(或不设)
- [ ] **PostgreSQL 模式**(多工厂/高并发):
  - [ ] `MES_DB_TYPE=postgresql` 及连接参数已配置
  - [ ] 已运行 `python scripts/generate_postgresql_schema.py > database/mes_postgresql.sql`
  - [ ] PostgreSQL 实例已建库,`mes_postgresql.sql` 已导入
  - [ ] 应用启动后 `init_db()` 无报错
  - [ ] 按 `docs/postgresql-migration.md` 的"验证清单"逐项验证
- [ ] 数据库文件/卷已做持久化挂载(Docker: `./database:/app/database`)
- [ ] **负责人**:运维 / **验证**:`/healthz` 返回 200,`/readyz` 返回 200

### 2.3 容器与进程
- [ ] `Dockerfile` 的 HEALTHCHECK 用 `python -c "urllib..."` 探测 `/healthz`(非 curl)
- [ ] `docker-compose.yml` 的 healthcheck 同上,含 `start_period`
- [ ] `production.py` 启动日志含各阶段耗时(`init_db` / `init_sample_data`)
- [ ] Waitress 已安装(`pip show waitress`),非 Flask 内置服务器
- [ ] **负责人**:运维 / **验证**:`docker compose up`,`docker ps` 状态 healthy

---

## 三、安全加固

### 3.1 传输安全
- [ ] Nginx/反向代理已部署 `deploy/nginx/mes.conf`
- [ ] TLS 证书已配置(正式证书或 Let's Encrypt)
- [ ] HTTP → HTTPS 301 跳转生效
- [ ] HSTS / X-Content-Type-Options / X-Frame-Options 响应头存在
- [ ] `curl -I http://<host>/` 返回 301,`curl -I https://<host>/healthz` 返回 200
- [ ] **负责人**:运维 / **验证**:浏览器开发者工具看响应头

### 3.2 Session 安全
- [ ] `SESSION_COOKIE_HTTPONLY=True`(代码已设)
- [ ] `MES_ENV=production` 时 `SESSION_COOKIE_SECURE=True`(代码已设)
- [ ] `SESSION_COOKIE_SAMESITE=Lax`(代码已设)
- [ ] **负责人**:开发 / **验证**:浏览器看 Cookie 属性

### 3.3 限流
- [ ] `flask-limiter` 已安装时优先使用(`pip show flask-limiter`)
- [ ] 未安装时,内置内存限流器兜底,默认 `200 per day`、`50 per hour`
- [ ] 验证:连续请求 51 次 `/healthz` 后第 51 次返回 429
- [ ] Nginx 登录接口限流 `1r/s`、API 限流 `10r/s` 生效
- [ ] **负责人**:运维 / **验证**:压测脚本快速打登录接口,观察 429

### 3.4 机台接入安全
- [ ] V1 端点配置了机台来源 IP 白名单(`allowed_remote_ip`)
- [ ] V2 端点配置了共享密钥(`shared_secret`)
- [ ] V2 防重放已启用(`require_request_nonce=1`)
- [ ] 机台 TCP 端口与办公网络隔离(防火墙/VLAN)
- [ ] **负责人**:运维 / **验证**:`/api/iot/machine/endpoints` 查端点配置

### 3.5 边缘网关安全
- [ ] HTTP 模式:网关密钥通过 `MES_GATEWAY_SECRETS_JSON` 注入,非明文
- [ ] MQTT 模式:mTLS 证书已部署(见第五节)
- [ ] 网关数据库(`*.edge.db`)权限 600,专用服务账号
- [ ] **负责人**:运维 / **验证**:`edge_gateway_service.py --show-config` 不泄露密钥

---

## 四、监控与日志

### 4.1 结构化日志
- [ ] `MES_LOG_FORMAT=json`(默认)或 `text`
- [ ] 日志输出为单行 JSON,含 `ts`/`level`/`logger`/`msg` 字段
- [ ] 异常日志含 `stack` 字段
- [ ] 日志文件轮转:`logs/mes_YYYYMMDD.log`,10MB×5 份
- [ ] **负责人**:运维 / **验证**:`tail -f logs/mes_*.log | python -m json.tool`

### 4.2 日志收集
- [ ] 日志目录已挂载/采集到集中平台(ELK/Loki/Datadog)
- [ ] 告警规则:ERROR 级别日志 > 阈值时告警
- [ ] 告警规则:`/healthz` 连续 3 次 503 告警
- [ ] **负责人**:运维 / **验证**:采集平台看是否收到 MES 日志

### 4.3 健康检查端点
- [ ] `/healthz` 返回 200(存活探针,无认证)
- [ ] `/readyz` 返回 200(就绪探针,含关键表检查)
- [ ] `/healthz/full` 返回完整诊断(建议加认证或仅内网访问)
- [ ] 负载均衡/K8s 探针配置指向 `/healthz` 和 `/readyz`
- [ ] **负责人**:运维 / **验证**:`curl http://<host>/healthz/full | python -m json.tool`

### 4.4 关键指标监控
- [ ] CPU/内存/磁盘 监控
- [ ] 数据库连接数/锁等待 监控
- [ ] MQTT 消费者心跳(`/healthz/full` 的 `mqtt_consumer.status`)
- [ ] 边缘网关待处理事件数(`/healthz/full` 的 `edge_gateway.pending_events`)
- [ ] AIM outbox 待派发数(`/healthz/full` 的 `aim_outbox.pending`)
- [ ] 机台端点监听状态(`/healthz/full` 的 `machine_endpoints`)
- [ ] **负责人**:运维 / **验证**:监控面板

---

## 五、MQTT mTLS 证书

### 5.1 证书签发
- [ ] `python scripts/gen_mqtt_certs.py init` 已执行,CA + 消费者证书已生成
- [ ] 每个网关 `python scripts/gen_mqtt_certs.py gateway <id>` 已签发
- [ ] `certs/` 目录在 `.gitignore` 中(已确认)
- [ ] CA 私钥(`certs/mqtt/ca/ca.key`)离线保存,未部署到任何节点
- [ ] **负责人**:运维 / **验证**:`python scripts/gen_mqtt_certs.py list`

### 5.2 证书部署
- [ ] Broker:`ca.pem` + `broker.pem` + `broker.key` 已部署
- [ ] Broker:`mosquitto.conf` 启用 `require_certificate true`
- [ ] Broker:ACL 配置限制网关只能操作自身主题
- [ ] 中央消费者:`central-consumer.pem/.key` + `ca.pem` 已部署
- [ ] 各网关:`<id>.pem/.key` + `ca.pem` 已部署,环境变量 `MES_EDGE_MQTT_*` 指向
- [ ] **负责人**:运维 / **验证**:网关 `edge_gateway_service.py --once` 成功

### 5.3 证书运维
- [ ] 证书过期监控(到期前 30 天告警)
- [ ] 轮换流程已演练:`python scripts/gen_mqtt_certs.py rotate <id>`
- [ ] CRL 吊销流程已记录(见 `docs/mqtt-certificate-management.md`)
- [ ] **负责人**:运维 / **验证**:`openssl x509 -in <cert> -enddate -noout`

---

## 六、备份与恢复

### 6.1 备份
- [ ] `scripts/backup_database.py` 已加入定时任务(cron/任务计划),每日执行
- [ ] 备份保留份数合理(`--keep 30` 或按需)
- [ ] 备份输出目录已挂载到持久存储/异地
- [ ] **负责人**:运维 / **验证**:手动跑一次 `python scripts/backup_database.py --keep 2`

### 6.2 恢复演练
- [ ] **SQLite**:从 zip 恢复到测试环境,应用能正常启动
- [ ] **PostgreSQL**:`pg_restore -d mes_test <dump>` 成功,应用能正常启动
- [ ] 恢复耗时已记录,满足 RTO 要求
- [ ] **负责人**:运维 / **验证**:在测试环境执行恢复

---

## 七、压测与验收

### 7.1 压测
- [ ] `python scripts/load_test.py --base-url <url> --scenario all --users 50 --duration 60`
- [ ] 登录场景:错误率 < 1%,P95 < 500ms
- [ ] 过站场景:无数据库死锁,P95 < 1s
- [ ] 设备事件场景:无序列号冲突,P95 < 200ms
- [ ] 压测后 `/healthz/full` 无 failed/error 堆积
- [ ] **负责人**:开发 / **验证**:压测脚本 JSON 输出

### 7.2 端到端验收
- [ ] 按 `docs/MES_端到端验收案例.md` 逐项验证
- [ ] AIM 机台接入:按 `docs/AIM机台接入操作手册.md` 完成一台真实机台接入
- [ ] 边缘网关:按 `docs/edge-gateway-runtime.md` 完成一个网关联调
- [ ] **负责人**:开发+业务 / **验证**:验收文档签字

### 7.3 业务功能冒烟
- [ ] admin/admin123 能登录,首次登录后**立即修改默认密码**
- [ ] 基础数据:产品/工序/工单 CRUD 正常
- [ ] 生产:报工、过站、防呆校验正常
- [ ] 质量:IQC/PQC/OQC 录入和查询正常
- [ ] 库存:入出库正常
- [ ] 导入导出:CSV/Excel 正常
- [ ] 看板:实时刷新正常
- [ ] **负责人**:业务 / **验证**:手动操作

---

## 八、上线后首周值守

- [ ] 安排专人 7×24 值班首周
- [ ] `/healthz/full` 每日检查 2 次
- [ ] 日志 ERROR 告警有人响应
- [ ] 数据库备份每日检查是否成功
- [ ] 机台掉线/边缘网关断连有人处理
- [ ] 一周后做首次复盘,记录遗留问题
- [ ] **负责人**:运维 / **验证**:值守日志

---

## 签字确认

| 角色 | 姓名 | 日期 | 签字 |
|------|------|------|------|
| 开发负责人 | | | |
| 运维负责人 | | | |
| 业务负责人 | | | |
| 项目经理 | | | |

> 全部打勾 + 签字后,方可正式上线。

---

## 附录:关键文件索引

| 类别 | 文件 |
|------|------|
| 测试 | `tests/conftest.py`, `pytest.ini`, `.github/workflows/ci.yml` |
| 生产配置 | `.env.production`, `Dockerfile`, `docker-compose.yml`, `docker-compose.postgres.yml`, `production.py` |
| 数据库 | `backend/utils/database.py`, `backend/utils/postgres_compat.py`, `scripts/generate_postgresql_schema.py`, `database/mes_postgresql.sql`, `docs/postgresql-migration.md` |
| 安全 | `backend/app.py`(Cookie/限流), `deploy/nginx/mes.conf`, `deploy/nginx/proxy_params.conf` |
| 证书 | `scripts/gen_mqtt_certs.py`, `docs/mqtt-certificate-management.md` |
| 日志/监控 | `backend/utils/json_logger.py`, `backend/utils/health_checks.py`, `production.py` |
| 备份 | `scripts/backup_database.py` |
| 压测 | `scripts/load_test.py` |
| 验收 | `docs/MES_端到端验收案例.md`, `docs/AIM机台接入操作手册.md`, `docs/edge-gateway-runtime.md` |
