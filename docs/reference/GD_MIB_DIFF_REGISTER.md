# 原 Word 与 MIB 核对差异台账

## 用途与审阅方法

本台账把 Git 基线提交 3c269db 中的 SNMP数据文档.md（原 Word 忠实转换）映射到随附原始 MIB。分类含义：

- **保留**：原声明可由随附资料支持，但必要时补足访问实例或适用范围。
- **修正**：原声明与 MIB 冲突，或其 OID、枚举、权限不完整。
- **删除/降级**：原声明在本批资料中找不到依据；不等于现场一定不成立，只是不应作为本交付的可实施事实。
- **新增**：原 Word 没有、但监控采集/告警实现必须知道的 MIB 事实。

最终实施以 docs/devices/ 为准；SNMP数据文档.md 保留原表主体，用于审阅基线与修订的 Git 差异。建议从仓库内执行：

~~~text
git diff --find-renames 3c269db..HEAD -- SNMP数据文档.md docs/ DIFF-REGISTER.md qa/
~~~

## 资料覆盖与边界

|资料包|已核对的随附 MIB|正式接入文档|结论|
|---|---|---|---|
|cc160|GUD-SMI、GUD-CCDM、GUD-CCDMCPU、GUD-CCDMCON、GUD-CCDMDWC、GUD-GENERALTRAPS|[cc160 / ControlCenter-Digital](docs/devices/cc160-controlcenter-digital.md)|6 个文件；204 个 OBJECT-TYPE（含表、Entry、索引）；无可写对象；1 个通用通知。文件夹名与具体硬件料号无映射证据。|
|ccdm|同上 6 个 MIB|[CCDM / ControlCenter-Digital](docs/devices/ccdm-controlcenter-digital.md)|与 cc160 的 6 份 MIB SHA-256 完全相同；不构成第二套独立协议。204 个 OBJECT-TYPE、20 张表、1 个通用通知；无可写对象。|
|dp|GUD-SMI、GUD-DP12MUXATC、GUD-GENERALTRAPS|[DP1.2-MUX-ATC](docs/devices/dp12-mux-atc.md)|3 个文件；47 个产品 OBJECT-TYPE；4 张状态表；1 个通知；29 个可读监控对象、6 个可写控制对象。|
|vision|GUD-SMI、GUD-VISIONXSCPU、GUD-VISIONXSCON、GUD-GENERALTRAPS|[VisionXS CPU/CON](docs/devices/visionxs-cpu-con.md)|4 个文件；69 个 OBJECT-TYPE；CPU 28、CON 27 个可读业务变量；无可写对象；1 个通用通知。MIB 未给 VisionXS 2.0 的专用对象/适用矩阵。|

每项的文件版本、SHA-256、父子 OID 推导和原文行号见对应的 docs/evidence/ 文件。

## 全局声明的差异

|编号|原 Word 基线声明（对应章节）|分类|MIB 核对结论与修订|依据/去向|
|---|---|---|---|---|
|1|“SNMP v2c/v3，GET/WALK UDP 161，Trap UDP 162”（一、对接概述）|删除/降级|厂商 MIB 的 SNMPv2-SMI 导入仅说明 MIB 语法；四包均未说明设备实际启用版本、端口、community/USM、认证/加密、ACL、Trap 目的地址或设备侧启用步骤。改为厂商/现场确认前提。|四份设备文档“接入方式与实施前提”。|
|2|“所有 OID 均为只读”（一、对接概述）|修正|CCDM/cc160 与 Vision 包的可读叶对象为 read-only；**DP 有 6 个 read-write 标量**：selectedChannel 和 5 个 disable*。|[DP 文档：交互与写操作](docs/devices/dp12-mux-atc.md#交互与写操作)。|
|3|“所有接口数量…完全一致，无遗漏无多余”“全 OID 无问号”|删除/降级|基线把标量对象 OID 当成实例、把表列 OID 当成无索引路径，且遗漏 DP 写对象、可选组、表索引及通用 Trap 的真实定义；绝对准确性声明撤销。|本台账第 6–10 项；各证据台账。|
|4|企业根 1.3.6.1.4.1.32828|保留（注明前提）|厂商 MIB 可证实 gudEnterprise ::= { enterprises 32828 }；数值前缀 1.3.6.1.4.1 是标准 SNMPv2-SMI enterprises 根，不是厂商文件中的数值定义。|各 docs/evidence/ 的 OID 根推导。|
|5|RAID：仅列 failure/resync/recover/ok（1.1）|修正|RaidStatus 还定义 check(3)、repair(4)；不得丢弃中间状态或自行映射健康。|ccdm/GUD-CCDM-MIB.txt:115-126；CCDM/cc160 文档。|
|6|“端口/SFP 状态”统一映射 0–3（1.1）|修正|该枚举只适用于使用 SfpModuleStatus 的对象；CAT 端口等使用不同类型（例如 down/up）。需按每一对象的 SYNTAX 解码。|各设备文档的数据字典。|
|7|“通用 Trap 绑定变量共 4 个；OID …2.1.0.1；gudTrapLevel 1/2/3=Info/Warning/Critical”（十三）|修正|唯一厂商通知为 generalNotification：1.3.6.1.4.1.32828.2.1.0.4，只有 level（.0.2，未枚举的 Integer32）与 message（.0.3）。sysUpTime.0/snmpTrapOID.0 是标准通知封装，不是本厂商 MIB 的另外两个变量；无严重度、触发、恢复或目的地址定义。|GUD-GENERALTRAPS-MIB.txt:30-54；正式文档“告警与 Trap 接收”。|
|8|WALK 比 GET 快 5–10 倍、3 次不响应离线、光功率 0.01 dBm 除以 100、连续两次阈值告警（十四）|删除/降级|均未由随附 MIB 定义。表可以按 INDEX 对可读列 GETNEXT/GETBULK 遍历，但效能、重试/离线、单位转换和阈值是平台策略/实机验证事项。|修订后的第十四章；各设备“限制”。|

## 分设备/原 Word 章节的差异

|原 Word 章节|分类|保留、修正、遗漏或多余内容|最终依据|
|---|---|---|---|
|二、CCDM 本体接口|修正 + 新增|身份、版本、电源、RAID、网口、风扇和 I/O 卡主题可保留；但标量必须补 .0，原“完整 OID”表中的表列必须补完整 table、Entry、列、索引路径，且 not-accessible 的表、Entry、索引不能 GET。新增 I/O 卡/端口实际索引、MAX-ACCESS、errorGroup 可选性和完整 RAID 枚举。|[CCDM](docs/devices/ccdm-controlcenter-digital.md)；[证据](docs/evidence/ccdm-controlcenter-digital-mib-evidence.md)。|
|三、CCC 本体接口|删除/降级|随附 GUD-SMI-MIB 仅列出 gudCCDC（ControlCenter-Compact）子树；未提供 GUD-CCDC-MIB 或 CCC 对象定义。原 Word 的 CCC OID 表、数量、枚举差异和“可复用”结论均**无法验证**，不能放入实现。|需厂商补充 CCC 原始 MIB；GUD-SMI-MIB.txt:115-121。|
|四、CCDM 下联 CPU|修正 + 新增|CPU MIB 的对象/表主题可保留；原表的短 OID 不足以访问表列。新增 targetModuleIndex、每个列的表实例、枚举、只读权限、实际行由 WALK 决定。|[CCDM 文档：CPU](docs/devices/ccdm-controlcenter-digital.md)。|
|五、CCC 下联 CPU|删除/降级|没有 CCC CPU 专属 MIB；“字段与 CCDM 完全一致，仅 OID 前缀不同”无原文依据。|需厂商补充 CCC CPU MIB。|
|六、CCDM 下联 CON|修正 + 新增|CON 对象/表可保留为监控范围；必须按 userModuleIndex 等索引遍历，补齐 MAX-ACCESS、SFP 的实际 SYNTAX/单位和只读限制。|[CCDM 文档：CON](docs/devices/ccdm-controlcenter-digital.md)。|
|七、CCC 下联 CON|删除/降级|没有 CCC CON 专属 MIB；“完全一致、仅 OID 前缀不同”不能验证。|需厂商补充 CCC CON MIB。|
|八、CCDM 下联 DWC|修正 + 新增|DWC 主题可保留；动态用户、视频、链路表均需真实索引实例，freeze/activeTransmissionPort 也不是可 SET 控制。新增复合索引、范围仅代表可取值而非实际行数。|[CCDM 文档：DWC](docs/devices/ccdm-controlcenter-digital.md)。|
|九、CCC 下联 DWC|删除/降级|没有 CCC DWC 专属 MIB；不能复用 CCDM MIB 作为事实。|需厂商补充 CCC DWC MIB。|
|十、VisionXS-CPU|修正 + 新增|CPU 的身份、状态、视频、链路主题可保留；原表对象在产品前缀后使用 .1.2...，而 MIB 对象根为 .2，且标量漏 .0、表漏索引。新增 errorGroup optional、temperature1/fan1 的 DisplayString 限制、视频/链路索引。|[VisionXS 文档：CPU](docs/devices/visionxs-cpu-con.md)。|
|十一、VisionXS-CON|修正 + 新增|CON 的身份、状态、显示、链路主题可保留；同样将 .1.2... 改为对象根 .2，补 .0/表索引。无证据表明原文提到的 VisionXS 2.0 子型号均适用。|[VisionXS 文档：CON](docs/devices/visionxs-cpu-con.md)。|
|十二、DP12-MUX|修正 + 新增|身份、状态、CPU/视频/控制台/风扇主题可保留；原表对象根 .1.2... 错置，应为产品根后的 .2；4 张表均遗漏真实表根和索引。原文漏掉 6 个 read-write 控制对象及其风险/确认要求。|[DP 文档](docs/devices/dp12-mux-atc.md)；[证据](docs/evidence/dp12-mux-atc-mib-evidence.md)。|

## 原 Word 的未覆盖信息与最终文档新增项

|新增内容|为什么需要|落点|
|---|---|---|
|每份 MIB 的模块版本、更新时间、SHA-256|识别资料版本、避免厂商替换文件后继续沿用旧 OID。|每份正式文档“范围与证据”。|
|完整标量 .0 规则与表索引/GETNEXT/GETBULK 方式|否则采集器会请求错误对象，或把 not-accessible 索引作为监控指标。|每份正式文档“发现与轮询数据字典”。|
|MAX-ACCESS 与 DP 的受控 SET 列表|区分可读、不可访问和可写；避免 UI 误发 SET 或遗漏真实控制风险。|各“交互与写操作”。|
|Trap 的真实通知 OID、变量、未定义语义和建议去重键|避免把整数 level 伪造为严重度，或凭空处理恢复告警。|各“告警与 Trap 接收”。|
|可选组、字段类型/单位限制、索引范围与待厂商确认项|避免将 MIB 存在的对象假设为所有机型必有，或把字符串误作可阈值化数值。|各“已知限制与待厂商确认项”。|
|可执行核验清单|将文档事实转为实机 GET/WALK/Trap/SET（适用时）验收步骤。|各文档末章；另见 qa/ 的独立抽检。|

## 明确的待厂商补件清单

1. CCC / ControlCenter-Compact 主机、CPU、CON、DWC 的原始 MIB 文件；目前只有产品树标识，不能验证 Word 的四组 CCC 表。
2. 每个设备包实际启用的 SNMP 版本、UDP 端口、凭据/USM 与认证加密、ACL、防火墙、Trap 接收地址和通知启用步骤。
3. generalNotification.level 的枚举/严重度、触发与恢复规则，以及哪些产品会发送该通用通知。
4. 温度、电流、电压、DisplayString 传感器值的格式/单位/阈值与告警策略；以及各表索引至物理槽位/端口的映射。
