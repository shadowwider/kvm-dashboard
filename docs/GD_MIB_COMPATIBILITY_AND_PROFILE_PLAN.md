# G&D MIB 兼容性、证据分类与多 Profile 接入计划

> 状态：调研结论，尚未实施 Profile 架构。
> 更新：2026-07-26
> 适用项目：`H:\WORK\I\kvm-dashboard`

## 1. 本文用途

本项目需要接入多类 G&D KVM/矩阵设备，不能再把任意 `1.3.6.1.4.1.32828.*` 的 `sysObjectID` 替换进同一份 CCDC OID 表。本文件记录：

- 已调研的设备/MIB 家族及其边界；
- 当前系统能够复用、不能复用和必须重构的部分；
- Trap、实机日志和旧本地模拟器日志的证据分类；
- 后续实施的 Profile 架构、准入规则和工作量；
- 后续维护者需要优先阅读的原始参考资料。

本文中的“已证实”仅表示由 MIB 或已定位的实机日志支持；不表示所有厂商型号或固件均相同。

## 2. 最重要的原始参考资料

### 2.1 单一入口文档

后续工作首先阅读本项目内的固定快照：

```text
/docs/reference/GD_MIB_DIFF_REGISTER.md
```

该文件来自：

```text
H:\WORK\I\kvm\new\kvm-snmp-monitoring-docs\DIFF-REGISTER.md
```

来源仓库在本次调研时的提交为 `cb1e29a`。该台账是唯一应作为多 Profile 实施入口的文档：它列出资料覆盖范围、MIB 版本/证据边界、产品间差异、通用 Trap 限制、CCC/CCDC 所缺资料，以及正式实施应以 `docs/devices/` 字典为准的规则。

本地采用**复制快照**而非文件系统链接，以保证 Git 克隆、CI、GitHub 渲染和其他开发机均可访问。原始仓库更新后，必须比对其新版本并更新快照，同时记录来源提交。

### 2.2 不可省略的次级资料

单一入口文件不足以直接写 OID；实现某个 Profile 前，必须读取来源仓库中对应的数据字典：

| Profile | 必读来源文件 |
|---|---|
| `ccdm_matrix` | `H:\WORK\I\kvm\new\kvm-snmp-monitoring-docs\docs\devices\ccdm-controlcenter-digital.md` |
| `visionxs_cpu` / `visionxs_con` | `H:\WORK\I\kvm\new\kvm-snmp-monitoring-docs\docs\devices\visionxs-cpu-con.md` |
| `dp12_mux_atc` | `H:\WORK\I\kvm\new\kvm-snmp-monitoring-docs\docs\devices\dp12-mux-atc.md` |
| 所有 Profile 的证据/版本/行号 | `H:\WORK\I\kvm\new\kvm-snmp-monitoring-docs\docs\evidence\` |

当前 CCDC/CCC Profile 的原始 `GUD-CCDC-MIB`、CPU、CON、DWC MIB 不在这批资料中。没有这些文件时，不能把 CCDC 的现有 OID 表提升为厂商验证事实。

## 3. Profile 是什么

Profile 不是“每台设备一套接收服务”，而是一个可版本化的协议/能力定义。一个 Profile 应定义：

```text
- 精确 sysObjectID 匹配规则与候选固件/MIB 版本
- 可达性探测 OID
- 允许轮询的标量和表、表索引解析方式
- 数据类型、枚举、单位和可选字段
- 设备/模块/端口实体模型与父子关系
- Trap notification Profile、可识别消息模板
- 允许的 UI 视图和报警策略
- 是否存在 SNMP SET，以及写入的 RBAC、审计和回读要求
```

设备接入时，应先读取标准 `sysObjectID.0`，使用**完整产品 OID**选择候选 Profile，再读取身份、序列号、固件和少量产品专用对象确认。不能仅凭 IP、名称、`32828` 企业根或 UI 中的“CPU/CON”字样识别。

## 4. 提议的 Profile 说明

| Profile | 代表什么 | 精确产品 OID | 当前兼容性 | 识别和使用原则 |
|---|---|---|---|---|
| `ccdc_legacy` | 当前系统假定的 ControlCenter-Compact/CCC 矩阵，以及其 CPU/CON 下联模块 | `1.3.6.1.4.1.32828.3.257.16` | 现有系统的历史原生模型；新资料不能完整证明其字段/表定义 | 仅在实机 GET/WALK 与厂商 CCDC MIB 验证后启用；不能从 CCDM 文档推导出其兼容性 |
| `ccdm_matrix` | ControlCenter-Digital 矩阵/机箱，包含 CPU、CON、DWC、风扇、电源、I/O 卡及端口 | `1.3.6.1.4.1.32828.3.257.10` | CPU/CON 主表与当前端点模型有明显结构匹配；机箱、端口、DWC 和复合索引不兼容 | 先做 CCDM 专用读取计划；CPU/CON 可通过兼容适配器复用矩阵 UI，卡/端口不能伪造为普通 endpoint |
| `visionxs_cpu` | VisionXS-CPU 独立发送端/目标端设备 | `1.3.6.1.4.1.32828.3.768.768` | 不兼容当前矩阵端点假设 | 作为独立 Device/Node；有视频和链路表，不应被合成矩阵下的 CPU 行 |
| `visionxs_con` | VisionXS-CON 独立接收端/控制台设备 | `1.3.6.1.4.1.32828.3.769.768` | 不兼容当前矩阵端点假设 | 作为独立 Device/Node；显示、冻结和链路能力与 CPU Profile 不同 |
| `dp12_mux_atc` | DP1.2-MUX-ATC 独立 DisplayPort KVM 切换器 | `1.3.6.1.4.1.32828.3.1792.17` | 不兼容当前 CCDC 表结构 | 单独的通道/视频/控制台表 Profile；含 `selectedChannel` 与五个 `disable*` 可写 OID，默认必须禁用 SET |

`cc160` 与 `ccdm` 资料包中的六个 MIB 文件 SHA-256 相同，属于同一 `ccdm_matrix` Profile，不是两个协议。

## 5. Trap：正式 MIB 与日志证据

### 5.1 厂商 MIB 定义的通用 Trap

所有本次调研的 CCDM、DP、VisionXS MIB 都使用同一套通用通知：

```text
notification = 1.3.6.1.4.1.32828.2.1.0.4
level        = 1.3.6.1.4.1.32828.2.1.0.2
message      = 1.3.6.1.4.1.32828.2.1.0.3
```

MIB 仅定义：`level` 是未枚举的 `Integer32`，`message` 是 `DisplayString`。MIB **没有**定义 level 到 Critical/Warning/Info 的映射，也没有定义触发条件、恢复规则、Trap 目标、端口、SNMP 版本或确认机制。

因此今后应保存原始 `level`、`message`、`snmpTrapOID.0`、来源、接收时间和所有 varbind；UI 严重度必须明确标记为本平台策略，不能伪称厂商 MIB 语义。

### 5.2 两组日志不能混淆

| 日志 | 时间/来源 | OID 布局 | 分类 |
|---|---|---|---|
| `H:\WORK\I\kvm-dashboard\logs\trap_raw.log` | 2026-07-20，`192.168.0.1` | 正式 `.32828.2.1.0.{2,3,4}` | **实机记录，已确认** |
| `H:\WORK\I\kvm-dashboard\logs\poll_raw.log` | 2026-07-20，`192.168.0.1` | 实机 CCDC/DP 轮询数据 | **实机记录，已确认** |
| `H:\WORK\I\kvm-dashboard\backend\logs\trap_raw.log` | 2026-04-15，`127.0.0.1` | `.32828.5.0.4`、`.32828.5.1.0.{2,3}` | **旧本地模拟器/测试流量，强证据支持** |

之前把 `.32828.5.*` 说成“实际设备捕获布局”是错误的。判断其为旧模拟器/测试流量，不仅因为 OID 不在厂家 MIB 中，还因为来源是 loopback、模块名是 `CPU-{1,2,3}-nnn`/`CON-{1,2,3}-nnn`、多交换机命名和事件文本均与项目模拟器模式吻合。反之，7 月 20 日实机数据使用正式 `.32828.2.*`。

现有代码保留 `.5.*` 仅用于旧本地历史数据/模拟器兼容；后续应将其明确命名为 `legacy-dashboard-simulator-v1`，不能把它当作 G&D 正式 Profile。正式接收路径应匹配完整 `snmpTrapOID.0` 与同一 Profile 的 level/message varbind 组合，不能只凭其中任一个 OID 判断。

### 5.3 实机消息的可用方式

7 月实机日志包含类似：

```text
... entered critical state: 'Offline'
... left critical state: 'Online'
SFP Rx power changed
SFP type changed
Display connection state changed
```

这些消息可用于丰富告警流和在经过模板验证后形成“进入/离开/值变化”的辅助状态。但它们是自由文本，并非 MIB 的结构化 CPU/CON 映射契约。必须按 Profile 和已验证消息模板解析，无法识别时仅保存原文和 raw varbind；不能因为 `level=2` 自动假定“进入告警”或“离线”。

## 6. 当前系统可复用与必须重构的部分

### 可以复用

- FastAPI、APScheduler、pysnmp asyncio transport、快速 `sysObjectID` 健康探测；
- `Device`、状态历史、告警流、WebSocket Hub；
- CCDM CPU/CON 主表的多数列与现有 CPU/CON 矩阵 UI；
- `OIDRegistry` 的显示、归档、告警开关思想。

### 当前不可安全泛化的部分

1. OID Registry 是全局表，没有 `profile_id`、适用固件或能力过滤；当前会把所有已启用表轮询到每台设备。
2. 轮询器只取 OID 最后一段做索引，无法正确表达 CCDM 卡/端口、CPU/CON fan/GPIO、DWC、DP CPU-video 等复合索引。
3. 前端默认两 PSU、两网口、六个风扇和 CPU/CON 矩阵；VisionXS、DP、CCDM 机箱都不满足该通用假设。
4. 当前 CCDC 的通用端口表、温度/风扇数值阈值和字段类型不能自动套用到 CCDM、VisionXS 或 DP。
5. DP 的 SNMP SET 不能进入普通 OID 管理或轮询设置；必须单独做权限、二次确认、审计、回读和失败处理。

## 7. 安全的设备准入流程

```text
1. GET sysObjectID.0
2. 精确匹配候选 Profile 的完整产品 OID
3. GET 该 Profile 的 deviceId/deviceType/serial/firmware
4. WALK 至少一个该 Profile 的只读表，验证表根和索引形状
5. 保存 profile、精确 sysObjectID、固件、序列号、能力探测结果
6. 仅启用该 Profile 定义的 OID 计划
7. 任一步失败或返回 noSuchObject：标记 unknown/unverified，不回退到 ccdc_legacy
```

表的 `INDEX` 上限只代表可取值范围，不代表真实存在的模块、通道或端口；必须 WALK 可读列来发现实际行。可选 error group 的 `noSuchObject` 是能力缺失，不是设备离线。

## 8. 建议实施顺序与工作量

| 阶段 | 交付 | 估计 |
|---|---|---:|
| 0 | Profile 数据模型、MIB/固件证据登记、准入探测、原始 GET/WALK/Trap fixture | 3–5 工程日 |
| 1 | Profile 化 OID Registry、实体/复合索引模型、Profile 专用 poll plan、兼容 API 适配层 | 8–12 工程日 |
| 2 | CCDM Matrix Profile：CPU/CON 兼容矩阵、机箱/卡/端口库存与状态 | 6–10 工程日 |
| 3 | VisionXS CPU/CON 独立节点 Profile | 5–8 工程日 |
| 4 | DP 只读 Profile；若要 SET，另加受控操作链路 | 7–12 工程日 |
| 5 | Profile/能力驱动前端、通用实体详情、回归 fixtures | 8–14 工程日 |

- **只实现 CCDM 并尽量复用现有矩阵 UI：约 14–22 工程日。**
- **实现安全的多 Profile 平台：约 30–49 工程日。**
- 均不含厂商补件、现场设备、固件差异和 30 次以上实机验证等待时间。

## 9. 必须向厂商或现场补齐的资料

1. CCDC/CCC 主机、CPU、CON、DWC 原始 MIB；
2. 每个目标型号/固件实际启用的 SNMP 版本、端口、凭据、USM、ACL 和 Trap 配置；
3. `generalNotification.level` 的厂商严重度、进入/恢复规则；
4. 温度/风扇/电流/电压字符串格式、单位和阈值；
5. 物理端口与模块/槽位映射；
6. 各设备族真实 GET/WALK/Trap 样本和固件清单。

## 10. 后续维护规则

- 不要因一个新 `sysObjectID` 属于 `32828` 企业树就启用旧的 CCDC 全量轮询。
- 新设备先建立 Profile fixture，再更新 OID Registry/前端。
- 不要把 MIB 中未定义的严重度、阈值、恢复语义写成厂商事实。
- 每次厂商 MIB 更新需记录文件版本、SHA-256、适用固件、差异和回归样本。
- `.32828.5.*` 旧本地测试格式不作为生产厂商兼容性依据。
