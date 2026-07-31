# L03 PATCH 路径与事务契约

> 状态：Candidate
> 更新日期：2026-07-31
> 适用范围：定义 L3 运行时 path、路径注册、batch 校验、原子提交、结果和失败
> 语义；不定义 HTTP payload、状态码、SNMP SET、UI 表单或拓扑编辑。
> 验证状态：实现、事务故障注入、确定性 property、回归、问题清单和三轮独立
> 审计已完成，技术 Gate 通过；仅 Git Gate 待完成。

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
| `layers/L03_RUNTIME_STATE_CONTRACT.md` | `Candidate` | 本次 L3 契约，尚无 Accepted commit | 必须与本文同批验收 |

L1/L2 工件哈希见 `L02_PROFILE_MODEL_CONTRACT.md`。本层不得另存一套 OID、
枚举、INDEX 或字段映射。

## 本层不得重新解释的事实

- path 只能由 L2 的 canonical field/table/index ID 构造；
- INDEX 顺序由 `IndexDef.position` 决定；
- row 只能来自 L2 validated fixture；
- MAX-ACCESS 由 L1/L2 决定，runtime PATCH 权限由 L3 registry 决定；
- 厂家 `read-write` 不授权 SNMP SET；
- UI label、厂家对象名和数值 OID 均不能作为可写 path；
- optional 未启用或 row 不存在时，path 不存在。

MIB 事实来源边界仍是
`docs/reference/docs/devices/`、Accepted L1 Golden 和 Accepted L2
Profile/fixture。不得访问兼容性计划中记录的仓库外原始 MIB 路径、
`docs/reference/docs/evidence` 或现场日志。

## 1. Path 的设备作用域

`device_id` 由 `read/patch/reset/action` 的方法参数提供，不写进叶 path。

正确：

```text
device_id = "sim-device-01"
path      = "scalars.temperature"
```

禁止：

```text
devices[sim-device-01].scalars.temperature
sim-device-01.scalars.temperature
```

原因：

- 避免 path 同时承担路由和字段身份；
- 防止 device ID 中的字符影响字段 grammar；
- batch 事务可以先解析明确的 device scope；
- L7 可以独立决定 URL/body 如何携带 device ID。

## 2. 规范路径

### 2.1 可读 identity

固定只读 path：

```text
identity.device_id
identity.profile_id
identity.profile_version
identity.host
identity.snmp_port
identity.system_oid
```

它们必须出现在 registry 中，`runtime_writable=false`。

### 2.2 Scalar

```text
scalars.<field_id>
```

示例只说明语法，不新增厂家事实：

```text
scalars.temperature
scalars.device_name
```

`<field_id>` 必须是当前 `ProfileDef.scalars[].canonical_field`，且该 scalar
已在 fixture 实例化。

### 2.3 Table column

```text
tables.<table_id>[<row-key>].<column_id>
```

单索引语法示例：

```text
tables.cpu_module[1].device_status
```

复合索引语法示例：

```text
tables.cpu_module_fan[1,2].fan_speed
```

这些名称只是 canonical 语法示例。实际 path 集合只能由当前 L2 catalog 和
fixture 生成。

### 2.4 Table index

INDEX 进入可读但永久不可写 path：

```text
tables.<table_id>[<row-key>].indexes.<index_id>
```

例如：

```text
tables.cpu_module_fan[1,2].indexes.target_module_index
tables.cpu_module_fan[1,2].indexes.fan_index
```

index path 的值必须等于 row-key 中对应 `IndexDef.position` 的元素。

## 3. Grammar

availability 另有一条可读、不可 PATCH 的规范 path：

```text
runtime.availability
```

它由 `action()`/`reset()` 的内部状态机修改。动作事件和 reset 事件都使用这条
registry path，不产生 registry 外的 changed path。

规范 grammar：

```text
path               = identity-path | runtime-path | scalar-path
                   | table-column-path | table-index-path
identity-path      = "identity." identity-field
identity-field     = "device_id" | "profile_id" | "profile_version"
                   | "host" | "snmp_port" | "system_oid"
runtime-path       = "runtime.availability"
scalar-path        = "scalars." canonical-id
table-column-path  = "tables." canonical-id "[" row-key "]." canonical-id
table-index-path   = "tables." canonical-id "[" row-key "].indexes." canonical-id
row-key            = canonical-int ("," canonical-int)*
canonical-int      = "0" | negative-int | positive-int
positive-int       = nonzero-digit digit*
negative-int       = "-" nonzero-digit digit*
canonical-id       = lower-alpha (lower-alpha | digit | "_")*
```

`canonical-id` 还必须满足 L2 的 `lower_snake_case` 校验，不能以 `_` 结尾、
不能包含连续空 segment，也不能由请求临时发明。

### 3.1 Signed decimal 规范

允许：

```text
[0]
[1]
[-1]
[1,2]
[-2,0,17]
```

禁止：

```text
[+1]      # 禁止加号
[01]      # 禁止前导零
[-0]      # 零只有一种写法
[1,]      # 禁止空项
[,1]      # 禁止空项
[1,,2]    # 禁止空项
[1, 2]    # 禁止空格
[]        # 至少一个 index
```

解析后的整数 tuple 还必须通过 L2 index range，并精确命中当前 fixture 的
显式 row。语法合法或 index 在允许范围内都不等于 row 存在。

### 3.2 不提供 escaping

规范 ID 只允许 L2 的 `lower_snake_case`，row-key 只允许 signed decimal 和
逗号，所以 path 不需要 escaping。

以下形式全部拒绝，不做解码：

- `%xx` percent encoding；
- 反斜杠 escaping；
- 引号、括号内 JSON、空格；
- Unicode 同形字符；
- 厂家 `MODULE::name`；
- 数值 OID；
- UI label。

服务器不得“修正”非规范 path。parse 后重新 encode 的结果必须与输入字节
完全一致，否则按 non-canonical path 拒绝。

## 4. Row-key 顺序、唯一性和排序

### 4.1 顺序

row-key tuple 的第 N 个值对应：

```text
TableDef.indexes[N].position == N
```

不得使用：

- fixture JSON 对象字段顺序；
- 字母排序后的 index 名；
- OID 最后一段；
- UI 列顺序；
- INDEX range 的笛卡尔积。

### 4.2 唯一和可逆

对每张表必须满足：

```text
encode(index_tuple) -> one canonical row-key
decode(canonical row-key) -> the same integer tuple
registry[(table_id, tuple)] -> exactly one explicit row
```

重复 tuple、不同字符串解析到同一 tuple、缺少/额外 index 都必须在构造阶段
失败。运行时不得以“最后一项覆盖前一项”消解冲突。

### 4.3 确定性排序

registry、snapshot 使用同一规范排序：

1. identity；
2. runtime availability；
3. scalar；
4. table；
5. table ID；
6. row tuple 按整数逐项字典序；
7. index 在 column 之前；
8. index 按 `IndexDef.position`；
9. column 按 L2 `TableDef.columns` 的稳定 schema 顺序。

JSON object 字段顺序不构成 row/index 身份语义。实现可以选择数组或有序映射
表达 registry/snapshot，但重复执行必须一致。

patch 的 `changed_paths` 保留归一化 batch 的输入顺序，并移除实际未改变的
同值项；这使调用者能够把结果逐项映射回请求。action/reset 没有调用者字段
顺序，使用 registry 规范顺序。无论哪种顺序，path 都必须规范且唯一。

## 5. `RuntimePathRegistry` 和 `PathSpec`

registry 在 `RuntimeState` 构造时一次生成，之后冻结。每个 path 必须唯一映射
到一个 `PathSpec`。

`PathSpec` 至少包含：

| 属性 | 含义 |
|---|---|
| `path` | 唯一规范字符串 |
| `kind` | identity/runtime/scalar/index/column |
| `device_id` | registry 内部作用域；不嵌入 path |
| `field_id` | canonical leaf/index ID |
| `table_id` | table path 时存在 |
| `row_key` / `index_tuple` | table path 时存在，顺序由 L2 决定 |
| `value_type` | L3 严格运行时类型 |
| `enum` / `range` | L2 原样约束 |
| `length_policy` | L2 明示长度或标为 platform-runtime-policy |
| `optional_group` | L2 optional 引用 |
| `runtime_writable` | Simulator PATCH 权限 |
| `vendor_max_access` | L1/L2 厂家事实 |
| `vendor_snmp_writable` | `vendor_max_access == read-write` 的只读派生值 |

权限矩阵：

| path kind | 可 read | runtime PATCH | vendor SNMP writable |
|---|---:|---:|---:|
| identity | 是 | 否 | 不适用 |
| runtime availability | 是 | 否；仅 action/reset 内部状态机可改 | 不适用 |
| table index | 是 | 否 | 否 |
| fixture scalar | 是 | 是（受类型约束） | 独立记录，可能是是或否 |
| fixture table column | 是 | 是（受类型约束） | 独立记录，可能是是或否 |
| optional 未启用 | path 不存在 | 否 | schema 事实仍由 L2 保存 |
| fixture 未声明 row | path 不存在 | 否 | schema 事实仍由 L2 保存 |
| unsupported syntax | 可以作为构造失败诊断；不得可写 | 否 | 不改变厂家事实 |

`vendor_snmp_writable=true` 不允许绕过 L4 的 SET 策略；
`runtime_writable=true` 也不能被解释为厂家设备可写。

## 6. Batch 输入

L3 `patch(device_id, changes)` 接受：

```text
Mapping[path, value]
Sequence[(path, value)]
```

归一化后必须是非空、有上限的有序 batch。当前契约上限为 `100` 项；上层若
需要更大操作，应拆分为多个显式事务并接受多个 revision。Mapping 使用其稳定
迭代顺序；Sequence 用于保留输入顺序，并允许实现检测重复 path。

每项只有：

```text
path
value
```

L3 不接受：

- 任意嵌套 merge object；
- JSON Patch 的 add/remove/move/copy；
- row create/delete；
- Profile、host、system_oid 或 index 修改；
- `emit_trap` 之类协议副作用开关；
- 同一 batch 中重复的规范 path。

`runtime.availability` 虽存在于 registry，也不得放入 patch batch。

重复 path 必须拒绝整个 batch，不能采用 first-wins、last-wins 或按请求顺序
多次改写。

## 7. 完整验证顺序

在任何 state、revision 或 event 改变前，按以下顺序验证完整 batch：

1. batch 是 `1..100` 项；
2. device ID 存在；
3. 每个 path 语法合法且已经是规范形式；
4. batch 内 path 无重复；
5. 每个 path 精确存在于该设备 registry；
6. `runtime_writable=true`；
7. row、optional group 和 leaf 仍存在于已冻结实例；
8. value 严格类型正确；
9. enum 正确；
10. numeric range 正确；
11. string length 正确；
12. 所有项都能应用到 working copy；
13. 计算实际 diff 和规范排序的 changed paths；
14. 单次 commit。

未知 SYNTAX 必须 fail closed。整数必须显式拒绝 bool；当前 Accepted L2
Profile 没有独立 Boolean runtime 类型，因此所有 bool 输入均拒绝。不得执行
字符串到数字、float 到 int、label 到 enum value 的隐式转换。

L1/L2 当前未携带厂家字符串 SIZE。L3 固定使用：

```text
PLATFORM_STRING_MAX_UTF8_BYTES = 4096
len(value.encode("utf-8")) <= 4096
length_policy = platform-runtime-policy
```

该策略适用于 L2 当前 string-like syntax，canonical value 仍是 `str`，
bytes 不被接受。具体常量和 UTF-8 byte 单位必须进入 `PathSpec` 及验证报告，
不得伪称厂家限制。

## 8. Working copy 与单次 commit

事务流程：

```text
lock
  capture current device values and global revision (initial revision is 1)
  validate complete batch against immutable registry
  deep/frozen working copy
  apply all proposed values to working copy
  diff current vs working
  if no actual diff:
      return no-op result
  commit working copy once
  global revision += 1 exactly once
  append one StateEvent exactly once
  return PatchResult
unlock
```

在 commit 前禁止：

- 修改 live nested dict；
- 增加 revision；
- append event；
- 广播 WebSocket；
- 生成或发送 Trap；
- 刷新 OID cache；
- 触碰 Agent、Bridge 或持久化。

L4+ 的副作用只能在 L3 成功返回后消费已提交结果；若上层副作用失败，不得
反向伪造 L3 batch 曾失败。跨层回滚由对应上层契约另行定义。

## 9. `PatchResult` 和 `StateEvent`

成功结果 `PatchResult` 至少必须让调用者确定：

- device ID；
- 是否发生实际改变；
- commit 后的全局 revision；
- 规范、去重、按归一化输入顺序的 `changed_paths`；
- 每个 changed path 的已提交值；
- 关联的唯一 `StateEvent`（发生改变时）。

如果所有新值都等于当前值：

```text
changed=false
changed_paths=[]
revision=current revision
event=None
```

不得增加 revision 或追加空事件。

发生改变时，整个 batch 只产生一个 `StateEvent`。事件的 `changed_paths`
必须与提交前后实际 diff 完全相等；不能包含同值项，也不能漏掉 reset/action
实际改变的路径。

## 10. 失败零副作用

任何一项失败必须拒绝整个 batch。失败前后的以下值逐字节或语义相等：

- `snapshot()`；
- 该设备 `renderable_snapshot()`；
- 所有 `read()` 结果；
- availability；
- 全局 revision；
- event log 长度与内容；
- registry；
- baseline；
- 其他设备状态。

特别需要故障注入：

- 第一项合法、最后一项 unknown path；
- 第一项合法、最后一项 enum/range/length 越界；
- 第一项合法、最后一项 read-only identity/index；
- 合法 table、合法 index range、但 row 不存在；
- 相同 path 使用两种非规范写法；
- working copy 应用中注入异常；
- 并发线程在验证和 commit 之间竞争。

异常必须是可区分的 L3 领域异常。HTTP status、JSON error body 和字段级 UI
展示属于 L7/L9，不在本层导入。

## 11. 并发边界

整个场景只使用一个 `RuntimeState` 写锁和一个全局 revision。每次 patch 在同一
临界区内完成验证、working copy、diff、commit 和 event。

必须保证：

- 两个设备并发 patch 得到不同且连续的全局 revision；
- 同一设备两个并发 patch 不发生 lost update；
- reader 只能看到事务前或事务后状态；
- snapshot 的 revision、device values 和 event tail 来自同一提交点；
- 内部 per-device 对象不能先行 commit；
- 事件顺序与 revision 顺序一致。

性能优化不得缩小原子边界。若未来采用读写锁或 copy-on-write，必须证明等价
语义并更新本契约和并发测试。

## 12. 验收测试

### 12.1 Grammar 与 registry

- scalar、单索引、复合索引合法 path；
- `+1`、`01`、`-0`、空项、空格、escaping 全部拒绝；
- encode/decode property test；
- row tuple 数量、位置、range、显式存在性；
- duplicate path 和 canonical collision；
- identity/index read-only；
- `runtime_writable` 与 `vendor_snmp_writable` 的四种组合。

### 12.2 值

- integer/bool 严格边界；
- enum 首尾值与非法值；
- range 最小/最大与上下越界；
- string 平台长度上限的 `limit-1/limit/limit+1`；
- unknown syntax；
- optional 未启用；
- 未声明 table/row/column。

### 12.3 事务

- 1 项和 100 项合法 batch；
- 101 项拒绝；
- 中间/最后一项失败后零副作用；
- 同值 batch 幂等；
- 混合同值/变更值时 changed paths 只含真实变化；
- 单 batch 只产生一次 revision/event；
- event 与 diff 一致。

### 12.4 并发与 property

- 多线程、多设备随机合法 patch；
- reader 与 writer 并发；
- 随机非法 batch rollback；
- revision 严格单调、无重复、无跳号；
- event 数等于实际 commit 数；
- 最终 snapshot 可以通过成功 event 序列重放到等价值状态。

事件保留只覆盖最近 `EVENT_HISTORY_LIMIT=100` 个已提交事件；超过窗口的重放
测试必须从对应 snapshot 起算，不能假设 L3 保存永久历史。

测试结果、随机种子、运行次数和耗时必须由 L03 验证报告回填。当前不得写
“Accepted”。当前结果见
`verification/L03_RUNTIME_STATE_REPORT.md`。

## 13. Gate 矩阵

| 项目 | 通过条件 | 当前状态 |
|---|---|---|
| 路径唯一 | 规范 grammar 无歧义、row-key 可逆 | 自动测试 PASS；固定种子 500 轮往返 |
| Registry | 只从 L2 schema + 显式 fixture 构建并冻结 | 自动测试 PASS |
| 权限分离 | runtime 与 vendor SNMP writable 分开 | 自动测试 PASS |
| 结构保护 | identity/index/row/profile/host/system_oid 拒绝写 | 自动测试 PASS |
| 完整校验 | type/enum/range/length/optional/row 全覆盖 | 自动测试 PASS；当前 Profile 无 IpAddress leaf，边界已记录 |
| 原子 commit | 一 batch 一次 commit/revision/event | PASS；100 接受/101 拒绝专项已固定 |
| Rollback | 任意失败零副作用 | 自动测试 PASS；含四类 event 物化失败 |
| 幂等 | 同值 patch 不增加 revision/event | 自动测试 PASS |
| 并发 | 无半状态、lost update 或重复 revision | PASS；单/多设备并发专项已固定 |
| 上层边界 | L3 core 无 FastAPI、SNMP、Trap、WS、UI 依赖 | 静态实现边界 PASS；ScenarioState 兼容 facade 单独保留 |
| 独立审计 | 无 P0/P1 | 三轮完成；最终 P0=0/P1=0 |

当前结论：`Candidate / technical Gate passed`。契约、实现、property/
concurrency/rollback、验证报告、问题清单和独立审计均已完成；只待形成真实
Git 基线后 Accepted，并进入收敛后的 L4 后端完成层。

## 14. 未验证边界

本契约即使通过，也不证明：

- L4 OID renderer 已消费 `renderable_snapshot()`；
- SNMP GET/WALK 返回值或 SET 行为正确；
- Agent cache 按 revision 正确失效；
- Trap、WebSocket 或 UI 已消费 changed paths；
- topology lifecycle、Bridge、store 或 API 具备事务性；
- 真实设备支持相同运行时修改或字符串长度。
