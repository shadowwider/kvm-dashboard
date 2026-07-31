# ADR-002：Profile 命名、身份与版本

> 状态：Accepted
> 日期：2026-07-31
> 决策范围：Profile、对象、内部字段和展示 key 的稳定身份；不定义运行时状态路径或 UI 文案。

## 1. 下层契约依赖

- `layers/L00_BASELINE_AND_ENVIRONMENT.md` /
  status=`Accepted for Windows local port mode` /
  `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc`
- `layers/L01_MIB_GOLDEN_CONTRACT.md` /
  status=`Accepted for local curated device dictionary snapshot` /
  `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc`
- `layers/L01_TRAP_EVIDENCE_CONTRACT.md` /
  status=`Accepted for local curated device dictionary snapshot` /
  `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc`
- `layers/L02_PROFILE_MODEL_CONTRACT.md` / status=`Accepted` /
  implementation baseline=`f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc`

依赖工件的精确 SHA-256 见 L02 契约 1.1 节。L0/L1/L2 实际工件已由
`f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` 固定。

## 2. 背景

现有实现混用：

- 厂家 camelCase 对象名；
- Python snake_case 状态字段；
- 页面 fallback 字段；
- 跨产品 `COMMON_SCALARS`；
- 同名但属于不同模块、不同 OID 的对象。

例如 `fanTable` 在 CCDM 的 CON、CPU、DWC 和机框模块中分别存在，
`mainPower` 也存在于多个模块。裸对象名不是全局唯一键。若继续用名字相同
作为复用依据，会重新引入错误 OID、错误默认值和 UI 写入无效字段。

## 3. 决策

### 3.1 Profile ID

当前只接受：

```text
ccdc_legacy
ccdm_matrix
visionxs_cpu
visionxs_con
dp12_mux_atc
```

Profile ID 使用稳定 `lower_snake_case`，表达协议/产品模型，不表达某台设备、
固件、host、port 或页面类型。`cc160` 不建立第二个 Profile；CCDC 不作为
未知 Profile 的 fallback。

现有 `ScenarioDevice`、Bridge manifest 和旧 API 在 L6/L7 契约迁移前仍可
传输 `ccdc_legacy_unverified`、`dp12_mux_atc_readonly`。它们只是 transport
alias，进入 L2 catalog 时必须分别规范化为 `ccdc_legacy`、
`dp12_mux_atc`；不得作为第二套 Profile schema，也不得改变现有 Bridge
序列化行为。

`ccdc_legacy` 的 vendor `ProfileDef` 固定为 `0` objects。为了复现旧项目而
保留的历史 OID 只能属于显式
`project-legacy-compatibility` adapter，不能共享 vendor Profile 身份、
evidence revision 或厂家命名空间。

### 3.2 Profile 识别

Profile 的协议身份由以下组合确定：

```text
profile_id
exact sysObjectID
profile_version
evidence_revision
```

`sysObjectID` 必须完整数值精确匹配。禁止使用企业根、OID 前缀、IP、显示名、
CPU/CON 文字或“最接近的 Profile”回退识别。

### 3.3 厂家对象身份

对象的权威主键是完整数值 OID。可读审查键为：

```text
<MIB module>::<vendor object name>
```

必须同时保留：

- `vendor_name`：L1 `name` 原文；
- `vendor_module`：L1 `module` 原文；
- `qualified_vendor_name`：L1 `qualified_name`；
- `oid`：L1 完整数值对象定义 OID。

不得重写厂家大小写、拼写或枚举 label。裸 `vendor_name` 只能用于显示和搜索，
不能作为跨模块唯一键。

### 3.4 内部规范字段

平台内部使用稳定的 `field_id` / `table_id`：

- 仅含小写 ASCII、数字和下划线；
- 以字母开头；
- 在其 Profile 作用域内唯一；
- 同一个厂家对象在同一 Profile 版本中只能映射到一个规范字段；
- 同名厂家对象跨模块冲突时必须通过领域前缀或 table/module scope 消歧；
- 映射表是显式代码/数据，不能在请求时由正则、UI label 或自动 camelCase
  转换临时生成。

推荐模式：

```text
scalar:       device_id
table:        cpu_module
column:       cpu_module.target_usb_hid
qualified:    ccdm_matrix.cpu_module.target_usb_hid
```

L3 的路径语法由 L3 契约决定，但只能从这些规范 ID 构造，不能直接把厂家名
或 UI label 当成可写路径。

### 3.5 UI label

L2 只提供稳定 `label_key`，例如：

```text
simulator.profiles.ccdm_matrix
simulator.tables.cpu_module
simulator.fields.target_usb_hid
```

中文、英文和其他实际文案属于 L9 i18n 资源。改变显示文案不改变
`field_id`，也不改变厂家对象名。

### 3.6 别名和迁移

内部 ID 一旦被 L3/API 使用后不得静默重命名。需要重命名时：

1. 新增显式版本化 migration；
2. 记录旧 ID → 新 ID；
3. 旧 ID 只能在有期限、可观测的兼容入口解析；
4. schema metadata 只发布新 ID，并携带弃用信息；
5. 不允许同时写入两个状态字段以“兼容”。

厂家对象名变化只能由 L1 evidence 更新触发。UI label 变化不需要字段迁移。

## 4. 版本决策

### 4.1 三种版本不得混用

| 版本 | 表达内容 | 示例 |
|---|---|---|
| `model_schema_version` | L2 序列化结构 | 整数 `1` |
| `profile_version` | 某个 Profile 的平台 schema 兼容性 | `1.0.0` |
| `evidence_revision` | L1 Golden schema + SHA-256 | `schema=1;sha256=<64 hex>` |

Git commit 是交付可追溯性，不代替上述三种版本；SHA-256 也不代替
`profile_version` 的兼容性含义。

### 4.2 Profile SemVer

- **MAJOR**：删除/重命名规范字段、改变类型/索引形状、改变实例键、改变
  sysObjectID 匹配或其他 L3/API 不兼容变更；
- **MINOR**：在 L1 更新后增加对象/表、增加可选能力、增加向后兼容 metadata；
- **PATCH**：不改变 schema 语义的 label key、说明、来源定位或实现修复。

L1 OID、类型、权限、枚举或 INDEX 改变时，即使 Profile SemVer 判断为兼容，
也必须更新 `evidence_revision` 并运行完整等价投影测试。

### 4.3 当前初始版本

五个 Profile 在 L2 首次验收时从 `1.0.0` 开始。`ccdc_legacy` 的 `1.0.0`
只表示“空对象、legacy-unverified 的平台 schema 已版本化”，不表示厂家
对象或实机兼容性已验证。

## 5. 不采用的方案

### 5.1 继续复用 `COMMON_SCALARS`

不采用。相同业务词不证明对象 OID、SYNTAX、枚举、optional 或产品适用性相同。
可以复用纯构造函数和校验器，不能复用未经 Profile 明确声明的厂家事实。

### 5.2 以裸厂家对象名作为内部字段

不采用。CCDM 多模块存在同名对象，且厂家 camelCase 与现有 snake_case 状态
会继续产生冲突。

### 5.3 以 UI label 作为 API 字段

不采用。本地化、文案调整和产品名称变化会破坏状态持久化与客户端。

### 5.4 只用 sysObjectID 或 Git commit 表示版本

不采用。sysObjectID 不表达 schema 演进；Git commit 不表达兼容性；工作树
未提交时更不能伪造归属。

### 5.5 未知设备回退到 CCDC

不采用。`ccdc_legacy` 缺少厂家对象字典；回退会把历史假设提升为协议事实。

## 6. 后果

正向：

- L3 能使用稳定字段而不复制 OID；
- 相同厂家名在不同模块中不再碰撞；
- UI 文案变化不影响 API；
- L1 evidence 改变可被 digest 和等价投影立即发现；
- `SIM-STATE-003` 的命名根因可在 L2 关闭。

代价：

- 需要显式维护 vendor → canonical → label key 映射；
- 首次迁移必须处理已有状态字段别名；
- Profile 变更必须同时判断 SemVer 和 evidence revision；
- 任何后续 schema 变更都必须形成新的可审计提交并重新执行 Gate。

## 7. 验收

必须测试：

1. 五个 Profile ID 和精确 sysObjectID 一一对应；
2. 每个对象 OID、厂家限定名和内部 ID 唯一；
3. CCDM 的重复裸名称不会发生覆盖；
4. 内部 ID 全部符合命名正则；
5. UI label key 与厂家名、内部 ID 分离；
6. evidence digest 不匹配时加载或 Gate 失败；
7. CCDC 保持空对象和 `legacy-unverified`；
8. project legacy adapter 的对象不会进入 CCDC vendor Profile 投影；
9. Profile 模块不导入 UI、socket、state/runtime。

实际命令和结果写入
`verification/L02_PROFILE_MODEL_REPORT.md`。测试、全回归和独立复审已经
通过；实现与证据基线已提交，因此本 ADR 为 `Accepted`。
