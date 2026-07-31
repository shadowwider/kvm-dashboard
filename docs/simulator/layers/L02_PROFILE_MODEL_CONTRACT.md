# L02 Profile 领域模型契约

> 状态：Accepted
> 更新日期：2026-07-31
> 适用范围：把 L1 独立 Golden 转换为可版本化的 Profile schema；不处理运行时状态、UDP/SNMP、Trap 编码、Bridge、WebSocket 或 UI。
> 来源保证：`local-curated-snapshot-not-verified-against-original-mib-in-this-run`

## 1. 下层契约依赖

| 下层交付 | 状态 | Git / 版本边界 | L2 使用方式 |
|---|---|---|---|
| `layers/L00_BASELINE_AND_ENVIRONMENT.md` | `Accepted for Windows local port mode` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | 只继承 Windows 本地可复现环境和测试入口 |
| `decisions/ADR-001-LOCAL_ADDRESS_MODES.md` | `Accepted for L0` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | 只继承本地 `port` 模式，不把地址模式写入 Profile 事实 |
| `verification/L00_CURRENT_REPRODUCTIONS.md` | `Accepted for Windows local port mode` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | 继承测试环境和未验证 Docker 边界 |
| `layers/L01_MIB_GOLDEN_CONTRACT.md` | `Accepted for local curated device dictionary snapshot` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc`；由本节 SHA-256 固定工件 | OID、SYNTAX、MAX-ACCESS、枚举、范围、单位、INDEX、optional 事实的唯一输入 |
| `layers/L01_TRAP_EVIDENCE_CONTRACT.md` | `Accepted for local curated device dictionary snapshot` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc`；由本节 SHA-256 固定工件 | 仅保存 Trap evidence reference；L2 不复制或编码 varbind |
| `verification/L01_MIB_COVERAGE_REPORT.md` | `Accepted for local curated device dictionary snapshot` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | 继承五 Profile 覆盖计数、CCDC 边界和未验证范围 |
| `verification/L01_PROFILE_DRIFT.json` | L1→L2 起始诊断，`ok=false` | schema version `1`，`commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | 保留 L2 修改前的历史差异，不覆盖、不作为厂家事实源 |
| `verification/L02_PROFILE_CATALOG_DRIFT.json` | L2 当前全语义诊断，`ok=true` | schema version `2`，`commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | 记录 L2 catalog、fixture 和完整语义投影的当前结果 |

L0/L1/L2 实际工件已由提交
`f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` 固定。该提交是 L3 可引用的
实现与证据基线；原始 MIB 和现场设备仍不在本轮验收范围内。

### 1.1 L1 Golden 精确固定

L2 依赖以下工作树工件。`schema_version` 均为 `1`：

| 文件 | Profile / 布局 | 证据状态 | SHA-256 |
|---|---|---|---|
| `backend/tests/golden/simulator/ccdm.objects.json` | `ccdm_matrix` | `local-device-dictionary-snapshot` | `dc2fa2a8ef223348be2a49cf2456094099680a54ad58ee60838294ec042a952d` |
| `backend/tests/golden/simulator/visionxs_cpu.objects.json` | `visionxs_cpu` | `local-device-dictionary-snapshot` | `1fa9a8c4ca001cc33ec7c9fe6d7949fe8bb31472f505e028acdbecf1b9d0a08a` |
| `backend/tests/golden/simulator/visionxs_con.objects.json` | `visionxs_con` | `local-device-dictionary-snapshot` | `d40bcf845ae091ef09071d335187bf8f49393b6226bc46c2be728f5581900b40` |
| `backend/tests/golden/simulator/dp12_mux_atc.objects.json` | `dp12_mux_atc` | `local-device-dictionary-snapshot` | `8225e8ecc2d86c2a7c85ebd02040d2bdbbdd0e8b998880e25da77a128c1c81cf` |
| `backend/tests/golden/simulator/ccdc_legacy.objects.json` | `ccdc_legacy` | `legacy-unverified` | `f8027d3567ac23259718f20a63363be2391599652c2255cf532b603a6d52d858` |
| `backend/tests/golden/simulator/trap_formal.json` | `gud-general-notification-formal-v1` | 本地设备字典快照 + 已分类捕获 | `db6f15fb02ccdff11f644b626d34dcb5042cb30576b60f236000b46529cda47f` |
| `backend/tests/golden/simulator/trap_legacy_dashboard_v1.json` | `legacy-dashboard-simulator-v1` | 项目历史捕获，不是厂家 MIB | `e665fcbbb0f33858a4afd1c925dc0ca7f023f7fe5d3473cb7a0fb0061549c83c` |

任何 SHA-256 改变都必须先回到 L1 复核来源、差异和独立测试，然后显式升级
L2 的 `evidence_revision`。L2 不允许自动接受“最新文件”。

## 2. 本层不得重新解释的事实

L2 必须原样继承：

- L1 给出的数值 OID、对象种类、SYNTAX、MAX-ACCESS、枚举、范围、单位和
  INDEX 顺序；
- scalar 的 `.0` 实例规则，以及 table、Entry、index 不可直接 GET 的事实；
- `read-write` 是厂家对象权限事实，不是 Simulator/Dashboard 已获 SET 授权；
- optional 只表示设备能力可能存在，不表示每个 fixture 默认存在；
- INDEX 最大范围是值域，不是实际模块、端口或通道数量；
- `ccdc_legacy` 是 `legacy-unverified`，其对象 manifest 故意为空，禁止从
  CCDM 替换 OID 前缀生成对象；
- formal Trap 和 `legacy-dashboard-simulator-v1` 是两套独立证据布局，
  `level` 没有厂家枚举或严重度映射。

本轮厂家对象事实只使用仓库内
`docs/reference/docs/devices/*.md` 和 Accepted L1 Golden。兼容性计划中的
仓库外来源路径是历史调研记录，不是本层输入、运行依赖或验收依据；L2
禁止访问、重新核验或引用仓库外原始 MIB/evidence。

## 3. 目标与非目标

L2 只回答：

1. 一个 Profile 包含哪些对象定义；
2. 每个对象怎样被稳定、无歧义地命名；
3. Profile 怎样绑定精确 `sysObjectID`、证据版本和模型版本；
4. fixture 怎样显式选择 optional 能力并声明实际表行；
5. L3 怎样在不读取 UI、socket 或协议实现的情况下消费 schema。

L2 不回答：

- 当前设备实例值、PATCH 路径、revision 或事务；
- ASN.1 编码、GET/GETNEXT/GETBULK/SET 或 EndOfMibView；
- Trap BER、发送、接收、归属和平台 severity；
- Dashboard poll plan、Bridge、REST/WS payload；
- UI label 的中文/英文实际文案、表单控件或虚拟列表；
- 物理拓扑、路由、拖拽和拉线。

## 4. 核心不可变模型

实现必须提供冻结或等价不可变的数据结构：

```text
ProfileDef
 ├─ ScalarDef[]
 ├─ TableDef[]
 │   ├─ IndexDef[]
 │   └─ ColumnDef[]
 └─ evidence / naming / version references
```

### 4.1 `ProfileDef`

至少包含：

| 字段 | 约束 |
|---|---|
| `profile_id` | 稳定的内部 ID，只能是 ADR-002 规定的五个值 |
| `profile_version` | SemVer；描述 L2 schema 的兼容性版本 |
| `model_schema_version` | L2 序列化模型版本，当前从 `1` 开始 |
| `sys_object_id` | 完整数值 OID，匹配方式固定为 `exact` |
| `evidence_status` | 原样继承 L1；不得自行提升 |
| `evidence_revision` | L1 manifest schema version + 文件 SHA-256 的不可变引用 |
| `display_name_key` | 可选的 i18n key；不是厂家对象事实 |
| `scalars` | `ScalarDef` 的不可变序列 |
| `tables` | `TableDef` 的不可变序列 |
| `trap_evidence_refs` | 可选的 L1 fixture ID + SHA-256 引用；不得复制通知对象定义 |

Profile 不得保存 host、port、community、设备 ID、实例值、表行、运行状态、
WebSocket topic 或 UI 组件配置。

当前 Python 实现采用 `schema_version`、`evidence_version`、
`source_manifest_sha256`、`canonical_field`、`ui_label` 等字段名；其中
`ui_label` 保存的是 i18n key，而不是硬编码中文/英文文案。它们分别对应本节
的 model schema、evidence revision、field ID 和 label key 语义。

### 4.2 `EnumDef`

至少包含：

- `type_name`：L1 SYNTAX 名；
- `labels_to_values`：厂家标签到整数值的原样映射；
- 可选内部展示 key 映射，但不得修改厂家标签和值。

枚举值必须是整数。fixture 中有默认/初始值时，该值必须属于枚举值集合。
L2 不从名字、UI 文案或历史状态值补充厂家未定义枚举。

### 4.3 `IndexDef`

至少包含：

- 厂家对象名、厂家模块名和 `MODULE::name`；
- 内部规范 `field_id`；
- 数值对象 OID、SYNTAX、允许范围；
- 在表 INDEX 中的零基 `position`。

`IndexDef` 描述索引结构，不保存某一行的实际索引值。复合索引顺序必须与
L1 `index_order` 完全一致，不能排序、折叠或只保留最后一段。

### 4.4 `ScalarDef`

至少包含：

- 厂家对象名、`MODULE::name`、内部 `field_id`、`label_key`；
- 对象定义 OID和 `.0` 实例模板；
- SYNTAX、MAX-ACCESS、枚举、范围、单位；
- compliance / optional 能力标记；
- L1 来源引用和证据 revision；
- MIB 默认值（若 L1 明确定义）；不得保存 fixture 初始值。

### 4.5 `ColumnDef`

字段与 `ScalarDef` 的共同约束一致，另外必须包含：

- 所属 `table_id`；
- 列对象定义 OID及从 Entry OID 得出的列号；
- 与 `TableDef.indexes` 一致的 `index_order`；
- 完整实例 OID 模板。

同一 `TableDef` 不允许重复列号，单个 Profile 不允许重复对象定义 OID。

### 4.6 `TableDef`

至少包含：

- 厂家 table/Entry 对象名、模块名和限定名；
- 内部稳定 `table_id` 和 `label_key`；
- table OID、Entry OID；
- 有序 `IndexDef`；
- 有序 `ColumnDef`；
- table/Entry 的 L1 结构事实和来源引用。

同名 `fanTable` 等厂家对象可存在于不同模块。实现必须以完整数值 OID和
`MODULE::name` 区分，不能以裸 `name` 或公共 Python 常量合并。

## 5. 三层命名契约

每个可读对象必须同时保留三层名称：

| 层 | 示例 | 用途 | 能否作为厂家事实 |
|---|---|---|---:|
| 厂家对象名 | `targetUsbHid` | MIB/Golden 对照和诊断 | 是 |
| 内部规范字段 | `target_usb_hid` | L3 状态键、API path 的稳定输入 | 否，属于平台设计 |
| UI label key | `simulator.fields.target_usb_hid` | L9 本地化展示 | 否 |

厂家身份的唯一键是完整数值 OID，审查键为 `MODULE::name`；裸厂家对象名
不保证跨模块唯一。内部字段统一使用 `lower_snake_case`，UI 只能通过
`label_key` 找文案，不能把中文、英文标题反向转换成字段名。

重名、别名和版本升级规则见
`decisions/ADR-002-PROFILE-NAMING-AND-VERSIONING.md`。

## 6. Profile 与 L1 Manifest 的等价投影

实现必须提供确定性的 `ProfileDef -> L1 object projection`。投影至少逐对象
比较以下字段：

```text
module, name, qualified_name, oid, kind, syntax, max_access,
enum, range, unit, index_order, compliance, optional_group,
gettable, writable, instance_rule, get_oid_template, source
```

L2 的 `field_id`、`table_id`、`label_key` 和 Profile 版本是附加平台元数据，
不参与改写 L1 字段。比较规则：

1. L1 对象集合和 L2 投影集合完全相等；
2. 不允许缺失、多余或重复 OID；
3. table/Entry/index 必须保留，不得只比较可 GET 叶；
4. CCDC 投影对象集合必须为空；
5. Profile loader 不得读取 `backend/tests/golden` 作为生产运行时数据源；
6. 测试从独立 Golden 加载 expected，再与 L2 投影比较，禁止反向生成 expected。

`ccdc_legacy` 的 vendor `ProfileDef` 必须保持 `0` objects。现有模拟器历史 OID
若为回归目的暂时保留，只能进入单独命名、证据状态为
`project-legacy-compatibility` 的 compatibility adapter；它不得进入 vendor
Profile 投影、不得被描述为 CCDC 厂家对象，也不得被未知设备自动选中。

若生产 catalog 由工具生成，生成输入也只能是本仓库 Accepted L1 Golden，
并且生成产物必须可审查、可重复、由上述 SHA-256 固定。

`L01_PROFILE_DRIFT.json` 只诊断 L2 修改前的 OID 集合、表数和字面初始值
合法性，必须作为历史起点保持 `ok=false`。L2 不得覆盖该文件；当前结果写入
`L02_PROFILE_CATALOG_DRIFT.json`。即使 L2 当前报告为 `ok=true`，Gate 仍必须
逐对象比较 `syntax`、`max_access`、`enum`、`range`、`unit`、
`index_order`、`optional_group`、来源和 evidence revision，不能只看总布尔值。

## 7. Optional 能力和 fixture 实例

Profile 定义、能力选择和实例值必须是三种不同对象：

```text
ProfileDef                   # 全部定义
FixtureProfileConfig         # 该 fixture 启用哪些 optional 能力
FixtureDeviceValues          # scalar 值和显式 table rows
```

当前内置实例固定在
`backend/simulator/catalog/l2_default_fixtures.json`，SHA-256 为
`57e634931337d41f0e55aaa4588f2cfa4146c66ec3ba5e59690c3d9285503a57`。
生产 loader 只读该静态工件并用 `FixtureSpec` / `FixtureRow` 全量校验；不得
在运行时按字段名、SYNTAX 或 index 上限猜测缺失值。

规则：

1. optional 对象保留在 `ProfileDef`，默认不实例化；
2. fixture 必须显式列出 `enabled_optional_groups`；
3. 未启用 optional group 时不得生成其 scalar `.0` 或表行；
4. 表未提供 `rows` 时实例数为 `0`；
5. 每行必须显式给出完整有序索引和字段值；
6. 索引范围只用于验证，不参与行生成；
7. 禁止 `range(1, max+1)`、笛卡尔积或按 UI 数量隐式补行；
8. fixture 值必须通过 enum/range/类型检查；验证失败不得产生部分实例。

详细取舍见
`decisions/ADR-003-OPTIONAL-GROUP-AND-FIXTURE-ROWS.md`。

## 8. Metadata 契约与性能预算

L2 的 Profile metadata 是 schema metadata，只能描述：

- Profile ID / version / evidence；
- scalar、table、column、index 定义；
- 三层命名；
- 类型、枚举、范围、单位、访问和 optional 能力；
- L1 evidence reference。

它不得包含某个 fixture 的值、行、路径、运行状态或按索引展开的字段。
因此 metadata 大小只随对象定义数增长，不随 fixture 行数增长。

Candidate 预算：

| 指标 | 上限 |
|---|---:|
| 单 Profile 紧凑 JSON | `256 KiB` |
| 五 Profile 合计紧凑 JSON | `512 KiB` |
| 单次生成五 Profile metadata（热进程） | `100 ms` |
| CCDM metadata 定义叶数量 | `142`，不得展开成当前约 `4428` 个实例字段 |

当前已记录基线为 CCDM metadata `975,114 bytes`、`4428` 个实例字段、约
`4.09 ms`。L2 目标不是单纯追求更快，而是只输出 schema 与 row-key template，
彻底移除按 fixture 行展开的字段；行键模板只能描述 INDEX 形状，不能带实际
row index 或 value。

验收测试必须构造 `0` 行和大量显式行的两个 fixture，并断言 Profile metadata
字节完全相同。时间结果应记录在 L02 验证报告；超预算时必须先压缩 schema
引用或提供分页式 schema API，不能删除 L1 对象。

## 9. L3 唯一消费接口

L2 至少向 L3 提供以下纯 schema 能力，具体 Python 名称可不同，但语义必须
等价：

```text
get_profile(profile_id, profile_version=None) -> ProfileDef
iter_object_definitions(profile) -> ordered immutable definitions
project_l1_manifest(profile) -> deterministic object projection
validate_fixture_schema(profile, fixture_config) -> validated fixture input
profile_metadata(profile) -> schema-only serializable mapping
```

接口要求：

- 相同输入产生相同顺序和内容；
- 返回对象不能被调用者原地修改；
- 不导入 `state.py`、`snmp_agent.py`、FastAPI、WebSocket 或前端资源；
- 不打开 UDP socket，不读写数据库、topology store 或 runtime JSON；
- fixture 校验只验证结构和值域，不建立 revision、event 或可写路径索引；
- L3 不得绕过这些接口重新维护 OID、枚举或命名映射。

## 10. 验收矩阵

| 验收项 | 通过条件 | 当前状态 |
|---|---|---|
| 五个 `ProfileDef` | 精确 sysObjectID、证据状态和版本均固定 | PASS |
| L1 等价投影 | 五份对象 manifest 全字段投影完全匹配 | PASS |
| CCDM 差异 | 20 表、142 可 GET 叶；缺 0、多 0、非法初始值 0 | PASS |
| 对象唯一性 | 无重复 OID；同表无重复列号 | PASS |
| 命名 | vendor / canonical / UI key 三层均存在且无冲突 | PASS |
| optional | 默认不实例化；显式启用后才可提供值 | PASS |
| fixture rows | 所有行显式；无范围/笛卡尔积生成 | PASS |
| metadata | schema-only，并满足大小/时间预算 | PASS |
| 分层边界 | Profile 代码无 UI、socket、state/runtime 依赖 | PASS |
| 回归 | L0、L1、现有 Simulator 回归全绿 | PASS（99 项） |

建议从 `backend` 执行：

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\test_simulator_profile_model.py `
  tests\test_simulator_profile_golden_drift.py `
  tests\test_simulator_profiles.py -q
```

再执行 L0、L1 和 Simulator 全回归。实际命令、退出码、计数、metadata
字节/时间和环境必须记录到
`verification/L02_PROFILE_MODEL_REPORT.md`，不得把计划命令写成已通过。

## 11. Gate L2

本契约只有在以下全部成立后才能从 `Candidate` 改为 `Accepted`：

1. 五个 Profile 的 L1 等价投影全部通过；
2. `L01_PROFILE_DRIFT.json` 保持 L2 修改前的 `ok=false` 历史证据，
   `L02_PROFILE_CATALOG_DRIFT.json` 的当前全语义结果为 `ok=true`；
3. L1 全字段语义投影（含 syntax/access/enum/range/unit/index/optional/
   evidence）完全匹配，不能只看 drift 的 OID/表数/默认值结果；
4. 所有 fixture 初始值通过类型、enum 和 range 校验；
5. optional 默认关闭且每张表行均来自显式 fixture；
6. metadata 只含 schema + row-key template、不展开实例，并满足预算；
7. Profile 代码可被 L3 以纯 schema 接口消费；
8. `SIM-STATE-003` 的三层命名根因和 `SIM-UI-003` 的 schema 膨胀根因关闭；
9. L0/L1/L2 专项和现有 Simulator 回归通过；
10. 独立审计无 P0/P1；
11. L0/L1/L2 工件形成可审计 Git 提交，上层可使用真实 `commit=<sha>` 引用。

当前结论：`Accepted`。
`verification/L02_PROFILE_MODEL_REPORT.md` 已记录代码、工件、测试和独立
复审结果；L0/L1/L2 实际工件已由
`f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` 固定，L3 可以正式开发。
