# VisionXS MIB 原文证据与 OID 推导记录

## 证据范围、计数与读法

本记录仅以 `vision/` 中的四份 `*-MIB.txt` 为 MIB/OID 事实来源；未使用外网资料，也不把同目录 PDF 中的监控表当作 MIB 对象、权限或 Trap 定义来源。

- 模块数：4；`OBJECT-TYPE` 定义数：69（通用 Trap 2、CPU 34、CON 33）；其中 CPU 可读业务变量 28、CON 可读业务变量 27，通用通知变量 2；`NOTIFICATION-TYPE` 数：1；`TRAP-TYPE` 数：0。
- `enterprises` 由 `SNMPv2-SMI` 导入，随附 MIB 没有给出它的数字根。因此，以下 `1.3.6.1.4.1` 是为方便实施而使用的 SNMP 标准 `enterprises` 根写法，**不能只凭随附四份原文独立复算**；原文可独立核验的主证据同时保留为符号 OID 路径。`gudEnterprise ::= { enterprises 32828 }` 是随附资料给出的第一个数值弧。源：`vision/GUD-SMI-MIB.txt:4-6,26-31`。
- 标量实际 GET 实例在对象基础 OID 之后加 `.0`；这是 SNMP 标量实例写法。表项不添加 `.0`，而在列 OID 后添加 MIB 声明的 `INDEX` 值。表、entry 与 index 为 `not-accessible`，不作为单独业务采集点。其表索引原文见各表的证据行。

|文件|行数|`MODULE-IDENTITY` 原文版本/更新时间|SHA-256|
|---|---:|---|---|
|`vision/GUD-SMI-MIB.txt`|502|Rev. 1.7；`202305010000Z`；源：`:8-20`|`d08d60f5f715556ab12339eb59bd1a91355e686b463d7f75e9d6b764c05ae96e`|
|`vision/GUD-GENERALTRAPS-MIB.txt`|89|Rev. 1.0；`200901141407Z`；源：`:16-28`|`d575b112175e1e23b98f98afb97e053bc86ad4fe2a10df8d137f595c160fc1e9`|
|`vision/GUD-VISIONXSCPU-MIB.txt`|554|Rev. 1.1；`202404010000Z`；源：`:13-25`|`3a0c95d685c69b453d6ac04498901615f822517d898a47c904e09d7b2d2d5534`|
|`vision/GUD-VISIONXSCON-MIB.txt`|522|Rev. 1.1；`202404010000Z`；源：`:14-26`|`8a280a6b197dad57eacbe03c48e40572ecfc997899f0e37d0f74c804a36f478d`|

## `GUD-SMI-MIB`：产品树原文与复算

|符号 OID（原文）|父子弧|实施用数值 OID|原文证据|
|---|---|---|---|
|`gudEnterprise`|`{ enterprises 32828 }`|`1.3.6.1.4.1.32828`|`vision/GUD-SMI-MIB.txt:26-31`|
|`gudTrap`|`{ gudEnterprise 2 }`|`1.3.6.1.4.1.32828.2`|`vision/GUD-SMI-MIB.txt:36-40`|
|`gudGeneralTrap`|`{ gudTrap 1 }`|`1.3.6.1.4.1.32828.2.1`|`vision/GUD-SMI-MIB.txt:52-58`|
|`gudProduct`|`{ gudEnterprise 3 }`|`1.3.6.1.4.1.32828.3`|`vision/GUD-SMI-MIB.txt:45-49`|
|`gudKVMEXTENDERCPU`|`{ gudProduct 768 }`|`1.3.6.1.4.1.32828.3.768`|`vision/GUD-SMI-MIB.txt:178-184`|
|`gudKVMEXTENDERCON`|`{ gudProduct 769 }`|`1.3.6.1.4.1.32828.3.769`|`vision/GUD-SMI-MIB.txt:187-193`|
|`gudVISIONXSCPU`|`{ gudKVMEXTENDERCPU 768 }`|`1.3.6.1.4.1.32828.3.768.768`|`vision/GUD-SMI-MIB.txt:268-274`|
|`gudVISIONXSCON`|`{ gudKVMEXTENDERCON 768 }`|`1.3.6.1.4.1.32828.3.769.768`|`vision/GUD-SMI-MIB.txt:277-283`|

复算：CPU 设备前缀 = `enterprises.32828.3.768.768`，CON 设备前缀 = `enterprises.32828.3.769.768`，通用 Trap 前缀 = `enterprises.32828.2.1`；与上表每段逐层父子关系一致。MIB 使用 `OBJECT-IDENTITY` 描述 CPU/CON 分别为 VISION-XS-CPU/CON。源：`vision/GUD-SMI-MIB.txt:268-283`。

## `GUD-GENERALTRAPS-MIB`：通知与对象证据

模块身份位于 `{ gudGeneralTrap 1 }`；`gudGeneralNotifications` 位于 `{ gudGeneralTrap 0 }`，故其实施前缀为 `1.3.6.1.4.1.32828.2.1.0`。源：`vision/GUD-GENERALTRAPS-MIB.txt:16-30`。

|对象/通知|原文符号路径|数值 OID / 实例|类型、权限或对象列表|原文证据|
|---|---|---|---|---|
|`level`|`gudGeneralNotifications.2`|`1.3.6.1.4.1.32828.2.1.0.2`|`Integer32`，`read-only`；描述为 notification level；无枚举|`vision/GUD-GENERALTRAPS-MIB.txt:32-38`|
|`message`|`gudGeneralNotifications.3`|`1.3.6.1.4.1.32828.2.1.0.3`|`DisplayString`，`read-only`；消息文本|`vision/GUD-GENERALTRAPS-MIB.txt:40-46`|
|`generalNotification`|`gudGeneralNotifications.4`|`1.3.6.1.4.1.32828.2.1.0.4`|`NOTIFICATION-TYPE`；`OBJECTS { level, message }`；仅称 G&D general notification|`vision/GUD-GENERALTRAPS-MIB.txt:48-54`|

通知合规组明确列出 `generalNotification`，对象组列出 `level, message`；没有触发条件、级别词典、恢复通知或接收方配置 OID。源：`vision/GUD-GENERALTRAPS-MIB.txt:60-86`。

## `GUD-VISIONXSCPU-MIB`：类型、对象与索引证据

CPU 模块身份为 `{ gudVISIONXSCPU 1 }`；业务对象树不在该 module-identity 下，而是 `objects ::= { gudVISIONXSCPU 2 }`，再分为 `identify=objects.1`、`info=objects.2`、`status=objects.3`、`errormessages=objects.1000`。复算后分别为 `C.2`、`C.2.1`、`C.2.2`、`C.2.3`、`C.2.1000`，其中 `C=1.3.6.1.4.1.32828.3.768.768`。源：`vision/GUD-VISIONXSCPU-MIB.txt:13-25,135-164`。

### CPU 文本约定（对象解码的唯一枚举来源）

|类型|原文枚举|原文证据|
|---|---|---|
|`PowerStatus`|`off(0)`、`on(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:30-37`|
|`NetworkInterfaceStatus`|`down(0)`、`up(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:39-46`|
|`ConnectionStatus`|`notConnected(0)`、`connected(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:48-55`|
|`LinkStatus`|`down(0)`、`up(1)`、`crossed(2)`|`vision/GUD-VISIONXSCPU-MIB.txt:57-65`|
|`TransparentUsbLinkStatus`|`down(0)`、`up(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:67-74`|
|`VideoType`|`none(0)`、`vga(1)`、`dvisl(2)`、`dvidl(3)`、`dmdp(4)`、`dp(5)`、`hdmi(6)`|`vision/GUD-VISIONXSCPU-MIB.txt:76-88`|
|`KeyboardMouseStatus`|`none(0)`、`keyboard(1)`、`mouse(2)`、`keyboardMouse(3)`|`vision/GUD-VISIONXSCPU-MIB.txt:90-99`|
|`UsbHidStatus`|`notConnected(0)`、`connected(1)`、`initialized(2)`|`vision/GUD-VISIONXSCPU-MIB.txt:101-109`|
|`Usb20Status`|`inactive(0)`、`active(1)`|`vision/GUD-VISIONXSCPU-MIB.txt:111-118`|
|`SfpModuleStatus`|`noModule(0)`、`moduleDeactivated(1)`、`down(2)`、`up(3)`|`vision/GUD-VISIONXSCPU-MIB.txt:120-129`|

### CPU 非表对象（全部逐项 `OBJECT-TYPE` 证据）

以下“GET 实例”均为对象基础 OID 加 `.0`；每个对象原文均明示 `MAX-ACCESS read-only`。

|对象|原文符号路径|GET 实例（数值）|SYNTAX/描述摘要|原文证据|
|---|---|---|---|---|
|`deviceId`|`identify.1`|`1.3.6.1.4.1.32828.3.768.768.2.1.1.0`|`DisplayString`；device ID|`vision/GUD-VISIONXSCPU-MIB.txt:191-197`|
|`deviceCl`|`identify.2`|`1.3.6.1.4.1.32828.3.768.768.2.1.2.0`|`DisplayString`；device class|`vision/GUD-VISIONXSCPU-MIB.txt:199-205`|
|`deviceType`|`identify.3`|`1.3.6.1.4.1.32828.3.768.768.2.1.3.0`|`DisplayString`；device type|`vision/GUD-VISIONXSCPU-MIB.txt:207-213`|
|`serialNumber`|`identify.4`|`1.3.6.1.4.1.32828.3.768.768.2.1.4.0`|`DisplayString`；serial number|`vision/GUD-VISIONXSCPU-MIB.txt:215-221`|
|`etherAddress0`|`identify.5`|`1.3.6.1.4.1.32828.3.768.768.2.1.5.0`|`PhysAddress`；first ethernet port MAC|`vision/GUD-VISIONXSCPU-MIB.txt:223-229`|
|`firmwareVersion`|`info.1`|`1.3.6.1.4.1.32828.3.768.768.2.2.1.0`|`DisplayString`；firmware version|`vision/GUD-VISIONXSCPU-MIB.txt:232-238`|
|`mainPower`|`status.1`|`1.3.6.1.4.1.32828.3.768.768.2.3.1.0`|`PowerStatus`；main power device|`vision/GUD-VISIONXSCPU-MIB.txt:241-247`|
|`redundantPower`|`status.2`|`1.3.6.1.4.1.32828.3.768.768.2.3.2.0`|`PowerStatus`；redundant power device|`vision/GUD-VISIONXSCPU-MIB.txt:249-255`|
|`temperature1`|`status.3`|`1.3.6.1.4.1.32828.3.768.768.2.3.3.0`|`DisplayString`；internal temperature 1；`UNITS` 仅为注释|`vision/GUD-VISIONXSCPU-MIB.txt:257-264`|
|`fan1`|`status.502`|`1.3.6.1.4.1.32828.3.768.768.2.3.502.0`|`DisplayString`；fan 1 speed；`UNITS` 仅为注释|`vision/GUD-VISIONXSCPU-MIB.txt:266-273`|
|`networkInterface0`|`status.506`|`1.3.6.1.4.1.32828.3.768.768.2.3.506.0`|`NetworkInterfaceStatus`；first network interface|`vision/GUD-VISIONXSCPU-MIB.txt:275-281`|
|`transparentUsbLink`|`status.10`|`1.3.6.1.4.1.32828.3.768.768.2.3.10.0`|`TransparentUsbLinkStatus`；transparent USB module link|`vision/GUD-VISIONXSCPU-MIB.txt:283-289`|
|`targetPower`|`status.11`|`1.3.6.1.4.1.32828.3.768.768.2.3.11.0`|`PowerStatus`；target power|`vision/GUD-VISIONXSCPU-MIB.txt:291-297`|
|`targetUsbHid`|`status.13`|`1.3.6.1.4.1.32828.3.768.768.2.3.13.0`|`UsbHidStatus`；USB keyboard/mouse connection to target|`vision/GUD-VISIONXSCPU-MIB.txt:299-305`|
|`targetUsb20`|`status.15`|`1.3.6.1.4.1.32828.3.768.768.2.3.15.0`|`Usb20Status`；USB 2.0 extender connection to target|`vision/GUD-VISIONXSCPU-MIB.txt:307-313`|
|`transparentUsbSfpModule`|`status.16`|`1.3.6.1.4.1.32828.3.768.768.2.3.16.0`|`SfpModuleStatus`；USB SFP link status|`vision/GUD-VISIONXSCPU-MIB.txt:315-321`|
|`transparentUsbTxPower`|`status.17`|`1.3.6.1.4.1.32828.3.768.768.2.3.17.0`|`Integer32`；USB SFP TX power [uW]|`vision/GUD-VISIONXSCPU-MIB.txt:323-329`|
|`transparentUsbRxPower`|`status.18`|`1.3.6.1.4.1.32828.3.768.768.2.3.18.0`|`Integer32`；USB SFP RX power [uW]|`vision/GUD-VISIONXSCPU-MIB.txt:331-337`|
|`transparentUsbSfpType`|`status.19`|`1.3.6.1.4.1.32828.3.768.768.2.3.19.0`|`DisplayString`；USB SFP type|`vision/GUD-VISIONXSCPU-MIB.txt:339-345`|
|`generalErrorCode`|`errormessages.1`|`1.3.6.1.4.1.32828.3.768.768.2.1000.1.0`|`Integer32`；error code；无代码字典|`vision/GUD-VISIONXSCPU-MIB.txt:482-488`|
|`generalErrorMessage`|`errormessages.2`|`1.3.6.1.4.1.32828.3.768.768.2.1000.2.0`|`DisplayString`；error message|`vision/GUD-VISIONXSCPU-MIB.txt:490-496`|

### CPU 表结构、索引与列（每个结构/列逐项证据）

|对象|数值基础 OID 或行实例模式|权限/索引/语义|原文证据|
|---|---|---|---|
|`videoChannelTable`|`1.3.6.1.4.1.32828.3.768.768.2.3.1000`|`SEQUENCE OF VideoChannelEntry`，`not-accessible`|`vision/GUD-VISIONXSCPU-MIB.txt:351-357`|
|`videoChannelEntry`|`1.3.6.1.4.1.32828.3.768.768.2.3.1000.1`|`not-accessible`；`INDEX { videoChannelIndex }`|`vision/GUD-VISIONXSCPU-MIB.txt:359-366`|
|`videoChannelIndex`|`1.3.6.1.4.1.32828.3.768.768.2.3.1000.1.1.<i>`|`Integer32(1..4)`，`not-accessible`；索引，不能单独 GET|`vision/GUD-VISIONXSCPU-MIB.txt:368-380`|
|`targetVideoCable`|`1.3.6.1.4.1.32828.3.768.768.2.3.1000.1.2.<i>`|`ConnectionStatus`，`read-only`；target video cable connection|`vision/GUD-VISIONXSCPU-MIB.txt:382-388`|
|`targetVideoSignal`|`1.3.6.1.4.1.32828.3.768.768.2.3.1000.1.3.<i>`|`VideoType`，`read-only`；video signal status|`vision/GUD-VISIONXSCPU-MIB.txt:390-396`|
|`linkChannelTable`|`1.3.6.1.4.1.32828.3.768.768.2.3.1001`|`SEQUENCE OF LinkChannelEntry`，`not-accessible`|`vision/GUD-VISIONXSCPU-MIB.txt:403-409`|
|`linkChannelEntry`|`1.3.6.1.4.1.32828.3.768.768.2.3.1001.1`|`not-accessible`；`INDEX { linkChannelIndex }`|`vision/GUD-VISIONXSCPU-MIB.txt:411-418`|
|`linkChannelIndex`|`1.3.6.1.4.1.32828.3.768.768.2.3.1001.1.1.<i>`|`Integer32(1..8)`，`not-accessible`；索引，不能单独 GET|`vision/GUD-VISIONXSCPU-MIB.txt:420-435`|
|`link`|`1.3.6.1.4.1.32828.3.768.768.2.3.1001.1.2.<i>`|`LinkStatus`，`read-only`|`vision/GUD-VISIONXSCPU-MIB.txt:437-443`|
|`sfpModule`|`1.3.6.1.4.1.32828.3.768.768.2.3.1001.1.3.<i>`|`SfpModuleStatus`，`read-only`|`vision/GUD-VISIONXSCPU-MIB.txt:445-451`|
|`sfpTxPower`|`1.3.6.1.4.1.32828.3.768.768.2.3.1001.1.4.<i>`|`Integer32`，`read-only`；[uW]|`vision/GUD-VISIONXSCPU-MIB.txt:453-459`|
|`sfpRxPower`|`1.3.6.1.4.1.32828.3.768.768.2.3.1001.1.5.<i>`|`Integer32`，`read-only`；[uW]|`vision/GUD-VISIONXSCPU-MIB.txt:461-467`|
|`sfpType`|`1.3.6.1.4.1.32828.3.768.768.2.3.1001.1.6.<i>`|`DisplayString`，`read-only`|`vision/GUD-VISIONXSCPU-MIB.txt:469-475`|

CPU 合规声明：`identifyGroup`、`infoGroup`、`statusGroup` 是强制组，`errorGroup` 是可选组；透明 USB 的五个对象被注释出 `statusGroup` 列表。源：`vision/GUD-VISIONXSCPU-MIB.txt:502-552`。

## `GUD-VISIONXSCON-MIB`：类型、对象与索引证据

CON 模块身份为 `{ gudVISIONXSCON 1 }`；其业务对象树同样从 `objects ::= { gudVISIONXSCON 2 }` 开始，分支为 `identify=.1`、`info=.2`、`status=.3`、`errormessages=.1000`。复算中 `K=1.3.6.1.4.1.32828.3.769.768`。源：`vision/GUD-VISIONXSCON-MIB.txt:14-26,112-160`。

### CON 文本约定（对象解码的唯一枚举来源）

|类型|原文枚举|原文证据|
|---|---|---|
|`Boolean`|`false(0)`、`true(1)`|`vision/GUD-VISIONXSCON-MIB.txt:31-38`|
|`PowerStatus`|`off(0)`、`on(1)`|`vision/GUD-VISIONXSCON-MIB.txt:40-47`|
|`NetworkInterfaceStatus`|`down(0)`、`up(1)`|`vision/GUD-VISIONXSCON-MIB.txt:49-56`|
|`ConnectionStatus`|`notConnected(0)`、`connected(1)`|`vision/GUD-VISIONXSCON-MIB.txt:58-65`|
|`LinkStatus`|`down(0)`、`up(1)`、`crossed(2)`|`vision/GUD-VISIONXSCON-MIB.txt:67-75`|
|`TransparentUsbLinkStatus`|`down(0)`、`up(1)`|`vision/GUD-VISIONXSCON-MIB.txt:77-84`|
|`KeyboardMouseStatus`|`none(0)`、`keyboard(1)`、`mouse(2)`、`keyboardMouse(3)`|`vision/GUD-VISIONXSCON-MIB.txt:86-95`|
|`SfpModuleStatus`|`noModule(0)`、`moduleDeactivated(1)`、`down(2)`、`up(3)`|`vision/GUD-VISIONXSCON-MIB.txt:97-106`|

### CON 非表对象（全部逐项 `OBJECT-TYPE` 证据）

以下“GET 实例”均为对象基础 OID 加 `.0`；每个对象原文均明示 `MAX-ACCESS read-only`。

|对象|原文符号路径|GET 实例（数值）|SYNTAX/描述摘要|原文证据|
|---|---|---|---|---|
|`deviceId`|`identify.1`|`1.3.6.1.4.1.32828.3.769.768.2.1.1.0`|`DisplayString`；device ID|`vision/GUD-VISIONXSCON-MIB.txt:168-174`|
|`deviceCl`|`identify.2`|`1.3.6.1.4.1.32828.3.769.768.2.1.2.0`|`DisplayString`；device class|`vision/GUD-VISIONXSCON-MIB.txt:176-182`|
|`deviceType`|`identify.3`|`1.3.6.1.4.1.32828.3.769.768.2.1.3.0`|`DisplayString`；device type|`vision/GUD-VISIONXSCON-MIB.txt:184-190`|
|`serialNumber`|`identify.4`|`1.3.6.1.4.1.32828.3.769.768.2.1.4.0`|`DisplayString`；serial number|`vision/GUD-VISIONXSCON-MIB.txt:192-198`|
|`etherAddress0`|`identify.5`|`1.3.6.1.4.1.32828.3.769.768.2.1.5.0`|`PhysAddress`；first ethernet port MAC|`vision/GUD-VISIONXSCON-MIB.txt:200-206`|
|`firmwareVersion`|`info.1`|`1.3.6.1.4.1.32828.3.769.768.2.2.1.0`|`DisplayString`；firmware version|`vision/GUD-VISIONXSCON-MIB.txt:209-215`|
|`mainPower`|`status.1`|`1.3.6.1.4.1.32828.3.769.768.2.3.1.0`|`PowerStatus`；main power device|`vision/GUD-VISIONXSCON-MIB.txt:218-224`|
|`redundantPower`|`status.2`|`1.3.6.1.4.1.32828.3.769.768.2.3.2.0`|`PowerStatus`；redundant power device|`vision/GUD-VISIONXSCON-MIB.txt:226-232`|
|`temperature1`|`status.3`|`1.3.6.1.4.1.32828.3.769.768.2.3.3.0`|`DisplayString`；internal temperature 1；`UNITS` 仅为注释|`vision/GUD-VISIONXSCON-MIB.txt:234-241`|
|`fan1`|`status.502`|`1.3.6.1.4.1.32828.3.769.768.2.3.502.0`|`DisplayString`；fan 1 speed；`UNITS` 仅为注释|`vision/GUD-VISIONXSCON-MIB.txt:243-250`|
|`networkInterface0`|`status.506`|`1.3.6.1.4.1.32828.3.769.768.2.3.506.0`|`NetworkInterfaceStatus`；first network interface|`vision/GUD-VISIONXSCON-MIB.txt:252-258`|
|`consoleUSBConnection`|`status.9`|`1.3.6.1.4.1.32828.3.769.768.2.3.9.0`|`KeyboardMouseStatus`；local console USB keyboard/mouse|`vision/GUD-VISIONXSCON-MIB.txt:260-266`|
|`transparentUsbLink`|`status.10`|`1.3.6.1.4.1.32828.3.769.768.2.3.10.0`|`TransparentUsbLinkStatus`；transparent USB module link|`vision/GUD-VISIONXSCON-MIB.txt:268-274`|
|`transparentUsbSfpModule`|`status.16`|`1.3.6.1.4.1.32828.3.769.768.2.3.16.0`|`SfpModuleStatus`；USB SFP link status|`vision/GUD-VISIONXSCON-MIB.txt:276-282`|
|`transparentUsbTxPower`|`status.17`|`1.3.6.1.4.1.32828.3.769.768.2.3.17.0`|`Integer32`；USB SFP TX power [uW]|`vision/GUD-VISIONXSCON-MIB.txt:284-290`|
|`transparentUsbRxPower`|`status.18`|`1.3.6.1.4.1.32828.3.769.768.2.3.18.0`|`Integer32`；USB SFP RX power [uW]|`vision/GUD-VISIONXSCON-MIB.txt:292-298`|
|`transparentUsbSfpType`|`status.19`|`1.3.6.1.4.1.32828.3.769.768.2.3.19.0`|`DisplayString`；USB SFP type|`vision/GUD-VISIONXSCON-MIB.txt:300-306`|
|`generalErrorCode`|`errormessages.1`|`1.3.6.1.4.1.32828.3.769.768.2.1000.1.0`|`Integer32`；error code；无代码字典|`vision/GUD-VISIONXSCON-MIB.txt:449-455`|
|`generalErrorMessage`|`errormessages.2`|`1.3.6.1.4.1.32828.3.769.768.2.1000.2.0`|`DisplayString`；error message|`vision/GUD-VISIONXSCON-MIB.txt:457-463`|

### CON 表结构、索引与列（每个结构/列逐项证据）

|对象|数值基础 OID 或行实例模式|权限/索引/语义|原文证据|
|---|---|---|---|
|`videoChannelTable`|`1.3.6.1.4.1.32828.3.769.768.2.3.1000`|`SEQUENCE OF VideoChannelEntry`，`not-accessible`|`vision/GUD-VISIONXSCON-MIB.txt:312-318`|
|`videoChannelEntry`|`1.3.6.1.4.1.32828.3.769.768.2.3.1000.1`|`not-accessible`；`INDEX { videoChannelIndex }`|`vision/GUD-VISIONXSCON-MIB.txt:320-327`|
|`videoChannelIndex`|`1.3.6.1.4.1.32828.3.769.768.2.3.1000.1.1.<i>`|`Integer32(1..4)`，`not-accessible`；索引，不能单独 GET|`vision/GUD-VISIONXSCON-MIB.txt:329-342`|
|`displayConnection`|`1.3.6.1.4.1.32828.3.769.768.2.3.1000.1.2.<i>`|`ConnectionStatus`，`read-only`；display connection to console|`vision/GUD-VISIONXSCON-MIB.txt:344-350`|
|`displayType`|`1.3.6.1.4.1.32828.3.769.768.2.3.1000.1.3.<i>`|`DisplayString`，`read-only`；display type|`vision/GUD-VISIONXSCON-MIB.txt:352-358`|
|`freeze`|`1.3.6.1.4.1.32828.3.769.768.2.3.1000.1.4.<i>`|`Boolean`，`read-only`；freeze active|`vision/GUD-VISIONXSCON-MIB.txt:360-366`|
|`linkChannelTable`|`1.3.6.1.4.1.32828.3.769.768.2.3.1001`|`SEQUENCE OF LinkChannelEntry`，`not-accessible`|`vision/GUD-VISIONXSCON-MIB.txt:373-379`|
|`linkChannelEntry`|`1.3.6.1.4.1.32828.3.769.768.2.3.1001.1`|`not-accessible`；`INDEX { linkChannelIndex }`|`vision/GUD-VISIONXSCON-MIB.txt:381-388`|
|`linkChannelIndex`|`1.3.6.1.4.1.32828.3.769.768.2.3.1001.1.1.<i>`|`Integer32(1..8)`，`not-accessible`；索引，不能单独 GET|`vision/GUD-VISIONXSCON-MIB.txt:390-405`|
|`link`|`1.3.6.1.4.1.32828.3.769.768.2.3.1001.1.2.<i>`|`LinkStatus`，`read-only`|`vision/GUD-VISIONXSCON-MIB.txt:407-413`|
|`sfpModule`|`1.3.6.1.4.1.32828.3.769.768.2.3.1001.1.3.<i>`|`SfpModuleStatus`，`read-only`|`vision/GUD-VISIONXSCON-MIB.txt:415-421`|
|`sfpTxPower`|`1.3.6.1.4.1.32828.3.769.768.2.3.1001.1.4.<i>`|`Integer32`，`read-only`；[uW]|`vision/GUD-VISIONXSCON-MIB.txt:423-429`|
|`sfpRxPower`|`1.3.6.1.4.1.32828.3.769.768.2.3.1001.1.5.<i>`|`Integer32`，`read-only`；[uW]|`vision/GUD-VISIONXSCON-MIB.txt:431-437`|
|`sfpType`|`1.3.6.1.4.1.32828.3.769.768.2.3.1001.1.6.<i>`|`DisplayString`，`read-only`|`vision/GUD-VISIONXSCON-MIB.txt:439-445`|

CON 合规声明：`identifyGroup`、`infoGroup`、`statusGroup` 是强制组，`errorGroup` 为可选组；透明 USB 的部分对象被注释出 `statusGroup`。源：`vision/GUD-VISIONXSCON-MIB.txt:469-520`。

## 交叉核对结论（仅原文可证明的事实）

1. 两个 VisionXS 设备 MIB 都没有通知定义；包中唯一通知来自通用 Trap MIB，故不可声称这是 VisionXS 专属或默认启用的 Trap。
2. 所有业务采集对象均为只读；未发现任何 `read-write`/`read-create` 对象，表索引也不可访问。
3. CPU 与 CON 各有一个最多四行的视频/显示表和一个最多八行的链路表；索引只给数值范围，并未给物理端口、主/备角色或行出现条件。
4. `errorGroup` 在两设备 MIB 中均为 optional；错误代码没有值域解释。
5. 两设备均把温度和风扇定义为 `DisplayString`，故随附 MIB 不足以把它们作为严格数值指标或据此设阈值。
