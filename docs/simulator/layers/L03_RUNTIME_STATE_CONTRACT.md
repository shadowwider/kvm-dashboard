# L03 类型化运行时状态契约

> 状态：Accepted
> 更新日期：2026-07-31
> 适用范围：从 Accepted L2 Profile 和显式 fixture 建立场景级、类型安全、
> 线程安全的唯一运行时状态源；本层不启动 UDP Agent，不编码 ASN.1，不发送
> Trap，也不定义 REST、WebSocket 或 UI。
> 验证状态：实现、专项、全回归、问题清单、三轮独立审计和 Git Gate 已完成；
> L3 Core `P0=0 / P1=0`，实现基线
> `91e5ffb4dd6941f46ed1911d1dd91371816be63b`。

## 下层契约依赖

| 下层交付 | Accepted 状态 | 实现/证据工件 | 正式 Gate |
|---|---|---|---|
| `layers/L00_BASELINE_AND_ENVIRONMENT.md` | `Accepted for Windows local port mode` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `decisions/ADR-001-LOCAL_ADDRESS_MODES.md` | `Accepted for L0` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `verification/L00_CURRENT_REPRODUCTIONS.md` | `Accepted for Windows local port mode` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `layers/L01_MIB_GOLDEN_CONTRACT.md` | `Accepted for local curated device dictionary snapshot` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `layers/L01_TRAP_EVIDENCE_CONTRACT.md` | `Accepted for local curated device dictionary snapshot` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `verification/L01_MIB_COVERAGE_REPORT.md` | `Accepted for local curated device dictionary snapshot` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `layers/L02_PROFILE_MODEL_CONTRACT.md` | `Accepted` | 实现与证据 `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | Accepted 状态 `commit=8060a2c` |
| `decisions/ADR-002-PROFILE-NAMING-AND-VERSIONING.md` | `Accepted` | 实现与证据 `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | Accepted 状态 `commit=8060a2c` |
| `decisions/ADR-003-OPTIONAL-GROUP-AND-FIXTURE-ROWS.md` | `Accepted` | 实现与证据 `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | Accepted 状态 `commit=8060a2c` |
| `verification/L02_PROFILE_MODEL_REPORT.md` | `Accepted` | 实现与证据 `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | Accepted 状态 `commit=8060a2c` |

L3 只消费 L2 的冻结 `ProfileDef`、经过
`validate_fixture_schema()` 验证的 `FixtureSpec` 及其公共只读接口。L3 不从
现有 `ScenarioState`、旧 `profiles.py`、SNMP renderer、页面字段或历史状态
字典反推 schema。

## 本层不得重新解释的事实

- OID、SYNTAX、MAX-ACCESS、枚举、范围、单位、INDEX 顺序和 optional 事实
  由 Accepted L1 Golden 决定；
- Profile ID、精确 `sysObjectID`、厂家名/规范字段名/UI key、Profile 版本、
  evidence revision 和显式 fixture 行由 Accepted L2 决定；
- `read-write` 只是厂家 SNMP 对象权限事实，不是 Simulator 运行时 PATCH
  权限，也不是 SNMP SET 授权；
- `read-only` 的设备状态值可以为了模拟故障而成为
  `runtime_writable=true`，但不得因此修改其厂家 MAX-ACCESS；
- optional group 未启用、fixture 未声明的行或列，在运行时就是不存在，不得
  依据 INDEX 上限、父行、UI 数量或字段名补造；
- `ccdc_legacy` 仍是 `legacy-unverified`；L3 不为其发明厂家对象；
- formal Trap 与 legacy Trap 的布局属于 L1/L4，不进入 L3 状态事务。

本层允许的 MIB 事实来源只包括：

```text
docs/reference/docs/devices/
Accepted L1 Golden
Accepted L2 Profile catalog 与 fixture
```

`docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md` 中出现的仓库外路径只是历史
调研记录。L3 禁止跟随访问仓库外原始 MIB、`docs/reference/docs/evidence` 或
现场日志，也不得把它们写成运行依赖。

## 1. 目标与非目标

### 1.1 目标

L3 必须提供：

1. 一个场景级唯一运行时状态源；
2. 从 L2 schema 和显式 fixture 确定性实例化的 scalar、table row 和 index；
3. 只读、确定性的路径注册表；
4. 类型、枚举、范围、字符串长度、optional 和行存在性校验；
5. 完整 batch 验证、working copy 和单次原子 commit；
6. 单一全局 revision 和 event 序列；
7. reset、disconnect、power_off、restore 的确定性状态机；
8. 在同一锁边界下生成的 `snapshot()` 和 `renderable_snapshot()`。

### 1.2 非目标

L3 不负责：

- OID 到 ASN.1 值的编码；
- GET、GETNEXT、GETBULK、SET 或 EndOfMibView；
- UDP Agent 的 bind、ready、stop 或错误恢复；
- Trap 构造、发送、归属或 severity；
- topology start/switch/stop 和持久化；
- Dashboard Bridge、REST/WS 状态码或前端表单；
- 物理端口、业务路由、拖拽或拉线。

这些能力分别由 L4–L11 继承本层契约后实现。

## 2. 场景级唯一状态源

### 2.1 公共构造边界

L3 的场景级入口为：

```text
RuntimeState(devices: Iterable[RuntimeDeviceSpec])
```

每个 `RuntimeDeviceSpec` 至少包含：

```text
device_id
ProfileDef
validated FixtureSpec
host
snmp_port
```

构造时必须一次性验证：

- `device_id` 非空且场景内唯一；
- Profile、fixture 的 ID、版本和 evidence revision 完全匹配；
- fixture 已通过 L2 全量 schema 校验；
- `system_oid` 只能来自 `ProfileDef.sys_object_id`；
- host/port 只是不可变设备身份，不参与 Profile 识别；
- scalar、table、row 和 index 没有重复规范键；
- 所有值都能进入 L3 的受支持运行时类型集合。

任一设备失败时，整个 `RuntimeState` 构造失败，不产生部分场景状态、路径
注册表、revision 或 event。

### 2.2 状态组成

概念模型：

```text
RuntimeState
├─ immutable device identities
├─ immutable ProfileDef / FixtureSpec references
├─ immutable RuntimePathRegistry
├─ immutable baseline values
├─ current runtime values
│  ├─ availability
│  ├─ scalars
│  └─ tables
│     └─ explicit row tuple
│        ├─ immutable indexes
│        └─ mutable column values
├─ one global revision
├─ one bounded in-memory event log
└─ one re-entrant lock
```

全局 revision 初始值固定为 `1`。构造初始状态不是一次用户事务，因此构造时
不产生 event；第一次有实际改变的事务提交为 revision `2`。

`availability` 只允许：

```text
connected
disconnected
powered_off
```

它与 Profile scalar/table 值分离。`disconnect`、`power_off` 和 `restore`
不得根据业务名称猜写 `main_power`、`mainPower`、`power_state` 或任何其他
Profile 字段。

### 2.3 唯一 revision 和 event 真值

多设备场景只能公开：

- 一个全局单调递增 revision；
- 一个按 revision 排序的 event log；
- 一次事务对应至多一次 revision 增量和一个 event。

禁止同时公开“Scenario revision”和“per-device revision”两套可见真值。
实现可以在内部封装设备值对象，但设备对象不能有独立公开 commit。所有变更
必须由 `RuntimeState` 在同一把锁下 prepare、validate、commit。

若将来需要跨多个设备的单次事务，必须先在 working copy 中准备全部设备，再
由场景级入口一次提交；不得先提交第一个设备，再因后续设备失败回滚外层数字。

## 3. 不可变结构与可变值

### 3.1 永久不可通过 PATCH 修改

以下结构字段必须进入只读 registry 或完全不暴露为 path：

- `device_id`、Profile ID/version/evidence；
- `system_oid`、host、SNMP port；
- scalar/table/column 的规范 ID；
- table row 的存在性和规范 row key；
- INDEX 名称、位置和值；
- fixture ID、optional group 启用集合；
- topology 的 device/endpoint/port/route ID；
- L1/L2 来源、OID、SYNTAX、MAX-ACCESS、枚举和范围；
- revision、event、baseline 和 registry 本身。

结构变更必须走 L2 fixture、L5 生命周期或 L10 topology 的新版本，不得伪装
成运行时 PATCH。

### 3.2 允许作为运行时值

只有当前 fixture 已实例化并由 `RuntimePathRegistry` 标记
`runtime_writable=true` 的 scalar 或 column leaf 可以 PATCH。

默认策略是：

- fixture 中存在的受支持 scalar leaf：可模拟修改；
- fixture 显式行中存在的受支持 column leaf：可模拟修改；
- identity 和 index：只读；
- 未启用 optional group：不存在；
- 未实例化 table row：不存在；
- 未知或 L3 不支持的 SYNTAX：fail closed，不产生可写 path。

运行时可写表示“Simulator 控制平面可以改变模拟值”，与厂家 SNMP
MAX-ACCESS 无关。

## 4. 路径注册表

L3 必须在构造时生成冻结的 `RuntimePathRegistry`。注册表由 L2 schema 与
显式 fixture 决定，不能在每次请求时从任意 dict 动态发现。

公共只读值对象包括：

```text
RuntimePathRegistry
PathSpec
PatchResult
StateEvent
ActionResult
```

每个 `PathSpec` 至少表达：

- 规范 path；
- device scope；
- path kind：identity、scalar、table index 或 table column；
- L2 field/table/index ID；
- 当前显式 row tuple（如适用）；
- 运行时值类型和约束；
- enum、range、字符串长度策略和 optional group；
- `runtime_writable`；
- `vendor_snmp_writable`；
- 厂家 `max_access` 的只读 metadata 引用。

availability 使用唯一规范 path：

```text
runtime.availability
```

它存在于 registry、可 `read()`，但 `runtime_writable=false`；普通 PATCH 永远
拒绝。只有 `action()` 和 `reset()` 的内部状态机可以改变它，相关 event 的
`changed_paths` 也使用同一条 registry path，不产生 registry 外的隐藏路径。

`vendor_snmp_writable` 只能由 L1/L2 的 `max_access=read-write` 得出。
`runtime_writable` 由 L3 的模拟状态策略得出。两者必须分别序列化、分别测试，
不得用一个布尔字段替代另一个。

规范路径语法、row key 和排序规则见：

```text
layers/L03_PATCH_PATH_AND_TRANSACTION_CONTRACT.md
decisions/ADR-004-STATE-KEYS-AND-COMPOSITE-INDEXES.md
```

## 5. 值校验

### 5.1 类型

L3 必须使用严格 JSON/Python 类型，不做宽松转换：

| schema 类型族 | 接受 | 拒绝示例 |
|---|---|---|
| Integer/Integer32/Unsigned/Gauge/Counter/TimeTicks 或 enum | `int`，且不是 `bool` | `true`、`false`、`"1"`、`1.0` |
| DisplayString/OctetString/PhysAddress/IpAddress 等当前 L2 字符串族 | `str` | bytes、数字、对象、数组 |
| 未知或不支持的 SYNTAX | 无可写输入 | 任意值均拒绝 |

Python 中 `bool` 是 `int` 的子类，因此整数校验必须显式排除 `bool`。当前
Accepted L2 Profile 没有独立的 Boolean runtime 类型，L3 对所有 bool 输入
fail closed；不得根据现有值 `0/1` 猜成 boolean。未来若 L1/L2 新增明确
Boolean 事实，必须先升级下层契约和本层类型矩阵。

L2 `IpAddress` runtime 值除 `str` 和长度外，还必须是可解析的 IPv4 文本；
IPv6、数字、bytes 和非法地址拒绝。该校验是 L3 对已声明 SYNTAX 的类型约束，
不重新定义任何具体厂家对象。

### 5.2 enum、range 和长度

校验顺序固定为：

1. 严格类型；
2. enum 集合；
3. 数值 range；
4. 字符串长度；
5. optional 和 row existence。

enum 和 range 必须原样使用 L2 定义。字符串长度如果 L1/L2 没有携带厂家
SIZE，使用明确命名、写入 `PathSpec` 的平台安全策略：

```text
PLATFORM_STRING_MAX_UTF8_BYTES = 4096
length = len(value.encode("utf-8"))
length_policy = platform-runtime-policy
```

该上限适用于当前 L2 string-like syntax：
`DisplayString`、`PhysAddress`、`IpAddress`、`OCTET STRING` 和
`OctetString`。canonical runtime value 始终保持 `str`，不转换为 bytes。
4096 UTF-8 bytes 不是厂家/MIB SIZE，不得反写 L1/L2 metadata，也不得从字段
名、当前字符串或 UI 控件猜测另一套厂家长度。

L3 验证报告必须记录常量、UTF-8 byte 计数方式和多字节边界测试，并明确该
结果不证明厂家设备可接受同样长度。

### 5.3 optional 和显式行

- optional group 未启用：对应实例 path 不注册；
- optional group 已启用但 fixture 缺少必填值：构造失败；
- table row 必须精确来自 fixture；
- path 的 row tuple 必须与显式行完全匹配；
- INDEX 合法但 fixture 不存在的 tuple 仍是 unknown path；
- 不得在 PATCH 时创建 row、column、dict 或 optional group。

## 6. 公开读取边界

### 6.1 `snapshot(device_id=None)`

`snapshot(device_id=None)` 是控制平面快照。省略 device ID 时返回整个场景；
指定 device ID 时只返回该设备，但仍携带同一个场景全局 revision 和当前
event window，不创建 per-device revision/event 真值。方法必须在同一锁内
捕获并返回调用者不可原地修改的副本或冻结值。它至少包含：

- 全局 revision；
- 按确定顺序排列的设备；
- 每台设备的只读 identity；
- availability；
- scalar 值；
- table 的显式 row tuple、只读 indexes 和 column 值。
- 当前进程内已保留的 event window。

snapshot 不得包含内部 lock、working copy、可变 Profile 对象、community、
token 或未过滤异常对象。调用者修改返回对象不得影响运行状态。

### 6.2 `renderable_snapshot(device_id=None)`

`renderable_snapshot(device_id=None)` 是 L4 的纯输入边界；省略 device ID
时返回全部设备，指定时只返回目标设备。它只包含：

- 同一锁下读取的全局 revision；
- device ID、Profile ID/version/evidence、精确 system OID；
- 按规范排序的 `enabled_optional_groups`；
- availability；
- 当前已验证 scalar 值；
- 当前显式 table rows、规范有序 index tuple 和 column 值。

它不得包含：

- event log；
- path registry；
- host 或 SNMP port；
- Trap 请求；
- REST/WS payload；
- UI label 文案；
- ASN.1 对象；
- UDP socket、Agent 或 Bridge 状态。

同一 revision 下重复调用必须产生相同语义内容。`snapshot()` 与
`renderable_snapshot()` 必须来自同一已提交状态，不能观察到 working copy。

### 6.3 `read()` 和 `events()`

- `read(device_id, path)` 只能解析 registry 中的规范 path；
- identity 和 index 可以 read，但不能 patch；
- `events()` 只读取已提交事件，按 revision 严格递增；
- event 保留是 L3 进程内诊断能力，不承诺跨进程、重启或 L5 持久化；
- 超出内存保留窗口的事件不可被上层当作可靠审计归档。

## 7. 原子事务和并发

所有写操作统一遵循：

```text
acquire one RuntimeState lock
  resolve device and immutable registry
  validate the complete request
  build a working copy
  calculate actual changed paths
  commit all changes once
  increment global revision at most once
  append one event at most once
release lock
```

失败路径不得改变：

- current values；
- availability；
- revision；
- event log；
- `snapshot()`；
- `renderable_snapshot()`；
- registry 或 baseline。

只读操作也必须在同一锁边界捕获 revision 和值，不能先读 revision、解锁后再读
state。实现不得把内部 dict、list 或 Pydantic mutable reference 直接返回。

完整 PATCH 契约见
`L03_PATCH_PATH_AND_TRANSACTION_CONTRACT.md`。

## 8. 动作状态机

### 8.1 转移表

| 当前 availability | 操作 | 结果 | revision/event |
|---|---|---|---|
| `connected` | `disconnect` | `disconnected` | 各增加一次 |
| `connected` | `power_off` | `powered_off` | 各增加一次 |
| `connected` | `restore` | 目标已是 `connected` | 幂等；均不增加 |
| `disconnected` | `disconnect` | 目标已是 `disconnected` | 幂等；均不增加 |
| `disconnected` | `power_off` | `powered_off` | 各增加一次 |
| `disconnected` | `restore` | `connected` | 各增加一次 |
| `powered_off` | `power_off` | 目标已是 `powered_off` | 幂等；均不增加 |
| `powered_off` | `restore` | `connected` | 各增加一次 |
| `powered_off` | `disconnect` | 非法转移 | 拒绝；零副作用 |

旧入口中的 `pause` 不建立第四种 L3 状态。若 L7 需要兼容旧 payload，只能在
上层明确规范化为 `disconnect`，不能在 L3 同时维护 paused/disconnected 两套
真值。

### 8.2 action 结果

`action(device_id, action)` 返回只读 `ActionResult`，至少能表达：

- device ID；
- 当前全局 revision；
- from/to availability；
- 是否实际改变；
- changed paths；
- 已提交 event（若发生改变）。

幂等动作返回当前状态，`changed=false`、`changed_paths=[]`，不增加 revision，
不追加 event。非法动作抛出细分领域异常，状态完全不变。

动作只改变 availability。它不发 Trap、不启停 Agent、不清理 Bridge，也不改
任何按业务名猜测的 Profile scalar。

## 9. Reset 语义

`reset(device_id)` 将指定设备的：

- scalar 和 table column 值恢复为构造时的已验证 fixture baseline；
- availability 恢复为 `connected`；
- identity、row、index、Profile 和 registry 保持不变。

如果存在实际差异，reset 是一次事务：一个全局 revision、一个 event，事件的
`changed_paths` 包含所有真实改变且按 registry 顺序排列。如果设备已经与 baseline
完全一致，reset 幂等，不增加 revision/event。

reset 失败时不能留下部分 scalar 已恢复、table 未恢复或 availability 已改变的
半状态。场景级“重建全部设备”或 topology switch 属于 L5，不得复用本方法
假装完成生命周期事务。

## 10. Event 契约与保留边界

每次有实际改变的 patch、action 或 reset 产生一个 `StateEvent`。事件至少包含：

- 与 commit 相同的全局 revision；
- device ID；
- event kind；
- 规范、去重、确定性的 `changed_paths`；patch 保留归一化输入顺序，
  action/reset 使用 registry 顺序；
- 操作摘要，不包含 token/community；
- 可审计的发生顺序。

一个 batch 不得按字段产生多个事件。事件必须在状态提交的同一锁和同一临界区
追加；不能出现“state 已变但 event 未写”或“event 已写但 state 未变”。

L3 只保证固定上限的进程内保留策略：

```text
EVENT_HISTORY_LIMIT = 100
```

超过 100 项时按最旧 revision 淘汰。L3 不执行磁盘/数据库持久化，不承诺重启
恢复、跨进程订阅或永久 event ID；这些由 L5/L7 决定。

## 11. 公共 API 与异常

L3 公共能力至少包括：

```text
RuntimeState(devices)
RuntimeState.single(device_id, profile, fixture, host=None, snmp_port=None)
RuntimeState.snapshot(device_id=None)
RuntimeState.renderable_snapshot(device_id=None)
RuntimeState.read(device_id, path)
RuntimeState.patch(device_id, changes)
RuntimeState.reset(device_id)
RuntimeState.reset_all()
RuntimeState.action(device_id, action)
RuntimeState.events()
RuntimeState.path_registry(device_id)
```

`reset_all()` 是场景级一次提交：所有设备的实际 diff 使用
`devices[<device_id>].<relative-path>` 形成 changed paths，并共享一个全局
revision/event。它不能接受调用者注入的额外 changed paths；场景 facade 的
domain path 合并入口保持内部可见。

上层不得：

- 直接访问或修改 `_state`、设备内部 dict 或 fixture；
- 直接调用内部 device value object 的 commit；
- 绕过 registry 写任意 path；
- 为旧 UI payload 保留第二份可变状态；
- 根据厂家对象名、OID 或 UI label 临时拼可写路径。

实现必须提供可区分的领域异常，至少覆盖：

- unknown device；
- malformed/non-canonical path；
- unknown path/row；
- read-only path；
- duplicate path；
- type、enum、range、length validation；
- invalid action transition；
- unsupported syntax；
- construction/fixture mismatch。

HTTP 422/409 等映射属于 L7；L3 异常本身不得导入 FastAPI。

## 12. 测试要求

### 12.1 构造与 registry

- 五个 Profile 的已验证 fixture 可构造；
- 重复 device ID、Profile/fixture mismatch、错误 system OID 全部拒绝；
- registry 只包含显式实例；
- optional 未启用和缺失 row 不产生 path；
- identity/index 只读，scalar/column 权限与 vendor MAX-ACCESS 分离；
- unknown SYNTAX fail closed。

### 12.2 类型与 property tests

- integer 拒绝 bool、float 和数字字符串；
- 当前 schema 的任何 path 都拒绝 bool，不把它当作 integer；
- enum、range、平台字符串长度边界的边界值和越界值；
- 随机合法值 patch 后 read/snapshot/renderable 一致；
- 随机非法 batch 后完整快照、revision 和 events 不变；
- row-key encode/decode 往返唯一；
- 随机重复 path、乱序复合索引、未实例化 row 全部拒绝。

### 12.3 原子性与并发

- batch 前项合法、后项失败时零副作用；
- 100 项合法 batch 只增加一次 revision 和一个 event；
- 幂等 patch/action/reset 不增加 revision/event；
- 多线程 read 与 patch 不出现半状态；
- 多设备并发 patch 的全局 revision 唯一、严格递增；
- snapshot 的 revision 与值来自同一 commit；
- event changed paths 与实际 diff 完全相等。

### 12.4 动作

- 状态转移表每一格都有断言；
- `powered_off -> disconnect` 拒绝且零副作用；
- power_off/restore 不修改任何 Profile scalar；
- reset 同时恢复值和 availability，且只提交一次。

实际测试命令、用例数、耗时、并发轮数、随机种子和失败注入结果必须写入独立
L03 验证报告。当前结果见
`verification/L03_RUNTIME_STATE_REPORT.md`；独立审计、100/101 batch 边界、
单/多设备并发和 Git Gate 均已完成。

## 13. Gate L3 验收矩阵

| Gate 项 | 通过条件 | 当前状态 |
|---|---|---|
| 下层引用 | L0/L1/L2 Accepted 状态和真实 commit 已逐项引用 | PASS |
| 唯一状态源 | 一个场景级 lock/revision/event；无公开 per-device commit | 自动测试 PASS |
| 类型化实例 | 只从 L2 Profile + validated fixture 构造 | 自动测试 PASS |
| 路径 registry | scalar、单索引、复合索引唯一且可逆 | 自动测试 PASS |
| 结构保护 | identity/index/row/profile/host/system_oid 不可写 | 自动测试 PASS |
| 值校验 | type/enum/range/length/optional/row existence 全覆盖 | 自动测试 PASS；当前 Profile 无 IpAddress leaf，边界已记录 |
| 原子 batch | 完整验证、working copy、一次 commit/revision/event | PASS；100 接受/101 拒绝专项已固定 |
| 零副作用 | 任意失败后 state/revision/events/renderable 不变 | 自动测试 PASS；固定种子 100 轮 |
| 动作状态机 | 全转移表、幂等和非法转移测试通过 | 自动测试 PASS |
| 并发 | property/concurrency 测试无半状态和重复 revision | PASS；单/多设备 writer、snapshot 并发已覆盖 |
| 问题关闭 | `SIM-STATE-001/002/003` 的 L3 部分关闭 | 问题清单已回填 |
| 独立审计 | 无 P0/P1 | 三轮完成；最终 P0=0/P1=0 |
| Git 基线 | L3 代码、测试、文档和验证报告形成真实 commit | PASS；`91e5ffb4dd6941f46ed1911d1dd91371816be63b` |

当前结论：`Accepted`。专项 `91 passed`、后端全量 `176 passed`，三轮独立
审计最终 `P0=0 / P1=0`，实现与证据已由 commit `91e5ffb4dd69` 固定。
收敛后的 L4 后端完成层正式解锁。

## 14. 未验证的上层边界

即使 L3 通过，也仍不证明：

- ASN.1 编码或真实 UDP GET/WALK 正确；
- SNMP SET 被允许；L4 当前仍应统一返回 notWritable；
- disconnect/power_off 已真正停止 Agent；
- Trap 已发送、接收或正确归属；
- topology switch、store 或 lease 具备事务性；
- REST/WS 双客户端同步；
- Dashboard 多 Profile poll plan；
- 页面参数编辑、拓扑拖拽或拉线可用；
- 原始 MIB、现场设备或目标固件兼容性。

这些结论分别等待收敛后的 L4 后端完成层和 L5 前端完成与发布层。
