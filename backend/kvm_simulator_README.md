# 本地 SNMP 模拟器：可视化组网与人工测试

`backend/simulator/` 是本项目的本地 G&D/KVM SNMP 测试服务器。它模拟 SNMP v2c 设备、发送 G&D Trap，并可通过本地 bridge 把模拟拓扑注册进 Dashboard。Dashboard 当前支持 5 个规范 Profile：`ccdc_legacy`、`ccdm_matrix`、`dp12_mux_atc`、`visionxs_con`、`visionxs_cpu`。模拟器用于开发和验收，不是生产设备代理。

## 当前能力

- 拓扑 API：`GET/POST/PUT/DELETE /api/v1/topologies`，内置 5 个只读 preset，由旧场景转换而来。
- 运行控制：`POST /api/v1/topologies/{id}/start|stop`。
- 状态操控：`PATCH /api/v1/runtime/devices/{id}/state` 只接受由当前
  L2 fixture 实例生成的 L3 规范路径，例如
  `scalars.switch_temperature`、
  `tables.target_module_table[1].device_status` 和
  `tables.gud_ccdmdwc_mib_fan_table[1,1].fan_speed`。旧
  `ports[...]`、`endpoints[...]`、厂家名和任意 nested path 会以 422 拒绝。
- 设备动作：`POST /api/v1/runtime/devices/{id}/actions` 的 L3 规范动作是
  `disconnect`、`power_off`、`restore`；旧 `pause` 仅在场景 facade
  归一化为 disconnect，不建立第四种运行状态。
- Trap 控制台 API：`POST /api/v1/traps`，支持单/多设备、`formal`/`legacy` layout、level/message。
- WebSocket：`WS /api/v1/ws`，向 simulator-ui 推送 snapshot、状态事件、拓扑事件和 Trap 发送事件。
- Profile/OID：当前 L2 typed Profile 与 Dashboard Profile runtime 共同覆盖
  `ccdc_legacy`、`ccdm_matrix`、`dp12_mux_atc`、`visionxs_con`、
  `visionxs_cpu`。Dashboard 会按识别出的 Profile 采集并持久化 scalar/entity
  状态；Accepted L1/L2 静态对照和 fixture 仍用于约束对象、类型与模拟值。
  本地 fixture 通过不等于完成了全部真机 UDP/ASN.1 兼容性验证，现场验收仍应
  对照对应设备 MIB 和抓包证据。
- 可视化 UI：根目录 `simulator-ui/` 是独立 React + Vite + `@xyflow/react` 项目，开发时连接模拟器 API，构建后可由模拟器 FastAPI 托管。

## 设备与 Profile

启动并选择 `all-profiles` 后，Dashboard 的设备列表/管理页应出现以下 5 个
以 `SIM /` 开头的设备：

| 模拟设备 | 规范 Profile | port 模式地址 | Dashboard 验证重点 |
|---|---|---|---|
| `SIM / Legacy CCDC Matrix` (`sim-ccdc-01`) | `ccdc_legacy` | `127.0.0.1:11161` | 矩阵、CPU/CON、轮询、Trap 和详情字段 |
| `SIM / CCDM Matrix` (`sim-ccdm-01`) | `ccdm_matrix` | `127.0.0.1:11162` | 矩阵、模块实体、风扇/状态字段和详情 |
| `SIM / VisionXS CPU` (`sim-vision-cpu-01`) | `visionxs_cpu` | `127.0.0.1:11163` | 独立 CPU 的 scalar/entity 与详细状态 |
| `SIM / VisionXS CON` (`sim-vision-con-01`) | `visionxs_con` | `127.0.0.1:11164` | 独立 CON 的 scalar/entity 与详细状态 |
| `SIM / DP12 MUX` (`sim-dp12-01`) | `dp12_mux_atc` | `127.0.0.1:11165` | MUX/ATC 通道、状态实体与详细字段 |

`CC160` 与 `CCDM` 共用 `ccdm_matrix`，不建立单独的 CC160 Profile。模拟器
transport 中的历史标识 `ccdc_legacy_unverified` 和
`dp12_mux_atc_readonly` 会分别规范化为 `ccdc_legacy` 和
`dp12_mux_atc`；Dashboard、API 和验收文档统一使用上表中的规范 Profile ID。

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

### A. 验证五 Profile 与设备清单

1. 在模拟器 UI 或 fallback 页启动 `all-profiles`。
2. Dashboard 刷新后，在“设备”或 Admin → Devices 确认看到上述 5 个 `SIM /` 设备。
3. 逐台点击设备，详情中的 Profile、scalar、entity 和字段状态应与设备类型一致。
4. `SIM / Legacy CCDC Matrix` 与 `SIM / CCDM Matrix` 属于矩阵 Profile，
   可在保留的矩阵页验证 CPU/CON 或模块状态。
5. 原 Dashboard“拓扑”tab 已替换为普通设备表格；设备列表应同时展示全部
   5 台设备，不再要求从旧拓扑图验收设备状态。

### B. 验证整台矩阵断网/恢复

1. 对 Legacy CCDC Matrix 执行 `disconnect` 或 fallback 页的“断网”。
2. 约 1–2 秒后，Dashboard 中对应矩阵设备应离线；其下 CPU/CON 也应显示为父设备离线。
3. 执行 `restore`，等待健康探测恢复设备在线。

### C. 验证 CPU/CON 状态与 Trap

1. Legacy CCDC 的 `CPU-1-001` 继续使用专用 endpoint 兼容入口；它属于
   project-domain 状态，不是厂家 Profile 通用 PATCH。
2. CCDM 的 `CPU-CCDM-001` 使用规范 runtime path：

```json
{
  "patches": [
    {
      "path": "tables.target_module_table[1].device_status",
      "value": 0
    }
  ],
  "emit_trap": true
}
```

请求地址为
`PATCH /api/v1/runtime/devices/sim-ccdm-01/state`。成功响应包含
`revision`、`changed_paths`、`committed_values` 和 `idempotent`。
任意一项类型、范围或路径非法时，整个 batch 拒绝，状态/revision/event
均不改变。

3. 专用 endpoint status 入口若用于 CCDM，会与同一 canonical table leaf
   在一个 revision/event 内同步；`video_connected` 等没有显式 Profile
   映射的字段不得解释为 SNMP OID 已改变。
4. 状态型 Trap 的 formal 布局为：

```text
notification = 1.3.6.1.4.1.32828.2.1.0.4
level        = 1.3.6.1.4.1.32828.2.1.0.2
message      = 1.3.6.1.4.1.32828.2.1.0.3
```

5. Dashboard 的矩阵、设备详情和告警流应反映当前 Profile 的最新状态；
   CCDM、DP12、VisionXS CPU/CON 与 Legacy CCDC 都必须按各自 Profile 展示，
   不能回退为统一的 Legacy CCDC 字段集合。
6. 将 status 改回 `1` 验证恢复。对 CON 重复同样动作。

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

### E. 验证 Dashboard 视图

1. 矩阵视图保持可用，用于查看矩阵 Profile 的 CPU/CON 或模块状态。
2. 切换到设备列表，确认 5 台设备均以表格行展示，并可点击打开完整详情。
3. 旧拓扑 tab 不再展示图形拓扑；当前对应入口就是设备列表。
4. Simulator UI 内的 route/edge 仍是场景控制数据，标记为
   `simulation-declared`，不是 SNMP 自动发现的真实物理连线，也不是当前
   Dashboard 设备列表的验收依据。

### F. 验证 SNMP v2c 自动发现

现场自动发现与 Simulator bridge 是两条独立的设备加入路径。在 Admin 配置扫描
CIDR、community 和 SNMP 端口后启动扫描，后端会使用 SNMP v2c GET
`sysObjectID.0` 识别上述 5 个 Profile；识别成功后直接新增或更新设备，结果为
`imported` 或 `updated`，没有预览/确认步骤。单次配置的网段最多展开 256 个
可用主机。

本机 `SIM_ADDRESS_MODE=port` 下 5 台设备共用 `127.0.0.1`、仅端口不同，因此
五设备联调优先使用 bridge。需要验证“一个地址一台设备、统一 UDP 161”的现场
发现流程时，使用可路由测试网段或满足本机绑定条件的 `loopback` 模式。

## 自动验证命令

服务启动后先执行五设备 smoke：

```powershell
cd H:\WORK\I\kvm-dashboard\backend
.\.venv\Scripts\python.exe -m simulator.l0_check smoke `
  --expected-topology all-profiles `
  --expected-agents 5 `
  --require-bridge `
  --require-ui

Invoke-RestMethod http://127.0.0.1:18890/api/v1/status
```

`/api/v1/status` 应返回 `status=ok`、`runtime.device_count=5`、
`agents.expected=5` 和 `agents.running=5`；5 个 agent binding 应分别对应
`11161` 至 `11165`。smoke 非零或计数不一致时，不应进入页面验收。

后端：

```bash
cd H:\WORK\I\kvm-dashboard\backend
.venv\Scripts\python.exe -m compileall -q simulator tests
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider

# L3 状态层专项
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider \
  tests/test_simulator_l3_runtime_state.py \
  tests/test_simulator_l3_integration.py \
  tests/test_simulator_runtime_patch.py \
  tests/test_simulator_core.py \
  tests/test_simulator_lifecycle.py \
  tests/test_simulator_ui_contract.py
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
| 某个 Profile 的详情为空或字段明显不匹配 | 检查 bridge manifest 的 Profile、SNMP agent binding、Dashboard poller 日志和对应 fixture；5 个 Profile 都应进入各自的采集与详情展示流程。 |
| Trap 不出现 | 本地非 Docker 联调确认 Dashboard 与模拟器都使用 UDP `10162`；Docker 现场设备发送宿主机 UDP `162`，Compose 映射到容器内 `10162`。 |
| loopback 模式无法绑定 `127.0.1.x:161` | 先改回 `SIM_ADDRESS_MODE=port`；确认系统权限、防火墙、容器网络和端口占用。 |
| 前端连错后端 | Dashboard 前端设置 `VITE_BACKEND_TARGET=http://127.0.0.1:18002`；simulator-ui 设置 `VITE_SIMULATOR_TARGET=http://127.0.0.1:18890`。 |
| 端口被占用 | 改 `18002`、`3001`、`18890` 或 `SIM_SNMP_PORT_BASE`，并同步更新相关 URL。 |

## 安全边界

- Bridge 默认关闭，只有本地显式 `SIMULATOR_BRIDGE_ENABLED=true` 才开放。
- Bridge 仅创建、更新或删除自身 run 拥有的 `sim_<run_id>_` 设备和端点。
- DP 的 SNMP SET 没有在模拟器或 Dashboard 中启用；DP 可写对象只作为模拟器内部状态字段修改。
- 不要提交 bridge token、真实 community、现场地址或测试数据库。
- 旧单文件 `backend/kvm_simulator.py` 与 `backend/run_simulators_large.py` 保留为 legacy 脚本，不是本次 v3 simulator-ui 工作流的入口。
