# KVM 本地 SNMP 测试服务器

新的本地测试服务器位于 `backend/simulator/`，用于让 Dashboard 后端与前端在没有现场设备时验证 SNMP 轮询、快速离线检测、正式 Trap、模块状态、端口状态和**明确标记为模拟数据**的 CPU→CON 路由展示。

它不是生产设备代理，也不代表 Dashboard 已自动支持所有厂商 Profile。

## 运行方式

### 1. 启动 Dashboard 后端

在 `backend/.env` 添加本地专用配置（不要提交真实 token）：

```ini
SIMULATOR_BRIDGE_ENABLED=true
SIMULATOR_BRIDGE_TOKEN=local_dev_simulator_token
```

然后启动后端：

```bash
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. 启动 Dashboard 前端

```bash
cd frontend
npm run dev
```

### 3. 启动模拟器

```bash
cd backend
set SIMULATOR_BRIDGE_TOKEN=local_dev_simulator_token
set SIM_DASHBOARD_URL=http://127.0.0.1:8000/api/v1
set SIM_RUN_ID=local-simulator
.venv\Scripts\python.exe -m simulator
```

打开 `http://127.0.0.1:8888`，选择场景并执行状态/路由操作。模拟器会先更新其 SNMP 可读状态，再发送正式 Trap，然后调用本地桥接注册并同步 Dashboard。

## 场景

| 场景 | 用途 | Dashboard 当前轮询能力 |
|---|---|---|
| `ccdc-regression` | 现有 CCDC 风格 Dashboard 的端到端回归测试 | 完整轮询、状态列探测和 Trap 均可验证 |
| `ccdm-matrix-basic` | MIB 调研支持的 CCDM 身份、端点、端口和模拟路由 fixture | 仅注册、拓扑/身份 fixture；当前生产 poller 不声明支持 |
| `visionxs-pair` | VisionXS CPU/CON 独立设备 fixture | 仅注册、拓扑/身份 fixture |
| `dp12-readonly` | DP1.2-MUX-ATC 只读 fixture | 仅注册、拓扑/身份 fixture；不实现 SNMP SET |
| `all-profiles` | 同时展示所有 fixture | 仅 `ccdc-regression` 走当前完整轮询 |

`ccdc-regression` 明确是历史 Dashboard 兼容场景，不应被当作厂商验证的 CCDC MIB 定义。其余 Profile 的 MIB/证据边界见 `docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md`。

## 可验证行为

- **暂停 SNMP**：模拟设备管理网/电源不可达；Dashboard 一秒级健康探测应显示设备离线。
- **CPU/CON 离线或在线**：先改变 SNMP 表状态，再发 `.32828.2.1.0.4` 通知；Dashboard 应更新端点和告警流。
- **模拟路由**：CPU→CON 路由仅为 `simulation-declared` 测试数据，Topology 视图会标记为“模拟拓扑”，不代表 SNMP 发现的真实物理连接。
- **重置**：恢复场景初始状态。

Trap 使用正式 G&D 通用布局：

```text
notification = 1.3.6.1.4.1.32828.2.1.0.4
level        = 1.3.6.1.4.1.32828.2.1.0.2
message      = 1.3.6.1.4.1.32828.2.1.0.3
```

## 安全边界

- Dashboard 桥接默认关闭；仅本地显式 `SIMULATOR_BRIDGE_ENABLED=true` 后才开放。
- 桥接仅创建、更新和删除以 `sim_<run_id>_` 开头且由对应 run 拥有的设备/端点。
- DP 的 SNMP SET 在模拟器和 Dashboard 中均未启用。
- 不要将模拟器桥接 Token、真实 community 或现场地址提交到仓库。
