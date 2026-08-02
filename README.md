# KVM 监控大屏系统 (KVM Dashboard)

> 专为上海机场 G&D KVM 设备（如 ControlCenter-Compact / ControlCenter-IP）打造的工业级、动态实时监控与拓扑大屏系统。

## 🌟 核心特性

1. **智能拓扑生成 (Auto-Topology)**：无需手动绘制。自动通过 SNMP 探获设备下挂的所有 CPU/CON 终端，以及视频线的插拔状态，动态渲染带光效的树状网络拓扑图。
2. **"体检+急诊" 双通道监控**：
   - **主动轮询 (Pull)**：高性能并发调度器（Semaphore 限流 + SnmpEngine 复用），每分钟对所有设备进行主动状态拉取。
   - **被动接收 (Push)**：监听 UDP 162 端口，实时接收交换机 SNMP Trap 告警， WebSocket 毫秒级推送到前端大屏。
3. **指标自由配置 (Configurable Metrics)**：告别 Hardcode 的硬编码解析。基于权威厂商 MIB，可在管理后台自由开关任何指标的**轮询**、**入库存档**、**告警阈值**。
4. **时序数据超大规模支持**：原生支持 SQLite（开发测试）及 **PostgreSQL + TimescaleDB**（生产），单节点轻松支持 500 台 KVM + 万级终端节点的高频数据吞吐与历史趋势压缩（ECharts 可视化）。
5. **别名沉浸映射**：对于非人类友好的 SNMP 硬件编码，支持第一视角的终端别名映射重命名表。

---

## 🏗️ 架构概览

| 层级 | 技术栈 | 说明 |
|------|--------|------|
| **后端 API** | `FastAPI` (Python 3.10) | 纯异步、高性能 OpenAPI 接口 |
| **持久层** | `PostgreSQL 16` + `TimescaleDB` | RDBMS 关系型管理 + 压缩超表时序引擎 |
| **ORM & DB** | `SQLAlchemy 2.0` (asyncpg/aiosqlite) | 自动适配 SQLite 测试模式与生产模式 |
| **SNMP 通信** | `pysnmp` (纯 asyncio) | 对接全线设备，单次 WALK 高效汇聚端口数据 |
| **前端大屏** | `React 18` + `Vite` | 深色质感、Zustand 全局流、纯 SVG 拓扑图 + 手绘图表 |
| **部署交付** | `Docker Compose` | 一键拉起 DB + Backend + Frontend (Nginx) |

---

## 📂 核心交接文档指引

由于本项目开发严谨复杂，相关的深入逻辑设计和规范均已文档化：

1. **📚 API 契约文档** 👉 `tasks/api_docs.md`（含新增 `last_metrics` 端口状态字段说明）
2. **🎨 前端设计案** 👉 `tasks/frontend_plan.md`（UI 质感、CSS 色卡基准）
3. **🔧 物理端口逻辑** 👉 `docs/port_mapping_logic.md`（**必读**：解释如何通过 Column 1 映射机架位置）
4. **💡 生产避坑教训** 👉 `tasks/lessons.md`（包含并发限流、SNMP 库兼容性处理）
5. **📝 进度追踪清单** 👉 `tasks/todo.md`（项目大阶段总揽）
6. **🎮 本地 SNMP 模拟器指南** 👉 `backend/kvm_simulator_README.md`（启动本地后端、前端和多 Profile 模拟场景的人工测试步骤）
7. **🧭 G&D 设备架构与 MIB Profile** 👉 `docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md`（中心矩阵、DP 小矩阵、独立 VisionXS 端点及数据源边界）

---

## 🚀 快速启动

### 1. 环境要求
- **Python 3.10+** (后端)
- **Node.js 18+** (前端)
- **PostgreSQL 16+** (生产环境推荐) 或 **SQLite** (开发环境)

### 2. 开发模式启动
```bash
# 后端 (backend 目录下)
pip install -r requirements.txt
复制环境变量模板：
```bash
# Windows
Copy-Item ..\.env.example ..\.env
# Linux/Mac
cp ../.env.example ../.env
```
*(默认配置采用 SQLite 数据库，开箱即用无依赖)*

### 3. 运行后端服务
```bash
# 在 backend 目录下执行
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
服务启动后，访问 **[http://localhost:8000/api/docs](http://localhost:8000/api/docs)** 即可查看所有活体 API 接口。

## 检测snmp模拟器测试 
backend 目录下
.venv\Scripts\python.exe run_simulators_large.py 

 .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18002  启动监控后端  后端目录下

前端目录下启动页面
  npm.cmd run dev -- --host 127.0.0.1 --port 3001 --strictPort


大型模拟器
终端 1，启动 Dashboard 后端：
cd H:\WORK\I\kvm-dashboard\backend

$env:DB_MODE = "sqlite"
$env:SQLITE_PATH = "simulator_local.db"
$env:SNMP_TRAP_PORT = "10162"
$env:SNMP_DEFAULT_COMMUNITY = "public"

Remove-Item Env:SIMULATOR_BRIDGE_ENABLED -ErrorAction SilentlyContinue
Remove-Item Env:SIMULATOR_BRIDGE_TOKEN -ErrorAction SilentlyContinue

.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18002
终端 2，启动模拟器：
cd H:\WORK\I\kvm-dashboard\backend

$env:SIM_TOPOLOGY = "all-profiles"
$env:SIM_ADDRESS_MODE = "loopback"
$env:SIM_WEB_PORT = "18890"
$env:SNMP_COMMUNITY = "public"

$env:TRAP_TARGET_HOST = "127.0.0.1"
$env:SNMP_TRAP_PORT = "10162"

Remove-Item Env:SIMULATOR_BRIDGE_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:SIM_DASHBOARD_URL -ErrorAction SilentlyContinue

.\.venv\Scripts\python.exe -m simulator
然后在 Dashboard 的“管理后台 → 自动发现”中配置：
CIDR：127.0.1.0/29
SNMP 端口：161
community：public
启动扫描
扫描应识别并加入 5 台设备。之后后台会按正常轮询周期拉取数据；模拟器里触发 Trap 后，Dashboard 的 Trap Receiver 会收到 UDP 10162 通知，并对对应源 IP 的设备触发即时轮询。
验证成功的标准是：
自动发现结果为 5 台已识别/导入设备；
设备地址是 127.0.1.1:161 至 127.0.1.5:161；
Dashboard 设备详情中的 last_health_check、last_poll 持续更新；
修改模拟器状态后，下一轮轮询数据变化；
发送 Trap 后，Dashboard 出现 Trap/告警或相应实时更新。
---


## 🐳 Docker 生产部署 (一键起飞)

确保机房宿主机已安装 Docker 和 Docker Compose。

```bash
# 在项目根目录下，修改好 .env (务必将 DB_MODE 改为 postgres，并设置强密码)
docker-compose up -d --build
```

**容器说明**：
- `kvm_postgres`: 包含了 TimescaleDB 扩展的 PostgreSQL 实例 (占用本地 5432 端口可选)。
- `kvm_backend`: FastAPI 接口及轮询常驻服务，内部开放 8000。
- `kvm_frontend`: 托管静态资产与反代。

> ⚠️ 注意：由于 UDP 162(SNMP Trap) 属于特权端口，Docker 部署时可能需要特殊端口映射配置（参阅 `docker-compose.yml` 注释）。
