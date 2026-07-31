# L1 MIB 独立 Golden 契约

> 状态：Accepted for local curated device dictionary snapshot
> 更新日期：2026-07-31
> 适用范围：L1 只建立厂家对象和项目兼容证据，不修改 Simulator runtime、Profile、SNMP Agent、Dashboard 或前端。
> 来源保证：`local-curated-snapshot-not-verified-against-original-mib-in-this-run`；
> 本轮最终 Golden 的构建与验收只使用仓库内设备字典；原始 MIB 不作为
> Golden 输入、运行依赖或验收依据。

## 1. 下层契约依赖

- `L00_BASELINE_AND_ENVIRONMENT.md` / status=`Accepted for Windows local port mode`
- `ADR-001-LOCAL_ADDRESS_MODES.md` / status=`Accepted`

L1 只依赖 L0 提供的可复现环境，不从现有
`backend/simulator/profiles.py`、renderer 或运行时返回值反推厂家协议事实。

## 2. 事实来源和禁止来源

本层采用以下固定来源策略：

1. 厂家对象的 OID、SYNTAX、MAX-ACCESS、枚举、范围、单位、INDEX 和
   optional group，**只允许来自本仓库**
   `docs/reference/docs/devices/*.md`。
2. 多 Profile 接入、数据源优先级、设备准入和 formal/legacy Trap 边界来自
   `docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md`。
3. `docs/reference/GD_MIB_DIFF_REGISTER.md` 仅用于理解历史修订和资料缺口，
   不替代设备字典中的逐对象定义。
4. 本层不访问仓库外原始 MIB，不把仓库外文件路径写成 golden 的运行依赖。
5. 不得从 `PROFILE_DEFINITIONS`、Simulator 默认值、前端字段或现有测试生成
   golden expected。

因此，golden 是现有实现的独立审查源，而不是现有实现的序列化副本。

## 3. 交付文件

```text
backend/tests/golden/simulator/
  ccdm.objects.json
  visionxs_cpu.objects.json
  visionxs_con.objects.json
  dp12_mux_atc.objects.json
  ccdc_legacy.objects.json
  trap_formal.json
  trap_legacy_dashboard_v1.json
```

对象 manifest 与 Trap fixture 是两类不同契约：

- `*.objects.json` 描述厂家对象定义和访问实例规则；
- `trap_*.json` 描述通知 OID、varbind 布局和证据等级。

## 4. 对象 manifest 顶层结构

每份 `*.objects.json` 至少包含：

| 字段 | 约束 |
|---|---|
| `schema_version` | 当前为整数 `1` |
| `manifest_kind` | 固定为 `simulator-mib-object-golden` |
| `profile_id` | 与文件名和 L1 Profile 标识一致 |
| `evidence_status` | `local-device-dictionary-snapshot` 或 `legacy-unverified` |
| `source_contract` | 固定来源保证、生成器、独立性和禁止输入 |
| `sys_object_id` | 完整数值 `sysObjectID`；证据不足时仍需标明其来源等级 |
| `source_documents` | 四个厂家对象 manifest 仅列本仓库 `docs/reference/docs/devices/*.md` 及内容哈希；无厂家对象字典的 CCDC 只列兼容性计划 |
| `object_count` / `gettable_count` / `not_accessible_count` / `table_count` | 与数组实际内容一致的审计计数 |
| `tables` | 表、Entry、INDEX 顺序、允许范围和 optional group |
| `objects` | 独立对象数组，不由 Profile 代码生成 |

`source_contract.source_assurance` 必须为
`local-curated-snapshot-not-verified-against-original-mib-in-this-run`，且
`independent_of_simulator_profiles=true`。

四个有设备字典的 Profile 使用
`source_contract.authority=local-curated-device-dictionary-snapshot`；CCDC
没有厂家对象字典，只能使用
`project-compatibility-plan-legacy-boundary`，不得伪称设备字典 authority。

每个对象至少包含：

| 字段 | 含义 |
|---|---|
| `name` | 厂家对象名；不得用 UI label 替代 |
| `module` | 对象所属厂家模块或 `legacy-unverified` |
| `oid` | 对象定义 OID，不把 fixture 行号拼入定义 |
| `kind` | `scalar`、`table`、`entry`、`index` 或 `column` |
| `syntax` | 设备字典记录的 SMI 类型；字典未记录 table/Entry 的 ASN.1 行类型名时必须为 `null`，不得按对象名推造 |
| `max_access` | `read-only`、`read-write` 或 `not-accessible` |
| `enum` / `range` / `unit` | 未定义时必须为 `null`，不得猜测 |
| `index_order` | 表列实例的索引顺序；scalar 为空数组 |
| `optional_group` | 无证据时为 `null`，不能默认假定存在 |
| `source` | 本仓库设备字典文件和精确行号 |
| `gettable` | 只有可访问叶对象可为 `true` |
| `get_oid_template` | scalar 使用 `.0`；列使用声明顺序的索引占位符 |

禁止用字段缺失表达“不知道”。未知事实必须显式使用 `null`、空数组或
`legacy-unverified`。

## 5. 三类事实必须分离

### 5.1 对象定义

对象定义回答：

- 对象基础 OID 是什么；
- 它是 scalar、结构对象、索引还是可读/可写列；
- 类型、权限、枚举、范围、单位和索引顺序是什么。

对象定义不会因为某个模拟拓扑没有实例行而消失。

### 5.2 索引允许范围

设备字典中的 `1..20`、`1..2000`、`1..4` 等范围只表示合法索引值域。
它不表示设备一定安装了该数量的风扇、模块、卡或通道。

复合索引必须保留原顺序。例如卡端口、模块风扇和 DWC 链路不能被简化成
“只取 OID 最后一段”。

### 5.3 fixture 实际行

fixture 行属于后续 L2/L3 的显式设备/拓扑实例配置，不属于 L1 对象 manifest。
L1 不生成最大索引范围内的全部行，也不以 UI 展示数量推断行数。

上层只有在明确引用 L1 的表定义和索引规则后，才能声明 fixture 实际存在行。

## 6. scalar、表和访问规则

1. scalar 的 `oid` 保存对象定义 OID，`get_oid_template` 必须追加 `.0`。
2. table、Entry 和 `MAX-ACCESS not-accessible` 的 index：
   - `gettable=false`；
   - 不进入直接 GET 计划；
   - 仍保留在 manifest 中，用于审查结构和 INDEX。
3. 可读列的 `get_oid_template` 必须按 `index_order` 追加全部索引。
4. OID 唯一性按对象定义 OID 检查；同一表内列号不得重复。
5. 表发现应 WALK 可读列，不应 GET 结构对象或以最大范围合成行。
6. `read-write` 仅表示设备字典记录的权限，不表示当前平台允许发出 SET。
   DP 的六个写对象在 L1 保留真实权限，但 Simulator 和 Dashboard 的 SET
   仍由上层安全契约决定，当前默认禁用。

## 7. Profile 证据状态

| Profile | L1 证据状态 | 契约 |
|---|---|---|
| `ccdm_matrix` | `local-device-dictionary-snapshot` | 必须覆盖设备字典的 20 张表及全部已列对象 |
| `visionxs_cpu` | `local-device-dictionary-snapshot` | 独立设备；不得并入矩阵 CPU 行 |
| `visionxs_con` | `local-device-dictionary-snapshot` | 独立设备；不得并入矩阵 CON 行 |
| `dp12_mux_atc` | `local-device-dictionary-snapshot` | 通道模型；保留 6 个 read-write 事实但不授权 SET |
| `ccdc_legacy` | `legacy-unverified` | 当前资料缺少 CCDC/CCC 原始对象定义；不得从 CCDM 换前缀推导 |

`cc160` 和 `ccdm` 的本仓库字典快照描述同一 CCDM 协议资料，不建立第二个
独立 Profile。本轮 Golden 没有使用或重新核验原始 MIB；
`local-device-dictionary-snapshot` 只表示由本仓库设备字典整理，不表示
本轮完成原始 MIB 独立复核。

## 8. 独立验证规则

L1 测试至少断言：

- 五份对象 manifest 不导入 `backend/simulator/profiles.py`；
- 文件名、`profile_id`、证据状态和 `sys_object_id` 一致；
- 所有 OID 为规范数值字符串且在单一 manifest 内唯一；
- 每张表列号唯一；
- scalar 的 GET 实例以 `.0` 结尾；
- table、Entry、index 和 `not-accessible` 对象不可 GET；
- 表列索引模板与 `index_order` 完全一致；
- enum key、range 和默认 fixture 事实不混写；
- CCDM 表数是 20；
- CCDC 为 `legacy-unverified`，且没有伪造厂家对象；
- Trap fixture 使用独立测试，不混入对象 manifest 计数。

测试通过只能证明本仓库静态契约自洽；不能替代真实设备 GET/WALK/Trap。

## 9. 上层不得重新解释的事实

L2 及以上不得：

- 改写 OID、SYNTAX、MAX-ACCESS、枚举和 INDEX 顺序；
- 把 `legacy-unverified` 提升为厂家验证；
- 把 optional group 当成所有设备必有；
- 把索引范围当成 fixture 行；
- 为未定义的字符串传感器增加厂家单位或阈值；
- 通过公共字段名跨产品复制对象。

需要改变这些事实时，必须先修改本层 golden、来源行和独立测试，再升级上层。

## 10. Accepted 验收证据

以下证据已全部写入
`verification/L01_MIB_COVERAGE_REPORT.md`，构成本文件的 Accepted 依据：

1. 七份 golden 文件全部存在且 JSON 可解析；
2. 独立 golden 测试通过；
3. 覆盖报告列出每 Profile 的对象、表、权限和缺口实际计数；
4. Trap formal/legacy 独立断言通过；
5. SIM-MIB-001 至 SIM-MIB-005 以及 SIM-TRAP-002/003 的 L1 事实部分更新；
6. 仍未验证的实机、固件和 CCDC 边界明确保留。
