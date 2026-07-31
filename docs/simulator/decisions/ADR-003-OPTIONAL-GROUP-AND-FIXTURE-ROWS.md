# ADR-003：Optional 能力与 Fixture 行分离

> 状态：Accepted
> 日期：2026-07-31
> 决策范围：对象定义、optional 能力选择和 fixture 实际实例的边界；不定义运行时 PATCH 或 SNMP 缺失对象编码。

## 1. 下层契约依赖

- `layers/L00_BASELINE_AND_ENVIRONMENT.md` /
  status=`Accepted for Windows local port mode` /
  `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc`
- `layers/L01_MIB_GOLDEN_CONTRACT.md` /
  status=`Accepted for local curated device dictionary snapshot` /
  `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc`
- `verification/L01_PROFILE_DRIFT.json` / schema=`1` / `ok=false`
- `layers/L02_PROFILE_MODEL_CONTRACT.md` / status=`Accepted` /
  implementation baseline=`f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc`

L1 Golden 的精确 SHA-256 见 L02 契约 1.1 节。L0/L1/L2 实际工件已由
`f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` 固定。

## 2. 背景

现有 Profile 把三件事混在一起：

1. 厂家定义了哪些表、列和索引范围；
2. 某类设备可能支持哪些 optional 对象；
3. 当前模拟 fixture 实际装了多少模块、卡、端口和通道。

CCDM 因此按允许上限生成 19 张卡、每卡 16 个端口等笛卡尔积。当前精确记录
的 metadata 基线是 `975,114 bytes`、`4428` 个实例字段、约 `4.09 ms`；
问题不是速度数字本身，而是把不存在的实例混进 schema。索引上限只能验证
索引是否合法，不能证明实际硬件行存在。

## 3. 决策

使用三个独立层次：

```text
ProfileDef
  厂家对象全集、索引结构、允许范围、optional 事实

FixtureProfileConfig
  profile_id、profile_version、enabled_optional_groups

FixtureDeviceValues
  scalar_values、显式 table_rows
```

任何生成器、renderer 或 metadata API 都不得把三个对象重新合并成一个含
隐式最大行的字典。

## 4. Optional 能力

### 4.1 定义仍完整保留

L1 标记为 optional 的对象必须保留在 `ProfileDef`，以便审查完整对象集合。
“默认不生成”不等于从 schema 删除。

### 4.2 默认关闭

`enabled_optional_groups` 默认是空集合。未显式启用时：

- optional scalar 没有 `.0` 实例；
- optional table 没有 Entry/column 实例；
- metadata 仍描述它是 optional schema；
- L3/L4 对缺失实例的行为由后续契约定义。

### 4.3 内部 group ID

当前 L1 Golden 保存 compliance 和 optional 布尔事实，没有为所有对象提供
稳定的厂家 group 名。L2 可以为了 fixture 选择定义内部 `optional_group_id`，
但必须：

- 明确标记为 `platform-grouping`，不是厂家 MIB 名；
- 显式列出包含的 L1 对象 OID；
- 在单个 Profile 内唯一且版本化；
- 不扩大 L1 optional 对象集合；
- group 变更触发 Profile 版本评估。

若没有可靠分组依据，允许按对象建立最小 group；不允许因为字段名相似跨
Profile 自动合并。

### 4.4 Read-write 不等于启用 SET

DP 的六个 read-write 对象可以作为 optional fixture 能力提供模拟值，但这
不授权 SNMP SET。SET 的禁止/授权、RBAC、审计和回读属于 L4 及更上层。

## 5. Fixture scalar 值

fixture 初始值必须显式记录在 `FixtureDeviceValues.scalar_values`，不能放入
`ScalarDef` 的通用 `default`。

允许的唯一例外是 L1 明确存在的 MIB DEFVAL，且必须命名为 `mib_default`；
当前五份对象 Golden 的 `default` 均为 `null`，不能从现有模拟器值反推
厂家默认值。

fixture scalar 规则：

1. key 必须解析到当前 Profile 的规范字段；
2. optional 对象必须先启用所属 group；
3. 类型、enum、range 和长度必须通过 schema 校验；
4. 缺少必需 fixture 值时由明确的 fixture builder 报错或采用该 builder
   自己声明、可审查的初始值，不能落回 Profile 隐式厂家默认；
5. fixture builder 初始值也必须纳入测试和序列化输出。

## 6. Fixture table rows

每张表使用显式行：

```json
{
  "table_id": "cpu_module",
  "rows": [
    {
      "indexes": {
        "target_module_index": 1
      },
      "values": {
        "id": "CPU-001",
        "device_status": 2,
        "target_usb_hid": 1
      }
    }
  ]
}
```

复合索引示例：

```json
{
  "table_id": "cpu_module_fan",
  "rows": [
    {
      "indexes": {
        "target_module_index": 1,
        "fan_index": 1
      },
      "values": {
        "fan_name": "CPU-001 fan 1",
        "fan_speed": 3200
      }
    }
  ]
}
```

对象键使用 L2 规范 ID；metadata 同时保留厂家对象名用于审查。

### 6.1 行键

规范行键是按 `TableDef.indexes` 顺序组成的不可变 tuple：

```text
(target_module_index=1, fan_index=1)
```

JSON 对象的字段顺序不能代替 `IndexDef.position`。缺少索引、额外索引、
顺序/名称不匹配、越界或重复 tuple 必须使整个 fixture 校验失败。

### 6.2 禁止隐式扩展

禁止：

- 使用 index `max` 生成 `1..max`；
- 使用两个 index 范围生成笛卡尔积；
- 看到父模块行后自动创建全部子风扇/GPIO/视频/链路行；
- 依据 UI 卡片数、端点数或端口布局补齐行；
- 对缺列静默塞入与厂家 enum/range 不兼容的通用默认值；
- 把 table/Entry/index 结构对象生成成可 GET 实例。

表没有 `rows` 或 `rows=[]` 的含义都是当前 fixture 没有实例，不是 Profile
不支持该表。

### 6.3 允许的复用

可以使用显式 fixture builder 减少重复，但 builder 必须：

- 接受调用者明确传入的行数或索引 tuple；
- 生成结果可以序列化成完整显式行并接受审查；
- 不读取 L1 index max 决定实例数；
- 不在不同 Profile 间复制厂家 OID 或字段；
- 生成后运行与手写 fixture 相同的全量校验。

例如 `make_fan_rows(module_ids=[1], fan_indexes=[1, 2])` 可以生成 2 行；
`make_fan_rows_from_mib_max()` 不允许。

## 7. Metadata 与实例列表

Profile metadata 只描述 schema 与 row-key template，不包含 `rows`、实际
index tuple、实例 path 或当前 value。row-key template 只表达有序 INDEX
名称、类型和范围。实例查看属于 L3/L9 的独立 endpoint。

必须断言：

- 同一个 Profile 在零行、少量行和大量行 fixture 下 metadata 完全相同；
- metadata 字段数等于 schema 定义数，不是实例数；
- optional group 开关不会删除 schema，只影响实例可用性；
- 页面需要实例时必须请求 L3 snapshot/实例 metadata，不得让 L2 展开所有
  可能索引。

## 8. 校验与原子性边界

L2 fixture 校验至少覆盖：

- Profile/version/evidence revision 存在且匹配；
- optional group ID 合法；
- scalar/table/column ID 存在；
- read-only 厂家事实不影响“能否作为模拟初始值”，但不能被误标为 SET 授权；
- scalar/table value 的类型、enum、range；
- 索引名称、数量、顺序、范围和 tuple 唯一；
- optional 对象只有启用后才能实例化；
- 同一对象没有两种来源冲突的初始值。

L2 只返回“整个 fixture schema 有效/无效”。把校验后的 fixture 实例化为
线程安全状态、revision 和事件属于 L3；失败后状态不变的事务语义也由 L3
验收。

## 9. 迁移要求

现有 Profile 中的 `row_source=range`、`row_source=matrix` 和内嵌 `rows`
必须迁出定义层：

1. 先列出当前每张表实际希望模拟的最小行集合；
2. 将集合写进 preset/topology 的显式 fixture 配置；
3. 对每行运行 L2 schema 校验；
4. 删除定义层的范围/矩阵自动生成；
5. 用 L1 Golden 对比，确认 Profile 对象定义没有随行迁移丢失；
6. 对 CCDM 大表记录迁移前后实例数和 metadata 大小。

不得为了保持当前 4480 OID 行为而把最大范围完整抄成 fixture。若专项压力测试
确实需要大实例，应建立名称明确的 stress fixture，不作为默认
`all-profiles` 或回归 fixture。

## 10. 不采用的方案

### 10.1 所有 optional 默认启用

不采用。optional 是能力边界，不是所有设备/固件存在的事实。

### 10.2 以最大范围模拟“全参数”

不采用。“全参数”是 schema 覆盖完整，不是伪造最大硬件库存。

### 10.3 Profile 内保存默认 rows

不采用。这样会再次让对象定义、实例和拓扑耦合，且无法区分不同 fixture。

### 10.4 UI 首次打开时动态生成行

不采用。UI 不是设备事实源；第二浏览器和 SNMP renderer 会产生不同状态。

## 11. 后果

正向：

- 默认 fixture 只包含明确存在的模块/端口；
- metadata 不再按最大索引膨胀；
- optional 缺失可被正确建模；
- L3 能从同一 schema 建立类型化实例键；
- `SIM-MIB-004` 和 `SIM-UI-003` 的 L2 根因可关闭。

代价：

- preset/topology 需要显式维护行；
- 压力测试 fixture 必须单独定义；
- 现有依赖隐式行的 UI/测试需要在 L3 以后迁移；
- L2 通过不代表 L4 的 noSuchObject/EndOfMibView 已正确。

## 12. 验收

必须测试：

1. 五个 Profile 的对象定义不包含 fixture rows；
2. optional group 默认关闭；
3. 未启用 optional 对象不能出现在 fixture value 中；
4. 复合索引顺序和范围严格校验；
5. 重复行、缺索引、额外索引和非法值使整个 fixture 失败；
6. 所有默认 preset 行都能序列化为显式配置；
7. Profile metadata 与 fixture 行数量无关；
8. 代码中不存在从 index max 生成默认行的路径；
9. CCDM 不再默认创建 19×16 的多组端口笛卡尔积；
10. L0/L1/L2 专项、全回归和独立审计通过。

结果记录到 `verification/L02_PROFILE_MODEL_REPORT.md`。实现、测试和独立
复审已经通过；实现与证据基线已提交，因此本 ADR 为 `Accepted`。
