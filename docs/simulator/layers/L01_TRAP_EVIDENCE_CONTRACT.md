# L1 Trap 证据契约

> 状态：Accepted for local curated device dictionary snapshot
> 更新日期：2026-07-31
> 目的：固定厂家 formal Trap 与项目 legacy Trap 的独立事实，防止上层继续混用 OID 或发明 `level` 严重度。
> 来源保证：`local-curated-snapshot-not-verified-against-original-mib-in-this-run`；
> formal OID 来自仓库内设备字典；原始 MIB 不作为本 Trap fixture 的输入、
> 运行依赖或验收依据。

## 1. 下层契约依赖

- `L00_BASELINE_AND_ENVIRONMENT.md` / status=`Accepted for Windows local port mode`
- `L01_MIB_GOLDEN_CONTRACT.md` / status=`Accepted for local curated device dictionary snapshot`

本文件只定义 Trap 事实与证据等级。Trap BER 编码、发送、接收、设备归属、
平台 severity 策略和 UI 展示分别由 L4、L6、L9 决定。

## 2. 权威来源

厂家 formal Trap 的 OID、类型和对象列表只来自本仓库设备字典：

- `docs/reference/docs/devices/ccdm-controlcenter-digital.md:136-142`
- `docs/reference/docs/devices/visionxs-cpu-con.md:89-97`
- `docs/reference/docs/devices/dp12-mux-atc.md:114-120`
- `docs/reference/docs/devices/cc160-controlcenter-digital.md:119-125`

formal/legacy 的交互分类和现场/本地日志边界来自：

- `docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md:136-176`

本层不访问仓库外原始 MIB，也不把仓库外文件作为 fixture 依赖。

## 3. formal：厂家通用通知

`trap_formal.json` 固定以下布局：

| 角色 | 名称 | OID / 值 | 类型与约束 |
|---|---|---|---|
| 标准封装 | `sysUpTime.0` | `1.3.6.1.2.1.1.3.0` | SNMPv2 通知封装；不是厂家 `OBJECTS` 的第三个对象 |
| 标准封装 | `snmpTrapOID.0` | `1.3.6.1.6.3.1.1.4.1.0` | 值必须为厂家通知 OID |
| 厂家通知 | `generalNotification` | `1.3.6.1.4.1.32828.2.1.0.4` | `NOTIFICATION-TYPE` |
| 厂家变量 | `level` | `1.3.6.1.4.1.32828.2.1.0.2` | `Integer32`、read-only、**无枚举** |
| 厂家变量 | `message` | `1.3.6.1.4.1.32828.2.1.0.3` | `DisplayString`、read-only |

厂家 `OBJECTS` 只有 `{ level, message }`。接收器必须同时核对
`snmpTrapOID.0` 的值和两项厂家 varbind，不能仅凭 `.2`、`.3` 或企业根命中。
额外 varbind 必须原样保留，不应被静默删除。

### 3.1 formal 适用性

当前设备字典支持：

- `ccdm_matrix`
- `visionxs_cpu`
- `visionxs_con`
- `dp12_mux_atc`

这些字典包含同一通用通知定义，但不证明每台产品/固件默认启用或一定发送。

`ccdc_legacy` 仅有本仓库现场日志观察到 formal 布局；由于缺少 CCDC/CCC
对象字典，其状态只能是 `capture-observed-only`，不能写成厂家 MIB 已验证。

## 4. formal level 的硬边界

`level` 是未枚举 `Integer32`。L1 明确禁止：

- 把 `2/3/5` 写成厂家 `critical/warning/info`；
- 把同一 level 自动解释为“进入告警”或“恢复”；
- 从 message 中出现 `critical` 推导 level 的全局含义；
- 把实机日志出现过的 `0/2/5` 收窄成厂家允许值集合。

上层若需要 severity，必须保存 `raw_level`，再使用独立、可配置且标为
`platform-policy` 的映射。平台映射不能写回此 fixture。

## 5. formal 实机捕获事实

兼容性计划把 `logs/trap_raw.log` 分类为 2026-07-20 的实机记录。当前快照中
可观察到：

- notification 为 `.32828.2.1.0.4`；
- 两项厂家变量为 `.32828.2.1.0.{2,3}`；
- 标准封装含 `sysUpTime.0` 和 `snmpTrapOID.0`；
- 观察到的 raw level 包含 `0/2/5`；
- message 有“值变化”“进入状态”“离开状态”和人工测试等自由文本。

fixture 中只保存脱敏后的代表行。设备地址、设备编号和现场标识不复制到
golden。

这些捕获只证明该现场样本的报文布局，不证明：

- 任何 level 的厂家全局含义；
- 进入/离开或恢复的结构化语义；
- 每个 Profile、型号和固件都支持相同消息模板。

## 6. legacy-dashboard-simulator-v1

`trap_legacy_dashboard_v1.json` 只用于复现项目历史本地模拟器流量：

| 角色 | OID / 值 | 证据等级 |
|---|---|---|
| `snmpTrapOID.0` 的值 | `1.3.6.1.4.1.32828.5.0.4` | 本仓库 loopback 历史捕获 |
| legacy level | `1.3.6.1.4.1.32828.5.1.0.2` | 本仓库 loopback 历史捕获 |
| legacy message | `1.3.6.1.4.1.32828.5.1.0.3` | 本仓库 loopback 历史捕获 |

其规范名称必须是 `legacy-dashboard-simulator-v1`。它：

- 不是 G&D formal MIB；
- 不是实机协议证据；
- 不能成为 CCDM、VisionXS 或 DP 的默认 Trap；
- 不能证明 CCDC 厂家语义；
- 只能作为 Dashboard 历史兼容输入。

现有实现中的 legacy notification
`1.3.6.1.4.1.32828.5.1.0.4` 与捕获不一致。L1 fixture 将其记录为已知不兼容
OID；实际编码修复属于 L4。

## 7. 捕获行和协议定义必须分离

Trap fixture 同时保存两层信息：

1. `notification`、`vendor_objects` 或 `capture_derived_objects`：
   协议/兼容布局；
2. `capture_evidence.fixture_rows`：
   脱敏后的实际观察行。

观察行中的 level、message 和日期不能被提升为协议枚举、触发规则或支持矩阵。
日志后续追加也不应自动改写 formal OID 定义。

## 8. L4/L6 必须继承的断言

L4 协议测试必须：

- 独立加载两份 Trap fixture；
- 对原始 BER 捕获断言 `snmpTrapOID.0`、level 和 message 的准确 OID；
- formal 和 legacy 各自发送/接收，禁止共享 notification 常量；
- formal 使用 `.32828.2.1.0.4`；
- legacy 使用 `.32828.5.0.4`，而不是 `.32828.5.1.0.4`；
- 保留未知 varbind 和 raw level；
- 发送失败进入可见错误状态。

L6 归属测试必须：

- 在多设备同 host 时避免单结果 host 查询；
- 保存来源、接收时间、`snmpTrapOID.0`、raw level、message 和全部 varbind；
- 把设备归属事实与 severity 策略分开；
- 单独验证 port 与 loopback 地址模式。

## 9. Accepted 验收证据

以下证据均已具备：

1. 两份 JSON 可解析；
2. formal notification 与两项厂家对象均有本仓库设备字典来源；
3. formal/legacy notification OID 和变量组合独立断言；
4. `level.enum=null`、`severity_mapping=null` 被测试锁定；
5. legacy 被明确拒绝作为 vendor MIB 事实；
6. 覆盖报告记录实际测试命令和结果。
