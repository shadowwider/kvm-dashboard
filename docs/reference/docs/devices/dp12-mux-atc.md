# DP1.2-MUX-ATC SNMP 接入与监控字典

## 范围与证据

本草案的设备范围是 MIB 中明确写出的 `DP1.2-MUX-ATC`。资料包包含产品 MIB、公共 Trap MIB 和企业树 MIB；本文只把这三份 `*-MIB.txt` 作为 OID、语义、访问权限、枚举、索引及通知的事实来源，未以 PDF 或外部资料补全任何协议参数。

|MIB 模块（文件）|版本/时间（原文）|SHA-256|本设备中的作用|
|---|---|---|---|
|`GUD-DP12MUXATC-MIB`（`dp/GUD-DP12MUXATC-MIB.txt`）|`LAST-UPDATED 201805210000Z`，Rev. 1.1|`1FB33872C3BB51654839A591484738AE39C325DC0D940F4A09AF6FEC02709A5D`|设备身份、状态、4 个表、切换/配置 SET、错误对象。源：`dp/GUD-DP12MUXATC-MIB.txt:14-26`|
|`GUD-GENERALTRAP-MIB`（`dp/GUD-GENERALTRAPS-MIB.txt`）|`LAST-UPDATED 200901141407Z`，Rev. 1.0|`D575B112175E1E23B98F98AFB97E053BC86AD4FE2A10DF8D137F595C160FC1E9`|一个通用通知及其两个变量。源：`dp/GUD-GENERALTRAPS-MIB.txt:16-30`|
|`GUD-SMI-MIB`（`dp/GUD-SMI-MIB.txt`）|`LAST-UPDATED 202111110000Z`，Rev. 1.6|`6A1D390FB30B0943DACB6DA64D6845287792C202B340EFC7202CA4D2D60F613D`|供应商树、产品树及公共 Trap 树。源：`dp/GUD-SMI-MIB.txt:8-31`|

`GUD-SMI-MIB` 仅从 `SNMPv2-SMI` 导入 `enterprises`，随附原文没有给出其数字根（源：`dp/GUD-SMI-MIB.txt:4-6`）。因此为遵守“原文可独立推导”原则，本文 OID 保留为 `enterprises.32828...` 的符号前缀，不把未在随附资料定义的前缀改写为绝对数字。其后的每一段数字均按原文父子关系复算，详见 `work/dp/evidence.md`。

可复算的设备根为 `gudDP12MUXATC = enterprises.32828.3.1792.17`，产品 MIB 根为 `gudDP12MUXATCMIB = enterprises.32828.3.1792.17.1`。源：`dp/GUD-SMI-MIB.txt:26-31,45-49,315-319,340-346`；`dp/GUD-DP12MUXATC-MIB.txt:14-26`。

## 接入方式与实施前提

随附 MIB 未说明 SNMP 版本、UDP 端口、团体字、USM 用户、认证/加密算法、ACL、设备侧 SNMP 开关、Trap 接收地址或通知开关；MIB 中导入 `SNMPv2-SMI` 仅表示 MIB 编写所用语法，不能据此推断设备支持的协议版本。上述内容必须向厂商或从设备管理界面另行确认后，才可部署轮询器/Trap 接收器。

接入前至少加载本节列出的三份 MIB，使管理端可解析 `PowerStatus`、`VideoType` 等文本约定及公共通知。部署时使用只读凭据进行轮询；写操作必须使用另行授权的凭据和人工确认，见“交互与写操作”。

## 发现与轮询数据字典

### 轮询规则与枚举

所有下表中的非表格对象均为标量，轮询实例应在其对象 OID 后附加 `.0`。这是 SMI 标量实例规则的实施要求；MIB 本身没有逐条写出 `.0`。表的 `not-accessible` table/entry/index 不作为可 GET 的状态项，应对可读列使用 GETNEXT/GETBULK 遍历其表根，并按 `INDEX` 解析行键。每一数据点的原文证据见表内“出处”。

|文本约定|原始枚举（不得改作主观健康级别）|出处|
|---|---|---|
|`Boolean`|`false(0)`，`true(1)`|源：`dp/GUD-DP12MUXATC-MIB.txt:31-38`|
|`PowerStatus`|`off(0)`，`on(1)`|源：`dp/GUD-DP12MUXATC-MIB.txt:40-47`|
|`NetworkInterfaceStatus`|`down(0)`，`up(1)`|源：`dp/GUD-DP12MUXATC-MIB.txt:49-56`|
|`ConnectionStatus`|`notConnected(0)`，`connected(1)`|源：`dp/GUD-DP12MUXATC-MIB.txt:58-65`|
|`VideoType`|`none(0)`，`vga(1)`，`dvisl(2)`，`dvidl(3)`，`dmdp(4)`，`dp(5)`，`hdmi(6)`|源：`dp/GUD-DP12MUXATC-MIB.txt:67-79`|
|`KeyboardMouseStatus`|`none(0)`，`keyboard(1)`，`mouse(2)`，`keyboardMouse(3)`|源：`dp/GUD-DP12MUXATC-MIB.txt:81-90`|
|`UsbHidStatus`|`notConnected(0)`，`connected(1)`，`initialized(2)`|源：`dp/GUD-DP12MUXATC-MIB.txt:92-100`|
|`Usb30Status`|`inactive(0)`，`active(1)`（原文描述为 USB 2.0 extender）|源：`dp/GUD-DP12MUXATC-MIB.txt:102-109`|

### 身份与版本（标量、均只读）

|对象|对象 OID（轮询实例）|语法/含义|监控用途|出处|
|---|---|---|---|---|
|`deviceId`|`enterprises.32828.3.1792.17.2.1.1.0`|`DisplayString`；设备 ID|设备发现与资产主键候选|源：`dp/GUD-DP12MUXATC-MIB.txt:183-189`|
|`deviceCl`|`...17.2.1.2.0`|`DisplayString`；设备类别|设备分类展示|源：`dp/GUD-DP12MUXATC-MIB.txt:191-197`|
|`deviceType`|`...17.2.1.3.0`|`DisplayString`；设备类型|确认设备型号/类型|源：`dp/GUD-DP12MUXATC-MIB.txt:199-205`|
|`serialNumber`|`...17.2.1.4.0`|`DisplayString`；序列号|资产唯一标识候选|源：`dp/GUD-DP12MUXATC-MIB.txt:207-213`|
|`etherAddress0`|`...17.2.1.5.0`|`PhysAddress`；第一个以太网端口 MAC|网络资产识别|源：`dp/GUD-DP12MUXATC-MIB.txt:215-221`|
|`etherAddress1`|`...17.2.1.6.0`|`PhysAddress`；第二个以太网端口 MAC|网络资产识别|源：`dp/GUD-DP12MUXATC-MIB.txt:223-229`|
|`firmwareVersion`|`...17.2.2.1.0`|`DisplayString`；固件版本|版本盘点|源：`dp/GUD-DP12MUXATC-MIB.txt:233-239`|

其中 `...17` 为上节定义的 `enterprises.32828.3.1792.17`。同一缩写适用于本章所有 DP 设备对象 OID；完整逐项推导在证据台账中。

### 设备状态（标量、均只读）

|对象|对象 OID（轮询实例）|语法/状态解释|监控用途|出处|
|---|---|---|---|---|
|`mainPower`|`...17.2.3.1.0`|`PowerStatus`：`off(0)` / `on(1)`；主电源状态|主电源状态展示|源：`dp/GUD-DP12MUXATC-MIB.txt:243-249`|
|`redundantPower`|`...17.2.3.2.0`|`PowerStatus`：`off(0)` / `on(1)`；冗余电源状态|冗余电源状态展示|源：`dp/GUD-DP12MUXATC-MIB.txt:251-257`|
|`temperature1`|`...17.2.3.3.0`|`DisplayString`；原文称内部温度 1，单位 `[Deg C]`|内部温度展示；不设未经资料证实的阈值|源：`dp/GUD-DP12MUXATC-MIB.txt:259-266`|
|`powerCurrent`|`...17.2.3.500.0`|`DisplayString`；电源电流，注释单位 `A`|电源电流展示|源：`dp/GUD-DP12MUXATC-MIB.txt:268-275`|
|`powerVoltage`|`...17.2.3.501.0`|`DisplayString`；电源电压，注释单位 `V`|电源电压展示|源：`dp/GUD-DP12MUXATC-MIB.txt:277-284`|
|`consolePS2Connection`|`...17.2.3.7.0`|`KeyboardMouseStatus`：`none(0)` / `keyboard(1)` / `mouse(2)` / `keyboardMouse(3)`|控制台 PS/2 键鼠连接展示|源：`dp/GUD-DP12MUXATC-MIB.txt:286-292`；枚举源：`...:81-90`|
|`consoleUSBConnection`|`...17.2.3.8.0`|`KeyboardMouseStatus`：同上|控制台 USB 键鼠连接展示|源：`dp/GUD-DP12MUXATC-MIB.txt:294-300`；枚举源：`...:81-90`|
|`networkInterface0`|`...17.2.3.506.0`|`NetworkInterfaceStatus`：`down(0)` / `up(1)`；第 1 个网络接口|网络接口状态展示|源：`dp/GUD-DP12MUXATC-MIB.txt:302-308`；枚举源：`...:49-56`|
|`networkInterface1`|`...17.2.3.507.0`|`NetworkInterfaceStatus`：`down(0)` / `up(1)`；第 2 个网络接口|网络接口状态展示|源：`dp/GUD-DP12MUXATC-MIB.txt:310-316`；枚举源：`...:49-56`|

### CPU 通道状态表 `cpuChannelTable`

表根为 `...17.2.3.1000`，其 table/entry 均 `not-accessible`；行索引为 `cpuChannelIndex`，范围 `1..4`。对可读列以 GETNEXT/GETBULK 遍历 `...17.2.3.1000.1`，实例末尾依次追加 `<cpuChannelIndex>`；不单独 GET 表、entry 或索引对象。源：`dp/GUD-DP12MUXATC-MIB.txt:322-354`。

|可读列|列 OID 实例模板|语法/状态解释|监控用途|出处|
|---|---|---|---|---|
|`cpuChannelTargetUsbHid`|`...17.2.3.1000.1.2.<cpuChannelIndex>`|`UsbHidStatus`：`notConnected(0)` / `connected(1)` / `initialized(2)`|每 CPU 通道 USB HID 状态|源：`dp/GUD-DP12MUXATC-MIB.txt:356-362`；枚举源：`...:92-100`|
|`cpuChannelTargetDevice`|`...17.2.3.1000.1.3.<cpuChannelIndex>`|`DisplayString`；CPU 通道名称|通道标签|源：`dp/GUD-DP12MUXATC-MIB.txt:364-370`|
|`cpuChannelTargetPower`|`...17.2.3.1000.1.4.<cpuChannelIndex>`|`PowerStatus`：`off(0)` / `on(1)`；连接到 CPU 通道的目标电源状态|通道目标电源展示|源：`dp/GUD-DP12MUXATC-MIB.txt:372-378`；枚举源：`...:40-47`|
|`cpuChannelTargetPS2`|`...17.2.3.1000.1.5.<cpuChannelIndex>`|`ConnectionStatus`：`notConnected(0)` / `connected(1)`；目标 PS/2 键鼠连接|通道目标 PS/2 连接展示|源：`dp/GUD-DP12MUXATC-MIB.txt:380-386`；枚举源：`...:58-65`|
|`cpuChannelTargetUsb30`|`...17.2.3.1000.1.6.<cpuChannelIndex>`|`Usb30Status`：`inactive(0)` / `active(1)`；原文称 USB 2.0 extender 连接|通道扩展器状态展示|源：`dp/GUD-DP12MUXATC-MIB.txt:388-394`；枚举源：`...:102-109`|

### CPU 视频状态表 `cpuChannelVideoTable`

表根为 `...17.2.3.1001`；entry 的 `INDEX` 明确为 `{ cpuChannelIndex, cpuChannelVideoIndex }`。两个表/entry 和两个索引对象均 `not-accessible`；前一索引 `cpuChannelIndex` 的定义位于 CPU 通道表中，第二索引范围为 `1..4`。因此 walk 时按 MIB `INDEX` 次序将 `<cpuChannelIndex>.<cpuChannelVideoIndex>` 作为可读列实例后缀；设备实际返回的行数/组合由 walk 结果确认。源：`dp/GUD-DP12MUXATC-MIB.txt:400-429`。

|可读列|列 OID 实例模板|语法/状态解释|监控用途|出处|
|---|---|---|---|---|
|`cpuChannelVideoCable`|`...17.2.3.1001.1.2.<cpuChannelIndex>.<cpuChannelVideoIndex>`|`ConnectionStatus`：`notConnected(0)` / `connected(1)`；DP 视频线缆连接|CPU 视频线缆状态|源：`dp/GUD-DP12MUXATC-MIB.txt:431-437`；枚举源：`...:58-65`|
|`cpuChannelVideoSignal`|`...17.2.3.1001.1.3.<cpuChannelIndex>.<cpuChannelVideoIndex>`|`VideoType`：`none(0)`、`vga(1)`、`dvisl(2)`、`dvidl(3)`、`dmdp(4)`、`dp(5)`、`hdmi(6)`|CPU 视频信号类型展示|源：`dp/GUD-DP12MUXATC-MIB.txt:439-445`；枚举源：`...:67-79`|

### 控制台视频状态表 `consoleVideoTable`

表根为 `...17.2.3.1002`，`INDEX { consoleVideoIndex }`，索引范围 `1..4`。table、entry、index 都 `not-accessible`；用 GETNEXT/GETBULK 遍历 `...17.2.3.1002.1`，各可读列实例后附 `<consoleVideoIndex>`。源：`dp/GUD-DP12MUXATC-MIB.txt:451-481`。

|可读列|列 OID 实例模板|语法/状态解释|监控用途|出处|
|---|---|---|---|---|
|`displayConnection`|`...17.2.3.1002.1.2.<consoleVideoIndex>`|`ConnectionStatus`：`notConnected(0)` / `connected(1)`|控制台显示器连接展示|源：`dp/GUD-DP12MUXATC-MIB.txt:483-489`；枚举源：`...:58-65`|
|`displayType`|`...17.2.3.1002.1.3.<consoleVideoIndex>`|`DisplayString`；连接到控制台的显示器类型|控制台显示器类型展示|源：`dp/GUD-DP12MUXATC-MIB.txt:491-497`|
|`freeze`|`...17.2.3.1002.1.4.<consoleVideoIndex>`|`Boolean`：`false(0)` / `true(1)`；`true` 表示 freeze mode active|冻结模式状态展示|源：`dp/GUD-DP12MUXATC-MIB.txt:499-505`；枚举源：`...:31-38`|

### 风扇状态表 `fanTable`

表根为 `...17.2.3.1003`，`INDEX { fanIndex }`，索引范围 `1..20`。table、entry、index 均 `not-accessible`；遍历 `...17.2.3.1003.1`，读取如下列并在实例末尾附 `<fanIndex>`。源：`dp/GUD-DP12MUXATC-MIB.txt:511-539`。

|可读列|列 OID 实例模板|语法/单位|监控用途|出处|
|---|---|---|---|---|
|`fanSpeed`|`...17.2.3.1003.1.2.<fanIndex>`|`Integer32(0..10000)`，RPM|按风扇行展示转速；原文未给出故障阈值|源：`dp/GUD-DP12MUXATC-MIB.txt:541-547`|

### 错误对象（标量、只读）

|对象|对象 OID（轮询实例）|语法/含义|监控用途|出处|
|---|---|---|---|---|
|`generalErrorCode`|`...17.2.1000.1.0`|`Integer32`；错误码，无枚举定义|错误码原样展示/关联错误消息；不得把数值映射为严重度|源：`dp/GUD-DP12MUXATC-MIB.txt:607-613`|
|`generalErrorMessage`|`...17.2.1000.2.0`|`DisplayString`；描述问题的错误消息|错误文本展示|源：`dp/GUD-DP12MUXATC-MIB.txt:615-621`|

## 告警与 Trap 接收

资料只定义一项通用通知，未定义 DP1.2-MUX-ATC 专属通知。公共 Trap 树为 `gudGeneralTrap = enterprises.32828.2.1`，通知子树为 `gudGeneralNotifications = enterprises.32828.2.1.0`；它们与设备产品树的关系及数值推导见证据台账。源：`dp/GUD-SMI-MIB.txt:36-40,52-58`；`dp/GUD-GENERALTRAPS-MIB.txt:30-54`。

|通知|通知 OID|触发/恢复含义|`OBJECTS` 变量（Trap 中读取）|接收与去重建议|出处|
|---|---|---|---|---|---|
|`generalNotification`|`enterprises.32828.2.1.0.4`|原文仅称“G&D general notification”；未说明触发条件、告警严重度含义或恢复通知|`level`：`Integer32`，说明为通知级别，变量对象 OID `...2.1.0.2`；`message`：`DisplayString`，说明为消息文本，变量对象 OID `...2.1.0.3`|接收器保存发送方、通知 OID、`level` 和 `message`。可用这四项加接收时间窗口去重；这是接收端设计建议，不是 MIB 定义的告警键。未提供 Trap 接收地址/开关 OID。|源：`dp/GUD-GENERALTRAPS-MIB.txt:32-54`|

不要把 `level` 数值解释为任意固定的 Info/Warning/Critical，因为 MIB 未给枚举或严重度映射；不要假设该通知存在恢复事件。`level` 与 `message` 是通知的 `OBJECTS`，用于接收的 varbind 解析；是否能作为设备普通轮询对象，随附资料未说明。

## 交互与写操作

MIB 中仅有下列 6 个 `MAX-ACCESS read-write` 标量对象；它们的实例为 `.0`。`MAX-ACCESS` 支持在已获有效写入权限的 SNMP 会话中尝试 SET，但随附资料没有认证/授权、并发、持久化、回滚、审计或风险处置流程，实施前需厂商确认并在测试设备验证。

|对象|SET OID|可写值/原文作用|风险与前置条件|出处|
|---|---|---|---|---|
|`selectedChannel`|`...17.2.4.1.0`|`Integer32(1..4)`；读为 active channel，写为切换至该通道|会改变当前连接通道；应显示目标通道并二次确认，先验证通道标签/业务影响。|源：`dp/GUD-DP12MUXATC-MIB.txt:550-557`|
|`disableSwitching`|`...17.2.5.1.0`|`Boolean false(0)/true(1)`；写为启用/禁用通道切换|可能阻止业务切换；须经过变更批准。原文未定义 `false` 与“enable”的逐字映射以外的异常行为。|源：`dp/GUD-DP12MUXATC-MIB.txt:561-568`；枚举源：`...:31-38`|
|`disableFrontkeys`|`...17.2.5.2.0`|`Boolean`；写为启用/禁用前面板按键|可能改变本地操作能力；须人工确认。|源：`dp/GUD-DP12MUXATC-MIB.txt:570-577`；枚举源：`...:31-38`|
|`disableHotkeys`|`...17.2.5.3.0`|`Boolean`；写为启用/禁用热键|可能改变控制台操作路径；须人工确认。|源：`dp/GUD-DP12MUXATC-MIB.txt:579-586`；枚举源：`...:31-38`|
|`disableSerialPort`|`...17.2.5.4.0`|`Boolean`；写为启用/禁用串口切换|可能改变串口切换能力；须人工确认。|源：`dp/GUD-DP12MUXATC-MIB.txt:588-595`；枚举源：`...:31-38`|
|`disableRemoteControlApi`|`...17.2.5.5.0`|`Boolean`；写为启用/禁用 Remote control API 切换|可能使远程控制 API 的切换不可用；须人工确认，且避免把当前监控接口与该 API 混同。|源：`dp/GUD-DP12MUXATC-MIB.txt:597-604`；枚举源：`...:31-38`|

其余本章列出的设备对象均为 `read-only`，且 4 张表与索引对象为 `not-accessible`，不得作为 SET 目标。源：`dp/GUD-DP12MUXATC-MIB.txt:183-547,607-621`。

## 监控界面落地建议

下列映射只使用已证实对象，不预设健康阈值、不把枚举扩展为厂商未定义的告警规则。

|界面区域|可呈现内容|数据对象|
|---|---|---|
|设备概览卡|设备 ID、类别、类型、序列号、固件、两个 MAC|`deviceId`、`deviceCl`、`deviceType`、`serialNumber`、`firmwareVersion`、`etherAddress0`、`etherAddress1`|
|设备状态|主/冗余电源、内部温度、电源电流/电压、两个网络接口、PS/2/USB 键鼠状态、当前活动通道|`mainPower`、`redundantPower`、`temperature1`、`powerCurrent`、`powerVoltage`、`networkInterface0`、`networkInterface1`、`consolePS2Connection`、`consoleUSBConnection`、`selectedChannel`|
|CPU 通道表|通道索引、名称、USB HID、目标电源、PS/2、USB extender 状态|`cpuChannelIndex`（行键）、`cpuChannelTargetDevice`、`cpuChannelTargetUsbHid`、`cpuChannelTargetPower`、`cpuChannelTargetPS2`、`cpuChannelTargetUsb30`|
|视频/控制台表|CPU/视频索引、DP 线缆、信号类型；控制台索引、显示器连接、显示器类型、freeze|`cpuChannelIndex`、`cpuChannelVideoIndex`、`cpuChannelVideoCable`、`cpuChannelVideoSignal`、`consoleVideoIndex`、`displayConnection`、`displayType`、`freeze`|
|风扇/错误页|风扇索引与 RPM；错误码和错误文本|`fanIndex`、`fanSpeed`、`generalErrorCode`、`generalErrorMessage`|
|告警列表|通知接收时间、发送方、通知 OID、原始 `level`、`message`|`generalNotification`、`level`、`message`|
|受控操作区|当前/目标通道切换和 5 个操作禁用开关|`selectedChannel`、`disableSwitching`、`disableFrontkeys`、`disableHotkeys`、`disableSerialPort`、`disableRemoteControlApi`|

## 已知限制与待厂商确认项

1. 未说明 SNMP 协议版本、端口、凭据/认证/加密、访问控制、设备侧启用步骤、超时或建议轮询频率。
2. 原文没有自行给出导入符号 `enterprises` 的数字根，故本文没有将符号 OID 宣称为可由随附资料独立验证的绝对数字 OID。
3. 没有产品专属 Trap；唯一 `generalNotification` 没有触发条件、`level` 枚举/严重度映射、恢复语义、通知地址或启用配置 OID。
4. `generalErrorCode` 没有错误码字典；不能按数值自动分级。`temperature1`、`powerCurrent`、`powerVoltage` 与 `fanSpeed` 都没有告警阈值或采样语义。
5. `cpuChannelVideoEntry` 用 `{ cpuChannelIndex, cpuChannelVideoIndex }` 作索引，但其 `SEQUENCE` 仅列出 `cpuChannelVideoIndex` 等字段，且 `cpuChannelIndex` 定义在另一张表；须用真实 walk 验证行实例的索引编码和可出现的组合。
6. 4 个表的索引范围只是可取范围，未承诺实际存在的行数；应以 GETNEXT/GETBULK 结果驱动 UI 行数。
7. 写操作虽标为 `read-write`，但没有写入权限、失败码、持久化、回滚或并发规则，生产控制流程须另行确认。

## 可执行核验清单

以下检查在厂商确认连通参数后执行。示例 OID 保留 `enterprises` 符号根；加载随附 MIB 后由 SNMP 工具解析。若工具要求绝对数字根，应先向厂商索取/确认该根的来源，不要把本文未能从资料独立证明的数字写入基线。

1. **标量实例：**对 `deviceId.0`（`enterprises.32828.3.1792.17.2.1.1.0`）执行 SNMP GET，验证返回 `DisplayString`，并确认缺少 `.0` 的请求不能被当作标量值处理。依据：`dp/GUD-DP12MUXATC-MIB.txt:183-189`。
2. **枚举：**GET `networkInterface0.0`，确认返回值只按 `NetworkInterfaceStatus` 解码为 `down(0)` 或 `up(1)`，不把该数值映射为未经证实的告警严重度。依据：`dp/GUD-DP12MUXATC-MIB.txt:49-56,302-308`。
3. **CPU 通道表索引：**对 `cpuChannelTargetDevice` 列根 `...17.2.3.1000.1.3` 进行 GETNEXT/GETBULK，验证返回实例后缀为 `1..4` 范围内的一个 `cpuChannelIndex`，并将它作为通道行键。依据：`dp/GUD-DP12MUXATC-MIB.txt:330-370`。
4. **双索引视频表：**walk `cpuChannelVideoSignal` 列根 `...17.2.3.1001.1.3`，记录实际实例后缀并核对其顺序为 MIB 指定的 `<cpuChannelIndex>.<cpuChannelVideoIndex>`；若不符，保留原始响应并向厂商确认。依据：`dp/GUD-DP12MUXATC-MIB.txt:408-445`。
5. **风扇范围：**walk `fanSpeed` 列根 `...17.2.3.1003.1.2`，验证实际行键在 `fanIndex 1..20` 内，数值在 `Integer32(0..10000)` 内，并只按 RPM 展示、不擅自设阈值。依据：`dp/GUD-DP12MUXATC-MIB.txt:519-547`。
6. **Trap 变量：**向 Trap 接收器产生/等待一条 `generalNotification`，验证通知 OID 是 `...2.1.0.4`，并同时捕获 `level` 与 `message` 两个 OBJECTS 变量及原始值；检查不存在时不得伪造严重度或恢复状态。依据：`dp/GUD-GENERALTRAPS-MIB.txt:32-54`。
7. **读写权限：**在隔离设备读取并（获批准后）将 `selectedChannel.0` 设置为当前以外的 `1..4` 合法值，读取回显和 active channel；不得对 `mainPower` 或 `fanSpeed` 尝试 SET，因为二者为 `read-only`。依据：`dp/GUD-DP12MUXATC-MIB.txt:243-249,541-557`。
