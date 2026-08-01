# KVM Dashboard 与 KVM SNMP Simulator 启动/连接说明

> L0 更新（2026-07-31）：本文件保留架构说明；可直接执行的 PowerShell、
> CMD、doctor、smoke、端口和清理契约，以
> `docs/simulator/layers/L00_BASELINE_AND_ENVIRONMENT.md` 为准。
> 本文件下方现有 `set NAME=value` 代码块全部是 **Windows CMD**，
> 不能复制到 PowerShell。PowerShell 必须使用 `$env:NAME='value'`。
>
> L3 更新（2026-07-31）：运行时状态已改为 Profile/fixture 驱动的规范
> path、强类型校验和原子 batch。当前正式验收入口是 REST API 与 L3
> 测试，不是尚未进入 L8/L9 的页面编辑器。旧 `ports[...]`、
> `endpoints[...]` 和任意 nested path 不能作为通用 runtime PATCH。
> 规范路径、事务和状态机以
> `docs/simulator/layers/L03_RUNTIME_STATE_CONTRACT.md`、
> `docs/simulator/layers/L03_PATCH_PATH_AND_TRANSACTION_CONTRACT.md` 为准。

## 0. 启动前必须执行 L0 doctor

从 `backend` 目录执行。doctor 只打印脱敏后的最终配置，并检查计划端口：

```powershell
# PowerShell 示例
$env:SIMULATOR_UI_MODE='built'
.\.venv\Scripts\python.exe -m simulator.l0_check --json doctor --component all
```

```bat
rem CMD 示例
set "SIMULATOR_UI_MODE=built"
.venv\Scripts\python.exe -m simulator.l0_check --json doctor --component all
```

启动完成后执行：

```powershell
.\.venv\Scripts\python.exe -m simulator.l0_check smoke `
  --expected-topology all-profiles `
  --expected-agents 5 `
  --require-bridge `
  --require-ui
```

如果 doctor 或 smoke 返回非零，不得把“页面能打开”记录为启动成功。

## 1. 一共要起几个服务？

标准人工联调推荐起 **3 个服务**：

| 服务 | 必须 | 作用 | 推荐地址 |
|---|---:|---|---|
| KVM Dashboard 后端 | 是 | Dashboard API、数据库、SNMP poller、Trap receiver、Simulator bridge 接收端 | `http://127.0.0.1:18002` |
| KVM Dashboard 前端 | 是 | 你平时看的 KVM dashboard 页面 | `http://127.0.0.1:3001` |
| Simulator 后端 | 是 | SNMP Agent、拓扑/状态/Trap API、bridge 主动注册模拟设备 | `http://127.0.0.1:18890` |
| Simulator 前端 `simulator-ui` | 可选 | 可视化组网控制台；可独立 dev，也可 build 后由 Simulator 后端托管 | 独立 dev 或 `http://127.0.0.1:18890` |

也就是说不是一定要 4 个进程：

- 如果你执行了 `simulator-ui npm run build`，Simulator 前端会被 Simulator 后端托管，访问 `http://127.0.0.1:18890` 即可。
- 如果你要开发/热更新 Simulator UI，则再单独起 `simulator-ui npm run dev`，这时就是 4 个服务。

## 2. 它们之间怎么连接？

连接链路如下：

```text
simulator-ui 浏览器页面
        ↓ REST / WS
Simulator 后端 :18890
        ├─ 启动多个 SNMP Agent: 127.0.0.1:11161, 11162, ...
        ├─ 向 Dashboard 后端发送 bridge manifest
        └─ 向 Dashboard Trap receiver 发 Trap

KVM Dashboard 前端 :3001
        ↓ /api proxy
KVM Dashboard 后端 :18002
        ├─ 接收 Simulator bridge manifest
        ├─ 在数据库创建/更新 SIM 设备与端点
        ├─ SNMP poller 轮询模拟设备 host/port
        └─ Trap receiver 接收模拟 Trap
```

## 3. Dashboard 监听哪些模拟节点？需要手工配置吗？

通常 **不需要你在 Dashboard 里手工配置每个模拟节点**。

流程是：

1. 你在 Simulator 里启动一个 topology，例如 `all-profiles`。
2. Simulator 后端把 topology 里的设备清单通过 bridge 发给 Dashboard 后端。
3. Dashboard 后端根据 manifest 自动创建/更新 `SIM / ...` 设备。
4. 每个模拟设备的 `host` / `snmp_port` 来自 Simulator manifest。
5. Dashboard 的 poller 按数据库里的设备 host/port 去轮询 SNMP。

关键是两个环境变量要对上：

- Dashboard 后端：`SIMULATOR_BRIDGE_ENABLED=true`
- Dashboard 后端和 Simulator 后端：`SIMULATOR_BRIDGE_TOKEN` 必须一致

### 五 Profile 与 `all-profiles` 设备

系统与模拟器当前共同支持以下 5 个规范 Profile。`all-profiles` 在 port 模式下
一次启动 5 个 SNMP Agent：

| 模拟设备 | 规范 Profile | 地址 |
|---|---|---|
| `sim-ccdc-01` / `SIM / Legacy CCDC Matrix` | `ccdc_legacy` | `127.0.0.1:11161` |
| `sim-ccdm-01` / `SIM / CCDM Matrix` | `ccdm_matrix` | `127.0.0.1:11162` |
| `sim-vision-cpu-01` / `SIM / VisionXS CPU` | `visionxs_cpu` | `127.0.0.1:11163` |
| `sim-vision-con-01` / `SIM / VisionXS CON` | `visionxs_con` | `127.0.0.1:11164` |
| `sim-dp12-01` / `SIM / DP12 MUX` | `dp12_mux_atc` | `127.0.0.1:11165` |

`CC160` 与 `CCDM` 共用 `ccdm_matrix`，不建立第二套协议。模拟器内部兼容的
`ccdc_legacy_unverified`、`dp12_mux_atc_readonly` transport 标识会分别
规范化为 `ccdc_legacy`、`dp12_mux_atc`；Dashboard 和验收记录使用规范 ID。

## 4. 地址模式怎么选？

默认推荐本地开发用 port 模式：

```bat
set SIM_ADDRESS_MODE=port
```

效果：

```text
sim-ccdc-01  -> 127.0.0.1:11161
sim-ccdm-01  -> 127.0.0.1:11162
sim-vision-cpu-01 -> 127.0.0.1:11163
sim-vision-con-01 -> 127.0.0.1:11164
sim-dp12-01       -> 127.0.0.1:11165
```

优点是 Windows/普通权限/Docker 环境兼容性最好。

如果你想更接近真实多设备 IP，可以用 loopback 模式：

```bat
set SIM_ADDRESS_MODE=loopback
```

效果大致是：

```text
sim-ccdc-01  -> 127.0.1.1:161
sim-ccdm-01  -> 127.0.1.2:161
...
```

但这个模式对系统权限、端口占用、防火墙更敏感。

## 5. 架构示例：普通本地联调（Windows CMD）

下面保留连接架构示例。实际执行必须使用
`docs/simulator/layers/L00_BASELINE_AND_ENVIRONMENT.md` 的完整命令和 Gate。
`<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>` 必须替换为本轮随机值，并在两个后端终端
使用同一个值；不得把实际值写入仓库。

### 终端 1：启动 Dashboard 后端

```bat
cd H:\WORK\I\kvm-dashboard\backend
set DB_MODE=sqlite
set SQLITE_PATH=simulator_local.db
set SIMULATOR_BRIDGE_ENABLED=true
set "SIMULATOR_BRIDGE_TOKEN=<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>"
set SNMP_TRAP_PORT=10162
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18002
```

Dashboard 后端地址：

```text
http://127.0.0.1:18002
```

### 终端 2：启动 Dashboard 前端

```bat
cd H:\WORK\I\kvm-dashboard\frontend
set VITE_BACKEND_TARGET=http://127.0.0.1:18002
npm.cmd run dev -- --host 127.0.0.1 --port 3001 --strictPort
```

Dashboard 页面地址：

```text
http://127.0.0.1:3001
```

登录账号通常是：

```text
admin / admin123
```

### 终端 3：构建并启动 Simulator 后端 + Simulator UI

先构建 Simulator UI：

```bat
cd H:\WORK\I\kvm-dashboard\simulator-ui
npm.cmd ci
npm.cmd run build
```

再启动 Simulator：

```bat
cd H:\WORK\I\kvm-dashboard\backend
set SIM_WEB_PORT=18890
set SIM_TOPOLOGY=all-profiles
set SIM_ADDRESS_MODE=port
set "SIMULATOR_BRIDGE_TOKEN=<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>"
set SIM_DASHBOARD_URL=http://127.0.0.1:18002/api/v1
set SNMP_TRAP_PORT=10162
.venv\Scripts\python.exe -m simulator
```

Simulator 控制台地址：

```text
http://127.0.0.1:18890
```

### 启动后核对五设备

从 `backend` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m simulator.l0_check smoke `
  --expected-topology all-profiles `
  --expected-agents 5 `
  --require-bridge `
  --require-ui

Invoke-RestMethod http://127.0.0.1:18890/api/v1/status
```

smoke 必须成功；`/api/v1/status` 应显示 `status=ok`、
`runtime.device_count=5`、`agents.expected=5`、`agents.running=5`，agent
binding 对应 `11161` 至 `11165`。计数不一致时先修复 agent、topology 或
bridge，不要只凭页面能打开判断启动成功。

## 6. 可选：Simulator UI 独立 dev 模式

如果你不想 build，而是要独立跑 Simulator UI：

```bat
cd H:\WORK\I\kvm-dashboard\simulator-ui
npm.cmd ci
set "SIMULATOR_UI_PORT=13100"
set "VITE_SIMULATOR_TARGET=http://127.0.0.1:18890"
npm.cmd run dev -- --host 127.0.0.1 --port 13100 --strictPort
```

`simulator-ui/vite.config.js` 会读取上面的
`VITE_SIMULATOR_TARGET`，因此本例实际代理到：

```text
http://127.0.0.1:18890
```

未设置该变量时才回退到 `http://127.0.0.1:8888`；不需要临时修改
`vite.config.js`。非开发场景仍推荐 build 后由 Simulator 后端托管。

## 7. 人工测试顺序

1. 打开 Simulator 控制台：`http://127.0.0.1:18890`
2. 确认 topology 是 `all-profiles`，或者手动启动/保存一个 topology。
3. 打开 Dashboard：`http://127.0.0.1:3001`
4. 到设备/管理页看是否出现 `SIM / ...` 设备。
5. 在当前 L3 阶段，先通过 REST API/自动化测试做：
   - disconnect / restore
   - power off / restore
   - 用当前 device 的 L3 path registry 修改 scalar/table 实例值
   - 发送 Trap
   页面编辑和拉线分别属于 L8–L11，不能作为 L3 完成依据。
6. 在 Dashboard 里看：
   - 设备列表是否同时出现上述 5 台设备
   - 逐台点击后，Profile、scalar、entity 和详细字段是否与设备类型一致
   - Legacy CCDC 与 CCDM 的矩阵/模块状态是否可在保留的矩阵页查看
   - 设备在线/离线、端点、告警和 Trap 是否随模拟操作变化
   - 原拓扑 tab 是否已显示普通设备表格，而不是旧图形拓扑

### 自动发现验证

SNMP v2c 自动发现与 Simulator bridge 是两条独立路径。Admin 中保存扫描 CIDR、
community 和 SNMP 端口后启动扫描，Dashboard 会 GET `sysObjectID.0` 识别
Profile，并直接新增或更新设备；扫描结果使用 `imported` / `updated`，没有预览
或二次确认步骤。每个配置网段最多展开 256 个可用主机。

`SIM_ADDRESS_MODE=port` 的 5 个模拟 Agent 共用 `127.0.0.1`、仅端口不同，
因此本机五设备联调应优先使用 bridge。验证现场式自动发现时，应使用统一 UDP
161 且每台设备地址不同的可路由测试网段，或满足系统绑定条件的 loopback 模式。

## 8. 常见问题

### Dashboard 后端 8000 起不来

本机可能已有服务占用或权限拒绝。用上面推荐的 `18002`。

### Dashboard 里没有 SIM 设备

检查：

```text
Dashboard 后端 SIMULATOR_BRIDGE_ENABLED=true
Dashboard 后端 SIMULATOR_BRIDGE_TOKEN 和 Simulator 一致
Simulator 的 SIM_DASHBOARD_URL 指向 Dashboard 后端 /api/v1
Simulator topology 已启动
```

### Trap 不出现

本地非 Docker 联调时检查两边端口一致：

```text
Dashboard 后端 SNMP_TRAP_PORT=10162
Simulator 后端 SNMP_TRAP_PORT=10162
```

现场设备统一向宿主机 UDP `162` 发送 Trap。Docker Compose 的映射是
`162:10162/udp`，即宿主机 `162` 转发到 Dashboard 后端容器监听的 `10162`；
不要要求现场设备直接发送容器内端口 `10162`。

### Simulator 控制台发送 Trap 时出现 `POST /api/v1/traps 404`

`/api/v1/traps` 是 **Simulator 后端** (`18890`) 的控制接口，不是
Dashboard 后端 (`18002`) 的接口。该报错表示 Simulator UI 的 `/api` 代理被
错误地指向了 Dashboard，或把 Simulator 控制台的页面配置到了 Dashboard 前端。

在浏览器中使用以下两个独立入口：

```text
Simulator 控制台（发送 Trap、修改模拟状态）：http://127.0.0.1:18890
Dashboard（观察设备、矩阵、设备列表和告警）：http://127.0.0.1:3001
```

若使用 Simulator UI 的独立 dev 模式，必须在启动它的同一个 PowerShell 中设置：

```powershell
$env:VITE_SIMULATOR_TARGET='http://127.0.0.1:18890'
npm run dev -- --host 127.0.0.1 --port 13100 --strictPort
```

日志中的 `127.0.0.1:9157` 是浏览器的临时**客户端源端口**，不是应访问的
服务地址；不要据此把 Vite 或后端改到 9157。

### Bridge 心跳 `timed out`

Dashboard 忙于 Profile 采集、数据库写入或其他长任务时，Simulator 的 bridge
心跳可能超时。当前 Dashboard 会按 5 个 Profile 分别执行指标采集和状态持久化。
先检查 Dashboard 健康状态、poller 日志、数据库延迟和 bridge token；修复后重启
Dashboard 后端。若模拟设备已被过期租约回收，再重启 Simulator 重新建立 bridge
session。

### SNMP 轮询不通

默认 port 模式下检查模拟设备端口：

```text
127.0.0.1:11161
127.0.0.1:11162
...
```

这些 host/port 会通过 bridge manifest 自动写进 Dashboard 数据库。

## 9. 最小配置总结

Dashboard 后端必须有：

```bat
set SIMULATOR_BRIDGE_ENABLED=true
set "SIMULATOR_BRIDGE_TOKEN=<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>"
set SNMP_TRAP_PORT=10162
```

Simulator 后端必须有：

```bat
set "SIMULATOR_BRIDGE_TOKEN=<REPLACE_WITH_ONE_RANDOM_LOCAL_TOKEN>"
set SIM_DASHBOARD_URL=http://127.0.0.1:18002/api/v1
set SNMP_TRAP_PORT=10162
set SIM_ADDRESS_MODE=port
set SIM_TOPOLOGY=all-profiles
```

其中：

- `SIM_TOPOLOGY=all-profiles`：启动时加载 5 个内置 Profile fixture（Legacy CCDC、
  CCDM、VisionXS CPU/CON、DP12），便于一次做跨 Profile 验证。
- `SIM_ADDRESS_MODE=port`：所有模拟设备共享 `127.0.0.1`，但使用 `11161` 起的
  不同 SNMP UDP 端口；适合本机开发。`loopback` 才会使用 `127.0.1.x:161`。
- `SIMULATOR_BRIDGE_TOKEN`：Simulator 与 Dashboard 后端之间同步设备清单、心跳和
  清理会话的共享密钥。两端必须完全一致；用本地随机值替换占位符，且不要放进前端、
  日志或 Git。

Dashboard 前端必须指向 Dashboard 后端：

```bat
set VITE_BACKEND_TARGET=http://127.0.0.1:18002
```

Docker 部署的 Trap 端口语义：

```text
现场设备 -> 宿主机 UDP 162 -> Compose 162:10162/udp -> 后端容器 UDP 10162
```
