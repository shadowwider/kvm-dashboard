# L00 基线与运行环境契约

状态：`Accepted for Windows local port mode`
日期：2026-07-31
适用范围：本地 KVM Dashboard、KVM SNMP Simulator 和两个 Vite 前端
上层入口：`docs/simulator/LAYERED_DEVELOPMENT_PLAN.md`

## 1. 本层目标

L0 只解决四件事：

1. 所有人使用同一组地址、端口、数据库和环境变量；
2. 启动前能发现配置漂移和端口占用；
3. 启动后能判断 Dashboard、Simulator、Agent、Bridge 和 Trap 端口是否对齐；
4. 输出中不泄露 bridge token、SNMP community 或其他凭据。

本层不修改或解释 MIB、OID、Profile、运行状态字段、Trap 语义、拓扑语义和页面交互。

## 2. 下层契约依赖

L0 是最底层，没有代码层依赖。它只冻结当前工作区可以重复执行的运行边界。

## 3. 本层不得重新解释的事实

- 厂家 MIB、OID、枚举、索引和 Trap 定义由 L1 决定；
- Profile 结构由 L2 决定；
- 运行状态类型和 PATCH 原子性由 L3 决定；
- SNMP/Trap 协议正确性由 L4 决定；
- 生命周期、持久化和清理由 L5 决定；
- Dashboard 对不同 Profile 的采集边界由 L6 决定；
- UI 和拖拽拉线不属于 L0。

因此，L0 的 `status=ok` 只表示进程、配置和连接基线正常，不表示 MIB 或业务状态正确。

## 4. 固定的本地地址

| 组件 | 地址 | 用途 |
|---|---|---|
| Dashboard API | `http://127.0.0.1:18002` | API、数据库、调度器、Trap receiver、Bridge 接收端 |
| Dashboard UI | `http://127.0.0.1:3001` | Dashboard Vite |
| Simulator API/托管 UI | `http://127.0.0.1:18890` | Simulator REST、WebSocket、托管 UI |
| Simulator UI dev | `http://127.0.0.1:13100` | 独立 Vite dev |
| Dashboard Trap receiver | `0.0.0.0:10162/udp` | 本地非特权 Trap 端口 |
| 五个 preset Agent | `127.0.0.1:11161..11165/udp` | `all-profiles` 的 SNMP Agent |

本地数据库固定为：

```text
backend/simulator_local.db
```

该文件受 `.gitignore` 的 `*.db` 规则保护，不得提交。

日志目录固定为：

```text
backend/logs/
```

## 5. 环境变量契约

### 5.1 Dashboard 后端

| 变量 | L0 值 | 说明 |
|---|---|---|
| `DB_MODE` | `sqlite` | 本地联调禁止连接生产 PostgreSQL |
| `SQLITE_PATH` | `simulator_local.db` | 隔离测试库 |
| `BACKEND_HOST` | `127.0.0.1` | 同时供 doctor 和 Uvicorn 命令使用 |
| `BACKEND_PORT` | `18002` | 同时供 doctor 和 Uvicorn 命令使用 |
| `SIMULATOR_BRIDGE_ENABLED` | `true` | Dashboard 接受本地 bridge |
| `SIMULATOR_BRIDGE_TOKEN` | 运行时注入 | Dashboard 与 Simulator 必须相同 |
| `SNMP_DEFAULT_COMMUNITY` | 运行时注入 | Dashboard poller 使用 |
| `SNMP_TRAP_PORT` | `10162` | Dashboard Trap receiver 监听端口 |

### 5.2 Simulator 后端

| 变量 | L0 值 | 说明 |
|---|---|---|
| `SIMULATOR_HOST` | `127.0.0.1` | Simulator HTTP 监听地址 |
| `SIM_WEB_PORT` | `18890` | 托管 UI 模式的 HTTP 端口 |
| `SIM_TOPOLOGY` | `all-profiles` | L0 固定验收拓扑 |
| `SIM_ADDRESS_MODE` | `port` | Windows 默认模式 |
| `SIM_DASHBOARD_URL` | `http://127.0.0.1:18002/api/v1` | 必须包含 `/api/v1` |
| `SIM_RUN_ID` | `local-simulator` | Bridge 所有权边界 |
| `SIMULATOR_BRIDGE_TOKEN` | 运行时注入 | 与 Dashboard 相同 |
| `SNMP_COMMUNITY` | 运行时注入 | Simulator Agent 使用 |
| `TRAP_TARGET_HOST` | `127.0.0.1` | 本地 Dashboard Trap receiver |
| `SNMP_TRAP_PORT` | `10162` | 必须与 Dashboard 一致 |

注意两个 community 变量名称不同：

- Dashboard：`SNMP_DEFAULT_COMMUNITY`
- Simulator：`SNMP_COMMUNITY`

`doctor` 只报告二者是否相同，绝不打印实际值。

### 5.3 前端

| 变量 | L0 值 |
|---|---|
| `VITE_BACKEND_TARGET` | `http://127.0.0.1:18002` |
| `DASHBOARD_UI_HOST` | `127.0.0.1` |
| `DASHBOARD_UI_PORT` | `3001` |
| `SIMULATOR_UI_HOST` | `127.0.0.1` |
| `SIMULATOR_UI_PORT` | `13100` |
| `SIMULATOR_UI_MODE` | `built`（独立 Vite 时改为 `dev`） |

`simulator-ui/vite.config.js` 已参数化：

- 托管 UI 联调使用 Simulator `18890`；
- 独立 Vite dev 示例使用 Simulator `8888`；
- `VITE_SIMULATOR_TARGET` 由 simulator-ui Vite proxy 消费；
- `SIMULATOR_UI_PORT` 控制独立 dev server 端口。

## 6. L0 doctor 和 smoke

入口：

```text
backend/simulator/l0_check.py
```

从 `backend` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m simulator.l0_check doctor --component simulator
.\.venv\Scripts\python.exe -m simulator.l0_check smoke `
  --expected-topology all-profiles `
  --expected-agents 5 `
  --require-bridge `
  --require-ui
.\.venv\Scripts\python.exe -m simulator.l0_check --json snmp-get
```

机器可读输出：

```powershell
.\.venv\Scripts\python.exe -m simulator.l0_check --json doctor --component all
```

退出码：

| 退出码 | 含义 |
|---:|---|
| `0` | 没有 `fail`；允许有明确的 `warn` |
| `1` | 至少一项 `fail`，不得继续启动或验收 |
| `2` | 命令行参数错误 |

`doctor`：

- 合并当前目录 `.env` 与进程环境变量，进程环境优先；
- 打印最终 L0 配置，但只显示 secret 的 `configured/default/not-configured/default-placeholder`；
- 检查端口范围、URL、地址模式、community 对齐；
- 以独占绑定方式检查计划使用的 TCP/UDP 端口；
- 对 built-in preset 明确检查固定的 `11161..11165`。

`smoke`：

- 验证 Dashboard `/health`；
- 验证 Dashboard `/api/v1/health` 的数据库与 scheduler；
- 验证 Simulator `/api/v1/status`；
- 验证活动 topology；
- 验证 runtime device 数和 Agent 数；
- 验证 bridge 最近一次 reconcile 和 binding 数；
- 验证 Simulator Trap target 与 Dashboard Trap port 对齐；
- 可验证 Simulator 托管/fallback HTML 页面。

`snmp-get`：

- 必须在 Simulator Agent 已启动后执行；
- 对当前 built-in preset 的每个 Agent 发出真实
  `1.3.6.1.2.1.1.2.0` GET；
- 输出各绑定返回的精确 `sysObjectID.0`，任一端口无响应即退出 `1`；
- community 只从运行环境读取，不出现在输出中。

## 7. PowerShell 启动

不要在 PowerShell 中使用 CMD 的 `set NAME=value`。PowerShell 必须使用 `$env:NAME='value'`。

### 7.1 启动前统一 preflight

打开一个 PowerShell，执行。`<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>` 必须替换为
本轮临时生成的随机值，并在 Dashboard 与 Simulator 终端使用同一个值；
doctor 会拒绝未替换的占位符。不要把实际值写入文档、脚本或仓库文件。

```powershell
Set-Location 'H:\WORK\I\kvm-dashboard\backend'

$env:DB_MODE='sqlite'
$env:SQLITE_PATH='simulator_local.db'
$env:BACKEND_HOST='127.0.0.1'
$env:BACKEND_PORT='18002'
$env:DASHBOARD_UI_HOST='127.0.0.1'
$env:DASHBOARD_UI_PORT='3001'
$env:SIMULATOR_HOST='127.0.0.1'
$env:SIM_WEB_PORT='18890'
$env:SIMULATOR_UI_HOST='127.0.0.1'
$env:SIMULATOR_UI_PORT='13100'
$env:SIMULATOR_UI_MODE='built'
$env:SIM_TOPOLOGY='all-profiles'
$env:SIM_ADDRESS_MODE='port'
$env:SIM_DASHBOARD_URL='http://127.0.0.1:18002/api/v1'
$env:SIM_RUN_ID='local-simulator'
$env:SIMULATOR_BRIDGE_ENABLED='true'
$env:SIMULATOR_BRIDGE_TOKEN='<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>'
$env:SNMP_DEFAULT_COMMUNITY='public'
$env:SNMP_COMMUNITY='public'
$env:TRAP_TARGET_HOST='127.0.0.1'
$env:SNMP_TRAP_PORT='10162'
$env:VITE_BACKEND_TARGET='http://127.0.0.1:18002'

.\.venv\Scripts\python.exe -m simulator.l0_check --json doctor --component all
if ($LASTEXITCODE -ne 0) { throw 'L0 doctor failed; do not start services' }
```

`public` 仅是隔离本机模拟器的 community 示例；不得用于现场或生产设备。

### 7.2 Terminal 1：Dashboard 后端

在新的 PowerShell 中重新设置本节所需变量：

```powershell
Set-Location 'H:\WORK\I\kvm-dashboard\backend'
$env:DB_MODE='sqlite'
$env:SQLITE_PATH='simulator_local.db'
$env:BACKEND_HOST='127.0.0.1'
$env:BACKEND_PORT='18002'
$env:SIMULATOR_BRIDGE_ENABLED='true'
$env:SIMULATOR_BRIDGE_TOKEN='<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>'
$env:SNMP_DEFAULT_COMMUNITY='public'
$env:SNMP_COMMUNITY='public'
$env:SNMP_TRAP_PORT='10162'

.\.venv\Scripts\python.exe -m simulator.l0_check doctor --component dashboard
if ($LASTEXITCODE -ne 0) { throw 'Dashboard preflight failed' }

.\.venv\Scripts\python.exe -m uvicorn app.main:app `
  --host $env:BACKEND_HOST `
  --port ([int]$env:BACKEND_PORT)
```

### 7.3 Terminal 2：Dashboard UI

```powershell
Set-Location 'H:\WORK\I\kvm-dashboard\frontend'
$env:VITE_BACKEND_TARGET='http://127.0.0.1:18002'
npm.cmd run dev -- --host 127.0.0.1 --port 3001 --strictPort
```

### 7.4 Terminal 3：Simulator 与托管 UI

如需真实构建后的 UI，先执行：

```powershell
Set-Location 'H:\WORK\I\kvm-dashboard\simulator-ui'
npm.cmd ci
npm.cmd run build
```

再启动 Simulator：

```powershell
Set-Location 'H:\WORK\I\kvm-dashboard\backend'
$env:BACKEND_PORT='18002'
$env:SIMULATOR_HOST='127.0.0.1'
$env:SIM_WEB_PORT='18890'
$env:SIM_TOPOLOGY='all-profiles'
$env:SIM_ADDRESS_MODE='port'
$env:SIM_DASHBOARD_URL='http://127.0.0.1:18002/api/v1'
$env:SIM_RUN_ID='local-simulator'
$env:SIMULATOR_BRIDGE_ENABLED='true'
$env:SIMULATOR_BRIDGE_TOKEN='<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>'
$env:SNMP_DEFAULT_COMMUNITY='public'
$env:SNMP_COMMUNITY='public'
$env:TRAP_TARGET_HOST='127.0.0.1'
$env:SNMP_TRAP_PORT='10162'

.\.venv\Scripts\python.exe -m simulator.l0_check doctor --component simulator
if ($LASTEXITCODE -ne 0) { throw 'Simulator preflight failed' }

.\.venv\Scripts\python.exe -m simulator
```

### 7.5 Terminal 4：运行 smoke

必须在另一个 PowerShell 中设置与运行进程相同的非敏感地址配置：

```powershell
Set-Location 'H:\WORK\I\kvm-dashboard\backend'
$env:BACKEND_PORT='18002'
$env:SIM_WEB_PORT='18890'
$env:SIM_TOPOLOGY='all-profiles'
$env:SIM_DASHBOARD_URL='http://127.0.0.1:18002/api/v1'
$env:SNMP_TRAP_PORT='10162'
$env:SNMP_DEFAULT_COMMUNITY='public'
$env:SNMP_COMMUNITY='public'

.\.venv\Scripts\python.exe -m simulator.l0_check smoke `
  --expected-topology all-profiles `
  --expected-agents 5 `
  --require-bridge `
  --require-ui
if ($LASTEXITCODE -ne 0) { throw 'L0 smoke failed' }
```

## 8. CMD 启动

CMD 使用 `set "NAME=value"`，不要把下面命令复制到 PowerShell。

### 8.1 Dashboard 后端

```bat
cd /d H:\WORK\I\kvm-dashboard\backend
set "DB_MODE=sqlite"
set "SQLITE_PATH=simulator_local.db"
set "BACKEND_HOST=127.0.0.1"
set "BACKEND_PORT=18002"
set "SIMULATOR_BRIDGE_ENABLED=true"
set "SIMULATOR_BRIDGE_TOKEN=<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>"
set "SNMP_DEFAULT_COMMUNITY=public"
set "SNMP_COMMUNITY=public"
set "SNMP_TRAP_PORT=10162"

.venv\Scripts\python.exe -m simulator.l0_check doctor --component dashboard
if errorlevel 1 exit /b 1

.venv\Scripts\python.exe -m uvicorn app.main:app --host %BACKEND_HOST% --port %BACKEND_PORT%
```

### 8.2 Dashboard UI

```bat
cd /d H:\WORK\I\kvm-dashboard\frontend
set "VITE_BACKEND_TARGET=http://127.0.0.1:18002"
npm.cmd run dev -- --host 127.0.0.1 --port 3001 --strictPort
```

### 8.3 Simulator 与托管 UI

```bat
cd /d H:\WORK\I\kvm-dashboard\simulator-ui
npm.cmd ci
npm run build

cd /d H:\WORK\I\kvm-dashboard\backend
set "BACKEND_PORT=18002"
set "SIMULATOR_HOST=127.0.0.1"
set "SIM_WEB_PORT=18890"
set "SIM_TOPOLOGY=all-profiles"
set "SIM_ADDRESS_MODE=port"
set "SIM_DASHBOARD_URL=http://127.0.0.1:18002/api/v1"
set "SIM_RUN_ID=local-simulator"
set "SIMULATOR_BRIDGE_ENABLED=true"
set "SIMULATOR_BRIDGE_TOKEN=<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>"
set "SNMP_DEFAULT_COMMUNITY=public"
set "SNMP_COMMUNITY=public"
set "TRAP_TARGET_HOST=127.0.0.1"
set "SNMP_TRAP_PORT=10162"

.venv\Scripts\python.exe -m simulator.l0_check doctor --component simulator
if errorlevel 1 exit /b 1

.venv\Scripts\python.exe -m simulator
```

### 8.4 Smoke

```bat
cd /d H:\WORK\I\kvm-dashboard\backend
set "BACKEND_PORT=18002"
set "SIM_WEB_PORT=18890"
set "SIM_TOPOLOGY=all-profiles"
set "SIM_DASHBOARD_URL=http://127.0.0.1:18002/api/v1"
set "SNMP_TRAP_PORT=10162"
set "SNMP_DEFAULT_COMMUNITY=public"
set "SNMP_COMMUNITY=public"

.venv\Scripts\python.exe -m simulator.l0_check smoke --expected-topology all-profiles --expected-agents 5 --require-bridge --require-ui
if errorlevel 1 exit /b 1
```

## 9. 两种 Simulator UI 模式

### 9.1 构建后由 Simulator 托管

这是 L0 默认验收方式：

```text
simulator-ui npm run build
Simulator :18890 -> simulator-ui/dist
```

smoke 的 `--require-ui` 会验证 `http://127.0.0.1:18890/` 返回 HTML。

### 9.2 Vite dev

Vite proxy 必须显式指向当前 Simulator：

```powershell
# Simulator 终端
$env:SIM_WEB_PORT='8888'
.\.venv\Scripts\python.exe -m simulator

# simulator-ui 终端
$env:SIMULATOR_UI_MODE='dev'
$env:SIMULATOR_UI_PORT='13100'
$env:VITE_SIMULATOR_TARGET='http://127.0.0.1:8888'
npm.cmd run dev -- --host 127.0.0.1 --port 13100 --strictPort
```

验证：

```powershell
Invoke-WebRequest 'http://127.0.0.1:13100/' -UseBasicParsing
Invoke-RestMethod 'http://127.0.0.1:13100/api/v1/status'
```

第二条必须通过 Vite proxy 返回 Simulator status。

`doctor --component all` 只在 `SIMULATOR_UI_MODE=dev` 时检查独立的
`13100/tcp`。`built` 模式由 Simulator HTTP 端口提供页面，不应因为
本机另一个进程使用 `13100` 而产生假失败。

## 10. 地址模式

默认且推荐：

```text
SIM_ADDRESS_MODE=port
```

`all-profiles` 当前绑定：

```text
127.0.0.1:11161/udp
127.0.0.1:11162/udp
127.0.0.1:11163/udp
127.0.0.1:11164/udp
127.0.0.1:11165/udp
```

重要限制：当前 built-in preset 为设备保存了显式端口，设置 `SIM_SNMP_PORT_BASE` 不会重映射这些端口。doctor 会对此给出 `warn`。端口冲突时应先停止占用进程，不能依赖该变量“换端口”。

`loopback` 模式使用 `127.0.1.x:161`，受权限、防火墙和平台约束。选择依据见：

```text
docs/simulator/decisions/ADR-001-LOCAL_ADDRESS_MODES.md
```

## 11. Docker 边界

当前 `docker-compose.yml` 只有 PostgreSQL、Dashboard backend 和 Dashboard frontend：

```powershell
docker compose config
docker compose up -d postgres backend frontend
docker compose ps
```

当前没有 Simulator service，而且 Dashboard 容器中的 `127.0.0.1` 不等于宿主机或 Simulator 容器。把 host Simulator 的 `127.0.0.1:11161..11165` 注册给容器内 Dashboard 后，Dashboard 无法通过这些地址轮询。

所以 L0 的 Docker 结论是：

- Dashboard 生产 Compose 可以独立启动；
- 完整 Simulator→Dashboard→SNMP Docker 链路当前不支持；
- 不得把 `docker compose up` 当作 Simulator L0 通过证据；
- 容器地址和端口模型必须在 L5/L6 形成正式设计后再实现。

L0 不新增临时 Docker service，也不使用 host networking 绕过这个架构问题。

## 12. 停止与清理

1. 先在 Simulator 终端按 `Ctrl+C`，等待 Uvicorn lifespan 停止所有 Agent；
2. 再停止两个 Vite；
3. 最后停止 Dashboard；
4. 确认端口已经释放：

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object LocalPort -In 18002,3001,18890,13100

Get-NetUDPEndpoint |
  Where-Object LocalPort -In 10162,11161,11162,11163,11164,11165
```

5. 再次执行 doctor，所有计划端口应为 `available`。

注意：停止 Simulator 进程是否自动删除 Dashboard 中本次 run 的数据库记录属于 L5 生命周期/持久化问题。L0 只验证进程与端口释放，不把数据库清理假定为已经实现。

## 13. `/api/v1/status` L0 契约

该接口不需要认证，只能返回运行诊断，不得返回 token/community 原值。

关键字段：

```json
{
  "status": "ok | degraded",
  "runtime": {
    "running": true,
    "topology_id": "all-profiles",
    "revision": 1,
    "device_count": 5
  },
  "agents": {
    "expected": 5,
    "running": 5,
    "device_ids": [],
    "bindings": [
      {
        "device_id": "sim-ccdc-01",
        "host": "127.0.0.1",
        "port": 11161,
        "thread_alive": true,
        "ready": true,
        "error_type": null
      }
    ]
  },
  "bridge": {
    "enabled": true,
    "session_established": true,
    "binding_count": 5,
    "last_reconcile": {
      "ok": true
    }
  },
  "trap": {
    "target_host": "127.0.0.1",
    "target_port": 10162
  },
  "configuration": {
    "bridge_token": "configured",
    "community": "default | configured"
  }
}
```

`degraded` 的 L0 条件：

- 没有运行中的 topology；
- Agent 数、线程 readiness 或 binding 与 runtime device 不一致；
- bridge 已启用，但最近一次 reconcile 失败。

bridge 被明确禁用时不自动视为失败；需要 bridge 的验收必须使用 smoke 的
`--require-bridge`。该选项会先调用
`POST /api/v1/bridge/reconcile`，不能用历史成功快照替代当前 Dashboard 重试。

Dashboard 的 `/api/v1/health` 还必须返回
`trap_receiver.state=running` 和实际监听端口；Trap receiver 绑定失败会阻止
Dashboard 启动，不能再由后台线程静默吞掉。

## 14. Gate L0

| 条件 | 当前状态 |
|---|---|
| PowerShell 与 CMD 语法分离 | 已实现并分别实跑 |
| 配置脱敏 doctor | 已实现，URL/token/community 泄露测试通过 |
| 明确 TCP/UDP 占用地址 | 已实现，Agent 与 Trap 占用故障注入通过 |
| `/status` 显示 topology、Agent、binding、bridge、Trap | 已实现并实跑 |
| bridge 初始失败有结构化日志和显式 retry | 已实现并实跑 |
| 五 Profile 本地全链 smoke | PowerShell 与 CMD 均通过 |
| 五 Agent 真实 `sysObjectID.0` GET | 已通过，可由 `l0_check snmp-get` 独立复跑 |
| build 托管 UI | 已通过 |
| Vite dev proxy | 已参数化并在 `13100 → 8888` 实跑通过 |
| Docker 全链 | 当前架构不支持，不得声称通过 |
| 停止后端口释放 | TCP/UDP 全部实跑释放 |
| 停止后 Dashboard run 数据清理 | L5 问题，不属于 L0 关闭项 |

验收范围只覆盖 Windows 本地 `port` 模式。Docker Simulator 网络身份、
Dashboard run 自动清理以及完整 MIB/SNMP 语义仍由后续层处理，不得从本层
`Accepted` 推导这些能力已经完成。
