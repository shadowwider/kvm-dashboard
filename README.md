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

---

## GPT 图像生成工作流

安装 Python 依赖后，可直接在项目根目录运行 `image_gen.py` 调用 OpenAI 图像 API：

```bash
pip install -r backend/requirements.txt
```

先设置 API Key：

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your_api_key"
```

示例：

```bash
python image_gen.py generate \
  --model gpt-image-1 \
  --prompt "Native 4K photorealistic aerial drone photo of red desert sand dunes at sunrise, high oblique view, wind-carved sand ripples, sharp realistic texture, no text, no watermark." \
  --size 1536x1024 \
  --quality high \
  --output-format png \
  --out ~/example.png
```

说明：
- `--model` 可替换为你账户当前可用的 GPT 图像模型。
- `--out` 支持相对路径和 `~`。
- 脚本会把接口返回的 base64 图像解码后写入本地文件。

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
