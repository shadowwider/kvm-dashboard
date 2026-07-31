# 本地 SNMP 模拟器：可视化组网与人工测试

`backend/simulator/` 是本项目的本地 G&D/KVM SNMP 测试服务器。它模拟 SNMP v2c 设备、发送 G&D Trap，并可通过本地 bridge 把模拟拓扑注册进 Dashboard。它不是生产设备代理，也不表示当前 Dashboard 已经完整支持所有 G&D MIB Profile。

## 当前能力

- 拓扑 API：`GET/POST/PUT/DELETE /api/v1/topologies`，内置 5 个只读 preset，由旧场景转换而来。
- 运行控制：`POST /api/v1/topologies/{id}/start|stop`。
- 状态操控：`PATCH /api/v1/runtime/devices/{id}/state`，支持英文路径，例如 `scalars.temperature1`、`ports[1].status`、`endpoints[CPU-1-001].status`、`tables.linkChannel[1].sfpRxPower`。
- 设备动作：`POST /api/v1/runtime/devices/{id}/actions`，支持 `disconnect`、`pause`、`power_off`、`restore`。
- Trap 控制台 API：`POST /api/v1/traps`，支持单/多设备、`formal`/`legacy` layout、level/message。
- WebSocket：`WS /api/v1/ws`，向 simulator-ui 推送 snapshot、状态事件、拓扑事件和 Trap 发送事件。
- Profile/OID：当前声明式 Profile 覆盖 CCDC、CCDM、VisionXS CPU、VisionXS
  CON、DP12 MUX，但不能统称为完整厂家 OID map。L1 静态对照显示 CCDM
  当前仍是 15/20 张表、134/142 个可 GET 叶定义；Dashboard 现阶段仍只主动
  poll CCDC legacy 形状。
- 可视化 UI：根目录 `simulator-ui/` 是独立 React + Vite + `@xyflow/react` 项目，开发时连接模拟器 API，构建后可由模拟器 FastAPI 托管。

## 设备与 Profile

启动并选择 `all-profiles` 后，Dashboard 的设备列表/管理页应出现 5 个以 `SIM /` 开头的设备：

| 模拟设备 | 类型 | 当前可验证范围 |
|---|---|---|
| `SIM / Legacy CCDC Matrix` | 历史 CCDC 风格中心矩阵 | Dashboard 端到端：SNMP 轮询、1 秒可达性、CPU/CON 状态、正式 Trap、端口和模拟路由 |
| `SIM / CCDM Matrix` | ControlCenter-Digital 中心矩阵 | 当前 Profile 尚缺 5 表、11 个叶定义并多出 3 个无字典依据的公共 OID；只能作为 L2 整改 fixture |
| `SIM / VisionXS CPU` | 独立 CPU SNMP Agent | 对象定义层与本地设备字典快照一致；真实 UDP/fixture 行与现场设备兼容仍待 L4 验证 |
| `SIM / VisionXS CON` | 独立 CON SNMP Agent | 对象定义层与本地设备字典快照一致；真实 UDP/fixture 行与现场设备兼容仍待 L4 验证 |
| `SIM / DP12 MUX` | 独立 DP 小型通道切换器 | 对象定义层与本地设备字典快照一致；6 个 read-write 是字典事实，但 SNMP SET 仍拒绝且真实协议待 L4 验证 |

## 地址模式

默认兼容模式：

```bat
set SIM_ADDRESS_MODE=port
```

- 每台设备使用 `127.0.0.1` 和不同 UDP 端口，默认 `11161` 起。
- 适合普通开发环境、Docker/非管理员环境。

仿真局域网模式：

```bat
set SIM_ADDRESS_MODE=loopback
```

- 每台设备使用 `127.0.1.x:161`。
- Trap 发送 socket 会尽量绑定到对应设备 IP，使 Dashboard 看到的 Trap 源 IP 更接近真机。
- 源 IP 绑定是 best-effort；如果操作系统/容器不允许绑定，会回退为普通发送。

## 手工启动（Windows cmd）

需要三个终端，且 Dashboard 后端和模拟器的 token 必须完全相同。示例端口使用 `18002 / 3001 / 18890`，避免占用默认开发端口。
`<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>` 必须替换为本轮随机值；未替换的
占位符会被 L0 doctor 拒绝，实际值不得写入仓库。

### 终端 1：Dashboard 后端

```bat
cd H:\WORK\I\kvm-dashboard\backend
set DB_MODE=sqlite
set SQLITE_PATH=simulator_local.db
set SIMULATOR_BRIDGE_ENABLED=true
set "SIMULATOR_BRIDGE_TOKEN=<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>"
set SNMP_TRAP_PORT=10162
set SNMP_DEFAULT_COMMUNITY=public
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18002
```

`simulator_local.db` 是独立本地测试数据库；删除它会清除所有模拟设备和本地测试数据。

### 终端 2：Dashboard 前端

```bat
cd H:\WORK\I\kvm-dashboard\frontend
set VITE_BACKEND_TARGET=http://127.0.0.1:18002
npm.cmd run dev -- --host 127.0.0.1 --port 3001 --strictPort
```

浏览器打开 `http://127.0.0.1:3001`，登录：`admin / admin123`。

### 终端 3：模拟器后端

```bat
cd H:\WORK\I\kvm-dashboard\backend
set SIM_TOPOLOGY=all-profiles
set SIM_WEB_PORT=18890
set SIM_ADDRESS_MODE=port
set "SIMULATOR_BRIDGE_TOKEN=<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>"
set SIM_DASHBOARD_URL=http://127.0.0.1:18002/api/v1
set SIM_RUN_ID=local-simulator
set SNMP_TRAP_PORT=10162
set SNMP_COMMUNITY=public
.venv\Scripts\python.exe -m simulator
```

浏览器打开 `http://127.0.0.1:18890`。如果 `simulator-ui/dist` 已构建，会显示可视化组网页；否则显示轻量 fallback 控制页。

### 可选：simulator-ui 开发模式

```bat
cd H:\WORK\I\kvm-dashboard\simulator-ui
npm.cmd ci
set "SIMULATOR_UI_PORT=13100"
set "VITE_SIMULATOR_TARGET=http://127.0.0.1:18890"
npm.cmd run dev -- --host 127.0.0.1 --port 13100 --strictPort
```

Vite dev server 会按 `VITE_SIMULATOR_TARGET` 把 `/api` 和
`/api/v1/ws` 代理到 Simulator；上例明确指向
`http://127.0.0.1:18890`。未设置该变量时才回退到
`http://127.0.0.1:8888`。

构建后托管：

```bat
cd H:\WORK\I\kvm-dashboard\simulator-ui
npm run build
cd H:\WORK\I\kvm-dashboard\backend
.venv\Scripts\python.exe -m simulator
```

## 推荐人工测试顺序

### A. 验证拓扑与设备清单

1. 在模拟器 UI 或 fallback 页启动 `all-profiles`。
2. Dashboard 刷新后，在“设备”或 Admin → Devices 确认看到上述 5 个 `SIM /` 设备。
3. 点击 `SIM / Legacy CCDC Matrix`，在矩阵/拓扑中应见到 2 个 CPU 与 2 个 CON。
4. 其余设备代表不同厂商 Profile fixture，不应被伪装为 Legacy CCDC 端点。

### B. 验证整台矩阵断网/恢复

1. 对 Legacy CCDC Matrix 执行 `disconnect` 或 fallback 页的“断网”。
2. 约 1–2 秒后，Dashboard 中对应矩阵设备应离线；其下 CPU/CON 也应显示为父设备离线。
3. 执行 `restore`，等待健康探测恢复设备在线。

### C. 验证 CPU/CON 状态与 Trap

1. 对 `CPU-1-001` 执行旧 endpoint patch 或 runtime state patch，将 status 改为 `0`。
2. 模拟器会先改变 SNMP 状态，再发送正式 Trap：

```text
notification = 1.3.6.1.4.1.32828.2.1.0.4
level        = 1.3.6.1.4.1.32828.2.1.0.2
message      = 1.3.6.1.4.1.32828.2.1.0.3
```

3. Dashboard 的端点矩阵、拓扑与告警流应反映该 CPU 离线。
4. 将 status 改回 `1` 验证恢复。对 CON 重复同样动作。

### D. 验证 Trap 控制台

向单设备发送正式 Trap：

```bash
curl -X POST http://127.0.0.1:18890/api/v1/traps \
  -H "Content-Type: application/json" \
  -d '{"device_id":"sim-ccdc-01","level":3,"message":"entered critical state: Offline","layout":"formal"}'
```

向多设备发送 legacy Trap：

```bash
curl -X POST http://127.0.0.1:18890/api/v1/traps \
  -H "Content-Type: application/json" \
  -d '{"device_ids":["sim-ccdc-01","sim-ccdm-01"],"level":5,"message":"Display connection state changed","layout":"legacy"}'
```

### E. 验证模拟路由

1. 对 `CPU-1-001 → CON-1-001` 执行 route patch，将 state 改为 `disconnected`。
2. 打开 Dashboard 的拓扑视图；模拟路由状态应更新。
3. 该区域会明确显示“模拟拓扑”。这些 CPU→CON 路由来自场景/拓扑定义，标记为 `simulation-declared`，不是 SNMP 自动发现的真实物理连线。

## 自动验证命令

后端：

```bash
cd H:\WORK\I\kvm-dashboard
python -m py_compile backend/simulator/*.py backend/app/api/simulator.py
cd backend
.venv\Scripts\python.exe -m pytest tests/test_simulator_l0.py tests/test_trap_receiver_startup.py tests/test_health_probe.py tests/test_simulator_core.py tests/test_simulator_lifecycle.py tests/test_simulator_profiles.py tests/test_simulator_topologies.py tests/test_simulator_traps.py tests/test_simulator_ui_contract.py
```

simulator-ui：

```bash
cd H:\WORK\I\kvm-dashboard\simulator-ui
npm.cmd ci
npm.cmd run build
npm.cmd run lint
```

## 常见问题

| 现象 | 检查方式 |
|---|---|
| Dashboard 没有模拟设备 | 确认后端与模拟器都在运行；`SIMULATOR_BRIDGE_ENABLED=true`；两端 token 一致；模拟器启动拓扑；Dashboard 刷新一次。 |
| 只看到一台模拟矩阵 | 当前加载的是 `ccdc-regression`，启动或加载 `all-profiles`。 |
| 非 CCDC 设备在 Dashboard 没有完整指标 | 预期现象：目标是按 L1/L2 Golden 和 Profile 逐步补齐；当前 CCDM 尚未完整，生产 Dashboard poller Profile 化也属于后续层。 |
| Trap 不出现 | 确认 Dashboard 后端 `SNMP_TRAP_PORT` 与模拟器环境一致；默认本地为 UDP `10162`。 |
| loopback 模式无法绑定 `127.0.1.x:161` | 先改回 `SIM_ADDRESS_MODE=port`；确认系统权限、防火墙、容器网络和端口占用。 |
| 前端连错后端 | Dashboard 前端设置 `VITE_BACKEND_TARGET=http://127.0.0.1:18002`；simulator-ui 设置 `VITE_SIMULATOR_TARGET=http://127.0.0.1:18890`。 |
| 端口被占用 | 改 `18002`、`3001`、`18890` 或 `SIM_SNMP_PORT_BASE`，并同步更新相关 URL。 |

## 安全边界

- Bridge 默认关闭，只有本地显式 `SIMULATOR_BRIDGE_ENABLED=true` 才开放。
- Bridge 仅创建、更新或删除自身 run 拥有的 `sim_<run_id>_` 设备和端点。
- DP 的 SNMP SET 没有在模拟器或 Dashboard 中启用；DP 可写对象只作为模拟器内部状态字段修改。
- 不要提交 bridge token、真实 community、现场地址或测试数据库。
- 旧单文件 `backend/kvm_simulator.py` 与 `backend/run_simulators_large.py` 保留为 legacy 脚本，不是本次 v3 simulator-ui 工作流的入口。
