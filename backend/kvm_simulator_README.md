# 本地 SNMP 模拟器：启动与人工测试

`backend/simulator/` 是本项目的本地测试服务器。它模拟 SNMP v2c 设备、发送正式 G&D Trap，并通过本地 bridge 把场景设备注册进 Dashboard；它不是生产设备代理，也不表示当前 Dashboard 已经完整支持所有 G&D MIB Profile。

## 你应该看到什么

启动并在模拟器选择 `all-profiles` 后，Dashboard 的**设备列表/管理页**应出现 5 个以 `SIM /` 开头的设备：

| 模拟设备 | 类型 | 当前可验证范围 |
|---|---|---|
| `SIM / Legacy CCDC Matrix` | 历史 CCDC 风格中心矩阵 | **完整端到端**：SNMP 轮询、1 秒可达性、CPU/CON 状态、正式 Trap、端口和模拟路由 |
| `SIM / CCDM Matrix` | ControlCenter-Digital 中心矩阵 | 已注册、身份、端点和模拟拓扑；当前生产 poller 尚未 Profile 化，不应期待完整指标 |
| `SIM / VisionXS CPU` | 独立 CPU SNMP Agent | 已注册、身份和模拟拓扑 fixture |
| `SIM / VisionXS CON` | 独立 CON SNMP Agent | 已注册、身份和模拟拓扑 fixture |
| `SIM / DP12 MUX` | 独立 DP 小型通道切换器 | 已注册、身份和模拟拓扑 fixture；不提供 SNMP SET |

如果只加载 `ccdc-regression`，只会出现第一台设备；这是正确行为。

## 手工启动（Windows cmd）

需要三个终端，且三个命令中的 token 必须完全相同。示例端口特意使用 `18002 / 3001 / 18890`，避免占用默认开发端口。

### 终端 1：Dashboard 后端

```bat
cd H:\WORK\I\kvm-dashboard\backend
set DB_MODE=sqlite
set SQLITE_PATH=simulator_local.db
set SIMULATOR_BRIDGE_ENABLED=true
set SIMULATOR_BRIDGE_TOKEN=local_dev_simulator_token
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18002
```

`simulator_local.db` 是独立本地测试数据库；删除它会清除所有模拟设备和本地测试数据。

### 终端 2：Dashboard 前端

```bat
cd H:\WORK\I\kvm-dashboard\frontend
set VITE_BACKEND_TARGET=http://127.0.0.1:18002
npm run dev -- --host 127.0.0.1 --port 3001
```

浏览器打开 `http://127.0.0.1:3001`，登录：`admin / admin123`。

### 终端 3：模拟器

```bat
cd H:\WORK\I\kvm-dashboard\backend
set SIM_SCENARIO=all-profiles
set SIM_WEB_PORT=18890
set SIMULATOR_BRIDGE_TOKEN=local_dev_simulator_token
set SIM_DASHBOARD_URL=http://127.0.0.1:18002/api/v1
set SIM_RUN_ID=local-simulator
.venv\Scripts\python.exe -m simulator
```

浏览器打开 `http://127.0.0.1:18890`。加载场景后，刷新 Dashboard 一次；随后场景切换会通过 WebSocket 触发设备列表刷新。

## 推荐人工测试顺序

### A. 验证设备清单与场景

1. 在模拟器选择 `all-profiles` 并点击“加载场景”。
2. Dashboard 刷新后，在“设备”或 Admin → Devices 确认看到上述 5 个 `SIM /` 设备。
3. 点击 `SIM / Legacy CCDC Matrix`，在矩阵/拓扑中应见到 2 个 CPU 与 2 个 CON。
4. 其余 4 台代表不同厂商 Profile 的 fixture。它们应作为独立设备显示，而不是被伪装为 Legacy CCDC 端点。

### B. 验证整台矩阵断网/恢复

1. 在模拟器的 Legacy CCDC Matrix 区域点击“暂停 SNMP（模拟断网）”。
2. 约 1–2 秒后，Dashboard 中对应矩阵设备应离线；其下 CPU/CON 也应显示为父设备离线。
3. 点击“恢复 SNMP”，等待健康探测恢复设备在线。

### C. 验证 CPU/CON 状态与 Trap

1. 对 `CPU-1-001` 点击“离线 + Trap”。
2. 模拟器会先改变 SNMP 状态，再发送正式 Trap：

```text
notification = 1.3.6.1.4.1.32828.2.1.0.4
level        = 1.3.6.1.4.1.32828.2.1.0.2
message      = 1.3.6.1.4.1.32828.2.1.0.3
```

3. Dashboard 的端点矩阵、拓扑与告警流应反映该 CPU 离线。
4. 点击“在线 + Trap”验证恢复。对 CON 重复同样动作。

### D. 验证模拟路由

1. 在模拟器对 `CPU-1-001 → CON-1-001` 点击“断开”。
2. 打开 Dashboard 的拓扑视图；模拟路由状态应更新。
3. 该区域会明确显示“模拟拓扑”。这些 CPU→CON 路由来自场景定义，标记为 `simulation-declared`，**不是** SNMP 自动发现的真实物理连线。
4. 点击“连接”或“重置”验证恢复；重置会把整个场景恢复为初始状态并同步 Dashboard。

## 常见问题

| 现象 | 检查方式 |
|---|---|
| Dashboard 没有模拟设备 | 确认后端与模拟器都在运行；`SIMULATOR_BRIDGE_ENABLED=true`；两端 token 一致；模拟器页面重新加载场景；Dashboard 刷新一次。 |
| 只看到一台模拟矩阵 | 当前加载的是 `ccdc-regression`，在模拟器加载 `all-profiles`。 |
| 设备显示但没有完整指标 | 预期现象：当前只有 `ccdc-regression` 走完整 Legacy poller；CCDM/VisionXS/DP 是 Profile fixture，等待生产 Profile-aware poller 实现。 |
| Trap 不出现 | 确认后端的 `SNMP_TRAP_PORT` 与模拟器环境中的 `SNMP_TRAP_PORT` 一致；默认本地为 UDP `10162`。 |
| 前端连错后端 | 前端启动时必须设置 `VITE_BACKEND_TARGET=http://127.0.0.1:18002`；修改后要重启 Vite。 |
| 端口被占用 | 改 `18002`、`3001` 或 `18890`，同时把 `SIM_DASHBOARD_URL` 和 `VITE_BACKEND_TARGET` 指向新的后端端口。 |

## 安全边界

- Bridge 默认关闭，只有本地显式 `SIMULATOR_BRIDGE_ENABLED=true` 才开放。
- Bridge 仅创建、更新或删除自身 run 拥有的 `sim_<run_id>_` 设备和端点。
- DP 的 SNMP SET 没有在模拟器或 Dashboard 中启用。
- 不要提交 bridge token、真实 community、现场地址或测试数据库。
