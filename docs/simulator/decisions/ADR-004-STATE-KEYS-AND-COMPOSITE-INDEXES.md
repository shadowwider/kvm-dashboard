# ADR-004：运行时状态键与复合索引

> 状态：Accepted
> 日期：2026-07-31
> 决策范围：L3 scalar/table 实例的规范路径、row-key、结构字段和
> availability 建模；不定义 OID 编码、SNMP SET、REST/WS 或 UI 文案。
> 验证状态：实现、自动测试、问题清单、三轮独立审计和 Git Gate 已完成；
> 实现基线 `91e5ffb4dd6941f46ed1911d1dd91371816be63b`。

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

L1/L2 的精确 Golden SHA-256、Profile version 和 evidence revision 见
`L02_PROFILE_MODEL_CONTRACT.md`，本 ADR 不复制这些事实。

## 本层不得重新解释的事实

- 厂家对象身份由完整数值 OID 和 `MODULE::name` 决定；
- L3 path 使用 L2 canonical ID，不使用厂家对象名、OID 或 UI label；
- INDEX 名称、顺序、类型和 range 由 L1/L2 决定；
- INDEX range 不代表 fixture row；
- optional group 和 row 由显式 L2 fixture 决定；
- MAX-ACCESS 不决定 Simulator runtime PATCH 权限；
- `ccdc_legacy` 的厂家对象边界仍是 `legacy-unverified`。

事实来源只限仓库内 `docs/reference/docs/devices/`、Accepted L1 Golden 和
Accepted L2 Profile/fixture。兼容性计划中的仓库外路径、原始 MIB、
`docs/reference/docs/evidence` 和现场日志不在本决策输入范围。

## 1. 背景

旧状态实现同时存在：

- 任意 nested dict；
- `scalars.temperature` 一类 Profile path；
- `ports[1].status`、`endpoints[id].field` 一类 UI/拓扑 path；
- camelCase、snake_case 和厂家对象名混用；
- 只取复合 OID 最后一段作为 index；
- path 不存在时动态创建 dict。

结果是：

- PATCH 可以成功写入 renderer 从不读取的字段；
- 结构字段可以被当作普通值覆盖；
- 复合索引不同 row 可能碰撞；
- 同一个业务字段出现两份状态；
- 页面显示成功，但 SNMP 结果不变。

L2 已提供稳定 canonical ID、有序 `IndexDef.position` 和显式 fixture row。
L3 必须把它们转换成唯一且可逆的实例键，不能继续兼容任意路径。

## 2. 决策

### 2.1 Device ID 不进入叶 path

所有公开字段 path 相对单个 device。device ID 由方法参数携带：

```text
read(device_id, path)
patch(device_id, changes)
reset(device_id)
action(device_id, action)
```

这样 device 路由、字段 grammar 和多设备全局 revision 可以分别建模。

### 2.2 Scalar path

唯一格式：

```text
scalars.<L2 canonical field_id>
```

厂家名、OID、UI label 和 compatibility alias 都不能作为第二条可写 path。

### 2.3 Table row-key

table path 唯一格式：

```text
tables.<L2 table_id>[<canonical signed-decimal tuple>].<L2 column_id>
```

单索引：

```text
[1]
```

复合索引：

```text
[1,2]
```

tuple 元素严格按 `IndexDef.position`。row-key 只编码 index 值，不复制 index
名称，因为名称和顺序已经由 table schema 唯一确定。

规范整数仅允许：

```text
0
[1-9][0-9]*
-[1-9][0-9]*
```

禁止 `+`、前导零、`-0`、空项、空格和 escaping。decode 后必须 exact-match
显式 fixture row；不得按 range 创建 row。

### 2.4 Index 是 row 身份，不是值字段

index 以只读 path 暴露：

```text
tables.<table_id>[<row-key>].indexes.<index_id>
```

它可用于审查 snapshot 和 UI 元数据，但永远
`runtime_writable=false`。修改 index 的语义是删除旧 row、创建新 row，属于
fixture/topology 结构变更，不是 L3 PATCH。

### 2.5 Identity 独立只读

设备身份使用固定 path：

```text
identity.device_id
identity.profile_id
identity.profile_version
identity.host
identity.snmp_port
identity.system_oid
```

这些 path 可 read、不可 patch。`system_oid` 只能来自精确匹配的
`ProfileDef.sys_object_id`，不能被 scenario payload 覆盖。

### 2.6 Availability 不伪装成 Profile scalar

设备运行可用性独立建模为：

```text
connected
disconnected
powered_off
```

其唯一规范 path 是：

```text
runtime.availability
```

该 path 存在于 registry 且可 read，但 `runtime_writable=false`，普通 PATCH
永远拒绝；只有 action/reset 内部状态机可改。事件的 changed paths 使用同一
规范 path。

动作状态机修改 availability，不根据字段名猜写 Profile scalar。这样：

- CCDC legacy 不需要伪造 `main_power`；
- 不同 Profile 不会因同义词收到不同隐藏写入；
- L4/L5 可以明确区分“保留状态值”和“Agent 是否响应”；
- reset 可以确定性恢复 baseline 与 connected。

### 2.7 一个场景级提交序列

`RuntimeState` 管理所有设备、一个锁、一个全局 revision 和一个 event log。
内部 device value object 不公开独立 commit/revision。

即使一次 PATCH 只改变一台设备，上层看到的仍是场景全局 revision。这样 L7
以后可以用一个 revision 判断 snapshot/event 顺序，不必合并多个设备时钟。
初始 revision 固定为 `1`，构造不产生 event；event 仅在实际事务提交时产生，
进程内最多保留最近 `EVENT_HISTORY_LIMIT=100` 项。

### 2.8 字符串长度是平台策略，不是厂家事实

L2 当前没有携带厂家 SIZE。L3 对受支持 string-like syntax 采用
`PLATFORM_STRING_MAX_UTF8_BYTES=4096`，按 UTF-8 bytes 计数并将策略标为
`platform-runtime-policy`。这不改变厂家 MIB 事实，也不允许从 path、字段名
或 UI 推导其他长度。canonical runtime value 仍是 `str`，bytes 输入拒绝。

## 3. 为什么选择 positional numeric tuple

### 3.1 与 L1/L2 一致

SNMP table instance 的身份本质是按 INDEX 声明顺序排列的值。L2 已把该顺序
固定为连续 `IndexDef.position`。numeric tuple 是这一事实最小、无损的内部
表达。

### 3.2 可逆且无解析歧义

规范 signed decimal：

- 每个整数只有一种字符串表示；
- 逗号只分隔 tuple；
- canonical ID 不含方括号或逗号；
- 无需 percent encoding 或 JSON parser；
- `encode(decode(path)) == path` 可用 property test 证明。

### 3.3 不依赖 JSON 对象顺序

fixture 的 `indexes` 即使以映射输入，也必须先按 L2 position 验证并固化为
tuple。JSON 库、语言或人工编辑导致的 key 顺序变化不能改变 row 身份。

### 3.4 支持单索引和复合索引

单索引仍保留 tuple 形态 `[1]`，避免 scalar `[1]` 和裸 `1` 两套解析规则；
复合索引按原顺序自然扩展，不会只取最后一段。

## 4. 不采用的方案

### 4.1 任意 nested dict path

不采用。`_set_nested()` 式实现会在路径不存在时创建字段，无法证明该字段会被
renderer 消费，也无法保护结构字段。

### 4.2 用厂家对象名作为 path

不采用。同名对象可存在于不同模块；厂家 camelCase 也不是稳定 API 名。

### 4.3 用数值 OID 作为 path

不采用。OID 是厂家协议事实，不适合作为 UI/API 状态键；schema 版本迁移和
compatibility adapter 也需要与厂家 OID 身份分离。

### 4.4 `index_name=value` 组合

例如：

```text
[target_module_index=1,fan_index=2]
```

不采用。它重复 schema、扩大 escaping grammar，并允许请求通过重排/别名形成
多种等价字符串。index 名仍可从只读 registry 和 index path 获取。

### 4.5 JSON/URL 编码 row-key

不采用。`[{"a":1,"b":2}]`、base64、percent encoding 会引入 key 顺序、
escaping 和非规范等价值，增加安全和测试面。

### 4.6 只使用最后一个 index

不采用。复合 INDEX 会碰撞，且与 L1/L2 明确顺序冲突。

### 4.7 生成 row UUID

不采用。UUID 与厂家 INDEX 无确定映射，snapshot、renderer 和 fixture 无法
独立重建同一 row 身份。

### 4.8 以 INDEX 最大范围预注册所有 row

不采用。range 只验证合法值，不证明实例存在；这种方案会重新引入 L2 已删除
的伪库存和 metadata 膨胀。

### 4.9 让 SNMP MAX-ACCESS 决定 runtime writable

不采用。模拟器需要改变设备的 read-only 状态以制造故障；厂家 read-write
对象也不等于平台已获 SET 权限。两个维度必须并列记录。

### 4.10 用 `pause` 建第四种 availability

不采用。旧 `pause` 与 `disconnect` 对外语义重叠，会产生两个状态真值。兼容
转换属于 L7，L3 只保留三态状态机。

## 5. 规范排序

为保证 snapshot、event 和测试确定，使用：

```text
namespace（identity → runtime → scalars → tables）
→ schema field/table order
→ table_id
→ numeric index tuple
→ index position
→ column schema order
```

numeric tuple 按整数逐项比较，所以 `[2]` 在 `[10]` 之前。不得用完整 path
字符串的简单字典序替代 row tuple 数值排序。

registry 和 snapshot 不依赖请求顺序。patch 的 `changed_paths` 保留归一化
batch 输入顺序，便于调用者逐项关联结果；action/reset 使用 registry 顺序。
重复 path 直接拒绝，不允许同一路径在一个事务内出现两次。

## 6. 版本与迁移

本 row-key grammar 是 L3 公共契约。任一改变，例如：

- 改成 named index；
- 允许前导零或 escaping；
- 把 device ID 加入 path；
- 修改 canonical ID；
- 改变 INDEX 顺序；

都必须：

1. 先更新 L1/L2（若涉及厂家/字段/index 事实）；
2. 评估并升级 Profile MAJOR version；
3. 新增显式、单向、可测试的 path migration；
4. 更新本 ADR 和 L03 两份契约；
5. 重新执行 property、rollback、concurrency 和 L4 renderer 测试；
6. 禁止同时写旧 path 和新 path 两份状态。

只改变 UI label 不影响 path。

## 7. 后果

正向：

- 每个 fixture leaf 只有一个规范 path；
- 复合索引不碰撞；
- unknown path 无法动态创建状态；
- identity/index 得到明确结构保护；
- L4 可以从同一 row tuple 构造实例 OID；
- L4 可以从 renderable snapshot 获得排序后的 enabled optional groups，而
  不从缺失 path 反推能力；
- L7/L9 可以显示字段级错误而不猜测 alias；
- event changed paths 可稳定比较和重放。

代价：

- 旧 `ports[]`、`endpoints[]` 和 camelCase path 不能直接进入 L3；
- fixture/topology 结构变更必须使用上层专门操作；
- 客户端必须先读取 registry/metadata；
- schema/path 迁移必须版本化；
- 大量显式 row 会产生大量 registry entry，但只与真实 fixture 实例数增长。

## 8. 安全与分层后果

- path parser 不解码 URL 或 escaping，缩小歧义和注入面；
- device ID 单独传入，避免越过设备作用域；
- registry 精确命中，禁止 prototype/nested-key 式任意写入；
- 返回 snapshot 必须复制/冻结，防止调用者绕过 PATCH；
- path 不携带 token、community、host 凭据或 UI 文案；
- `vendor_snmp_writable` 只能展示证据，不能触发 SNMP SET。

## 9. 验收

必须用实际实现证明：

1. 五 Profile 的默认 fixture 都能生成唯一 registry；
2. scalar、单索引、复合索引 encode/decode property test 通过；
3. `+`、前导零、`-0`、空项、escaping 和非规范 ID 全部拒绝；
4. 相同 numeric tuple 不产生第二条 alias path；
5. index position 而不是 JSON key 顺序决定 row-key；
6. 未实例化 row、optional 未启用和 unknown syntax 不可写；
7. identity/index 永远 read-only；
8. runtime/vendor writable 分离；
9. availability 动作不改 Profile scalar；
10. 多设备只公开一个全局 revision/event 序列；
11. 并发、rollback 和幂等测试通过；
12. 独立审计无 P0/P1。

实际命令、结果、随机种子和未验证边界已写入
`verification/L03_RUNTIME_STATE_REPORT.md`。当前 row-key 500 轮确定性往返、
合法 patch 200 轮、非法 batch 100 轮、100/101 batch 边界以及单/多设备
并发均有自动证据；Hypothesis 未安装，以固定种子测试替代。三轮独立审计为
P0=0/P1=0，问题清单已回填，实现与证据已由 commit `91e5ffb4dd69`
固定。本 ADR 状态为 `Accepted`。

## 10. 未验证边界

本 ADR 不证明：

- L4 已正确把 numeric tuple 编码为实例 OID；
- SNMP SET 可用；
- Agent 缓存、Trap 或 lifecycle 正确；
- REST/WS 客户端已经迁移到新 path；
- UI 能展示/编辑大表；
- topology 的端口和 route 语义；
- 原始 MIB、现场设备或目标固件兼容性。
