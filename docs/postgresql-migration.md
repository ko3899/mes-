# PostgreSQL 迁移说明

本项目默认使用 SQLite（零依赖、开箱即用）。生产环境如需更高并发和可靠性，
可切换到 PostgreSQL。本文档说明当前迁移进度和操作步骤。

## 当前状态

| 能力 | 状态 |
|------|------|
| PostgreSQL 连接层 | ✅ 已完成（`backend/utils/postgres_compat.py`） |
| Schema 自动生成 | ✅ 已完成（`scripts/generate_postgresql_schema.py`） |
| 生成好的 schema | ✅ `database/mes_postgresql.sql`（156 表 / 38 索引 / 87 外键） |
| `init_db()` 分发 | ✅ PostgreSQL 模式走 schema 文件 + 最小种子 |
| `_init_extra_tables()` / `_create_indexes()` | ✅ PostgreSQL 模式跳过（schema 已含） |
| 运行时 SQL 兼容 | ⚠️ 部分完成（见下） |
| 实时验证 | ❌ 待有 PostgreSQL 实例后验证 |

## 已处理的运行时兼容

以下 SQLite 语法已在 `postgres_compat.py` 的 `_translate_sql()` 中**自动翻译**,无需改业务代码:

- `?` 占位符 → `%s`(psycopg2 风格)
- `PRAGMA foreign_keys = ON` 等 → `SELECT 1`(无害化)
- `PRAGMA table_info(t)` → `information_schema.columns` 查询(返回行兼容 `row[1]` 取列名)
- `SELECT ... FROM sqlite_master WHERE type='table' AND name=?` → `information_schema.tables`
- `datetime('now','-N minutes')` → `now() - interval 'N minutes'`
- `INSERT OR IGNORE INTO` → `INSERT INTO ... ON CONFLICT DO NOTHING`
- `GROUP_CONCAT(x)` → `string_agg(x::text, ',')`
- `INSERT ... RETURNING id` 自动追加,支持 `cursor.lastrowid`
- `RealDictCursor` + 自定义 `_DualRow` 同时支持 `row['col']` 和 `row[N]` 数字索引

## 已知未处理项(需逐个适配)

以下情况遇到时需手动修改对应 SQL:

1. `INSERT OR REPLACE INTO` → `INSERT ... ON CONFLICT DO UPDATE`(代码库中目前为 0 处)
2. `PRAGMA index_list(t)` / `PRAGMA foreign_key_list(t)` → 需改用 `information_schema` 或 `pg_catalog`
3. `PRAGMA foreign_key_check` → 自定义查询
4. `strftime('%Y-%m', col)` 等 SQL 层 SQLite 函数(代码库中目前为 0 处,均为 Python `datetime.strftime`)
5. 大小写敏感的 `LIKE` → `ILIKE`(如需不区分大小写)
6. 自增列已转为 `SERIAL`,`lastrowid` 仅对有 `id` 列的表有效
7. SQLite 的 `ON CONFLICT(col) DO UPDATE` 语法在 PostgreSQL 中需确保冲突列有唯一约束/主键

## 部署步骤（Docker Compose）

```bash
# 1. 确保生成了最新 schema
python scripts/generate_postgresql_schema.py > database/mes_postgresql.sql

# 2. 用 PostgreSQL 覆盖文件启动
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d

# 3. 查看日志
docker compose logs -f mes-factory
```

PostgreSQL 容器启动时会自动执行 `database/mes_postgresql.sql` 建表。
应用启动时 `init_db()` 会检测 `MES_DB_TYPE=postgresql` 并确保 schema 存在，
然后插入最小种子数据（默认租户、admin/user 角色、admin 账户，密码 admin123）。

## 部署步骤（手动 / 非 Docker）

```bash
# 1. 安装依赖
pip install psycopg2-binary

# 2. 准备 PostgreSQL 实例
createdb mes_factory
psql mes_factory -f database/mes_postgresql.sql

# 3. 配置环境变量
export MES_DB_TYPE=postgresql
export MES_DB_HOST=localhost
export MES_DB_PORT=5432
export MES_DB_NAME=mes_factory
export MES_DB_USER=mes
export MES_DB_PASS=your_password
export MES_ENV=production
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# 4. 启动
python production.py
```

## 重新生成 Schema

当 SQLite 端的 `init_db()` 或 `_init_extra_tables()` 有表结构变更时，
重新生成 PostgreSQL schema：

```bash
python scripts/generate_postgresql_schema.py > database/mes_postgresql.sql
```

生成器会：
- 运行 SQLite 的 `init_db()` + `_init_extra_tables()` + `_create_indexes()`
- 读取 `sqlite_master` 中的 DDL
- 将 `INTEGER PRIMARY KEY AUTOINCREMENT` 转为 `SERIAL PRIMARY KEY`
- 将 `BLOB` 转为 `BYTEA`
- 把外键拆成独立的 `ALTER TABLE ... ADD CONSTRAINT` 语句（避免建表顺序问题）

## 验证清单

部署到 PostgreSQL 后，按以下顺序验证：

- [ ] 应用能启动（`python production.py` 无报错）
- [ ] `/healthz` 返回 200
- [ ] admin/admin123 能登录
- [ ] 基础数据 CRUD（产品、工单、报工）
- [ ] 机台通讯端点配置
- [ ] 设备平台事件摄入
- [ ] 质量处置流程
- [ ] 导入导出（CSV/Excel）

遇到 SQL 报错时，参照"已知未处理项"逐个修复对应文件。
