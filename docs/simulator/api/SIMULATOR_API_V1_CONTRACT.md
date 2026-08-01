# Simulator API v1 契约

> 状态：Draft for L4（已冻结并验证 runtime PATCH 垂直切片；其余端点仍为 Draft）
> 日期：2026-08-01
> 所属层：L4 后端完成层
> 消费者：`simulator-ui`、自动化验收脚本；Dashboard 通过 Bridge/UDP/Trap 集成

## 1. 契约原则

- 服务器是 active topology、runtime、revision 和可写 metadata 的唯一真值；
- 客户端不得发送 OID、厂家对象名或任意 nested path 代替 L3 canonical path；
- 所有成功写操作返回 commit revision、changed paths、committed values 和
  idempotent；
- 所有失败写操作不改变 runtime、revision、event、Agent 或 Bridge manifest；
- OpenAPI schema、REST fixture 和 WS fixture 必须由独立测试固定；
- token、community、现场地址和异常对象不得进入响应或 WS。

## 2. 当前已有端点

当前 `backend/simulator/main.py` 已提供：

```text
GET    /api/v1/status
GET    /api/v1/profiles
GET    /api/v1/topologies
POST   /api/v1/topologies
GET    /api/v1/topologies/{id}
PUT    /api/v1/topologies/{id}
DELETE /api/v1/topologies/{id}
POST   /api/v1/topologies/{id}/start
POST   /api/v1/topologies/{id}/stop
GET    /api/v1/state
PATCH  /api/v1/runtime/devices/{device_id}/state
POST   /api/v1/runtime/devices/{device_id}/actions
PATCH  /api/v1/devices/{device_id}/endpoints/{endpoint_id}
PATCH  /api/v1/devices/{device_id}/routes/{route_id}
POST   /api/v1/traps
POST   /api/v1/reset
POST   /api/v1/bridge/reconcile
WS     /api/v1/ws
```

`scenarios` 和 `reachability` 是 compatibility 入口。L4 必须决定保留、标记
deprecated 或迁移，不能让前端同时维护两套产品流程。

## 3. L4 必须冻结的公共模型

### 3.1 Status

必须明确返回：

- service status；
- active topology ID、running、revision；
- expected/running/ready Agent 数量和脱敏 binding；
- Bridge enabled/session/reconcile 状态；
- Trap target/receiver 验证状态；
- UI mode 和脱敏配置摘要。

### 3.2 Profile metadata

必须区分 schema 和 runtime instance：

- Profile ID/version/evidence version/system OID；
- scalar/table/index/column 定义；
- syntax/enum/range/optional group；
- vendor SNMP writable 与 runtime writable；
- 当前 topology 每台设备的实际 path registry；
- 禁止按 index range 展开不存在的 row。

`GET /api/v1/profiles` 只返回稳定 schema，**不**返回特定运行场景的 row/path。
实际已实例化的可读写路径统一由 `GET /api/v1/state.runtime_instances`
提供；前端不得用 schema 的 index range 自行展开编辑控件。

### 3.3 Runtime snapshot

一个响应中至少固定：

```text
schema_version
revision
active_topology_id
scenario/topology
devices[].availability
devices[].profile_state
runtime_instances.devices[].device_id
runtime_instances.devices[].path_registry.paths[]
runtime_instances.devices[].path_registry.writable_paths[]
recent events or event cursor
```

snapshot 内 revision 与全部值必须来自同一 L3 capture，不得分别读取 device 和
profile state 后拼接。

`path_registry` 是 L3 `PathSpec.to_dict()` 的只读投影，仅含当前 topology 的
真实 fixture path。每条 path 都包含 `runtime_writable`、`vendor_snmp_writable`、
`syntax`、enum/range/optional/index 信息；不存在的 row、disabled optional group、
identity/index/availability 都不得以可编辑路径出现。

### 3.4 Patch

请求继续使用：

```json
{
  "patches": [
    {"path": "scalars.switch_temperature", "value": "66.6"}
  ],
  "emit_trap": false,
  "expected_revision": 12
}
```

L4 必须增加或明确 expected revision/冲突策略。成功响应至少固定：

```text
revision
device_id
changed_paths[]
committed_values[{path,value}]
idempotent
event
lifecycle_intent
state
snapshot
```

`expected_revision` 可省略以兼容本地单操作者模式；提供时必须精确等于服务器
当前 revision，否则返回 HTTP `409`，`detail.code=revision_conflict`，并携带
`current_revision` 与 `retryable=true`。

已验证的 PATCH 响应中的 `state` 与 `snapshot` 相同，且包括
`runtime_instances`；这样 L5 可以在一次响应中拿到 committed value、revision 和
实际可写 path，而不必猜测或另建前端字段表。

### 3.5 Device action

正式动作只有：

```text
disconnect
power_off
restore
```

`pause` 不形成第四种 L3 状态。响应与 Patch 使用同一 commit 摘要，并明确
from/to availability。Agent 副作用失败的 HTTP 结果和补偿语义由 L4 冻结。

### 3.6 Topology

必须冻结：

- preset read-only 与 user topology CRUD；
- schema version；
- device/module/port/edge 全局 ID；
- physical edge 与 simulation route 分离；
- active topology 禁删；
- save validation 和无损 round trip；
- start/switch/stop 的 prepare/commit/rollback 结果。

### 3.7 Trap

必须明确 target device IDs、preset/custom message、level、formal/legacy layout、
发送结果和失败明细。客户端不得指定任意外部 host/port，避免把 API 变成 UDP
转发器。

## 4. 统一错误模型

L4 必须将错误冻结为可判定结构，至少覆盖：

```text
validation_error
unknown_resource
revision_conflict
illegal_transition
binding_conflict
lifecycle_failed
bridge_failed
protocol_render_failed
forbidden
rate_limited
```

错误响应至少包含稳定 code、可展示 message、field/path details、current
revision 和 retryable；不得要求前端解析 Python 异常字符串。

## 5. WebSocket

建立连接时第一条消息必须是完整 snapshot 或明确的 revision refetch 指令。
后续事件统一包含：

```text
type
schema_version
revision
event_id
changed_paths
state/snapshot 或 requires_refetch
```

L4 必须固定 topology start/stop/reset、runtime patch、device action、Trap、
Bridge degradation 和 Agent lifecycle 事件；实现断线重连、revision gap 检测和
慢客户端策略。前端只能按 revision 顺序应用，发现 gap 立即 GET `/state`。

当前已验证的 runtime PATCH 事件采用完整 snapshot：

```text
type=runtime_state_patch
schema_version=1
revision
event_id
changed_paths
committed_values
state/snapshot（包含 runtime_instances）
```

连接首包为 `type=snapshot` 加完整 state。topology、Trap、Bridge、重连和慢客户
端策略尚未冻结，L5 只能把它们作为待接入能力，不能假定已经完成。

## 6. 安全与兼容

- 控制 API 的认证/本地模式策略必须显式；
- WebSocket 校验 Origin/认证；
- topology 中 host/port 必须经过 allowlist 和端口冲突检查；
- Trap target 只能引用已加载设备；
- 写入频率、batch 大小、消息长度和 topology 大小有上限；
- compatibility endpoint 必须在 OpenAPI 标记 deprecated，不能静默长期存在。

当前收口约束：Topology host 默认只允许 loopback；额外 host 必须在
`SIM_ALLOWED_HOSTS` 精确列出。WebSocket 默认只接受浏览器同源，Vite 等开发源必须
通过 `SIM_ALLOWED_ORIGINS` 显式列出。Topology 用户文档带 revision，PUT 的旧 revision
返回 `revision_conflict`，不得覆盖较新的保存。

## 7. 从 Draft 到 Accepted 的条件

- 每个端点有 request/response/error Golden fixture；
- OpenAPI snapshot 有 drift test；
- 两客户端、冲突、断线重连和 revision gap 测试通过；
- L3 commit 结果与 API/WS/SNMP 实际观察一致；
- L4 独立审计无 P0/P1；
- 本文与 L4 验证报告引用同一真实 commit。

在 Accepted 前，前端可以按 fixture 开发组件，但不得把临时响应形状写成自己
的第二份接口定义。
