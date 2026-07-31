# CCDM MIB 原文证据与 OID 推导

## 证据范围与盘点

本文件只引用 `../ccdm` 的 `*-MIB.txt`，不使用 PDF 或外部资料补全 MIB 事实。共读取 6 个 MIB：4 个 CCDM 数据模块、1 个通用通知模块、1 个 GUD SMI 根模块。按原文 `OBJECT-TYPE` 声明计数：基础 CCDM 86、CON 42、CPU 36、DWC 38、通用 Trap 2，共 204；`NOTIFICATION-TYPE` 为 1 个（`generalNotification`）。其中计数包含 table、entry 和 `not-accessible` 索引对象，不能把它们都当成可读监控点。

| 文件 | SHA-256 | 版本/更新时间的原文证据 |
|---|---|---|
| `ccdm/GUD-SMI-MIB.txt` | `3D2D24835286B8F874FCD7291D6A0D7C80DECDEBE130C557F35D2B1FEDEBD476` | `:8-20` |
| `ccdm/GUD-CCDM-MIB.txt` | `7C02E8F43D7F2FE327BFDDCAF6B8929E9563E9D8711AD3290E05D4FB3D442F82` | `:14-26` |
| `ccdm/GUD-CCDMCON-MIB.txt` | `5FF037BC86F801C05190F01447CD3AD486270F1E5D120FBF0C49A76AFEA3AB33` | `:14-26` |
| `ccdm/GUD-CCDMCPU-MIB.txt` | `61A5B63829177285D8F3C3607496D54FD2EBBC4810D8952B7B85F6E55E455135` | `:14-26` |
| `ccdm/GUD-CCDMDWC-MIB.txt` | `DBFDB891CE5F175A4050234ACE17DEF73F75A328301DE695E255E7EF1B9ED715` | `:14-26` |
| `ccdm/GUD-GENERALTRAPS-MIB.txt` | `D575B112175E1E23B98F98AFB97E053BC86AD4FE2A10DF8D137F595C160FC1E9` | `:16-28` |

## 数值 OID 推导（已复算）

`enterprises` 是标准根 `1.3.6.1.4.1`。原文定义 `gudEnterprise ::= { enterprises 32828 }`、`gudProduct ::= { gudEnterprise 3 }`、`gudDIGITALMATRIXSWITCH ::= { gudProduct 257 }`、`gudCCDM ::= { gudDIGITALMATRIXSWITCH 10 }`，故：

```text
gudEnterprise                 = 1.3.6.1.4.1.32828
gudProduct                    = 1.3.6.1.4.1.32828.3
gudDIGITALMATRIXSWITCH        = 1.3.6.1.4.1.32828.3.257
P = gudCCDM                   = 1.3.6.1.4.1.32828.3.257.10
gudCCDMMIB                    = P.1
gudCCDMCON                    = P.1.1
gudCCDMCPU                    = P.1.2
gudCCDMDWC                    = P.1.3
gudGeneralTrap                = 1.3.6.1.4.1.32828.2.1
gudGeneralNotifications       = 1.3.6.1.4.1.32828.2.1.0
```

推导证据：`ccdm/GUD-SMI-MIB.txt:26-31,36-40,45-49,90-94,108-112`；子模块分配证据：`ccdm/GUD-CCDM-MIB.txt:14-30`；通用通知分配证据：`ccdm/GUD-GENERALTRAPS-MIB.txt:16-30`。本文件以下所有 `P` 均是上面的完整十进制 OID，不是另一个符号 OID。

## `GUD-SMI-MIB`：根与产品范围证据

| 标识符 | 分配 / 语义 | 原文 |
|---|---|---|
| `gudEnterprise` | `{ enterprises 32828 }`，GUD 企业根 | `ccdm/GUD-SMI-MIB.txt:26-31` |
| `gudTrap` / `gudGeneralTrap` | `{ gudEnterprise 2 }` / `{ gudTrap 1 }`，Trap 及 general trap 子树 | `ccdm/GUD-SMI-MIB.txt:36-40,54-58` |
| `gudProduct` / `gudDIGITALMATRIXSWITCH` | `{ gudEnterprise 3 }` / `{ gudProduct 257 }` | `ccdm/GUD-SMI-MIB.txt:45-49,90-94` |
| `gudCCDM` | `{ gudDIGITALMATRIXSWITCH 10 }`，描述为 ControlCenter-Digital 子树 | `ccdm/GUD-SMI-MIB.txt:106-112` |

其余 `GUD-SMI-MIB` 产品身份节点不属于 CCDM 资料的监控对象，未在此扩展；该模块内没有 `OBJECT-TYPE` 或通知定义。证据：`ccdm/GUD-SMI-MIB.txt:1-511`。

## `GUD-CCDM-MIB`：基础机框对象证据

模块身份为 `gudCCDMMIB=P.1`；`gudCCDMCON=P.1.1`、`gudCCDMCPU=P.1.2`、`gudCCDMDWC=P.1.3`。基础对象树为 `objects=P.2`，`identify=P.2.1`，`info=P.2.2`，`status=P.2.3`，`errormessages=P.2.1000`。源：`ccdm/GUD-CCDM-MIB.txt:14-30,133-167`。

### 文本约定（枚举原文）

| 类型 | 枚举 | 原文 |
|---|---|---|
| `PowerSupplyStatus` | `off(0), on(1), absent(2), failure(3)` | `ccdm/GUD-CCDM-MIB.txt:35-44` |
| `NetworkInterfaceStatus`、`CatPortStatus` | 均为 `down(0), up(1)` | `ccdm/GUD-CCDM-MIB.txt:46-62` |
| `FiberPortStatus`、`MultiPortStatus`、`TrunkPortStatus` | 均为 `noModule(0), deactivated(1), down(2), up(3)` | `ccdm/GUD-CCDM-MIB.txt:64-95` |
| `FunctionStatus` | `failure(0), ok(1)` | `ccdm/GUD-CCDM-MIB.txt:97-104` |
| `DeviceStatus` | `offline(0), online(1)` | `ccdm/GUD-CCDM-MIB.txt:106-113` |
| `RaidStatus` | `failure(0), resync(1), recover(2), check(3), repair(4), ok(5)` | `ccdm/GUD-CCDM-MIB.txt:115-126` |

### 标量对象（全部 `read-only`，实际 GET 追加 `.0`）

| 对象 | 完整数值 OID | SYNTAX | 原文行 |
|---|---|---|---|
| `deviceId` | `1.3.6.1.4.1.32828.3.257.10.2.1.1.0` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:193-199` |
| `deviceCl` | `1.3.6.1.4.1.32828.3.257.10.2.1.2.0` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:201-207` |
| `deviceType` | `1.3.6.1.4.1.32828.3.257.10.2.1.3.0` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:209-215` |
| `serialNumber` | `1.3.6.1.4.1.32828.3.257.10.2.1.4.0` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:217-223` |
| `etherAddress0` | `1.3.6.1.4.1.32828.3.257.10.2.1.5.0` | `PhysAddress` | `ccdm/GUD-CCDM-MIB.txt:225-231` |
| `etherAddress1` | `1.3.6.1.4.1.32828.3.257.10.2.1.6.0` | `PhysAddress` | `ccdm/GUD-CCDM-MIB.txt:233-239` |
| `firmwareVersion` | `1.3.6.1.4.1.32828.3.257.10.2.2.1.0` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:243-249` |
| `switchTemperature` | `1.3.6.1.4.1.32828.3.257.10.2.3.4.0` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:253-260` |
| `controllerTemperature` | `1.3.6.1.4.1.32828.3.257.10.2.3.5.0` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:262-269` |
| `raidStatusDevice1` | `1.3.6.1.4.1.32828.3.257.10.2.3.6.0` | `RaidStatus` | `ccdm/GUD-CCDM-MIB.txt:271-277` |
| `raidStatusDevice2` | `1.3.6.1.4.1.32828.3.257.10.2.3.7.0` | `RaidStatus` | `ccdm/GUD-CCDM-MIB.txt:279-285` |
| `functionSwitch` | `1.3.6.1.4.1.32828.3.257.10.2.3.9.0` | `FunctionStatus` | `ccdm/GUD-CCDM-MIB.txt:287-293` |
| `powerCurrent` | `1.3.6.1.4.1.32828.3.257.10.2.3.500.0` | `DisplayString`（`UNITS A` 被注释） | `ccdm/GUD-CCDM-MIB.txt:968-975` |
| `networkInterface0` | `1.3.6.1.4.1.32828.3.257.10.2.3.506.0` | `NetworkInterfaceStatus` | `ccdm/GUD-CCDM-MIB.txt:977-983` |
| `networkInterface1` | `1.3.6.1.4.1.32828.3.257.10.2.3.507.0` | `NetworkInterfaceStatus` | `ccdm/GUD-CCDM-MIB.txt:985-991` |
| `generalErrorCode` | `1.3.6.1.4.1.32828.3.257.10.2.1000.1.0` | `Integer32` | `ccdm/GUD-CCDM-MIB.txt:994-1000` |
| `generalErrorMessage` | `1.3.6.1.4.1.32828.3.257.10.2.1000.2.0` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:1002-1008` |

### 表、entry 和索引（`not-accessible`）

表/entry/index 的 `MAX-ACCESS` 及 `INDEX` 必须按下表处理；可读取的列紧随其后。表根由 `P.2.3.<table-id>` 推导，entry 都是 `<table-root>.1`。

| 表 | table / entry / index 对象与数值 OID | 索引原文证据 |
|---|---|---|
| 风扇 | `fanTable=P.2.3.1000`；`fanTableEntry=P.2.3.1000.1`；`fanIndex=P.2.3.1000.1.1` | `INDEX { fanIndex }`，`Integer32(1..20)`；`ccdm/GUD-CCDM-MIB.txt:299-328` |
| 电源 | `powerSupplyTable=P.2.3.1001`；`powerSupplyTableEntry=P.2.3.1001.1`；`powerSupplyIndex=P.2.3.1001.1.1` | `INDEX { powerSupplyIndex }`，`Integer32(1..3)`；`ccdm/GUD-CCDM-MIB.txt:350-381` |
| CAT 卡 | `ioCardCatTable=P.2.3.1002`；`ioCardCatEntry=P.2.3.1002.1`；`ioCardCatIndex=P.2.3.1002.1.1` | `INDEX { ioCardCatIndex }`，`Integer32(1..19)`；`ccdm/GUD-CCDM-MIB.txt:419-451` |
| CAT 端口 | `ioCardCatPortTable=P.2.3.1003`；`ioCardCatPortEntry=P.2.3.1003.1`；`ioCardCatPortIndex=P.2.3.1003.1.1` | `INDEX { ioCardCatIndex, ioCardCatPortIndex }`；端口 `Integer32(1..16)`；`ccdm/GUD-CCDM-MIB.txt:493-522` |
| Fiber 卡 | `ioCardFiberTable=P.2.3.1004`；`ioCardFiberEntry=P.2.3.1004.1`；`ioCardFiberIndex=P.2.3.1004.1.1` | `INDEX { ioCardFiberIndex }`，`Integer32(1..19)`；`ccdm/GUD-CCDM-MIB.txt:536-568` |
| Fiber 端口 | `ioCardFiberPortTable=P.2.3.1005`；`ioCardFiberPortEntry=P.2.3.1005.1`；`ioCardFiberPortIndex=P.2.3.1005.1.1` | `INDEX { ioCardFiberIndex, ioCardFiberPortIndex }`；端口 `Integer32(1..16)`；`ccdm/GUD-CCDM-MIB.txt:610-642` |
| Multi 卡 | `ioCardMultiTable=P.2.3.1006`；`ioCardMultiEntry=P.2.3.1006.1`；`ioCardMultiIndex=P.2.3.1006.1.1` | `INDEX { ioCardMultiIndex }`，`Integer32(1..19)`；`ccdm/GUD-CCDM-MIB.txt:680-712` |
| Multi 端口 | `ioCardMultiPortTable=P.2.3.1007`；`ioCardMultiPortEntry=P.2.3.1007.1`；`ioCardMultiPortIndex=P.2.3.1007.1.1` | `INDEX { ioCardMultiIndex, ioCardMultiPortIndex }`；端口 `Integer32(1..16)`；`ccdm/GUD-CCDM-MIB.txt:754-786` |
| Trunk 卡 | `ioCardTrunkTable=P.2.3.1008`；`ioCardTrunkEntry=P.2.3.1008.1`；`ioCardTrunkIndex=P.2.3.1008.1.1` | `INDEX { ioCardTrunkIndex }`，`Integer32(1..19)`；`ccdm/GUD-CCDM-MIB.txt:824-856` |
| Trunk 端口 | `ioCardTrunkPortTable=P.2.3.1009`；`ioCardTrunkPortEntry=P.2.3.1009.1`；`ioCardTrunkPortIndex=P.2.3.1009.1.1` | `INDEX { ioCardTrunkIndex, ioCardTrunkPortIndex }`；端口 `Integer32(1..16)`；`ccdm/GUD-CCDM-MIB.txt:898-930` |

每一行 table、entry 和 index 原文均为 `not-accessible`：风扇 `:299-328`、电源 `:350-381`、CAT `:419-451` / `:493-522`、Fiber `:536-568` / `:610-642`、Multi `:680-712` / `:754-786`、Trunk `:824-856` / `:898-930`。因此 index 是实例组成部分，而非独立轮询对象。

### 基础机框表的可读列（逐对象）

| 对象 | 数值列 OID（追加索引） | SYNTAX | 原文 |
|---|---|---|---|
| `fanName` | `P.2.3.1000.1.2.i` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:330-336` |
| `fanSpeed` | `P.2.3.1000.1.3.i` | `Integer32(0..10000)`，RPM | `ccdm/GUD-CCDM-MIB.txt:338-344` |
| `powerSupplyStatus` | `P.2.3.1001.1.2.i` | `PowerSupplyStatus` | `ccdm/GUD-CCDM-MIB.txt:383-389` |
| `powerSupplyTemperature` | `P.2.3.1001.1.3.i` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:391-397` |
| `powerSupplyVoltage` | `P.2.3.1001.1.4.i` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:399-405` |
| `powerSupplyFanFunction` | `P.2.3.1001.1.5.i` | `FunctionStatus` | `ccdm/GUD-CCDM-MIB.txt:407-413` |
| `ioCardCatId` | `P.2.3.1002.1.2.c` | `Integer32` | `ccdm/GUD-CCDM-MIB.txt:453-459` |
| `ioCardCatStatus` | `P.2.3.1002.1.3.c` | `DeviceStatus` | `ccdm/GUD-CCDM-MIB.txt:461-467` |
| `ioCardCatFunction` | `P.2.3.1002.1.4.c` | `FunctionStatus` | `ccdm/GUD-CCDM-MIB.txt:469-475` |
| `ioCardCatTemperature` | `P.2.3.1002.1.5.c` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:477-483` |
| `ioCardCatMatrixSlot` | `P.2.3.1002.1.6.c` | `Integer32` | `ccdm/GUD-CCDM-MIB.txt:485-491` |
| `ioCardCatPortStatus` | `P.2.3.1003.1.2.c.p` | `CatPortStatus` | `ccdm/GUD-CCDM-MIB.txt:524-530` |
| `ioCardFiberId` | `P.2.3.1004.1.2.c` | `Integer32` | `ccdm/GUD-CCDM-MIB.txt:570-576` |
| `ioCardFiberStatus` | `P.2.3.1004.1.3.c` | `DeviceStatus` | `ccdm/GUD-CCDM-MIB.txt:578-584` |
| `ioCardFiberFunction` | `P.2.3.1004.1.4.c` | `FunctionStatus` | `ccdm/GUD-CCDM-MIB.txt:586-592` |
| `ioCardFiberTemperature` | `P.2.3.1004.1.5.c` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:594-600` |
| `ioCardFiberMatrixSlot` | `P.2.3.1004.1.6.c` | `Integer32` | `ccdm/GUD-CCDM-MIB.txt:602-608` |
| `ioCardFiberPortStatus` | `P.2.3.1005.1.2.c.p` | `FiberPortStatus` | `ccdm/GUD-CCDM-MIB.txt:644-650` |
| `ioCardFiberTxPower` | `P.2.3.1005.1.3.c.p` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:652-658` |
| `ioCardFiberRxPower` | `P.2.3.1005.1.4.c.p` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:660-666` |
| `ioCardFiberSfpType` | `P.2.3.1005.1.5.c.p` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:668-674` |
| `ioCardMultiId` | `P.2.3.1006.1.2.c` | `Integer32` | `ccdm/GUD-CCDM-MIB.txt:714-720` |
| `ioCardMultiStatus` | `P.2.3.1006.1.3.c` | `DeviceStatus` | `ccdm/GUD-CCDM-MIB.txt:722-728` |
| `ioCardMultiFunction` | `P.2.3.1006.1.4.c` | `FunctionStatus` | `ccdm/GUD-CCDM-MIB.txt:730-736` |
| `ioCardMultiTemperature` | `P.2.3.1006.1.5.c` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:738-744` |
| `ioCardMultiMatrixSlot` | `P.2.3.1006.1.6.c` | `Integer32` | `ccdm/GUD-CCDM-MIB.txt:746-752` |
| `ioCardMultiPortStatus` | `P.2.3.1007.1.2.c.p` | `MultiPortStatus` | `ccdm/GUD-CCDM-MIB.txt:788-794` |
| `ioCardMultiTxPower` | `P.2.3.1007.1.3.c.p` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:796-802` |
| `ioCardMultiRxPower` | `P.2.3.1007.1.4.c.p` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:804-810` |
| `ioCardMultiSfpType` | `P.2.3.1007.1.5.c.p` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:812-818` |
| `ioCardTrunkId` | `P.2.3.1008.1.2.c` | `Integer32` | `ccdm/GUD-CCDM-MIB.txt:858-864` |
| `ioCardTrunkStatus` | `P.2.3.1008.1.3.c` | `DeviceStatus` | `ccdm/GUD-CCDM-MIB.txt:866-872` |
| `ioCardTrunkFunction` | `P.2.3.1008.1.4.c` | `FunctionStatus` | `ccdm/GUD-CCDM-MIB.txt:874-880` |
| `ioCardTrunkTemperature` | `P.2.3.1008.1.5.c` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:882-888` |
| `ioCardTrunkMatrixSlot` | `P.2.3.1008.1.6.c` | `Integer32` | `ccdm/GUD-CCDM-MIB.txt:890-896` |
| `ioCardTrunkPortStatus` | `P.2.3.1009.1.2.c.p` | `TrunkPortStatus` | `ccdm/GUD-CCDM-MIB.txt:932-938` |
| `ioCardTrunkTxPower` | `P.2.3.1009.1.3.c.p` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:940-946` |
| `ioCardTrunkRxPower` | `P.2.3.1009.1.4.c.p` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:948-954` |
| `ioCardTrunkSfpType` | `P.2.3.1009.1.5.c.p` | `DisplayString` | `ccdm/GUD-CCDM-MIB.txt:956-962` |

基础模块合规性把 `identifyGroup`、`infoGroup`、`statusGroup` 列为 mandatory，把 `errorGroup` 列为 optional；其中分组列出的可读对象可与以上逐对象证据交叉验证。源：`ccdm/GUD-CCDM-MIB.txt:1014-1075`。

## `GUD-CCDMCON-MIB`：控制台对象证据

模块身份为 `P.1.1.1`，对象树 `P.1.1.2`，状态树 `P.1.1.2.3`。源：`ccdm/GUD-CCDM-MIB.txt:28`、`ccdm/GUD-CCDMCON-MIB.txt:14-26,103-113`。

文本约定：`Boolean false(0)/true(1)`：`:31-38`；`PowerStatus off(0)/on(1)`：`:40-47`；`NetworkInterfaceStatus down(0)/up(1)`：`:49-56`；`DeviceStatus offline(0)/online(1)/ready(2)`：`:58-66`；`ConnectionStatus notConnected(0)/connected(1)`：`:68-75`；`KeyboardMouseStatus none(0)/keyboard(1)/mouse(2)/keyboardMouse(3)`：`:77-86`；`GpioValue inactive(0)/low(1)/high(2)`：`:88-96`，均在 `ccdm/GUD-CCDMCON-MIB.txt`。

### 主设备表 `userModuleTable`

`userModuleTable=P.1.1.2.3.1000`、`userModuleEntry=P.1.1.2.3.1000.1`、`userModuleIndex=P.1.1.2.3.1000.1.1`；三者为 `not-accessible`，`INDEX { userModuleIndex }`，范围 `Integer32(1..2000)`。源：`ccdm/GUD-CCDMCON-MIB.txt:138-194`。下列各列都是 `read-only`，实例后缀 `.u` 为 `userModuleIndex`。

| 对象 | 数值列 OID | SYNTAX | 原文 |
|---|---|---|---|
| `id` | `P.1.1.2.3.1000.1.2.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:196-202` |
| `cl` | `P.1.1.2.3.1000.1.3.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:204-210` |
| `name` | `P.1.1.2.3.1000.1.4.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:212-218` |
| `deviceStatus` | `P.1.1.2.3.1000.1.5.u` | `DeviceStatus` | `ccdm/GUD-CCDMCON-MIB.txt:220-226` |
| `mainPower` | `P.1.1.2.3.1000.1.6.u` | `PowerStatus` | `ccdm/GUD-CCDMCON-MIB.txt:228-234` |
| `redundantPower` | `P.1.1.2.3.1000.1.7.u` | `PowerStatus` | `ccdm/GUD-CCDMCON-MIB.txt:236-242` |
| `temperature1` | `P.1.1.2.3.1000.1.8.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:244-250` |
| `consolePS2Connection` | `P.1.1.2.3.1000.1.9.u` | `KeyboardMouseStatus` | `ccdm/GUD-CCDMCON-MIB.txt:252-258` |
| `consoleUSBConnection` | `P.1.1.2.3.1000.1.10.u` | `KeyboardMouseStatus` | `ccdm/GUD-CCDMCON-MIB.txt:260-266` |
| `displayConnection` | `P.1.1.2.3.1000.1.11.u` | `ConnectionStatus` | `ccdm/GUD-CCDMCON-MIB.txt:268-274` |
| `displayConnection1` | `P.1.1.2.3.1000.1.12.u` | `ConnectionStatus` | `ccdm/GUD-CCDMCON-MIB.txt:276-282` |
| `displayConnection2` | `P.1.1.2.3.1000.1.13.u` | `ConnectionStatus` | `ccdm/GUD-CCDMCON-MIB.txt:284-290` |
| `displayType` | `P.1.1.2.3.1000.1.14.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:292-298` |
| `displayType1` | `P.1.1.2.3.1000.1.15.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:300-306` |
| `displayType2` | `P.1.1.2.3.1000.1.16.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:308-314` |
| `freeze` | `P.1.1.2.3.1000.1.17.u` | `Boolean` | `ccdm/GUD-CCDMCON-MIB.txt:316-322` |
| `freeze1` | `P.1.1.2.3.1000.1.18.u` | `Boolean` | `ccdm/GUD-CCDMCON-MIB.txt:324-330` |
| `freeze2` | `P.1.1.2.3.1000.1.19.u` | `Boolean` | `ccdm/GUD-CCDMCON-MIB.txt:332-338` |
| `sfpTxPower` | `P.1.1.2.3.1000.1.20.u` | `Integer32`，`[uW]` | `ccdm/GUD-CCDMCON-MIB.txt:340-346` |
| `sfpTxPower1` | `P.1.1.2.3.1000.1.21.u` | `Integer32`，`[uW]` | `ccdm/GUD-CCDMCON-MIB.txt:348-354` |
| `sfpTxPower2` | `P.1.1.2.3.1000.1.22.u` | `Integer32`，`[uW]` | `ccdm/GUD-CCDMCON-MIB.txt:356-362` |
| `sfpRxPower` | `P.1.1.2.3.1000.1.23.u` | `Integer32`，`[uW]` | `ccdm/GUD-CCDMCON-MIB.txt:364-370` |
| `sfpRxPower1` | `P.1.1.2.3.1000.1.24.u` | `Integer32`，`[uW]` | `ccdm/GUD-CCDMCON-MIB.txt:372-378` |
| `sfpRxPower2` | `P.1.1.2.3.1000.1.25.u` | `Integer32`，`[uW]` | `ccdm/GUD-CCDMCON-MIB.txt:380-386` |
| `sfpType` | `P.1.1.2.3.1000.1.26.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:388-394` |
| `sfpType1` | `P.1.1.2.3.1000.1.27.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:396-402` |
| `sfpType2` | `P.1.1.2.3.1000.1.28.u` | `DisplayString` | `ccdm/GUD-CCDMCON-MIB.txt:404-410` |
| `activeTransmissionPort` | `P.1.1.2.3.1000.1.29.u` | `Integer32(1..2)` | `ccdm/GUD-CCDMCON-MIB.txt:412-418` |
| `networkInterface0` | `P.1.1.2.3.1000.1.30.u` | `NetworkInterfaceStatus` | `ccdm/GUD-CCDMCON-MIB.txt:420-426` |

### CON 风扇、GPIO 表（逐对象）

| 表及索引对象 | 可读对象 / 数值 OID / SYNTAX | 原文 |
|---|---|---|
| `fanTable=P.1.1.2.3.1001`，`fanTableEntry=...1001.1`，`fanIndex=...1001.1.1`；全部 `not-accessible`；`INDEX { userModuleIndex, fanIndex }`，`fanIndex 1..10` | `fanName=P.1.1.2.3.1001.1.2.u.f`，`DisplayString`；`fanSpeed=...1.3.u.f`，`Integer32(0..10000)`、RPM；均 `read-only` | `ccdm/GUD-CCDMCON-MIB.txt:432-477` |
| `gpioTable=P.1.1.2.3.1002`，`gpioTableEntry=...1002.1`，`gpioIndex=...1002.1.1`；全部 `not-accessible`；`INDEX { userModuleIndex, gpioIndex }`，`gpioIndex 1..4` | `gpioName=P.1.1.2.3.1002.1.2.u.g`，`DisplayString`；`gpioValue=...1.3.u.g`，`GpioValue`；均 `read-only` | `ccdm/GUD-CCDMCON-MIB.txt:483-528` |

CON 的 `statusGroup` 是 mandatory，列出了以上主设备、风扇和 GPIO 的读对象。源：`ccdm/GUD-CCDMCON-MIB.txt:534-559`。

## `GUD-CCDMCPU-MIB`：CPU 对象证据

模块身份为 `P.1.2.1`，对象树 `P.1.2.2`，状态树 `P.1.2.2.3`。源：`ccdm/GUD-CCDM-MIB.txt:29`、`ccdm/GUD-CCDMCPU-MIB.txt:14-26,130-140`。

文本约定（均在 `ccdm/GUD-CCDMCPU-MIB.txt`）：`PowerStatus` `:32-39`；`DeviceStatus` `:41-49`；`ConnectionStatus` `:51-58`；`KeyboardMouseStatus` `:60-69`；`UsbHidStatus notConnected(0)/connected(1)/initialized(2)` `:71-79`；`AccessStatus local(0)/remote(1)/localExclusive(2)/remoteExclusive(3)` `:81-90`；`VideoType none(0)/vga(1)/dvisl(2)/dvidl(3)/dmdp(4)/dp(5)/hdmi(6)` `:92-104`；`GpioValue` `:106-114`；`NetworkInterfaceStatus` `:116-123`。

### 主设备表 `targetModuleTable`

`targetModuleTable=P.1.2.2.3.1000`、`targetModuleEntry=P.1.2.2.3.1000.1`、`targetModuleIndex=P.1.2.2.3.1000.1.1`；均 `not-accessible`，`INDEX { targetModuleIndex }`，范围 `Integer32(1..2000)`。源：`ccdm/GUD-CCDMCPU-MIB.txt:166-216`。以下列均 `read-only`，`.t` 是目标模块索引。

| 对象 | 数值列 OID | SYNTAX | 原文 |
|---|---|---|---|
| `id` | `P.1.2.2.3.1000.1.2.t` | `DisplayString` | `ccdm/GUD-CCDMCPU-MIB.txt:218-224` |
| `cl` | `P.1.2.2.3.1000.1.3.t` | `DisplayString` | `ccdm/GUD-CCDMCPU-MIB.txt:226-232` |
| `name` | `P.1.2.2.3.1000.1.4.t` | `DisplayString` | `ccdm/GUD-CCDMCPU-MIB.txt:234-240` |
| `deviceStatus` | `P.1.2.2.3.1000.1.5.t` | `DeviceStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:242-248` |
| `mainPower` | `P.1.2.2.3.1000.1.6.t` | `PowerStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:250-256` |
| `redundantPower` | `P.1.2.2.3.1000.1.7.t` | `PowerStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:258-264` |
| `temperature1` | `P.1.2.2.3.1000.1.8.t` | `DisplayString` | `ccdm/GUD-CCDMCPU-MIB.txt:266-272` |
| `consolePS2Connection` | `P.1.2.2.3.1000.1.9.t` | `KeyboardMouseStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:274-280` |
| `consoleUSBConnection` | `P.1.2.2.3.1000.1.10.t` | `KeyboardMouseStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:282-288` |
| `targetPS2Connection` | `P.1.2.2.3.1000.1.11.t` | `KeyboardMouseStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:290-296` |
| `targetUsbHid` | `P.1.2.2.3.1000.1.12.t` | `UsbHidStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:298-304` |
| `targetVideoCable` | `P.1.2.2.3.1000.1.13.t` | `ConnectionStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:306-312` |
| `targetVideoCable1` | `P.1.2.2.3.1000.1.14.t` | `ConnectionStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:314-320` |
| `targetVideoCable2` | `P.1.2.2.3.1000.1.15.t` | `ConnectionStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:322-328` |
| `targetVideoSignal` | `P.1.2.2.3.1000.1.16.t` | `VideoType` | `ccdm/GUD-CCDMCPU-MIB.txt:330-336` |
| `targetVideoSignal1` | `P.1.2.2.3.1000.1.17.t` | `VideoType` | `ccdm/GUD-CCDMCPU-MIB.txt:338-344` |
| `targetVideoSignal2` | `P.1.2.2.3.1000.1.18.t` | `VideoType` | `ccdm/GUD-CCDMCPU-MIB.txt:346-352` |
| `targetPower` | `P.1.2.2.3.1000.1.19.t` | `PowerStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:354-360` |
| `targetAccess` | `P.1.2.2.3.1000.1.20.t` | `AccessStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:362-368` |
| `sfpTxPower` | `P.1.2.2.3.1000.1.21.t` | `Integer32`，`[uW]` | `ccdm/GUD-CCDMCPU-MIB.txt:370-376` |
| `sfpRxPower` | `P.1.2.2.3.1000.1.22.t` | `Integer32`，`[uW]` | `ccdm/GUD-CCDMCPU-MIB.txt:378-384` |
| `sfpType` | `P.1.2.2.3.1000.1.23.t` | `DisplayString` | `ccdm/GUD-CCDMCPU-MIB.txt:386-392` |
| `networkInterface0` | `P.1.2.2.3.1000.1.24.t` | `NetworkInterfaceStatus` | `ccdm/GUD-CCDMCPU-MIB.txt:394-400` |

### CPU 风扇、GPIO 表（逐对象）

| 表及索引对象 | 可读对象 / 数值 OID / SYNTAX | 原文 |
|---|---|---|
| `fanTable=P.1.2.2.3.1001`，`fanTableEntry=...1001.1`，`fanIndex=...1001.1.1`；均 `not-accessible`；`INDEX { targetModuleIndex, fanIndex }`，`fanIndex 1..10` | `fanName=P.1.2.2.3.1001.1.2.t.f`，`DisplayString`；`fanSpeed=...1.3.t.f`，`Integer32(0..10000)`、RPM；均 `read-only` | `ccdm/GUD-CCDMCPU-MIB.txt:406-451` |
| `gpioTable=P.1.2.2.3.1002`，`gpioTableEntry=...1002.1`，`gpioIndex=...1002.1.1`；均 `not-accessible`；`INDEX { targetModuleIndex, gpioIndex }`，`gpioIndex 1..4` | `gpioName=P.1.2.2.3.1002.1.2.t.g`，`DisplayString`；`gpioValue=...1.3.t.g`，`GpioValue`；均 `read-only` | `ccdm/GUD-CCDMCPU-MIB.txt:457-502` |

CPU 的 `statusGroup` 是 mandatory，列举了主设备、风扇和 GPIO 的全部可读列。源：`ccdm/GUD-CCDMCPU-MIB.txt:508-529`。

## `GUD-CCDMDWC-MIB`：DWC 对象证据

模块身份为 `P.1.3.1`，对象树 `P.1.3.2`，状态树 `P.1.3.2.3`。源：`ccdm/GUD-CCDM-MIB.txt:30`、`ccdm/GUD-CCDMDWC-MIB.txt:14-26,93-103`。

文本约定（均在 `ccdm/GUD-CCDMDWC-MIB.txt`）：`Boolean false(0)/true(1)` `:31-38`；`PowerStatus off(0)/on(1)` `:40-47`；`NetworkInterfaceStatus down(0)/up(1)` `:49-56`；`DeviceStatus offline(0)/online(1)/ready(2)` `:58-66`；`ConnectionStatus notConnected(0)/connected(1)` `:68-75`；`KeyboardMouseStatus none(0)/keyboard(1)/mouse(2)/keyboardMouse(3)` `:77-86`。

### 动态用户模块表 `dynamicUserModuleTable`

`dynamicUserModuleTable=P.1.3.2.3.1000`、`dynamicUserModuleEntry=P.1.3.2.3.1000.1`、`dynamicUserModuleIndex=P.1.3.2.3.1000.1.1`；均 `not-accessible`，`INDEX { dynamicUserModuleIndex }`，范围 `Integer32(1..2000)`。源：`ccdm/GUD-CCDMDWC-MIB.txt:128-165`。以下可读列实例后缀为 `.d`。

| 对象 | 数值列 OID | SYNTAX | 原文 |
|---|---|---|---|
| `id` | `P.1.3.2.3.1000.1.2.d` | `DisplayString` | `ccdm/GUD-CCDMDWC-MIB.txt:167-173` |
| `cl` | `P.1.3.2.3.1000.1.3.d` | `DisplayString` | `ccdm/GUD-CCDMDWC-MIB.txt:175-181` |
| `name` | `P.1.3.2.3.1000.1.4.d` | `DisplayString` | `ccdm/GUD-CCDMDWC-MIB.txt:183-189` |
| `deviceStatus` | `P.1.3.2.3.1000.1.5.d` | `DeviceStatus` | `ccdm/GUD-CCDMDWC-MIB.txt:191-197` |
| `mainPower` | `P.1.3.2.3.1000.1.6.d` | `PowerStatus` | `ccdm/GUD-CCDMDWC-MIB.txt:199-205` |
| `redundantPower` | `P.1.3.2.3.1000.1.7.d` | `PowerStatus` | `ccdm/GUD-CCDMDWC-MIB.txt:207-213` |
| `temperature1` | `P.1.3.2.3.1000.1.8.d` | `DisplayString` | `ccdm/GUD-CCDMDWC-MIB.txt:215-221` |
| `consoleUSBConnection` | `P.1.3.2.3.1000.1.9.d` | `KeyboardMouseStatus` | `ccdm/GUD-CCDMDWC-MIB.txt:223-229` |
| `networkInterface0` | `P.1.3.2.3.1000.1.10.d` | `NetworkInterfaceStatus` | `ccdm/GUD-CCDMDWC-MIB.txt:231-237` |
| `networkInterface1` | `P.1.3.2.3.1000.1.11.d` | `NetworkInterfaceStatus` | `ccdm/GUD-CCDMDWC-MIB.txt:239-245` |

### DWC 风扇、视频通道、链路通道表（逐对象）

| 表及索引对象 | 可读对象 / 数值 OID / SYNTAX | 原文 |
|---|---|---|
| `fanTable=P.1.3.2.3.1001`，`fanTableEntry=...1001.1`，`fanIndex=...1001.1.1`；均 `not-accessible`；`INDEX { dynamicUserModuleIndex, fanIndex }`，`fanIndex 1..10` | `fanName=P.1.3.2.3.1001.1.2.d.f`，`DisplayString`；`fanSpeed=...1.3.d.f`，`Integer32(0..10000)`、RPM；均 `read-only` | `ccdm/GUD-CCDMDWC-MIB.txt:251-296` |
| `videoChannelTable=P.1.3.2.3.1002`，`videoChannelEntry=...1002.1`，`videoChannelIndex=...1002.1.1`；均 `not-accessible`；`INDEX { dynamicUserModuleIndex, videoChannelIndex }`，视频通道 `1..4` | `displayConnection=P.1.3.2.3.1002.1.2.d.v`，`ConnectionStatus`；`displayType=...1.3.d.v`，`DisplayString`；均 `read-only` | `ccdm/GUD-CCDMDWC-MIB.txt:302-347` |
| `linkChannelTable=P.1.3.2.3.1003`，`linkChannelEntry=...1003.1`，`linkChannelIndex=...1003.1.1`；均 `not-accessible`；`INDEX { dynamicUserModuleIndex, linkChannelIndex }`，链路通道 `1..8` | `conid=P.1.3.2.3.1003.1.2.d.l`，`DisplayString`；`concl=...1.3.d.l`，`DisplayString`；`conname=...1.4.d.l`，`DisplayString`；`linkChannelStatus=...1.5.d.l`，`DeviceStatus`；`activeTransmissionPort=...1.6.d.l`，`Integer32(1..2)`；`sfpTxPower1=...1.7.d.l`，`Integer32 [uW]`；`sfpTxPower2=...1.8.d.l`，`Integer32 [uW]`；`sfpRxPower1=...1.9.d.l`，`Integer32 [uW]`；`sfpRxPower2=...1.10.d.l`，`Integer32 [uW]`；`sfpType1=...1.11.d.l`，`DisplayString`；`sfpType2=...1.12.d.l`，`DisplayString`；`freeze=...1.13.d.l`，`Boolean`；均 `read-only` | `ccdm/GUD-CCDMDWC-MIB.txt:354-489` |

DWC `statusGroup` 是 mandatory；它重复列出以上主设备、风扇、视频与链路通道的可读对象。源：`ccdm/GUD-CCDMDWC-MIB.txt:495-518`。

## `GUD-GENERALTRAP-MIB`：通知和变量证据

模块身份为 `1.3.6.1.4.1.32828.2.1.1`，通知子树为 `gudGeneralNotifications=1.3.6.1.4.1.32828.2.1.0`。源：`ccdm/GUD-GENERALTRAPS-MIB.txt:16-30`。

| 对象 / 通知 | 完整数值 OID | 定义 / 变量 | 原文 |
|---|---|---|---|
| `level` | `1.3.6.1.4.1.32828.2.1.0.2` | `OBJECT-TYPE`、`Integer32`、`read-only`；仅描述为 notification level，未给枚举/严重度 | `ccdm/GUD-GENERALTRAPS-MIB.txt:32-38` |
| `message` | `1.3.6.1.4.1.32828.2.1.0.3` | `OBJECT-TYPE`、`DisplayString`、`read-only`；message text | `ccdm/GUD-GENERALTRAPS-MIB.txt:40-46` |
| `generalNotification` | `1.3.6.1.4.1.32828.2.1.0.4` | `NOTIFICATION-TYPE`；`OBJECTS { level, message }`；无触发、恢复、严重度或设备关联语义 | `ccdm/GUD-GENERALTRAPS-MIB.txt:48-54` |

该 MIB 的合规性将该通知及其两个变量列为 mandatory；这不证明 CCDM 设备一定会发送它。源：`ccdm/GUD-GENERALTRAPS-MIB.txt:64-86`。

## 权限与遗漏事实

- 本证据范围内的数据列一律 `read-only`；每个 table、entry、index 均 `not-accessible`，未检出 `read-write`、`read-create` 或 `write-only`。逐对象行证据在本文件各表中。
- 这些 MIB 的 `IMPORTS` 只证明使用 SNMPv2 MIB 结构；没有给出设备的 SNMP 协议版本、UDP 端口、团体字、SNMPv3 安全、Trap 接收端设置或轮询频率。示例源：`ccdm/GUD-CCDM-MIB.txt:4-12`、`ccdm/GUD-GENERALTRAPS-MIB.txt:4-14`。
- 未找到 CCDM 专属 `NOTIFICATION-TYPE`；唯一通知为上述通用通知。没有恢复 Trap、严重度枚举或 Trap 配置对象的原文证据。
