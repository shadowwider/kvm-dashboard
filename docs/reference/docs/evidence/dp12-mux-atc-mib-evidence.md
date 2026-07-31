# DP1.2-MUX-ATC MIB 原文证据与 OID 推导台账

本台账仅引用 `dp/` 内的原始 `*-MIB.txt`。行号为本次交付读取到的原始文本行号；不引用 PDF 或外部资料。本文中的 `E` 是导入的 `enterprises` 符号。`GUD-SMI-MIB` 从 `SNMPv2-SMI` 导入该符号但没有在资料包中定义其数字根（源：`dp/GUD-SMI-MIB.txt:4-6`），所以 `E` 不被改写为不可从随附原文独立复算的绝对数值前缀。

## 文件清单与模块证据

|文件/模块|原文版本证据|本次使用的事实|
|---|---|---|
|`dp/GUD-SMI-MIB.txt` / `GUD-SMI-MIB`|模块元数据：`8-20`|`gudEnterprise`、产品树、公共 Trap 树和本设备产品节点。|
|`dp/GUD-DP12MUXATC-MIB.txt` / `GUD-DP12MUXATC-MIB`|模块元数据：`14-26`|DP1.2-MUX-ATC 身份、状态、表、写操作、错误对象、合规组。|
|`dp/GUD-GENERALTRAPS-MIB.txt` / `GUD-GENERALTRAP-MIB`|模块元数据：`16-28`|通用 Trap 的变量和通知。注意文件名与模块标识符的 `TRAPS`/`TRAP` 单复数不同，按原文保留。|

## OID 根与数值段复算

### DP1.2-MUX-ATC 产品树

|符号|原文赋值|展开结果|证据|
|---|---|---|---|
|`gudEnterprise`|`{ enterprises 32828 }`|`E.32828`|源：`dp/GUD-SMI-MIB.txt:26-31`|
|`gudProduct`|`{ gudEnterprise 3 }`|`E.32828.3`|源：`dp/GUD-SMI-MIB.txt:45-49`|
|`gudKVMSWITCH`|`{ gudProduct 1792 }`|`E.32828.3.1792`|源：`dp/GUD-SMI-MIB.txt:315-319`|
|`gudDP12MUXATC`|`{ gudKVMSWITCH 17 }`|`E.32828.3.1792.17`|源：`dp/GUD-SMI-MIB.txt:340-346`|
|`gudDP12MUXATCMIB`|`{ gudDP12MUXATC 1 }`|`E.32828.3.1792.17.1`|源：`dp/GUD-DP12MUXATC-MIB.txt:14-26`|
|`objects`|`{ gudDP12MUXATC 2 }`|`E.32828.3.1792.17.2`|源：`dp/GUD-DP12MUXATC-MIB.txt:116-120`|
|`identify`|`{ objects 1 }`|`E.32828.3.1792.17.2.1`|源：`dp/GUD-DP12MUXATC-MIB.txt:122-126`|
|`info`|`{ objects 2 }`|`E.32828.3.1792.17.2.2`|源：`dp/GUD-DP12MUXATC-MIB.txt:128-132`|
|`status`|`{ objects 3 }`|`E.32828.3.1792.17.2.3`|源：`dp/GUD-DP12MUXATC-MIB.txt:134-138`|
|`connection`|`{ objects 4 }`|`E.32828.3.1792.17.2.4`|源：`dp/GUD-DP12MUXATC-MIB.txt:140-144`|
|`configuration`|`{ objects 5 }`|`E.32828.3.1792.17.2.5`|源：`dp/GUD-DP12MUXATC-MIB.txt:146-150`|
|`errormessages`|`{ objects 1000 }`|`E.32828.3.1792.17.2.1000`|源：`dp/GUD-DP12MUXATC-MIB.txt:152-156`|

### 公共 Trap 树

|符号|原文赋值|展开结果|证据|
|---|---|---|---|
|`gudTrap`|`{ gudEnterprise 2 }`|`E.32828.2`|源：`dp/GUD-SMI-MIB.txt:36-40`|
|`gudGeneralTrap`|`{ gudTrap 1 }`|`E.32828.2.1`|源：`dp/GUD-SMI-MIB.txt:54-58`|
|`gudGeneralNotifications`|`{ gudGeneralTrap 0 }`|`E.32828.2.1.0`|源：`dp/GUD-GENERALTRAPS-MIB.txt:30-30`|

## `GUD-DP12MUXATC-MIB`：文本约定、对象与表

### 文本约定

|类型|枚举/范围|原文证据|
|---|---|---|
|`Boolean`|`false(0)`, `true(1)`|源：`dp/GUD-DP12MUXATC-MIB.txt:31-38`|
|`PowerStatus`|`off(0)`, `on(1)`|源：`dp/GUD-DP12MUXATC-MIB.txt:40-47`|
|`NetworkInterfaceStatus`|`down(0)`, `up(1)`|源：`dp/GUD-DP12MUXATC-MIB.txt:49-56`|
|`ConnectionStatus`|`notConnected(0)`, `connected(1)`|源：`dp/GUD-DP12MUXATC-MIB.txt:58-65`|
|`VideoType`|`none(0)`, `vga(1)`, `dvisl(2)`, `dvidl(3)`, `dmdp(4)`, `dp(5)`, `hdmi(6)`|源：`dp/GUD-DP12MUXATC-MIB.txt:67-79`|
|`KeyboardMouseStatus`|`none(0)`, `keyboard(1)`, `mouse(2)`, `keyboardMouse(3)`|源：`dp/GUD-DP12MUXATC-MIB.txt:81-90`|
|`UsbHidStatus`|`notConnected(0)`, `connected(1)`, `initialized(2)`|源：`dp/GUD-DP12MUXATC-MIB.txt:92-100`|
|`Usb30Status`|`inactive(0)`, `active(1)`|源：`dp/GUD-DP12MUXATC-MIB.txt:102-109`|

### 标量对象

下表 `OID` 是对象定义 OID；`实例` 列显示管理端轮询标量时使用的 `.0`。`.0` 是实例编排而非 MIB 中单独定义的一个对象。

|对象|OID（由根和原文赋值复算）|实例|SYNTAX|MAX-ACCESS|描述/单位|原文证据|
|---|---|---|---|---|---|---|
|`deviceId`|`E.32828.3.1792.17.2.1.1`|`...1.0`|`DisplayString`|`read-only`|ID of the device|源：`dp/GUD-DP12MUXATC-MIB.txt:183-189`|
|`deviceCl`|`E.32828.3.1792.17.2.1.2`|`...2.0`|`DisplayString`|`read-only`|Class of the device|源：`dp/GUD-DP12MUXATC-MIB.txt:191-197`|
|`deviceType`|`E.32828.3.1792.17.2.1.3`|`...3.0`|`DisplayString`|`read-only`|Type of the device|源：`dp/GUD-DP12MUXATC-MIB.txt:199-205`|
|`serialNumber`|`E.32828.3.1792.17.2.1.4`|`...4.0`|`DisplayString`|`read-only`|Serial number|源：`dp/GUD-DP12MUXATC-MIB.txt:207-213`|
|`etherAddress0`|`E.32828.3.1792.17.2.1.5`|`...5.0`|`PhysAddress`|`read-only`|First ethernet-port MAC address|源：`dp/GUD-DP12MUXATC-MIB.txt:215-221`|
|`etherAddress1`|`E.32828.3.1792.17.2.1.6`|`...6.0`|`PhysAddress`|`read-only`|Second ethernet-port MAC address|源：`dp/GUD-DP12MUXATC-MIB.txt:223-229`|
|`firmwareVersion`|`E.32828.3.1792.17.2.2.1`|`...1.0`|`DisplayString`|`read-only`|Firmware version|源：`dp/GUD-DP12MUXATC-MIB.txt:233-239`|
|`mainPower`|`E.32828.3.1792.17.2.3.1`|`...1.0`|`PowerStatus`|`read-only`|Main power status|源：`dp/GUD-DP12MUXATC-MIB.txt:243-249`|
|`redundantPower`|`E.32828.3.1792.17.2.3.2`|`...2.0`|`PowerStatus`|`read-only`|Redundant power status|源：`dp/GUD-DP12MUXATC-MIB.txt:251-257`|
|`temperature1`|`E.32828.3.1792.17.2.3.3`|`...3.0`|`DisplayString`|`read-only`|Internal temperature 1, `[Deg C]`|源：`dp/GUD-DP12MUXATC-MIB.txt:259-266`|
|`powerCurrent`|`E.32828.3.1792.17.2.3.500`|`...500.0`|`DisplayString`|`read-only`|Power-supply current, comment `A`|源：`dp/GUD-DP12MUXATC-MIB.txt:268-275`|
|`powerVoltage`|`E.32828.3.1792.17.2.3.501`|`...501.0`|`DisplayString`|`read-only`|Power-supply voltage, comment `V`|源：`dp/GUD-DP12MUXATC-MIB.txt:277-284`|
|`consolePS2Connection`|`E.32828.3.1792.17.2.3.7`|`...7.0`|`KeyboardMouseStatus`|`read-only`|Console PS/2 keyboard/mouse connection|源：`dp/GUD-DP12MUXATC-MIB.txt:286-292`|
|`consoleUSBConnection`|`E.32828.3.1792.17.2.3.8`|`...8.0`|`KeyboardMouseStatus`|`read-only`|Console USB keyboard/mouse connection|源：`dp/GUD-DP12MUXATC-MIB.txt:294-300`|
|`networkInterface0`|`E.32828.3.1792.17.2.3.506`|`...506.0`|`NetworkInterfaceStatus`|`read-only`|First network-interface status|源：`dp/GUD-DP12MUXATC-MIB.txt:302-308`|
|`networkInterface1`|`E.32828.3.1792.17.2.3.507`|`...507.0`|`NetworkInterfaceStatus`|`read-only`|Second network-interface status|源：`dp/GUD-DP12MUXATC-MIB.txt:310-316`|
|`selectedChannel`|`E.32828.3.1792.17.2.4.1`|`...1.0`|`Integer32(1..4)`|`read-write`|Read active channel; write switches to channel|源：`dp/GUD-DP12MUXATC-MIB.txt:550-557`|
|`disableSwitching`|`E.32828.3.1792.17.2.5.1`|`...1.0`|`Boolean`|`read-write`|Enable/disable channel switching|源：`dp/GUD-DP12MUXATC-MIB.txt:561-568`|
|`disableFrontkeys`|`E.32828.3.1792.17.2.5.2`|`...2.0`|`Boolean`|`read-write`|Enable/disable front keys|源：`dp/GUD-DP12MUXATC-MIB.txt:570-577`|
|`disableHotkeys`|`E.32828.3.1792.17.2.5.3`|`...3.0`|`Boolean`|`read-write`|Enable/disable hotkeys|源：`dp/GUD-DP12MUXATC-MIB.txt:579-586`|
|`disableSerialPort`|`E.32828.3.1792.17.2.5.4`|`...4.0`|`Boolean`|`read-write`|Enable/disable serial-port switching|源：`dp/GUD-DP12MUXATC-MIB.txt:588-595`|
|`disableRemoteControlApi`|`E.32828.3.1792.17.2.5.5`|`...5.0`|`Boolean`|`read-write`|Enable/disable Remote control API switching|源：`dp/GUD-DP12MUXATC-MIB.txt:597-604`|
|`generalErrorCode`|`E.32828.3.1792.17.2.1000.1`|`...1.0`|`Integer32`|`read-only`|Error code; no code list|源：`dp/GUD-DP12MUXATC-MIB.txt:607-613`|
|`generalErrorMessage`|`E.32828.3.1792.17.2.1000.2`|`...2.0`|`DisplayString`|`read-only`|Problem-description error message|源：`dp/GUD-DP12MUXATC-MIB.txt:615-621`|

### 表、entry 与索引证据

|表|table OID / 权限|entry OID / 权限|`INDEX` 与索引 OID、范围、权限|遍历可读列（列 OID 模板）|原文证据|
|---|---|---|---|---|---|
|`cpuChannelTable`|`E.32828.3.1792.17.2.3.1000` / `not-accessible`|`cpuChannelEntry = ...1000.1` / `not-accessible`|`{ cpuChannelIndex }`；`cpuChannelIndex = ...1000.1.1`，`Integer32(1..4)`，`not-accessible`|`cpuChannelTargetUsbHid ...1000.1.2.<cpuChannelIndex>`；`cpuChannelTargetDevice ...1.3.<cpuChannelIndex>`；`cpuChannelTargetPower ...1.4.<cpuChannelIndex>`；`cpuChannelTargetPS2 ...1.5.<cpuChannelIndex>`；`cpuChannelTargetUsb30 ...1.6.<cpuChannelIndex>`|源：`dp/GUD-DP12MUXATC-MIB.txt:322-394`|
|`cpuChannelVideoTable`|`E.32828.3.1792.17.2.3.1001` / `not-accessible`|`cpuChannelVideoEntry = ...1001.1` / `not-accessible`|`{ cpuChannelIndex, cpuChannelVideoIndex }`；`cpuChannelVideoIndex = ...1001.1.1`，`Integer32(1..4)`，`not-accessible`；第一索引取前表定义的 `cpuChannelIndex`|`cpuChannelVideoCable ...1001.1.2.<cpuChannelIndex>.<cpuChannelVideoIndex>`；`cpuChannelVideoSignal ...1.3.<cpuChannelIndex>.<cpuChannelVideoIndex>`|源：`dp/GUD-DP12MUXATC-MIB.txt:400-445`；`cpuChannelIndex` 源：`...:348-354`|
|`consoleVideoTable`|`E.32828.3.1792.17.2.3.1002` / `not-accessible`|`consoleVideoEntry = ...1002.1` / `not-accessible`|`{ consoleVideoIndex }`；`consoleVideoIndex = ...1002.1.1`，`Integer32(1..4)`，`not-accessible`|`displayConnection ...1002.1.2.<consoleVideoIndex>`；`displayType ...1.3.<consoleVideoIndex>`；`freeze ...1.4.<consoleVideoIndex>`|源：`dp/GUD-DP12MUXATC-MIB.txt:451-505`|
|`fanTable`|`E.32828.3.1792.17.2.3.1003` / `not-accessible`|`fanTableEntry = ...1003.1` / `not-accessible`|`{ fanIndex }`；`fanIndex = ...1003.1.1`，`Integer32(1..20)`，`not-accessible`|`fanSpeed ...1003.1.2.<fanIndex>`；`Integer32(0..10000)`，RPM，`read-only`|源：`dp/GUD-DP12MUXATC-MIB.txt:511-547`|

列对象逐项行号：`cpuChannelTargetUsbHid` `356-362`、`cpuChannelTargetDevice` `364-370`、`cpuChannelTargetPower` `372-378`、`cpuChannelTargetPS2` `380-386`、`cpuChannelTargetUsb30` `388-394`、`cpuChannelVideoCable` `431-437`、`cpuChannelVideoSignal` `439-445`、`displayConnection` `483-489`、`displayType` `491-497`、`freeze` `499-505`、`fanSpeed` `541-547`。均源：`dp/GUD-DP12MUXATC-MIB.txt` 对应行。

### 合规性/可选组证据

模块合规性把 `identifyGroup`、`infoGroup`、`statusGroup` 列为 mandatory；`connectionGroup`、`configurationGroup`、`errorGroup` 标为 optional。故 UI/轮询实现须接受后三组返回缺失/不支持，不能把 MIB 中存在即当作每台设备必有。源：`dp/GUD-DP12MUXATC-MIB.txt:628-644`。各组实际对象清单见 `646-705`。

## `GUD-GENERALTRAP-MIB`：通知与变量证据

|名称|OID 推导|语法/权限或通知内容|原文证据|
|---|---|---|---|
|`level`|`E.32828.2.1.0.2`|`Integer32`，`read-only`；描述仅为 notification level，无枚举|源：`dp/GUD-GENERALTRAPS-MIB.txt:32-38`|
|`message`|`E.32828.2.1.0.3`|`DisplayString`，`read-only`；消息文本|源：`dp/GUD-GENERALTRAPS-MIB.txt:40-46`|
|`generalNotification`|`E.32828.2.1.0.4`|`NOTIFICATION-TYPE`，`OBJECTS { level, message }`；描述仅为 G&D general notification|源：`dp/GUD-GENERALTRAPS-MIB.txt:48-54`|

原文没有其他 `NOTIFICATION-TYPE`/`TRAP-TYPE`，没有触发条件、恢复事件、`level` 严重度字典，亦没有 Trap 接收地址或通知启用对象。公共通知合规组将该通知与两个变量列为 mandatory。源：`dp/GUD-GENERALTRAPS-MIB.txt:64-86`。

## 计数与交叉复算

- DP 设备 MIB 中可读监控对象 29 个：身份 6、固件 1、设备状态标量 9、四张表的可读列 11、错误对象 2。
- 可写对象 6 个：`selectedChannel` 和 5 个 `disable*` 配置对象。
- 4 张表、5 个索引组成位置（其中 `cpuChannelIndex` 被两张表的 INDEX 引用，但只有一个对象定义）。
- 通知 1 个，通知变量 2 个。
- 复算抽样：`fanSpeed` = `E.32828.3.1792.17` + `.2`（objects）+ `.3`（status）+ `.1003`（fan table）+ `.1`（entry）+ `.2`（column），与原文 `fanTable`、`fanTableEntry`、`fanSpeed` 的赋值一致。源：`dp/GUD-DP12MUXATC-MIB.txt:116-120,134-138,511-547`。
