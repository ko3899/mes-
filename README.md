## AIM机台通讯

系统支持PPT定义的TCP Socket过站校验：旧机台发送SN并接收`<L1>/<L3>`；新机台可使用携带设备、工站、穴位、请求号和HMAC签名的V2协议。检测CSV导入后生成过站证据和待审核报工，L1本身不增加产量。操作步骤参见`docs/AIM机台接入操作手册.md`。

<div align="center">

# MES工厂管家

**轻量级制造执行系统 · 中小工厂数字化管理解决方案**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-green.svg)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3.x-yellow.svg)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-red.svg)](LICENSE)

[功能特性](#功能特性) · [快速开始](#快速开始) · [系统截图](#系统截图) · [API文档](#api文档) · [部署指南](#部署指南) · [贡献指南](#贡献指南)

</div>

---

## 项目简介

MES工厂管家是一套面向中小型制造企业的轻量级制造执行系统，提供从销售订单、生产计划、工单管理到质量检验的全流程数字化管理方案。

**核心优势：**
- 零依赖部署：基于 SQLite，无需额外数据库服务
- 双端协同：PC 管理后台 + 移动采集终端
- 开箱即用：一键启动，5 分钟完成部署
- 模块化架构：按需启用，灵活扩展

---

## 功能特性

<table>
<tr>
<td width="50%">

### 生产管理
- 销售订单管理
- 生产计划排程
- 工单下发与跟踪
- 任务分配与报工
- 生产进度可视化

</td>
<td width="50%">

### 质量管理
- 来料检验 (IQC)
- 过程检验 (PQC)
- 出货检验 (OQC)
- SPC 统计过程控制
- 不良品分析

</td>
</tr>
<tr>
<td>

### 库存管理
- 入库/出库管理
- 库存余额查询
- 物料批次追溯
- 库存预警

</td>
<td>

### 设备管理
- 设备台账维护
- 维修工单管理
- 保养计划制定
- 保养记录追踪

</td>
</tr>
<tr>
<td>

### 基础数据
- 车间/工序配置
- 产品/BOM 管理
- 工艺路线定义
- 数据字典维护

</td>
<td>

### 系统管理
- 用户/角色/权限
- 部门组织架构
- 审批流程配置
- 操作日志审计

</td>
</tr>
</table>

### 采集终端特性

| 功能 | 说明 |
|------|------|
| 扫码报工 | 支持工单号、任务号条码扫描 |
| 快捷操作 | 一键报工、快速检验 |
| 实时统计 | 任务进度、报工数据实时更新 |
| 离线友好 | 界面轻量，弱网环境可用 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户层                                │
├──────────────────────────┬──────────────────────────────────┤
│    移动采集终端 (8080)     │      PC 管理后台 (8081)          │
│    ┌─────────────────┐   │   ┌─────────────────────────┐   │
│    │  扫码  │ 报工   │   │   │  仪表盘 │ 报表 │ 审批   │   │
│    │  质检  │ 物料   │   │   │  基础数据 │ 系统管理     │   │
│    └─────────────────┘   │   └─────────────────────────┘   │
├──────────────────────────┴──────────────────────────────────┤
│                        服务层                                │
│    ┌──────────────────────────────────────────────────┐    │
│    │              Flask RESTful API                    │    │
│    │   auth │ system │ production │ quality │ ...      │    │
│    └──────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                        数据层                                │
│    ┌──────────────────────────────────────────────────┐    │
│    │                   SQLite                          │    │
│    │   sys_* │ base_* │ prod_* │ inv_* │ eqp_* │ ...  │    │
│    └──────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | 推荐 3.10+ |
| pip | 20.0+ | 包管理工具 |
| Flask | 2.x | Web 框架 |
| openpyxl | 3.x | Excel 处理 |

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-username/mes-factory-manager.git
cd mes-factory-manager

# 2. 安装依赖
pip install flask openpyxl

# 3. 启动服务
# Windows
双击 Start All.bat

# Linux/Mac
python backend/app.py &
cd frontend && python run.py &
cd admin && python run.py &
```

### 访问系统

| 系统 | 地址 | 用途 |
|------|------|------|
| 管理后台 | http://localhost:8081/admin | PC端管理操作 |
| 采集终端 | http://localhost:8080 | 移动端数据采集 |

### 默认账号

```
用户名: admin
密  码: admin123
```

> 首次登录后请立即修改默认密码

---

## 系统截图

<div align="center">

### 仪表盘
<!-- ![仪表盘](docs/images/dashboard.png) -->

### 生产管理
<!-- ![生产管理](docs/images/production.png) -->

### 采集终端
<!-- ![采集终端](docs/images/collector.png) -->

</div>

---

## 项目结构

```
mes-factory-manager/
├── backend/                    # 后端服务
│   ├── app.py                  # 应用入口
│   ├── blueprints/             # API 模块
│   │   ├── __init__.py
│   │   ├── auth.py             # 认证接口
│   │   ├── system.py           # 系统管理
│   │   ├── base_data.py        # 基础数据
│   │   ├── inventory.py        # 库存管理
│   │   ├── production.py       # 生产管理
│   │   ├── quality.py          # 质量管理
│   │   ├── equipment.py        # 设备管理
│   │   ├── tool.py             # 工具管理
│   │   ├── schedule.py         # 排班管理
│   │   ├── flow.py             # 审批流程
│   │   ├── dashboard.py        # 仪表盘
│   │   ├── report.py           # 报表统计
│   │   └── notification.py     # 消息通知
│   └── utils/                  # 工具模块
│       ├── database.py         # 数据库操作
│       ├── helpers.py          # 辅助函数
│       └── pdf_generator.py    # 报表生成
├── frontend/                   # 采集终端
│   ├── index.html              # 终端页面
│   └── run.py                  # 启动脚本
├── admin/                      # 管理后台
│   ├── index.html              # 后台页面
│   ├── run.py                  # 启动脚本
│   └── static/                 # 静态资源
│       ├── css/
│       │   └── style.css       # 样式文件
│       └── js/
│           ├── api.js          # API 封装
│           ├── app.js          # 主逻辑
│           ├── modal.js        # 弹窗组件
│           ├── menu.js         # 菜单组件
│           ├── crud.js         # CRUD 组件
│           ├── notification.js # 通知组件
│           └── pages/          # 页面模块
├── database/                   # 数据存储
│   └── mes.db                  # SQLite 数据库
├── docs/                       # 文档
│   └── compose/
├── Start All.bat               # Windows 一键启动
├── start.bat                   # Windows 后端启动
├── README.md                   # 项目说明
└── LICENSE                     # 开源协议
```

---

## API 文档

### 认证方式

所有 API 需先登录获取 Session，请求时自动携带 Cookie。

```bash
# 登录
curl -X POST http://localhost:8080/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### 响应格式

```json
// 成功
{
    "code": 0,
    "data": { ... },
    "message": "操作成功"
}

// 失败
{
    "code": 400,
    "message": "错误信息"
}
```

### 接口列表

<details>
<summary><b>认证接口</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/login | 用户登录 |
| POST | /api/logout | 用户退出 |
| GET | /api/user/info | 获取用户信息 |

</details>

<details>
<summary><b>生产管理</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/prod/workorder/list | 工单列表 |
| POST | /api/prod/workorder/add | 创建工单 |
| GET | /api/prod/task/list | 任务列表 |
| POST | /api/prod/task/update | 更新任务 |
| GET | /api/prod/report/list | 报工记录 |
| POST | /api/prod/report/add | 新增报工 |

</details>

<details>
<summary><b>库存管理</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/inv/inbound/list | 入库单列表 |
| POST | /api/inv/inbound/add | 创建入库单 |
| GET | /api/inv/outbound/list | 出库单列表 |
| GET | /api/inv/balance/list | 库存余额 |

</details>

<details>
<summary><b>质量管理</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/qm/incoming/list | 来料检验列表 |
| POST | /api/qm/incoming/add | 新增检验 |
| GET | /api/spc/chart | SPC 控制图数据 |
| GET | /api/spc/cpk | CPK 分析数据 |

</details>

<details>
<summary><b>其他接口</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/dashboard | 仪表盘统计 |
| GET | /api/dashboard/charts | 图表数据 |
| GET | /api/notification/unread/count | 未读通知数 |
| GET | /api/report/production/pdf | 导出报表 |

</details>

---

## 部署指南

### 开发环境

```bash
# 启用调试模式
export FLASK_ENV=development
python backend/app.py
```

### 生产环境

```bash
# 使用 Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 backend.app:app

# 或使用 uWSGI
pip install uwsgi
uwsgi --http 0.0.0.0:8080 --wsgi-file backend/app.py --callable app
```

### Docker 部署

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install flask openpyxl
EXPOSE 8080 8081
CMD ["python", "backend/app.py"]
```

```bash
docker build -t mes-factory .
docker run -p 8080:8080 -p 8081:8081 mes-factory
```

---

## 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 后端框架 | Flask | RESTful API |
| 数据库 | SQLite | 数据存储 |
| 前端 | HTML/CSS/JS | 用户界面 |
| 图表 | ECharts | 数据可视化 |
| 表格 | openpyxl | Excel 导入导出 |

---

## 更新日志

### v1.0.0 (2026-06-18)

- 初始版本发布
- 完整的生产管理流程
- 双端协同（PC + 移动端）
- 消息通知系统
- SPC 统计分析
- 数据导入导出

---

## 贡献指南

欢迎贡献代码、提交 Issue 或改进文档！

```bash
# 1. Fork 项目
# 2. 创建功能分支
git checkout -b feature/amazing-feature

# 3. 提交更改
git commit -m 'feat: add amazing feature'

# 4. 推送分支
git push origin feature/amazing-feature

# 5. 创建 Pull Request
```

### 提交规范

```
feat:     新功能
fix:      Bug 修复
docs:     文档更新
style:    代码格式
refactor: 代码重构
test:     测试相关
chore:    构建/工具
```

---

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。

---

<div align="center">

**如果这个项目对你有帮助，请给一个 Star 支持一下**

[![Star History Chart](https://api.star-history.com/svg?repos=your-username/mes-factory-manager&type=Date)](https://star-history.com/#your-username/mes-factory-manager&Date)

</div>
