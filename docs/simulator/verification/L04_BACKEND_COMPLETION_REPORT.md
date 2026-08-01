# L04 后端完成层验证报告

> 状态：Candidate — 已完成并验证首个协议/API/lifecycle 垂直切片；L4 全 Gate 尚未完成。
> 验证日期：2026-08-01
> 下层基线：L0–L3 Accepted，L3=`91e5ffb4dd69`

## 1. 本轮范围和来源边界

本轮仅使用 `docs/reference/docs/devices/`、Accepted L1 Golden、Accepted L2
catalog/fixture、Accepted L3 契约与当前工作树。没有读取仓库外原始 MIB、
`docs/reference/docs/evidence`、现场日志或网络设备。

实现和验证范围：真实 UDP SNMP v2c GET/GETNEXT/GETBULK/SET 拒绝、revision
缓存、Agent 协议错误状态、legacy Trap notification OID、重叠端口 topology
切换失败恢复、TopologyStore 原子写入，以及 PATCH→REST→WS→UDP 的同 revision
闭环。

## 2. 已实现并验证

| 能力 | 当前证据 |
|---|---|
| 五 Profile UDP GET | 独立 L1 JSON Golden 驱动；五个 sysObjectID 均以真实 loopback UDP 返回，四个 vendor Profile 另验证一个 Golden gettable OID；CCDC Golden 明确为 0 厂家对象，只验证其 Golden system OID。 |
| GETNEXT/GETBULK/SET | 数值 OID 排序、3 条 bulk、EndOfMibView、SET `notWritable(17)` 均实测。bulk `maxRepetitions` 被服务端限制为 100。 |
| 同 revision 读取 | Agent 每请求读取一次 `renderable_snapshot()`，按 L3 revision 缓存 immutable OID entries；CCDM PATCH 后 REST response、WS event 和实际 UDP GET 都观察到 revision 和值 `66.6`。 |
| Agent 可观测性 | renderer 注入 `ValueError` 后 `protocol_error_count=1`、`last_protocol_error_type=ValueError`、Agent 线程仍存活；恢复 renderer 后真实 UDP GET 成功。 |
| Trap | 修正 legacy notification OID 为 L1 legacy Golden 固定的 `.32828.5.0.4`；formal/legacy UDP 捕获回归通过。 |
| lifecycle 回滚 | 同 binding 候选 Agent 启动失败后，旧 `ScenarioState`、active topology 与重新启动的旧 Agent 保持可用，并以实际 UDP `sysObjectID.0` GET 验证。 |
| Store | process `RLock`、临时文件 flush/fsync、`os.replace`；replace 故障保留旧 JSON、无 tmp 残留；损坏文档通过 `invalid_documents()` 明确报告。 |
| API 给 L5 的实例元数据 | `/state`、PATCH response 和 PATCH WS snapshot 都带 `runtime_instances.devices[].path_registry`，只列真实 fixture path；PATCH 支持可选 `expected_revision`，过期值稳定返回 409 `revision_conflict`。 |

## 3. 执行命令与精确结果

工作目录：`H:\WORK\I\kvm-dashboard\backend`

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\test_simulator_l4_protocol.py `
  tests\test_simulator_traps.py `
  tests\test_simulator_trap_golden.py `
  tests\test_simulator_l3_integration.py `
  -q -p no:cacheprovider
```

结果：`38 passed in 6.04s`。其中 `test_simulator_l4_protocol.py` 为新增 12 项，
包含真实 UDP、raw BER、REST TestClient、WebSocket、端口重叠回滚与原子 store。

```powershell
.\.venv\Scripts\python.exe tools\build_simulator_mib_golden.py --check
.\.venv\Scripts\python.exe tools\build_simulator_profile_catalog.py --check
.\.venv\Scripts\python.exe -m compileall -q simulator tests
git diff --check
```

结果依次为：`checked 5 object manifests`、exit 0、exit 0、exit 0（仅 Windows
LF→CRLF 工作树提示）。

变更前完整后端基线为 `176 passed, 6 warnings in 15.24s`。子任务初次尝试完整回归时，
默认 `127.0.0.1:11161` 被 PID `16460` 的本项目 `uvicorn simulator.main:app`
浏览器验证进程占用，既有 lifecycle 测试按 L0 预期拒绝绑定，导致 5 项失败。根验收者
确认进程命令行、停止该已知本地进程并确认端口释放后，独立复跑：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

结果：`188 passed, 6 warnings in 17.15s`。因此端口占用不是本次实现的失败；但这不改变
第 5 节列出的 L4 全 Gate 缺项和 Candidate 状态。

## 4. 手工/API 验证步骤

1. 按 `L00_BASELINE_AND_ENVIRONMENT.md` 启动 Simulator，确保默认 UDP 端口未被其他测试实例占用。
2. `Invoke-RestMethod http://127.0.0.1:18890/api/v1/state`，确认 `runtime_instances.devices[].path_registry.writable_paths` 只出现实际实例。
3. PATCH CCDM 的 `scalars.switch_temperature` 为 `66.6`，请求带上刚读到的 `expected_revision`；预期返回 `revision`、`event.event_id`、`changed_paths`、`state/snapshot` 和 `runtime_instances`。
4. 用两个 WebSocket 客户端连接 `/api/v1/ws`：首包是 snapshot；写入后收到 `runtime_state_patch`，revision 与 REST 相同。再对 CCDM 发 SNMP v2c GET `1.3.6.1.4.1.32828.3.257.10.2.3.4.0`，预期 `66.6`。

## 5. 尚未关闭的 L4 问题

| 严重度 | 项目 | 状态 |
|---|---|---|
| P0 | Dashboard Trap receiver 在同 host 多设备、不同 SNMP port 时的精确 run/device 归属 | 未完成；UDP Trap source address 本身不携带 Agent listening port，需要 Bridge 身份协议或明确 capability 限制。 |
| P0 | Dashboard lifecycle cleanup / lease / crash cleanup | 未完成。 |
| P1 | 全端点稳定错误模型、OpenAPI snapshot、topology CRUD fixture | 未完成；仅 PATCH conflict 固定。 |
| P1 | WS reconnect、revision gap、慢客户端和全部 lifecycle/Trap/Bridge 事件 | 未完成；仅 PATCH full snapshot 已验证。 |
| P1 | topology 端口语义、route/physical-edge 无损语义 | 未完成。 |
| P1 | host allowlist、Origin/认证、rate/size 限制 | 未完成。 |
| P2 | Agent 请求指标、Bridge health/lease、跨进程 Store lock | 未完成。 |

结论：本报告不是 L4 Accepted 证据。它将可运行底座推进为可由 L5 使用的 API
切片，但只有完整 UDP/Trap/lifecycle/Bridge/API/WS/Security Gate 与干净全回归
完成后，才允许把 L4 状态改为 Accepted。

## 6. 后续收口增量（2026-08-01）

- Bridge 正常停止改为使用受 `session_id + session_epoch` 保护的清理端点；Dashboard
  增加租约、heartbeat 与过期 run 回收，旧进程不能清理新进程的记录；
- port 模式每个设备使用独立 `127.0.1.x` Trap 源地址，manifest 持久化该 identity，
  接收端只在唯一匹配时归属设备，缺失或冲突时不猜测；
- REST 与 WS 使用同一个含 `active_topology_id`/`runtime_instances` 的 snapshot，
  HTTP 错误统一为 `code/message/details/current_revision/retryable`；
- topology 保存拥有 revision 冲突控制；物理边必须连接未占用的 fixture port，route
  只能连接 endpoint；默认拒绝非 loopback host，WS 默认同源。

根验收在上述变更后执行后端全回归，结果为 `202 passed, 6 warnings in 16.58s`。
这些实现仍需要在已启用 Dashboard Bridge 的真实本地组合中完成 lease reaper 和 Trap
receiver 的端到端验证，故 L4 继续保持 Candidate。
