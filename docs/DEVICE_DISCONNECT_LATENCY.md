# KVM 设备断开检测延迟：代码调查与修复说明

## 目标与范围

机场控制大屏需要尽快区分三类断开：

1. 整台 ControlCenter/KVM 交换机、管理网络或交换机供电失联；
2. CPU/CON 模块失联；
3. 交换机仍在线时的物理端口/SFP/网线链路变化。

本次修改的目标是：在已正确配置网络与并发容量的前提下，让三类原始状态在约 1–2 秒内进入后端并通过 WebSocket 进入大屏。CPU/CON 与物理端口的关联**不会**仅因表索引相同而自动推断，必须先以真实设备样本验证。

## 修复前：实际控制流与慢的原因

### 配置真相

| 表面配置 | 原代码实际行为 |
|---|---|
| `SNMP_POLL_INTERVAL` | 唯一被 APScheduler 使用的全局完整轮询频率；默认/生产配置均为 45 秒。 |
| `Device.poll_interval` | 可在数据库、API 与管理页保存，但 `run_poll_cycle()` 从不读取它；将设备填成 `1` 不会改变任何调度行为。 |
| Trap | 启动 UDP 接收器、保存 `Alert` 并推送 `trap_received`，但不修改 `Device.last_status`、`Endpoint.last_status`，也不触发状态复核。 |

因此，之前“配置为一秒仍然慢”符合代码行为：很可能修改的是无效的设备级 `poll_interval`，而非唯一生效的全局环境变量；即使把完整轮询设为一秒，也会把每台设备约 20 个 GET 和 59 个表 WALK 放大到每秒一次，不是安全方案。

### 整机离线路径

修复前路径为：

```text
APScheduler (45 s) → run_poll_cycle()
  → poll_device()
  → sysObjectID GET (timeout=3 s, retries=1)
  → Device.last_status='offline' → device_update WebSocket
```

`sysObjectID` 单次失败在重试后约需 6 秒；还要加上等待下一次 45 秒调度的时间。完整轮询中又有并行 GET/WALK，坏的表 WALK 可持续很久；`max_instances=1` 和 `coalesce=True` 会避免堆叠，却会延后下一轮。故 5–10 秒观察值完全可能来自 GET 超时，整体最差远高于该值。

### 前端可见性问题

`device_update` 原本只更新 Zustand 的 `devices`，所以设备卡会变，但矩阵、拓扑、端点详情和 KPI 使用的 `endpoints` 会继续显示旧状态，直到 Dashboard 每 60 秒 `fetchAll()` 重拉 REST 数据。

### Trap 与物理断开

- 完全断网/断电的交换机不能发送 Trap，必须采用轮询探测。
- CPU/CON 的 Trap 文本可在格式匹配时识别为 `went offline` / `came online`，但修复前只是告警。
- `portTable.portStatus` 已被完整轮询读取，枚举为 `noModule`、`moduleDeactivated`、`down`、`up`，但未做实时转换，也没有已验证的模块/端口映射。

## 修复后：双速状态路径

### 快速健康循环

新增独立 `run_health_probe_cycle()`：

```text
每 SNMP_HEALTH_POLL_INTERVAL (默认 1 s)
  → 每台 active Device 仅 GET sysObjectID
  → timeout=0.25 s, retries=1（约 0.5 s 请求预算）
  → 有状态转换才写 Device.last_status / 广播 device_update
```

它和完整指标轮询使用独立的并发控制；不执行完整 WALK、不归档时序指标、不产生阈值告警。`last_health_check` 与 `last_poll` 分离：前者表示快速可达性，后者仍表示最后一次完整指标采集。

快速循环会记录周期耗时、最大探测时间、成功/失败/转换数量、设备数和容量退化状态。`GET /api/v1/health` 的 `health_probe` 字段可直接验证运行参数及最近一次周期。

容量估算：

```text
ceil(active_device_count / SNMP_HEALTH_CONCURRENCY)
× (SNMP_HEALTH_TIMEOUT × (SNMP_HEALTH_RETRIES + 1)
   + SNMP_HEALTH_TIMEOUT)
```

第二项预留交换机可达后并行读取 CPU、CON 与物理端口三条状态列的一次无重试请求。

估算值高于快速轮询间隔时，代码发出 `health_probe_capacity_degraded` 日志并在健康接口中显示 `capacity_degraded=true`。此时不能承诺 1–2 秒 SLO，应提高并发、降低受控设备数量或为探测服务拆分独立 worker。

### CPU/CON 与端口状态

每个健康周期在交换机仍可达时只读取三条状态列：CPU `deviceStatus`、CON `deviceStatus` 和 `portTable.portStatus`。变化立即广播：

- `endpoint_update`：更新 CPU/CON 的 `Endpoint.last_status` 和前端缓存；
- `port_update`：更新设备的 `last_metrics.ports` 缓存，保留 `mapping_verified=false`。

已识别的 CPU/CON Trap 在保存告警的同时也会立即写入并广播端点状态，再异步触发一次同样的轻量状态列复核。无法识别的 Trap 保持原有“仅告警”策略。

### 前端路径

`device_update` 携带 `reachability` 时，Zustand 会为同一设备的所有缓存端点临时加 `device_reachability='offline'`；端点状态工具优先判定此值。因此设备卡、矩阵、SVG 拓扑、端点详情和 KPI 同步变离线。恢复时仅清除该覆盖值，绝不会伪造 CPU/CON 的在线状态；详细模块真相继续由状态列和完整轮询决定。

## 配置与部署

生产 `.env.production` 已提供推荐初始值：

```ini
SNMP_POLL_INTERVAL=45
SNMP_HEALTH_POLL_ENABLED=true
SNMP_HEALTH_POLL_INTERVAL=1
SNMP_HEALTH_TIMEOUT=0.25
SNMP_HEALTH_RETRIES=1
SNMP_HEALTH_CONCURRENCY=20
SNMP_HEALTH_FAILURE_THRESHOLD=1
SNMP_ENDPOINT_STATUS_POLL_ENABLED=true
```

如现场 UDP 丢包导致误离线，可把 `SNMP_HEALTH_FAILURE_THRESHOLD` 调高到 `2`；代价是最坏检测延迟通常会超过两秒。不得把 `SNMP_POLL_INTERVAL` 降到一秒来替代健康循环。

Trap Docker 端口必须匹配：Docker 映射的是容器 UDP 10162，因此后端运行环境须有 `SNMP_TRAP_PORT=10162`（生产样例已设置）。设备若默认发送 UDP 162，则需由网络/防火墙转发到宿主机映射端口。

## 真实设备验收流程

1. 启动后调用 `/api/v1/health`，确认 `health_probe.enabled=true`、间隔/超时/重试值正确且 `capacity_degraded=false`。
2. 记录每次动作的物理时间、后端 `device_health_offline`/`device_health_recovered` 日志时间、WebSocket 时间戳和大屏变色时间。
3. 对整机管理网或供电断开/恢复至少重复 30 次；统计中位数和 p95，验收目标为中位数 < 1.2 秒、p95 < 2 秒。
4. 对单个 CPU/CON 模块执行相同测试，并保留原始 Trap varbind 与状态列 OID 样本。
5. 对每条物理端口逐一拔插，记录变化前后 CPU 表、CON 表、portTable 的完整原始 OID 行。仅在样本证明对应关系后，才可将端口变化展示为某个模块的关联故障。
6. 检查无重复 offline/recovery 广播、无 `health_probe_capacity_degraded`、无 SNMP engine/task 泄漏，且 45 秒完整轮询周期没有明显变慢。

## Worker 方案结论

当前单 worker FastAPI 进程内的独立、轻量 APScheduler 任务是最小且可观测的修复：它不增加 Redis/消息队列/领导者选举等新故障面。若实际设备规模无法通过容量公式，或需要多个 API 副本，则下一阶段应把快速 SNMP 探测提取为专门 worker，并增加分布式任务归属及可靠事件总线；在此之前不应横向增加当前 API 进程 worker，因为调度器和 WebSocket Hub 均为进程内状态。

## 回滚

将 `SNMP_HEALTH_POLL_ENABLED=false` 并重启后端可停止快速路径，完整 45 秒轮询保留原状。该回滚会恢复旧的慢检测行为；不要通过把完整轮询改为一秒替代它。
