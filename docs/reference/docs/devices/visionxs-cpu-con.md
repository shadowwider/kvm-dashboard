# VisionXS（CPU/CON）SNMP 接入与监控字典

## 范围与证据

本草案只核对 `vision/` 随附的四份 `*-MIB.txt`。产品 OID 树把 `gudVISIONXSCPU` 标为 VISION-XS-CPU、把 `gudVISIONXSCON` 标为 VISION-XS-CON；MIB 本身没有 `VisionXS 2.0` 专用对象、版本分支或适用机型矩阵。因此，本文将 CPU 与 CON 两个 MIB 描述为同一 VisionXS 包内的两种设备角色，不能据此推断某条目一定适用于任一 2.0 子型号。源：`vision/GUD-SMI-MIB.txt:268-283`。

|MIB 模块|用途|原文版本/更新时间|SHA-256|
|---|---|---|---|
|`GUD-SMI-MIB`|厂商根、产品和 VisionXS CPU/CON OID 父链|Rev. 1.7；2023-05-01|`d08d60f5f715556ab12339eb59bd1a91355e686b463d7f75e9d6b764c05ae96e`|
|`GUD-VISIONXSCPU-MIB`|CPU 身份、状态、视频/链路表和错误对象|Rev. 1.1；2024-04-01|`3a0c95d685c69b453d6ac04498901615f822517d898a47c904e09d7b2d2d5534`|
|`GUD-VISIONXSCON-MIB`|CON 身份、状态、显示/链路表和错误对象|Rev. 1.1；2024-04-01|`8a280a6b197dad57eacbe03c48e40572ecfc997899f0e37d0f74c804a36f478d`|
|`GUD-GENERALTRAPS-MIB`|通用通知及其两个 varbind|Rev. 1.0；2009-01-14|`d575b112175e1e23b98f98afb97e053bc86ad4fe2a10df8d137f595c160fc1e9`|

版本、模块身份与 OID 父链证据见：`vision/GUD-SMI-MIB.txt:8-31,45-49,178-193,268-283`、`vision/GUD-VISIONXSCPU-MIB.txt:13-25`、`vision/GUD-VISIONXSCON-MIB.txt:14-26`、`vision/GUD-GENERALTRAPS-MIB.txt:16-30`。所有下列数值 OID 均以 `1.3.6.1.4.1` 的 `enterprises` 根为前提，逐层由原文 `::= { parent n }` 相加；完整复算记录在同目录 [evidence.md](evidence.md)。

- CPU 产品前缀 `C = 1.3.6.1.4.1.32828.3.768.768`；其对象根为 `C.2`。源：`vision/GUD-SMI-MIB.txt:26-31,45-49,178-184,268-274`、`vision/GUD-VISIONXSCPU-MIB.txt:135-164`。
- CON 产品前缀 `K = 1.3.6.1.4.1.32828.3.769.768`；其对象根为 `K.2`。源：`vision/GUD-SMI-MIB.txt:26-31,45-49,187-193,277-283`、`vision/GUD-VISIONXSCON-MIB.txt:112-141`。
- 通知前缀 `T = 1.3.6.1.4.1.32828.2.1.0`。源：`vision/GUD-SMI-MIB.txt:26-31,36-40,54-58`、`vision/GUD-GENERALTRAPS-MIB.txt:30-54`。

## 接入方式与实施前提

- 两个设备 MIB 导入的是 `SNMPv2-SMI` 类型定义；这只说明 MIB 的 SMI 语法来源，**不能证明**设备可用的 SNMP 报文版本。随附 MIB 未说明 SNMPv1/v2c/v3、UDP 端口、团体字、用户名、认证/加密算法、访问控制、管理地址或 Trap 目的地址配置。源：`vision/GUD-VISIONXSCPU-MIB.txt:3-11`、`vision/GUD-VISIONXSCON-MIB.txt:4-12`、`vision/GUD-GENERALTRAPS-MIB.txt:6-14`。
- 将设备纳入监控前，应由厂商或设备配置界面提供可用的连接参数；本文不填写猜测的端口、community 或 v3 凭据。
- 对下列非表对象，数值 OID 后加标量实例后缀 `.0` 进行 GET；表中 `INDEX` 对象为 `not-accessible`，必须从可读列以 GETNEXT/GETBULK 遍历，不可单独 GET 索引对象。对象的 `OBJECT-TYPE`、`INDEX`、`MAX-ACCESS` 证据见本文数据字典中的逐项来源。
- 所有数值/状态的轮询周期、超时、重试和告警阈值均未在随附 MIB 中规定，需在监控平台策略中另行确定并记录。

## 发现与轮询数据字典

### 通用轮询规则

CPU 与 CON 的标量全部声明为 `read-only`；`DisplayString` 字段按字符串保存。`temperature1` 和 `fan1` 虽分别带有注释形式的 `Deg C`/`RPM`，其正式 `SYNTAX` 仍是 `DisplayString`，所以应先以原始字符串展示/存储，不能仅依据随附 MIB 强制按数值作图或设阈值。源：CPU `vision/GUD-VISIONXSCPU-MIB.txt:257-273`；CON `vision/GUD-VISIONXSCON-MIB.txt:234-250`。

### CPU（`GUD-VISIONXSCPU-MIB`）

标量的表中 OID 已含 `.0` 实例。所有行均为 `read-only`；枚举未被 MIB 定义的字段不添加主观状态含义。

|组别/对象|数值实例 OID|SYNTAX；监控用途与枚举|事实出处|
|---|---|---|---|
|身份：`deviceId`|`C.2.1.1.0`|`DisplayString`；设备 ID|`vision/GUD-VISIONXSCPU-MIB.txt:191-197`|
|`deviceCl`|`C.2.1.2.0`|`DisplayString`；设备 class|`vision/GUD-VISIONXSCPU-MIB.txt:199-205`|
|`deviceType`|`C.2.1.3.0`|`DisplayString`；设备 type|`vision/GUD-VISIONXSCPU-MIB.txt:207-213`|
|`serialNumber`|`C.2.1.4.0`|`DisplayString`；序列号|`vision/GUD-VISIONXSCPU-MIB.txt:215-221`|
|`etherAddress0`|`C.2.1.5.0`|`PhysAddress`；第一个以太网端口 MAC|`vision/GUD-VISIONXSCPU-MIB.txt:223-229`|
|信息：`firmwareVersion`|`C.2.2.1.0`|`DisplayString`；固件版本|`vision/GUD-VISIONXSCPU-MIB.txt:232-238`|
|电源：`mainPower`|`C.2.3.1.0`|`PowerStatus`；主电源，`off(0)`/`on(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:30-37,241-247`|
|`redundantPower`|`C.2.3.2.0`|`PowerStatus`；冗余电源，`off(0)`/`on(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:30-37,249-255`|
|环境：`temperature1`|`C.2.3.3.0`|`DisplayString`；内部温度 1；正式类型非数值|`vision/GUD-VISIONXSCPU-MIB.txt:257-264`|
|`fan1`|`C.2.3.502.0`|`DisplayString`；风扇 1 速度；正式类型非数值|`vision/GUD-VISIONXSCPU-MIB.txt:266-273`|
|网络：`networkInterface0`|`C.2.3.506.0`|`NetworkInterfaceStatus`；第一个网络接口，`down(0)`/`up(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:39-46,275-281`|
|透明 USB：`transparentUsbLink`|`C.2.3.10.0`|`TransparentUsbLinkStatus`；透明 USB 模块链路，`down(0)`/`up(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:67-74,283-289`|
|目标：`targetPower`|`C.2.3.11.0`|`PowerStatus`；target 电源，`off(0)`/`on(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:30-37,291-297`|
|`targetUsbHid`|`C.2.3.13.0`|`UsbHidStatus`；目标 USB 键盘/鼠标连接，`notConnected(0)`/`connected(1)`/`initialized(2)`|`vision/GUD-VISIONXSCPU-MIB.txt:101-109,299-305`|
|`targetUsb20`|`C.2.3.15.0`|`Usb20Status`；目标 USB 2.0 extender 连接，`inactive(0)`/`active(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:111-118,307-313`|
|透明 USB SFP：`transparentUsbSfpModule`|`C.2.3.16.0`|`SfpModuleStatus`；`noModule(0)`/`moduleDeactivated(1)`/`down(2)`/`up(3)`|`vision/GUD-VISIONXSCPU-MIB.txt:120-129,315-321`|
|`transparentUsbTxPower`|`C.2.3.17.0`|`Integer32`；USB SFP TX 功率，`uW`|`vision/GUD-VISIONXSCPU-MIB.txt:323-329`|
|`transparentUsbRxPower`|`C.2.3.18.0`|`Integer32`；USB SFP RX 功率，`uW`|`vision/GUD-VISIONXSCPU-MIB.txt:331-337`|
|`transparentUsbSfpType`|`C.2.3.19.0`|`DisplayString`；USB SFP 类型|`vision/GUD-VISIONXSCPU-MIB.txt:339-345`|
|错误：`generalErrorCode`|`C.2.1000.1.0`|`Integer32`；错误代码；MIB 未给代码表|`vision/GUD-VISIONXSCPU-MIB.txt:482-488`|
|`generalErrorMessage`|`C.2.1000.2.0`|`DisplayString`；问题描述文本|`vision/GUD-VISIONXSCPU-MIB.txt:490-496`|

CPU 视频表的根为 `C.2.3.1000`，条目为 `.1`，索引 `videoChannelIndex` 取值 `1..4` 且 `not-accessible`。从 `targetVideoCable`（列 2）或 `targetVideoSignal`（列 3）执行 GETNEXT/GETBULK，行实例分别为 `C.2.3.1000.1.2.<i>`、`C.2.3.1000.1.3.<i>`（`i=1..4`）。`targetVideoCable` 为 `ConnectionStatus`：`notConnected(0)`/`connected(1)`；`targetVideoSignal` 为 `VideoType`：`none(0)`、`vga(1)`、`dvisl(2)`、`dvidl(3)`、`dmdp(4)`、`dp(5)`、`hdmi(6)`。源：`vision/GUD-VISIONXSCPU-MIB.txt:48-88,351-396`。

CPU 链路表的根为 `C.2.3.1001`，条目为 `.1`，索引 `linkChannelIndex` 为 `1..8` 且 `not-accessible`。以可读列遍历：`link`=`C.2.3.1001.1.2.<i>`（`LinkStatus`: `down(0)`/`up(1)`/`crossed(2)`）、`sfpModule`=`C.2.3.1001.1.3.<i>`（`SfpModuleStatus`：`noModule(0)`/`moduleDeactivated(1)`/`down(2)`/`up(3)`）、`sfpTxPower`=`C.2.3.1001.1.4.<i>`（`Integer32`，uW）、`sfpRxPower`=`C.2.3.1001.1.5.<i>`（`Integer32`，uW）、`sfpType`=`C.2.3.1001.1.6.<i>`（`DisplayString`）。源：`vision/GUD-VISIONXSCPU-MIB.txt:57-65,120-129,403-475`。

`identifyGroup`、`infoGroup`、`statusGroup` 为强制组；`errorGroup` 为可选组。透明 USB 的部分对象虽已定义，但在 `statusGroup` 清单中被注释，不应以该强制组为由假定设备一定实现。源：`vision/GUD-VISIONXSCPU-MIB.txt:502-552`。

### CON（`GUD-VISIONXSCON-MIB`）

标量的表中 OID 已含 `.0` 实例。身份、信息、电源、温度、风扇、网络、透明 USB SFP 与错误对象与 CPU 的结构相同，但 OID 前缀为 `K`；CON 另有本地控制台 USB 和显示表，且没有 CPU 的 `target*` 对象。

|组别/对象|数值实例 OID|SYNTAX；监控用途与枚举|事实出处|
|---|---|---|---|
|身份：`deviceId` / `deviceCl` / `deviceType` / `serialNumber` / `etherAddress0`|`K.2.1.1.0` / `.2.0` / `.3.0` / `.4.0` / `.5.0`|依次为 `DisplayString` ID、class、type、序列号，及 `PhysAddress` 第一个以太网端口 MAC|`vision/GUD-VISIONXSCON-MIB.txt:168-206`|
|信息：`firmwareVersion`|`K.2.2.1.0`|`DisplayString`；固件版本|`vision/GUD-VISIONXSCON-MIB.txt:209-215`|
|电源：`mainPower` / `redundantPower`|`K.2.3.1.0` / `K.2.3.2.0`|`PowerStatus`；均为 `off(0)`/`on(1)`|`vision/GUD-VISIONXSCON-MIB.txt:40-47,218-232`|
|环境：`temperature1` / `fan1`|`K.2.3.3.0` / `K.2.3.502.0`|均为 `DisplayString`；内部温度 1 / 风扇 1 速度；不能将其正式类型视为数值|`vision/GUD-VISIONXSCON-MIB.txt:234-250`|
|网络：`networkInterface0`|`K.2.3.506.0`|`NetworkInterfaceStatus`；第一个网络接口，`down(0)`/`up(1)`|`vision/GUD-VISIONXSCON-MIB.txt:49-56,252-258`|
|本地控制台：`consoleUSBConnection`|`K.2.3.9.0`|`KeyboardMouseStatus`；`none(0)`/`keyboard(1)`/`mouse(2)`/`keyboardMouse(3)`|`vision/GUD-VISIONXSCON-MIB.txt:86-95,260-266`|
|透明 USB：`transparentUsbLink`|`K.2.3.10.0`|`TransparentUsbLinkStatus`；`down(0)`/`up(1)`|`vision/GUD-VISIONXSCON-MIB.txt:77-84,268-274`|
|透明 USB SFP：`transparentUsbSfpModule` / `transparentUsbTxPower` / `transparentUsbRxPower` / `transparentUsbSfpType`|`K.2.3.16.0` / `.17.0` / `.18.0` / `.19.0`|分别为 `SfpModuleStatus`（0–3 枚举）、`Integer32` TX uW、`Integer32` RX uW、`DisplayString` 类型|`vision/GUD-VISIONXSCON-MIB.txt:97-106,276-306`|
|错误：`generalErrorCode` / `generalErrorMessage`|`K.2.1000.1.0` / `K.2.1000.2.0`|`Integer32` 错误代码（无代码表）/ `DisplayString` 错误文本|`vision/GUD-VISIONXSCON-MIB.txt:449-463`|

CON 显示表根为 `K.2.3.1000`，条目 `.1`，索引 `videoChannelIndex` 为 `1..4` 且 `not-accessible`。从可读列 GETNEXT/GETBULK：`displayConnection`=`K.2.3.1000.1.2.<i>`（`ConnectionStatus`: `notConnected(0)`/`connected(1)`）、`displayType`=`K.2.3.1000.1.3.<i>`（`DisplayString`）、`freeze`=`K.2.3.1000.1.4.<i>`（`Boolean`: `false(0)`/`true(1)`）。源：`vision/GUD-VISIONXSCON-MIB.txt:31-38,58-65,312-366`。

CON 链路表根为 `K.2.3.1001`，条目 `.1`，索引 `linkChannelIndex` 为 `1..8` 且 `not-accessible`。以可读列遍历：`link`=`K.2.3.1001.1.2.<i>`（`LinkStatus`: `down(0)`/`up(1)`/`crossed(2)`）、`sfpModule`=`K.2.3.1001.1.3.<i>`（`SfpModuleStatus` 0–3）、`sfpTxPower`=`K.2.3.1001.1.4.<i>`（`Integer32`，uW）、`sfpRxPower`=`K.2.3.1001.1.5.<i>`（`Integer32`，uW）、`sfpType`=`K.2.3.1001.1.6.<i>`（`DisplayString`）。源：`vision/GUD-VISIONXSCON-MIB.txt:67-75,97-106,373-445`。

CON 的强制/可选组和透明 USB 备注与 CPU 相同：身份、信息、状态为 `MANDATORY-GROUPS`，错误组可选；透明 USB 部分条目被注释出 `statusGroup`。源：`vision/GUD-VISIONXSCON-MIB.txt:469-520`。

## 告警与 Trap 接收

随附包中只有一个 `NOTIFICATION-TYPE`：`generalNotification`，通知 OID 为 `T.4`，即 `1.3.6.1.4.1.32828.2.1.0.4`。它携带 `level`（`T.2`，`Integer32`，描述仅为 notification level）和 `message`（`T.3`，`DisplayString`，消息文本）两个对象。源：`vision/GUD-GENERALTRAPS-MIB.txt:30-54`。

|通知|通知 OID|携带变量|触发/恢复含义与限制|接收端去重建议|事实出处|
|---|---|---|---|---|---|
|`generalNotification`|`1.3.6.1.4.1.32828.2.1.0.4`|`level`=`1.3.6.1.4.1.32828.2.1.0.2`（`Integer32`）；`message`=`1.3.6.1.4.1.32828.2.1.0.3`（`DisplayString`）|原文只称“G&D general notification”；未说明具体触发条件、严重度映射、恢复通知或与 VisionXS 的绑定关系|建议把设备稳定标识（优先 `serialNumber`）、通知 OID、`level` 和 `message` 组成候选去重键；这是平台侧建议，不是厂商定义|`vision/GUD-GENERALTRAPS-MIB.txt:32-54`|

CPU/CON 设备 MIB 中没有 `NOTIFICATION-TYPE` 或 `TRAP-TYPE`。通用 Trap MIB 的合规声明仅表示其通知组包含该通知，不能证明每一台 VisionXS 已启用或会发送它。随附 MIB 也没有 Trap 接收端配置对象。源：`vision/GUD-GENERALTRAPS-MIB.txt:64-86`；CPU `vision/GUD-VISIONXSCPU-MIB.txt:1-554`；CON `vision/GUD-VISIONXSCON-MIB.txt:1-522`。

## 交互与写操作

- CPU 和 CON 的可读数据列一律为 `MAX-ACCESS read-only`；两个表、条目及索引均为 `not-accessible`。没有 `read-write`、`read-create` 或写操作对象，因此本包不支持用 SNMP SET 控制电源、freeze、USB、显示或链路。代表性证据：CPU `vision/GUD-VISIONXSCPU-MIB.txt:241-247,351-396,403-475`；CON `vision/GUD-VISIONXSCON-MIB.txt:218-224,312-366,373-445`。
- `generalErrorCode`/`generalErrorMessage` 也是只读，不能用来确认、清除或关闭告警。源：CPU `vision/GUD-VISIONXSCPU-MIB.txt:482-496`；CON `vision/GUD-VISIONXSCON-MIB.txt:449-463`。
- 资料未说明任何 SNMP 写入前置条件、值域以外的操作流程、事务/回滚或权限模型；实施阶段应禁用对本厂商 OID 的 SET，直至获得另行发布的厂商写操作资料。

## 监控界面落地建议

下列仅是已证实对象到 UI 的映射，不新增健康规则或阈值。

|页面/组件|CPU 映射|CON 映射|边界|
|---|---|---|---|
|设备概览卡|`deviceId`、`deviceType`、`serialNumber`、`firmwareVersion`、`etherAddress0`|同名对象|不要以未提供的“在线/离线”厂商 OID 填充状态卡|
|供电与环境|`mainPower`、`redundantPower`、`temperature1`、`fan1`|同名对象|温度/风扇先按 `DisplayString` 展示；不在本文定义告警阈值|
|网络与链路表|`networkInterface0`、`link*`、`sfp*`、透明 USB 链路/SFP|同名对象|链路行按 `linkChannelIndex` 汇聚；索引最多 8，实际出现行数需实测|
|视频/外设表|`targetVideoCable`、`targetVideoSignal`、`targetPower`、`targetUsbHid`、`targetUsb20`|`displayConnection`、`displayType`、`freeze`、`consoleUSBConnection`|视频/显示行按 `videoChannelIndex` 汇聚；索引最多 4|
|错误与告警列表|可选 `generalErrorCode`、`generalErrorMessage`；接收 `generalNotification` 时列出 `level`/`message`|同左|错误组可能未实现；`level` 无严重度字典，勿擅自映射为 P1/P2|

## 已知限制与待厂商确认项

1. 本包不能证明 VisionXS 2.0 与第一代 VisionXS 的具体 MIB 差异、支持矩阵或固件最低版本。
2. SNMP 报文版本、UDP 端口、认证/加密、读取凭据、ACL、Trap 目的地址及启用步骤均未说明。
3. `generalNotification` 的触发条件、`level` 数值含义、严重度、恢复语义和每设备支持性未说明；CPU/CON MIB 没有设备专属 Trap。
4. `errorGroup` 是可选组，且 `generalErrorCode` 未提供代码映射；不能把任意整数解释为健康/故障结论。
5. `temperature1`、`fan1` 是 `DisplayString`；尽管有被注释的单位文字，数值格式、精度、无效值和阈值均未定义。
6. 视频表最大索引是 4、链路表最大索引是 8，但 MIB 未说明每个索引对应的物理端口/冗余角色，也未承诺所有索引均会返回。
7. MIB 未提供设备整体 Online/Offline、轮询间隔、设备时间、事件确认/清除或任何 SET 控制接口；不得从同目录以外的产品经验补足。

## 可执行核验清单

以下检查均须在已由厂商确认的 SNMP 连接参数下执行；结果应保存原始请求/响应和固件版本。

1. **CPU 标量实例**：对 `1.3.6.1.4.1.32828.3.768.768.2.1.1.0` 执行 GET；确认返回 `deviceId`，并确认省略 `.0` 的请求不被误当成同一实例。依据：`vision/GUD-VISIONXSCPU-MIB.txt:191-197`。
2. **CON 显示表索引**：从 `1.3.6.1.4.1.32828.3.769.768.2.3.1000.1.2` 执行 GETBULK/GETNEXT；确认实际返回实例后缀只落在 `1..4`，将同一索引的列 2/3/4 关联，而不是单独轮询 `videoChannelIndex`。依据：`vision/GUD-VISIONXSCON-MIB.txt:312-366`。
3. **CPU 链路表与枚举**：遍历 `C.2.3.1001.1.2` 至 `.6`；确认每行索引在 `1..8`，并只将 `link` 的 `0/1/2` 显示为 MIB 原文 `down/up/crossed`，不改写为自定义告警等级。依据：`vision/GUD-VISIONXSCPU-MIB.txt:57-65,403-475`。
4. **错误组可选性**：分别 GET CPU/CON 的 `generalErrorCode.0` 和 `generalErrorMessage.0`；若返回 `noSuchObject`/不支持，UI 应标记“设备未实现可选 errorGroup”而非判为设备故障。依据：CPU `vision/GUD-VISIONXSCPU-MIB.txt:502-552`；CON `vision/GUD-VISIONXSCON-MIB.txt:469-520`。
5. **Trap varbind**：在 Trap 接收端抓取一条 `1.3.6.1.4.1.32828.2.1.0.4` 通知；断言其中包含 `1.3.6.1.4.1.32828.2.1.0.2` 的 `Integer32 level` 和 `1.3.6.1.4.1.32828.2.1.0.3` 的 `DisplayString message`。缺少任一变量或额外变量时保留原始 varbind，不臆测其语义。依据：`vision/GUD-GENERALTRAPS-MIB.txt:32-54`。
6. **只读保护**：对任一已确认可读对象（例如 CPU `mainPower.0`）仅执行 GET；在测试账户和监控采集器配置中禁止向此包 OID 发出 SET，并记录 MIB 的 `read-only` 定义。依据：`vision/GUD-VISIONXSCPU-MIB.txt:241-247`。
7. **字符串测量值**：采集 CPU/CON 的 `temperature1.0`、`fan1.0` 原始值；确认平台保留字符串原值，再决定是否获得厂商格式说明后另建数值指标。依据：CPU `vision/GUD-VISIONXSCPU-MIB.txt:257-273`；CON `vision/GUD-VISIONXSCON-MIB.txt:234-250`。
