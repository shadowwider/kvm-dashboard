# L00 当前复现与验证记录

状态：`Accepted for Windows local port mode`
验证日期：2026-07-31
工作区：`H:\WORK\I\kvm-dashboard`
分支：`feat/fast-kvm-disconnect-detection`
基线提交：`824c8bfed447ca831a05de3e432db62024f854e8`

## 1. 证据规则

| 标记 | 含义 |
|---|---|
| `PASS` | 本轮在当前工作区实际执行并满足断言 |
| `FAIL` | 本轮实际执行并复现失败 |
| `NOT RUN` | 尚未执行，不得按历史结果写成通过 |
| `BOUNDARY` | 当前架构明确不支持，不是假设性失败 |

所有命令必须记录：

- 执行目录；
- 命令；
- 退出码；
- 核心断言；
- 是否产生或遗留进程、端口、数据库和日志。

## 2. 修改前工作区基线

开始 L0 前，工作区已经存在用户未提交的 Simulator 改造：

```text
 M backend/app/api/simulator.py
 M backend/kvm_simulator_README.md
 M backend/simulator/bridge.py
 M backend/simulator/main.py
 M backend/simulator/models.py
 M backend/simulator/profiles.py
 M backend/simulator/scenarios.py
 M backend/simulator/snmp_agent.py
 M backend/simulator/state.py
 M backend/tests/test_simulator_core.py
?? backend/simulator/topologies/
?? backend/simulator/topology_store.py
?? backend/tests/test_simulator_lifecycle.py
?? backend/tests/test_simulator_profiles.py
?? backend/tests/test_simulator_runtime_patch.py
?? backend/tests/test_simulator_topologies.py
?? backend/tests/test_simulator_traps.py
?? backend/tests/test_simulator_ui_contract.py
?? docs/reference/docs/
?? docs/simulator/
?? docs/simulator_startup_connection_guide.md
?? simulator-ui/
```

保护规则：

- 未执行 `git reset`、`git checkout --`、`git clean`；
- 未删除数据库、日志、拓扑或 UI 构建产物；
- L0 对已有脏文件只追加 status/bridge/端口错误可见性；
- MIB、Profile、state、SNMP/Trap 语义、UI 页面和拓扑语义未纳入 L0。

## 3. 修改前问题复现

### R-L00-001：PowerShell 中 CMD `set` 不会写入进程环境

状态：`PASS`（问题已确认）

复现：

```powershell
Remove-Item Env:SIM_WEB_PORT -ErrorAction SilentlyContinue
set SIM_WEB_PORT=18890
[Environment]::GetEnvironmentVariable('SIM_WEB_PORT', 'Process')
```

修改前结果：进程环境仍为空，Simulator 会回退到默认 `8888`。

关闭方式：PowerShell 文档只使用 `$env:SIM_WEB_PORT='18890'`；CMD 文档只使用 `set "SIM_WEB_PORT=18890"`。

### R-L00-002：Simulator 没有统一 status

状态：`PASS`（问题已确认并已实现修复）

修改前请求：

```text
GET /api/v1/status
```

修改前结果：`404`。

当前实现：

- 返回 runtime/topology/revision/device count；
- 返回 Agent expected/running/device IDs；
- 返回 bridge 最近一次 reconcile、binding count 和失败原因；
- 返回 Trap target；
- token/community 只返回状态，不返回值。

### R-L00-003：初始 bridge reconcile 失败被静默丢弃

状态：`PASS`（问题已确认并已实现修复）

修改前位置：

```text
backend/simulator/main.py::_start_definition
```

修改前行为：调用 `bridge.reconcile(runtime)` 后不保存返回值，也不记录失败日志。

当前实现：

- `DashboardBridge` 保存最近一次结果和时间；
- `/api/v1/status` 暴露脱敏诊断；
- 初始失败写入 `simulator_bridge_reconcile_failed` 日志；
- bridge 未配置写入 `simulator_bridge_disabled` 日志；
- smoke 在 bridge 已启用但失败时返回非零。

### R-L00-004：built-in preset 不受 `SIM_SNMP_PORT_BASE` 控制

状态：`PASS`（问题已确认，未在 L0 修改）

事实：

- built-in scenario 为设备保存显式端口 `11161..11165`；
- `SIM_SNMP_PORT_BASE` 只参与缺少显式端口的 topology 默认值；
- 原启动文档把它描述成通用换端口方式，存在误导。

当前处理：

- doctor 在 preset + `SIM_SNMP_PORT_BASE` 时给出 `warn`；
- L0 文档要求停止占用者，不能依赖该变量重映射 preset；
- 是否让 preset 端口参数化属于后续 Profile/Topology 契约，不在 L0 擅自修改。

### R-L00-005：community 变量名不同

状态：`PASS`（问题已确认并由 doctor 阻断漂移）

```text
Dashboard: SNMP_DEFAULT_COMMUNITY
Simulator: SNMP_COMMUNITY
```

doctor 比较二者的实际值，只输出“相同/不同”，不输出原值。

### R-L00-006：Dashboard 与 Simulator 的 Trap 默认端口不同

状态：`PASS`（问题已确认并由 doctor 阻断漂移）

未设置 `SNMP_TRAP_PORT` 时：

```text
Dashboard 默认：162
Simulator 默认：10162
```

doctor 返回 fail，要求两边显式设置同一个端口。

### R-L00-007：simulator-ui dev proxy 曾固定为 8888

状态：`PASS`（L0 环境配置已修复）

当前实现：

- 托管构建模式使用 `18890`；
- Vite dev 通过 `VITE_SIMULATOR_TARGET` 选择 Simulator；
- 独立 dev 端口通过 `SIMULATOR_UI_PORT` 选择；
- 本轮在 `13100 → 8888` 完成真实 proxy 验证。

### R-L00-008：Docker 没有 Simulator service

状态：`BOUNDARY`

`docker-compose.yml` 当前只包含：

- postgres；
- Dashboard backend；
- Dashboard frontend。

而且容器内 `127.0.0.1` 不能访问宿主机 Simulator Agent。L0 不新增不可验证的临时 Docker service，不声称 Docker 全链通过。

## 4. 自动测试

### T-L00-001：L0 隔离测试

状态：`PASS`

目录：

```text
H:\WORK\I\kvm-dashboard\backend
```

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_simulator_l0.py -q
```

结果：

```text
............                                                             [100%]
12 passed
```

覆盖：

1. token/community 不出现在 resolved config；
2. community 漂移返回 fail；
3. Dashboard/Simulator Trap 默认端口漂移返回 fail；
4. TCP 占用错误包含精确地址；
5. built 模式不检查独立 UI dev 端口，dev 模式才检查；
6. runtime UDP preflight 错误包含精确地址；
7. bridge 保存最近一次结果且不泄露 token；
8. status 暴露 bridge 失败并返回 degraded；
9. smoke 对 topology、Agent、binding、scheduler、database、Trap receiver 做精确断言；
10. URL userinfo/query 和运行 secret 不进入 doctor/status 输出。
11. `snmp-get` 查询全部 preset 绑定，成功值和异常路径都不泄露 community。
12. `snmp-get` 将 SNMP `NoSuchObject/NoSuchInstance` 判为失败。

### T-L00-002：Python 编译

状态：`PASS`

命令：

```powershell
.\.venv\Scripts\python.exe -m py_compile `
  simulator\l0_check.py `
  simulator\bridge.py `
  simulator\main.py
```

结果：退出码 `0`。

### T-L00-003：Simulator doctor

状态：`PASS`

条件：

```text
SIM_TOPOLOGY=all-profiles
SIM_ADDRESS_MODE=port
SIM_WEB_PORT=18890
SIM_DASHBOARD_URL=http://127.0.0.1:18002/api/v1
SNMP_TRAP_PORT=10162
Dashboard/Simulator community 相同
```

命令：

```powershell
.\.venv\Scripts\python.exe -m simulator.l0_check --json doctor --component simulator
```

结果：

- `ok=true`；
- `18890/tcp` available；
- `11161..11165/udp` available；
- 配置输出未出现 token/community 原值。

## 5. 真实进程验证

验证时间：2026-07-31。所有服务使用临时 SQLite 数据库和本轮临时 token；
输出只记录 configured/unconfigured，不记录实际值。

| ID | 验证项 | 状态 | 通过断言 |
|---|---|---|---|
| T-L00-004 | PowerShell 三服务与托管 UI | `PASS` | health/database/scheduler/Trap running；5 Agent、5 binding；smoke=0 |
| T-L00-005 | CMD 三服务启动 | `PASS` | Dashboard UI=200；Simulator ok；5 Agent、5 binding；smoke=0 |
| T-L00-006 | build 后 Simulator 托管 UI | `PASS` | `/`=200；smoke `--require-ui` 通过 |
| T-L00-007 | simulator-ui Vite dev | `PASS` | `13100/api/v1/status` 经参数化 proxy 返回 5 Agent |
| T-L00-008 | bridge token 错误 | `PASS` | status degraded；binding=0；smoke=1 |
| T-L00-009 | Dashboard 不可达 | `PASS` | status degraded；显式 reconcile=503；smoke=1 |
| T-L00-010 | TCP 端口占用 | `PASS` | doctor 非零并显示精确 `host:port` |
| T-L00-011 | UDP Agent 端口占用 | `PASS` | 启动退出码3并显示 `127.0.0.1:11161` |
| T-L00-012 | Trap UDP 端口占用 | `PASS` | Dashboard 退出码3并显示 `udp://0.0.0.0:10162` |
| T-L00-013 | 停止与清理 | `PASS` | `18002/3001/18890/10162/11161..11165` 全部释放 |
| T-L00-014 | 真实 SNMP GET | `PASS` | 五端口 `sysObjectID.0` 均返回各自值 |
| T-L00-015 | URL 与 secret 脱敏 | `PASS` | userinfo/query URL 被拒绝；marker 未出现在 doctor/status |

Simulator UI 与 Dashboard 前端 build 均通过；Simulator UI lint 通过。
Dashboard 前端 lint 仍有 16 个既有错误，涉及 legacy/现有页面文件，L0 未修改
这些业务组件，因此记录为上层既有基线，不在环境层顺手修复。

### 5.1 PowerShell 全链执行记录

执行目录与启动命令：分别按
`L00_BASELINE_AND_ENVIRONMENT.md` 的 7.2、7.3、7.4、7.5 节执行。
环境变量使用 `$env:NAME='value'`，Bridge token 为运行时随机值，SQLite
数据库位于本轮临时目录，不在仓库内。

最终验收命令（`H:\WORK\I\kvm-dashboard\backend`）：

```powershell
.\.venv\Scripts\python.exe -m simulator.l0_check smoke `
  --expected-topology all-profiles `
  --expected-agents 5 `
  --require-bridge `
  --require-ui
```

退出码：`0`。

实际关键输出：

```text
dashboard.health=pass
dashboard.database=connected
dashboard.scheduler=True
dashboard.trap_receiver=running, port=10162
simulator.active_topology=all-profiles
simulator.agent_count=expected 5, running 5
simulator.agent_bindings=healthy 5, status_matches_state=True
simulator.bridge=enabled True, last_ok True
simulator.bridge_bindings=expected 5, actual 5
simulator.ui=status 200, text/html
```

三个子进程均由当次验收 harness 捕获并停止；原始 PID 未作为长期证据保留。
停止后再次独占绑定确认：

```text
18002/tcp=free
3001/tcp=free
18890/tcp=free
10162/udp=free
11161..11165/udp=free
```

没有遗留运行进程；临时数据库和日志不作为产品数据使用。

### 5.2 CMD 全链执行记录

执行目录与启动命令：分别按
`L00_BASELINE_AND_ENVIRONMENT.md` 的 8.1、8.2、8.3、8.4 节执行。
所有变量使用 `set "NAME=value"`，未使用 PowerShell 语法。

最终验收命令（`H:\WORK\I\kvm-dashboard\backend`）：

```bat
.venv\Scripts\python.exe -m simulator.l0_check smoke --expected-topology all-profiles --expected-agents 5 --require-bridge --require-ui
```

退出码：`0`。实际关键输出：

```text
Dashboard health=ok
Trap receiver=running, port=10162
Dashboard UI HTTP=200
Simulator status=ok
Agent expected/running=5/5
Bridge binding_count=5
smoke ok=true
secret marker absent=true
```

本次 CMD harness 的子进程 PID 只用于当次停止，未长期保留。退出后对
`18002/3001/18890/10162/11161..11165` 的 TCP/UDP listener 复查均为 `0`。

### 5.3 可复跑的真实 SNMP GET

执行目录：`H:\WORK\I\kvm-dashboard\backend`。

先按 7.4 节启动 `all-profiles` Simulator，再执行：

```powershell
$env:SIM_TOPOLOGY='all-profiles'
$env:SIM_ADDRESS_MODE='port'
$env:SIM_WEB_PORT='18890'
$env:SNMP_TRAP_PORT='10162'
$env:SNMP_COMMUNITY='public'
.\.venv\Scripts\python.exe -m simulator.l0_check --json snmp-get --timeout 1.0
```

2026-07-31 最终复跑的 Simulator PID 为 `23636`，Agent 数为 `5`，命令退出码
为 `0`。精确返回值：

```text
127.0.0.1:11161 -> SNMPv2-SMI::enterprises.32828.3.257.16
127.0.0.1:11162 -> SNMPv2-SMI::enterprises.32828.3.257.10
127.0.0.1:11163 -> SNMPv2-SMI::enterprises.32828.3.768.768
127.0.0.1:11164 -> SNMPv2-SMI::enterprises.32828.3.769.768
127.0.0.1:11165 -> SNMPv2-SMI::enterprises.32828.3.1792.17
```

停止 PID `23636` 后的实际复查：

```text
CLEANUP_TCP_18890=0
CLEANUP_UDP_AGENTS=0
```

该入口不会输出 `SNMP_COMMUNITY` 的值。它只证明五个 Agent 能对
`sysObjectID.0` 作真实响应，不替代 L1 的独立 MIB golden 验证。

### 5.4 故障注入执行记录

| 故障 | 实际操作 | 退出码/响应 | 关键断言 | 清理 |
|---|---|---|---|---|
| Bridge 目标不可达 | Simulator 指向未监听的 Dashboard URL，执行 `smoke --require-bridge` | `1` | status=`degraded`；last reconcile=`ok:false`；binding=`0`；无 secret | Simulator 已停，相关端口释放 |
| Bridge token 错误 | Dashboard 与 Simulator 注入不同随机 token，执行显式 reconcile | HTTP `401`；smoke=`1` | status=`degraded`；binding=`0`；无 token 值 | 三服务已停，相关端口释放 |
| Agent UDP 占用 | 先以独占 UDP socket 绑定 `127.0.0.1:11161`，再执行 `python -m simulator` | `3` | stderr 包含精确 `127.0.0.1:11161` 与 topology `all-profiles` | 占用 socket 与 Simulator 均关闭 |
| Trap UDP 占用 | 先以独占 UDP socket 绑定 `0.0.0.0:10162`，再启动 Dashboard | `3` | stderr 包含 `udp://0.0.0.0:10162`；application startup failed | 占用 socket 与 Dashboard 均关闭 |
| URL/secret 注入 | `SIM_DASHBOARD_URL` 使用 userinfo、query 和 marker 后执行 doctor | `1` | 明确拒绝 userinfo/query；输出不存在 marker | 无服务进程产生 |

同类独占绑定的可复跑隔离测试分别位于
`test_simulator_l0.py::test_runtime_preflight_error_contains_exact_udp_binding`、
`test_trap_receiver_startup.py` 和 URL 脱敏测试中。

### 5.5 前端构建记录

Simulator UI（`H:\WORK\I\kvm-dashboard\simulator-ui`）：

```powershell
npm.cmd run build
npm.cmd run lint
```

两条命令退出码均为 `0`；build 转换 `1929` 个模块。Vite dev 另在
`SIMULATOR_UI_PORT=13100`、`VITE_SIMULATOR_TARGET=http://127.0.0.1:8888`
下实跑，`GET /api/v1/status` 经 proxy 返回 `5` 个 Agent；停止后
`13100/tcp` 和 `8888/tcp` 均释放。

Dashboard 前端（`H:\WORK\I\kvm-dashboard\frontend`）：

```powershell
npm.cmd run build
npm.cmd run lint
```

build 退出码 `0`；lint 退出码 `1`，为 L0 修改前已存在且不在本层改动的
`16 errors / 8 warnings`。因此本项作为上层基线债务，不伪报通过。

## 6. 回归集

最终实际运行目录：`H:\WORK\I\kvm-dashboard\backend`。

最终实际命令：

```powershell
Set-Location 'H:\WORK\I\kvm-dashboard\backend'
.\.venv\Scripts\python.exe -m pytest `
  tests\test_simulator_l0.py `
  tests\test_trap_receiver_startup.py `
  tests\test_health_probe.py `
  tests\test_simulator_core.py `
  tests\test_simulator_lifecycle.py `
  tests\test_simulator_profiles.py `
  tests\test_simulator_topologies.py `
  tests\test_simulator_traps.py `
  tests\test_simulator_ui_contract.py
```

如果测试因当前环境的进程权限、UDP 权限或已有脏工作区失败，必须记录原始错误；不得把历史通过结果当成本轮通过。

本轮扩展回归结果：

```text
exit code: 0
38 passed, 2 warnings in 2.31s
```

两个 warning 均来自 pysnmp/pysmi 上游弃用项
`getReadersFromUrls`、`smiV1Relaxed`，不是测试失败。另执行
`python -m py_compile` 和 `git diff --check`，退出码均为 `0`
（后者只报告现有 LF/CRLF 转换提示）。

## 7. Gate 结论

当前结论：`L0 Accepted for Windows local port mode`。

通过范围：

- PowerShell 与 CMD 本地启动；
- build 托管和 Vite dev 两种 Simulator UI 模式；
- Dashboard Trap ready/error、Simulator Agent binding、Bridge reconcile；
- 端口冲突、错误 Bridge、敏感配置和停止清理。

不在本结论中的能力：

- Docker Simulator 全链；
- 停止 Simulator 后自动删除 Dashboard run 数据；
- 厂家 MIB、完整 SNMP 对象和 Trap 业务语义正确性；
- Dashboard 前端既有 lint 债务。

因此现在允许开始 L1 MIB golden 的正式开发；L2 仍必须等待 L1 Gate。
