# CCDM SNMP 接入与监控字典

## 范围与证据

本字典只依据 `ccdm/` 内随附的六个 MIB 文本编写；OID、语法、访问权限、枚举、索引和通知均以 MIB 为准。`GUD-SMI-MIB` 将 `gudCCDM` 明确为 ControlCenter-Digital 的子树，数值根为 `1.3.6.1.4.1.32828.3.257.10`（下文记为 **P**）。源：`ccdm/GUD-SMI-MIB.txt:26-31,45-49,90-94,108-112`。

| MIB 模块 | 资料版本/更新时间 | SHA-256 |
|---|---|---|
| `GUD-SMI-MIB` | Rev. 1.6 / 2021-11-11 | `3D2D24835286B8F874FCD7291D6A0D7C80DECDEBE130C557F35D2B1FEDEBD476` |
| `GUD-CCDM-MIB` | Rev. 1.5 / 2023-07-05 | `7C02E8F43D7F2FE327BFDDCAF6B8929E9563E9D8711AD3290E05D4FB3D442F82` |
| `GUD-CCDMCON-MIB` | Rev. 1.1 / 2023-01-01 | `5FF037BC86F801C05190F01447CD3AD486270F1E5D120FBF0C49A76AFEA3AB33` |
| `GUD-CCDMCPU-MIB` | Rev. 1.0 / 2020-09-09 | `61A5B63829177285D8F3C3607496D54FD2EBBC4810D8952B7B85F6E55E455135` |
| `GUD-CCDMDWC-MIB` | Rev. 1.0 / 2023-04-01 | `DBFDB891CE5F175A4050234ACE17DEF73F75A328301DE695E255E7EF1B9ED715` |
| `GUD-GENERALTRAP-MIB` | Rev. 1.0 / 2009-01-14 | `D575B112175E1E23B98F98AFB97E053BC86AD4FE2A10DF8D137F595C160FC1E9` |

各模块的版本和更新时间可由模块身份定义复核。源：`ccdm/GUD-SMI-MIB.txt:8-20`、`ccdm/GUD-CCDM-MIB.txt:14-26`、`ccdm/GUD-CCDMCON-MIB.txt:14-26`、`ccdm/GUD-CCDMCPU-MIB.txt:14-26`、`ccdm/GUD-CCDMDWC-MIB.txt:14-26`、`ccdm/GUD-GENERALTRAPS-MIB.txt:16-28`。本资料包含一个通用通知 MIB；未发现 CCDM 专属通知定义。

## 接入方式与实施前提

- 这些 MIB 使用 `SNMPv2-SMI` / `SNMPv2-TC` / `SNMPv2-CONF` 的对象和通知定义，但**随附资料未说明**设备端启用的 SNMP 版本、UDP 端口、团体字、SNMPv3 用户、认证或加密算法，也未说明管理端/Trap 接收端地址的配置方法。源：各 MIB 的 `IMPORTS`，例如 `ccdm/GUD-CCDM-MIB.txt:4-12`、`ccdm/GUD-GENERALTRAPS-MIB.txt:4-14`。
- 实施前应由厂商或设备配置页确认上述连接参数、ACL、防火墙、管理地址及 Trap 目的地。该项是部署前提，不是本 MIB 已定义的 SET 操作。
- 轮询根可从 `P.2`（基础 CCDM 数据）和以下子模块状态表开始：CON 根 `P.1.1.2.3`、CPU 根 `P.1.2.2.3`、DWC 根 `P.1.3.2.3`。根的推导和每个表的数值 OID 见 `evidence.md`。

## 发现与轮询数据字典

### 读法与 OID 记法

- 所有下表中的 `P` 都是数值前缀 `1.3.6.1.4.1.32828.3.257.10`，因此每一条“数值 OID”均可将 `P` 直接替换为该十进制前缀。其父子关系来自 `GUD-SMI-MIB`，复算过程见 `evidence.md`。源：`ccdm/GUD-SMI-MIB.txt:26-31,45-49,90-94,108-112`。
- 标量的对象标识符必须加实例 `.0`；表的可读列必须在列 OID 后附表索引实例。`not-accessible` 的 table、entry、index 不能作为独立 GET 对象，而应对表列执行 GETNEXT/GETBULK 遍历。
- 除特别注明外，以下可读对象均为 `MAX-ACCESS read-only`，监控用途是呈现其 MIB 原文描述的事实，不附加厂商未给出的阈值或健康规则。

### 基础机框：`GUD-CCDM-MIB`

基础对象树为 `P.2`：identify=`P.2.1`、info=`P.2.2`、status=`P.2.3`、errormessages=`P.2.1000`。源：`ccdm/GUD-CCDM-MIB.txt:133-167`。

| 对象 | 数值 OID（实例） | SYNTAX / 已定义含义 | 监控用途 | 来源 |
|---|---|---|---|---|
| `deviceId` | `P.2.1.1.0` | `DisplayString`，设备 ID | 资产标识 | `ccdm/GUD-CCDM-MIB.txt:193-199` |
| `deviceCl` | `P.2.1.2.0` | `DisplayString`，设备类别 | 资产标识 | `ccdm/GUD-CCDM-MIB.txt:201-207` |
| `deviceType` | `P.2.1.3.0` | `DisplayString`，设备类型 | 资产标识 | `ccdm/GUD-CCDM-MIB.txt:209-215` |
| `serialNumber` | `P.2.1.4.0` | `DisplayString`，序列号 | 资产标识 | `ccdm/GUD-CCDM-MIB.txt:217-223` |
| `etherAddress0` / `etherAddress1` | `P.2.1.5.0` / `P.2.1.6.0` | `PhysAddress`，第 1 / 第 2 以太网口 MAC | 网络资产标识 | `ccdm/GUD-CCDM-MIB.txt:225-239` |
| `firmwareVersion` | `P.2.2.1.0` | `DisplayString`，固件版本 | 版本盘点 | `ccdm/GUD-CCDM-MIB.txt:243-249` |
| `switchTemperature` | `P.2.3.4.0` | `DisplayString`，switch board 温度；`UNITS Deg C` 在原文被注释 | 温度展示；不可假定可作数值阈值 | `ccdm/GUD-CCDM-MIB.txt:253-260` |
| `controllerTemperature` | `P.2.3.5.0` | `DisplayString`，controller board 温度；`UNITS Deg C` 被注释 | 温度展示；格式待实测 | `ccdm/GUD-CCDM-MIB.txt:262-269` |
| `raidStatusDevice1` / `raidStatusDevice2` | `P.2.3.6.0` / `P.2.3.7.0` | `RaidStatus`：`failure(0), resync(1), recover(2), check(3), repair(4), ok(5)` | 两个 RAID 设备状态 | `ccdm/GUD-CCDM-MIB.txt:115-126,271-285` |
| `functionSwitch` | `P.2.3.9.0` | `FunctionStatus`：`failure(0), ok(1)` | switch board 功能状态 | `ccdm/GUD-CCDM-MIB.txt:97-104,287-293` |
| `powerCurrent` | `P.2.3.500.0` | `DisplayString`，电源电流；`UNITS A` 被注释 | 电流展示；格式/单位待实测确认 | `ccdm/GUD-CCDM-MIB.txt:968-975` |
| `networkInterface0` / `networkInterface1` | `P.2.3.506.0` / `P.2.3.507.0` | `NetworkInterfaceStatus`：`down(0), up(1)` | 第 1 / 第 2 网络接口链路状态 | `ccdm/GUD-CCDM-MIB.txt:46-53,977-991` |
| `generalErrorCode` / `generalErrorMessage` | `P.2.1000.1.0` / `P.2.1000.2.0` | `Integer32` 错误码 / `DisplayString` 问题描述 | 告警详情或错误诊断字段；错误码语义表未提供 | `ccdm/GUD-CCDM-MIB.txt:994-1008` |

基础机框表均位于 `P.2.3`；下表的“实例”中的 `i`、`c`、`p` 分别是对应索引值，而不是字面量。

| 表 / 索引与遍历 | 可读列（数值 OID；SYNTAX；用途/枚举） | 来源 |
|---|---|---|
| `fanTable`；`fanIndex i=1..20`；遍历 `P.2.3.1000.1.2`、`.3` | `fanName`=`P.2.3.1000.1.2.i`，`DisplayString`，风扇名称；`fanSpeed`=`P.2.3.1000.1.3.i`，`Integer32(0..10000)`、RPM，风扇转速 | `ccdm/GUD-CCDM-MIB.txt:299-344` |
| `powerSupplyTable`；`powerSupplyIndex i=1..3`；遍历 `P.2.3.1001.1.2` 至 `P.2.3.1001.1.5` | `powerSupplyStatus`=`P.2.3.1001.1.2.i`，`PowerSupplyStatus`：`off(0), on(1), absent(2), failure(3)`；`powerSupplyTemperature`=`P.2.3.1001.1.3.i`，`DisplayString`；`powerSupplyVoltage`=`P.2.3.1001.1.4.i`，`DisplayString`；`powerSupplyFanFunction`=`P.2.3.1001.1.5.i`，`FunctionStatus failure(0)/ok(1)` | `ccdm/GUD-CCDM-MIB.txt:35-44,97-104,350-413` |
| `ioCardCatTable`；`ioCardCatIndex c=1..19`；遍历 `P.2.3.1002.1.2` 至 `P.2.3.1002.1.6` | `ioCardCatId`=`P.2.3.1002.1.2.c`，`Integer32`；`ioCardCatStatus`=`P.2.3.1002.1.3.c`，`DeviceStatus offline(0)/online(1)`；`ioCardCatFunction`=`P.2.3.1002.1.4.c`，`FunctionStatus`；`ioCardCatTemperature`=`P.2.3.1002.1.5.c`，`DisplayString`；`ioCardCatMatrixSlot`=`P.2.3.1002.1.6.c`，`Integer32` | `ccdm/GUD-CCDM-MIB.txt:106-113,97-104,419-491` |
| `ioCardCatPortTable`；复合索引 `(c,p)`，`c=ioCardCatIndex`、`p=1..16`；遍历 `P.2.3.1003.1.2` | `ioCardCatPortStatus`=`P.2.3.1003.1.2.c.p`，`CatPortStatus down(0)/up(1)`，CAT IO 端口状态 | `ccdm/GUD-CCDM-MIB.txt:55-62,493-530` |
| `ioCardFiberTable`；`ioCardFiberIndex c=1..19`；遍历 `P.2.3.1004.1.2` 至 `P.2.3.1004.1.6` | `ioCardFiberId`=`P.2.3.1004.1.2.c`，`Integer32`；`ioCardFiberStatus`=`P.2.3.1004.1.3.c`，`DeviceStatus offline(0)/online(1)`；`ioCardFiberFunction`=`P.2.3.1004.1.4.c`，`FunctionStatus`；`ioCardFiberTemperature`=`P.2.3.1004.1.5.c`，`DisplayString`；`ioCardFiberMatrixSlot`=`P.2.3.1004.1.6.c`，`Integer32` | `ccdm/GUD-CCDM-MIB.txt:97-113,536-608` |
| `ioCardFiberPortTable`；复合索引 `(c,p)`，`c=ioCardFiberIndex`、`p=1..16`；遍历 `P.2.3.1005.1.2` 至 `P.2.3.1005.1.5` | `ioCardFiberPortStatus`=`P.2.3.1005.1.2.c.p`，`FiberPortStatus noModule(0)/deactivated(1)/down(2)/up(3)`；`ioCardFiberTxPower`=`P.2.3.1005.1.3.c.p`，`DisplayString`；`ioCardFiberRxPower`=`P.2.3.1005.1.4.c.p`，`DisplayString`；`ioCardFiberSfpType`=`P.2.3.1005.1.5.c.p`，`DisplayString` | `ccdm/GUD-CCDM-MIB.txt:64-73,610-674` |
| `ioCardMultiTable`；`ioCardMultiIndex c=1..19`；遍历 `P.2.3.1006.1.2` 至 `P.2.3.1006.1.6` | `ioCardMultiId`=`P.2.3.1006.1.2.c`，`Integer32`；`ioCardMultiStatus`=`P.2.3.1006.1.3.c`，`DeviceStatus offline(0)/online(1)`；`ioCardMultiFunction`=`P.2.3.1006.1.4.c`，`FunctionStatus`；`ioCardMultiTemperature`=`P.2.3.1006.1.5.c`，`DisplayString`；`ioCardMultiMatrixSlot`=`P.2.3.1006.1.6.c`，`Integer32` | `ccdm/GUD-CCDM-MIB.txt:97-113,680-752` |
| `ioCardMultiPortTable`；复合索引 `(c,p)`，`c=ioCardMultiIndex`、`p=1..16`；遍历 `P.2.3.1007.1.2` 至 `P.2.3.1007.1.5` | `ioCardMultiPortStatus`=`P.2.3.1007.1.2.c.p`，`MultiPortStatus noModule(0)/deactivated(1)/down(2)/up(3)`；`ioCardMultiTxPower`=`P.2.3.1007.1.3.c.p`，`DisplayString`；`ioCardMultiRxPower`=`P.2.3.1007.1.4.c.p`，`DisplayString`；`ioCardMultiSfpType`=`P.2.3.1007.1.5.c.p`，`DisplayString` | `ccdm/GUD-CCDM-MIB.txt:75-84,754-818` |
| `ioCardTrunkTable`；`ioCardTrunkIndex c=1..19`；遍历 `P.2.3.1008.1.2` 至 `P.2.3.1008.1.6` | `ioCardTrunkId`=`P.2.3.1008.1.2.c`，`Integer32`；`ioCardTrunkStatus`=`P.2.3.1008.1.3.c`，`DeviceStatus offline(0)/online(1)`；`ioCardTrunkFunction`=`P.2.3.1008.1.4.c`，`FunctionStatus`；`ioCardTrunkTemperature`=`P.2.3.1008.1.5.c`，`DisplayString`；`ioCardTrunkMatrixSlot`=`P.2.3.1008.1.6.c`，`Integer32` | `ccdm/GUD-CCDM-MIB.txt:97-113,824-896` |
| `ioCardTrunkPortTable`；复合索引 `(c,p)`，`c=ioCardTrunkIndex`、`p=1..16`；遍历 `P.2.3.1009.1.2` 至 `P.2.3.1009.1.5` | `ioCardTrunkPortStatus`=`P.2.3.1009.1.2.c.p`，`TrunkPortStatus noModule(0)/deactivated(1)/down(2)/up(3)`；`ioCardTrunkTxPower`=`P.2.3.1009.1.3.c.p`，`DisplayString`；`ioCardTrunkRxPower`=`P.2.3.1009.1.4.c.p`，`DisplayString`；`ioCardTrunkSfpType`=`P.2.3.1009.1.5.c.p`，`DisplayString` | `ccdm/GUD-CCDM-MIB.txt:86-95,898-962` |

### 控制台模块：`GUD-CCDMCON-MIB`

CON 模块状态树的数值前缀为 `P.1.1.2.3`，`userModuleTable` 为 `.1000`，其 entry 复合前缀为 `P.1.1.2.3.1000.1`。以 `userModuleIndex u=1..2000` 为第一个索引，表列 OID 末尾均为 `.u`。源：`ccdm/GUD-CCDM-MIB.txt:28`、`ccdm/GUD-CCDMCON-MIB.txt:103-113,138-194`。

| 对象 | 数值 OID（实例） | SYNTAX / 已定义含义 | 用途 | 来源 |
|---|---|---|---|---|
| `id`, `cl`, `name` | `P.1.1.2.3.1000.1.2.u`、`.3.u`、`.4.u` | 均为 `DisplayString`；ID、类别、名称 | 受监控控制台的资产列 | `ccdm/GUD-CCDMCON-MIB.txt:196-218` |
| `deviceStatus` | `P.1.1.2.3.1000.1.5.u` | `DeviceStatus offline(0)/online(1)/ready(2)` | 在线状态 | `ccdm/GUD-CCDMCON-MIB.txt:58-66,220-226` |
| `mainPower`, `redundantPower` | `P.1.1.2.3.1000.1.6.u`、`P.1.1.2.3.1000.1.7.u` | `PowerStatus off(0)/on(1)` | 主/冗余电源状态 | `ccdm/GUD-CCDMCON-MIB.txt:40-47,228-242` |
| `temperature1` | `P.1.1.2.3.1000.1.8.u` | `DisplayString`，内部温度 1 | 温度展示；格式待实测 | `ccdm/GUD-CCDMCON-MIB.txt:244-250` |
| `consolePS2Connection`, `consoleUSBConnection` | `P.1.1.2.3.1000.1.9.u`、`P.1.1.2.3.1000.1.10.u` | `KeyboardMouseStatus none(0)/keyboard(1)/mouse(2)/keyboardMouse(3)` | PS/2 与 USB 键鼠连接状态 | `ccdm/GUD-CCDMCON-MIB.txt:77-86,252-266` |
| `displayConnection`, `displayConnection1`, `displayConnection2` | `P.1.1.2.3.1000.1.11.u`、`P.1.1.2.3.1000.1.12.u`、`P.1.1.2.3.1000.1.13.u` | `ConnectionStatus notConnected(0)/connected(1)` | 显示器连接状态 | `ccdm/GUD-CCDMCON-MIB.txt:68-75,268-290` |
| `displayType`, `displayType1`, `displayType2` | `P.1.1.2.3.1000.1.14.u`、`P.1.1.2.3.1000.1.15.u`、`P.1.1.2.3.1000.1.16.u` | `DisplayString`，所连显示器类型 | 显示设备信息 | `ccdm/GUD-CCDMCON-MIB.txt:292-314` |
| `freeze`, `freeze1`, `freeze2` | `P.1.1.2.3.1000.1.17.u`、`P.1.1.2.3.1000.1.18.u`、`P.1.1.2.3.1000.1.19.u` | `Boolean false(0)/true(1)`；整体/第 1/第 2 视频输出 freeze | 视频冻结状态 | `ccdm/GUD-CCDMCON-MIB.txt:31-38,316-338` |
| `sfpTxPower`, `sfpTxPower1`, `sfpTxPower2` | `P.1.1.2.3.1000.1.20.u`、`P.1.1.2.3.1000.1.21.u`、`P.1.1.2.3.1000.1.22.u` | `Integer32`；原文标注 SFP TX power `[uW]` | SFP 发射功率 | `ccdm/GUD-CCDMCON-MIB.txt:340-362` |
| `sfpRxPower`, `sfpRxPower1`, `sfpRxPower2` | `P.1.1.2.3.1000.1.23.u`、`P.1.1.2.3.1000.1.24.u`、`P.1.1.2.3.1000.1.25.u` | `Integer32`；原文标注 SFP RX power `[uW]` | SFP 接收功率 | `ccdm/GUD-CCDMCON-MIB.txt:364-386` |
| `sfpType`, `sfpType1`, `sfpType2` | `P.1.1.2.3.1000.1.26.u`、`P.1.1.2.3.1000.1.27.u`、`P.1.1.2.3.1000.1.28.u` | `DisplayString`，SFP 类型 | 光模块信息 | `ccdm/GUD-CCDMCON-MIB.txt:388-410` |
| `activeTransmissionPort` | `P.1.1.2.3.1000.1.29.u` | `Integer32(1..2)` | 活动传输端口号 | `ccdm/GUD-CCDMCON-MIB.txt:412-418` |
| `networkInterface0` | `P.1.1.2.3.1000.1.30.u` | `NetworkInterfaceStatus down(0)/up(1)` | 模块网络链路状态 | `ccdm/GUD-CCDMCON-MIB.txt:49-56,420-426` |

| 表 / 复合索引与遍历 | 可读列（数值 OID；SYNTAX；用途/枚举） | 来源 |
|---|---|---|
| `fanTable`；`(u,f)`，`f=fanIndex 1..10`；遍历 `P.1.1.2.3.1001.1.2`、`P.1.1.2.3.1001.1.3` | `fanName`=`P.1.1.2.3.1001.1.2.u.f`，`DisplayString`；`fanSpeed`=`P.1.1.2.3.1001.1.3.u.f`，`Integer32(0..10000)`、RPM | `ccdm/GUD-CCDMCON-MIB.txt:432-477` |
| `gpioTable`；`(u,g)`，`g=gpioIndex 1..4`；遍历 `P.1.1.2.3.1002.1.2`、`P.1.1.2.3.1002.1.3` | `gpioName`=`P.1.1.2.3.1002.1.2.u.g`，`DisplayString`；`gpioValue`=`P.1.1.2.3.1002.1.3.u.g`，`GpioValue inactive(0)/low(1)/high(2)` | `ccdm/GUD-CCDMCON-MIB.txt:88-96,483-528` |

### CPU 模块：`GUD-CCDMCPU-MIB`

CPU 状态树前缀为 `P.1.2.2.3`。`targetModuleTable` entry 前缀为 `P.1.2.2.3.1000.1`，首索引 `targetModuleIndex t=1..2000`；以下表列的实例均为 `.t`。源：`ccdm/GUD-CCDM-MIB.txt:29`、`ccdm/GUD-CCDMCPU-MIB.txt:130-140,166-216`。

| 对象 | 数值 OID（实例） | SYNTAX / 已定义含义 | 用途 | 来源 |
|---|---|---|---|---|
| `id`, `cl`, `name` | `P.1.2.2.3.1000.1.2.t`、`.3.t`、`.4.t` | `DisplayString`；ID、类别、名称 | 目标模块资产列 | `ccdm/GUD-CCDMCPU-MIB.txt:218-240` |
| `deviceStatus` | `P.1.2.2.3.1000.1.5.t` | `DeviceStatus offline(0)/online(1)/ready(2)` | 在线状态 | `ccdm/GUD-CCDMCPU-MIB.txt:41-49,242-248` |
| `mainPower`, `redundantPower` | `P.1.2.2.3.1000.1.6.t`、`P.1.2.2.3.1000.1.7.t` | `PowerStatus off(0)/on(1)` | 主/冗余电源状态 | `ccdm/GUD-CCDMCPU-MIB.txt:32-39,250-264` |
| `temperature1` | `P.1.2.2.3.1000.1.8.t` | `DisplayString`，内部温度 1 | 温度展示；格式待实测 | `ccdm/GUD-CCDMCPU-MIB.txt:266-272` |
| `consolePS2Connection`, `consoleUSBConnection`, `targetPS2Connection` | `P.1.2.2.3.1000.1.9.t`、`P.1.2.2.3.1000.1.10.t`、`P.1.2.2.3.1000.1.11.t` | `KeyboardMouseStatus none(0)/keyboard(1)/mouse(2)/keyboardMouse(3)` | 控制台/目标 PS2 键鼠状态 | `ccdm/GUD-CCDMCPU-MIB.txt:60-69,274-296` |
| `targetUsbHid` | `P.1.2.2.3.1000.1.12.t` | `UsbHidStatus notConnected(0)/connected(1)/initialized(2)` | 目标 USB HID 状态 | `ccdm/GUD-CCDMCPU-MIB.txt:71-79,298-304` |
| `targetVideoCable`, `targetVideoCable1`, `targetVideoCable2` | `P.1.2.2.3.1000.1.13.t`、`P.1.2.2.3.1000.1.14.t`、`P.1.2.2.3.1000.1.15.t` | `ConnectionStatus notConnected(0)/connected(1)` | 目标视频线连接状态 | `ccdm/GUD-CCDMCPU-MIB.txt:51-58,306-328` |
| `targetVideoSignal`, `targetVideoSignal1`, `targetVideoSignal2` | `P.1.2.2.3.1000.1.16.t`、`P.1.2.2.3.1000.1.17.t`、`P.1.2.2.3.1000.1.18.t` | `VideoType none(0)/vga(1)/dvisl(2)/dvidl(3)/dmdp(4)/dp(5)/hdmi(6)` | 视频信号类型 | `ccdm/GUD-CCDMCPU-MIB.txt:92-104,330-352` |
| `targetPower` | `P.1.2.2.3.1000.1.19.t` | `PowerStatus off(0)/on(1)` | 所连设备电源状态 | `ccdm/GUD-CCDMCPU-MIB.txt:32-39,354-360` |
| `targetAccess` | `P.1.2.2.3.1000.1.20.t` | `AccessStatus local(0)/remote(1)/localExclusive(2)/remoteExclusive(3)` | 访问状态 | `ccdm/GUD-CCDMCPU-MIB.txt:81-90,362-368` |
| `sfpTxPower`, `sfpRxPower` | `P.1.2.2.3.1000.1.21.t`、`P.1.2.2.3.1000.1.22.t` | `Integer32`；原文标注 `[uW]` | SFP 发射/接收功率 | `ccdm/GUD-CCDMCPU-MIB.txt:370-384` |
| `sfpType` | `P.1.2.2.3.1000.1.23.t` | `DisplayString`，SFP 类型 | 光模块信息 | `ccdm/GUD-CCDMCPU-MIB.txt:386-392` |
| `networkInterface0` | `P.1.2.2.3.1000.1.24.t` | `NetworkInterfaceStatus down(0)/up(1)` | 网络接口链路状态 | `ccdm/GUD-CCDMCPU-MIB.txt:116-123,394-400` |

| 表 / 复合索引与遍历 | 可读列（数值 OID；SYNTAX；用途/枚举） | 来源 |
|---|---|---|
| `fanTable`；`(t,f)`，`f=fanIndex 1..10`；遍历 `P.1.2.2.3.1001.1.2`、`P.1.2.2.3.1001.1.3` | `fanName`=`P.1.2.2.3.1001.1.2.t.f`，`DisplayString`；`fanSpeed`=`P.1.2.2.3.1001.1.3.t.f`，`Integer32(0..10000)`、RPM | `ccdm/GUD-CCDMCPU-MIB.txt:406-451` |
| `gpioTable`；`(t,g)`，`g=gpioIndex 1..4`；遍历 `P.1.2.2.3.1002.1.2`、`P.1.2.2.3.1002.1.3` | `gpioName`=`P.1.2.2.3.1002.1.2.t.g`，`DisplayString`；`gpioValue`=`P.1.2.2.3.1002.1.3.t.g`，`GpioValue inactive(0)/low(1)/high(2)` | `ccdm/GUD-CCDMCPU-MIB.txt:106-114,457-502` |

### DWC 模块：`GUD-CCDMDWC-MIB`

DWC 状态树前缀为 `P.1.3.2.3`。`dynamicUserModuleTable` entry 前缀为 `P.1.3.2.3.1000.1`，首索引为 `dynamicUserModuleIndex d=1..2000`；以下表列实例均为 `.d`。源：`ccdm/GUD-CCDM-MIB.txt:30`、`ccdm/GUD-CCDMDWC-MIB.txt:93-103,128-165`。

| 对象 | 数值 OID（实例） | SYNTAX / 已定义含义 | 用途 | 来源 |
|---|---|---|---|---|
| `id`, `cl`, `name` | `P.1.3.2.3.1000.1.2.d`、`.3.d`、`.4.d` | `DisplayString`；ID、类别、名称 | 动态用户模块资产列 | `ccdm/GUD-CCDMDWC-MIB.txt:167-189` |
| `deviceStatus` | `P.1.3.2.3.1000.1.5.d` | `DeviceStatus offline(0)/online(1)/ready(2)` | 在线状态 | `ccdm/GUD-CCDMDWC-MIB.txt:58-66,191-197` |
| `mainPower`, `redundantPower` | `P.1.3.2.3.1000.1.6.d`、`P.1.3.2.3.1000.1.7.d` | `PowerStatus off(0)/on(1)` | 主/冗余电源 | `ccdm/GUD-CCDMDWC-MIB.txt:40-47,199-213` |
| `temperature1` | `P.1.3.2.3.1000.1.8.d` | `DisplayString`，内部温度 1 | 温度展示；格式待实测 | `ccdm/GUD-CCDMDWC-MIB.txt:215-221` |
| `consoleUSBConnection` | `P.1.3.2.3.1000.1.9.d` | `KeyboardMouseStatus none(0)/keyboard(1)/mouse(2)/keyboardMouse(3)` | USB 键鼠连接状态 | `ccdm/GUD-CCDMDWC-MIB.txt:77-86,223-229` |
| `networkInterface0`, `networkInterface1` | `P.1.3.2.3.1000.1.10.d`、`P.1.3.2.3.1000.1.11.d` | `NetworkInterfaceStatus down(0)/up(1)` | 两个网络接口链路状态 | `ccdm/GUD-CCDMDWC-MIB.txt:49-56,231-245` |

| 表 / 复合索引与遍历 | 可读列（数值 OID；SYNTAX；用途/枚举） | 来源 |
|---|---|---|
| `fanTable`；`(d,f)`，`f=fanIndex 1..10`；遍历 `P.1.3.2.3.1001.1.2`、`P.1.3.2.3.1001.1.3` | `fanName`=`P.1.3.2.3.1001.1.2.d.f`，`DisplayString`；`fanSpeed`=`P.1.3.2.3.1001.1.3.d.f`，`Integer32(0..10000)`、RPM | `ccdm/GUD-CCDMDWC-MIB.txt:251-296` |
| `videoChannelTable`；`(d,v)`，`v=videoChannelIndex 1..4`；遍历 `P.1.3.2.3.1002.1.2`、`P.1.3.2.3.1002.1.3` | `displayConnection`=`P.1.3.2.3.1002.1.2.d.v`，`ConnectionStatus notConnected(0)/connected(1)`；`displayType`=`P.1.3.2.3.1002.1.3.d.v`，`DisplayString` | `ccdm/GUD-CCDMDWC-MIB.txt:68-75,302-347` |
| `linkChannelTable`；`(d,l)`，`l=linkChannelIndex 1..8`；遍历 `P.1.3.2.3.1003.1.2` 至 `P.1.3.2.3.1003.1.13` | `conid`=`P.1.3.2.3.1003.1.2.d.l`，`DisplayString`；`concl`=`P.1.3.2.3.1003.1.3.d.l`，`DisplayString`；`conname`=`P.1.3.2.3.1003.1.4.d.l`，`DisplayString`；`linkChannelStatus`=`P.1.3.2.3.1003.1.5.d.l`，`DeviceStatus offline(0)/online(1)/ready(2)`；`activeTransmissionPort`=`P.1.3.2.3.1003.1.6.d.l`，`Integer32(1..2)`；`sfpTxPower1`=`P.1.3.2.3.1003.1.7.d.l`，`Integer32 [uW]`；`sfpTxPower2`=`P.1.3.2.3.1003.1.8.d.l`，`Integer32 [uW]`；`sfpRxPower1`=`P.1.3.2.3.1003.1.9.d.l`，`Integer32 [uW]`；`sfpRxPower2`=`P.1.3.2.3.1003.1.10.d.l`，`Integer32 [uW]`；`sfpType1`=`P.1.3.2.3.1003.1.11.d.l`，`DisplayString`；`sfpType2`=`P.1.3.2.3.1003.1.12.d.l`，`DisplayString`；`freeze`=`P.1.3.2.3.1003.1.13.d.l`，`Boolean false(0)/true(1)` | `ccdm/GUD-CCDMDWC-MIB.txt:31-38,58-66,354-489` |

## 告警与 Trap 接收

`GUD-GENERALTRAP-MIB` 只定义了一个通知。其数值路径的根为 `1.3.6.1.4.1.32828.2.1.0`（`gudGeneralNotifications`）；这是 Trap 子树，不属于 CCDM 产品根 `P`。源：`ccdm/GUD-SMI-MIB.txt:26-31,36-40,54-58`、`ccdm/GUD-GENERALTRAPS-MIB.txt:30-54`。

| 通知 | 通知 OID | `OBJECTS` 变量 | 已证实含义 / 接收处理 | 建议去重键 | 来源 |
|---|---|---|---|---|---|
| `generalNotification` | `1.3.6.1.4.1.32828.2.1.0.4` | `level`=`1.3.6.1.4.1.32828.2.1.0.2`（`Integer32`，notification level）；`message`=`1.3.6.1.4.1.32828.2.1.0.3`（`DisplayString`，消息文本） | 接收并保存 OID、来源设备、接收时间、`level` 原值和 `message` 原文。MIB 没有给 `level` 枚举、严重度映射、触发/恢复语义或设备/端口关联字段，因此不可推断告警等级或恢复关系。 | `(来源IP/引擎标识, notification OID, level 原值, message 原文)`；时间窗口由平台策略配置，非 MIB 事实 | `ccdm/GUD-GENERALTRAPS-MIB.txt:30-54` |

随附 MIB 未定义 CCDM 专属通知、恢复 Trap、Trap 目标配置对象或 Trap 严重度字典；必须向厂商确认实际设备是否发出上述通用通知以及 `level` 的取值含义。

## 交互与写操作

- 本资料中已定义的可轮询监控对象均为 `read-only`；所有表、entry 和 index 均为 `not-accessible`。未发现 `read-write`、`read-create` 或 `MAX-ACCESS write-only` 对象。因此当前监控 UI 只能做查询/展示，不能基于这些 MIB 承诺任何 SET、端口启停、告警确认、Trap 订阅或阈值下发操作。源：`ccdm/GUD-CCDM-MIB.txt:193-1008`、`ccdm/GUD-CCDMCON-MIB.txt:138-528`、`ccdm/GUD-CCDMCPU-MIB.txt:166-502`、`ccdm/GUD-CCDMDWC-MIB.txt:128-489`。
- MIB 的 `MODULE-COMPLIANCE` 指定基础 `identifyGroup`、`infoGroup`、`statusGroup` 为 mandatory，而 `errorGroup` 是 optional；各 CON/CPU/DWC 的 `statusGroup` 为 mandatory。应将错误码/消息的缺失（例如 `noSuchObject`）作为可选组不支持处理，不能视为写入失败。源：`ccdm/GUD-CCDM-MIB.txt:1014-1075`、`ccdm/GUD-CCDMCON-MIB.txt:534-559`、`ccdm/GUD-CCDMCPU-MIB.txt:508-529`、`ccdm/GUD-CCDMDWC-MIB.txt:495-518`。

## 监控界面落地建议

以下是对已证实对象的呈现映射，不定义 MIB 未给出的阈值、健康规则或控制按钮。

| 页面区域 | 仅使用的已证实对象 |
|---|---|
| 设备概览 | 基础机框的 `deviceId`、`deviceCl`、`deviceType`、`serialNumber`、`firmwareVersion`、`etherAddress0/1`；CON/CPU/DWC 模块表的 `id`、`cl`、`name`、`deviceStatus` |
| 机框健康与资源 | `switchTemperature`、`controllerTemperature`、`raidStatusDevice1/2`、`functionSwitch`、`powerCurrent`、`fanName/fanSpeed`、`powerSupplyStatus/Temperature/Voltage/FanFunction`、`networkInterface0/1` |
| IO 卡与端口表 | 四类 IO card 的 `Id/Status/Function/Temperature/MatrixSlot`；CAT/Fiber/Multi/Trunk port 的状态、Tx/Rx power、SFP type；表键使用卡索引和端口索引 |
| CON/CPU/DWC 状态页 | 对应模块的数据字典中的电源、温度、键鼠、显示/视频、访问、链路、SFP、风扇和 GPIO；每个表行保留 MIB 索引作为稳定识别字段 |
| 告警列表 | `generalErrorCode/generalErrorMessage` 的轮询值，以及 `generalNotification` 收到的 `level/message`；二者不能从资料中推断必然对应关系 |

## 已知限制与待厂商确认项

1. 随附资料未说明 SNMP 版本、端口、凭据、SNMPv3 安全参数、ACL、Trap 目的地或设备端开启步骤。
2. 通用 Trap 的 `level` 是未枚举的 `Integer32`；没有严重度、清除/恢复或确认语义，也没有指出 CCDM 是否产生该 Trap。
3. 温度、电流、电压和 CCDM IO 光功率多为 `DisplayString`；原文只有部分被注释掉的单位，不应在采集器中强转数值或预置阈值，须用实机样本确认格式。
4. `generalErrorCode` 没有错误码字典，且 `errorGroup` 是 optional；不应将缺少该对象解释为故障。
5. 一个表的索引上限来自 `SYNTAX`，不代表实际装机数量；应以 GETNEXT/GETBULK 发现到的实例为准。
6. `DeviceStatus ready(2)`、各 `freeze` 值、`AccessStatus` 等仅按枚举显示；是否需要升级为告警未在 MIB 中规定。
7. `sfpRxPower2` 的 DWC 原文描述写为 “SFP RX power 1”，而对象名是 `sfpRxPower2`；本文保留对象名和数值 OID，不改写为厂商未确认的语义。源：`ccdm/GUD-CCDMDWC-MIB.txt:459-465`。

## 可执行核验清单

1. 在实机上以 GET 读取 `P.2.1.1.0` 至 `P.2.1.6.0`，确认全部标量须以 `.0` 实例访问并记录 `deviceId`、MAC 的返回类型。依据：`ccdm/GUD-CCDM-MIB.txt:193-239`。
2. 对 `P.2.3.1000.1.2` 执行 GETBULK/GETNEXT，确认 `fanName` 的实例后缀为单一 `fanIndex(1..20)`，再以同一实例读取 `.3` 验证 RPM。依据：`ccdm/GUD-CCDM-MIB.txt:299-344`。
3. 对 `P.2.3.1003.1.2` 遍历，验证 CAT 端口状态实例后缀顺序为 `(ioCardCatIndex, ioCardCatPortIndex)`，并仅把返回的 `0/1` 显示为 `down/up`。依据：`ccdm/GUD-CCDM-MIB.txt:493-530,55-62`。
4. 分别读取 `P.2.3.6.0` 和 `.7.0`，确认 RAID 值按 `0..5` 的 `RaidStatus` 枚举展示，不把 `resync/recover/check/repair` 擅自折算为正常/故障。依据：`ccdm/GUD-CCDM-MIB.txt:115-126,271-285`。
5. 对一个 CON 模块遍历 `P.1.1.2.3.1000.1.20` 至 `.25`，核对 SFP 功率返回为 `Integer32` 且原文单位为 `[uW]`，以实机样本验证多个 transmission line 的实际存在。依据：`ccdm/GUD-CCDMCON-MIB.txt:340-386`。
6. 对一个 CPU 模块遍历 `P.1.2.2.3.1000.1.16` 至 `.20`，确认视频类型、目标电源、访问状态按各自枚举渲染。依据：`ccdm/GUD-CCDMCPU-MIB.txt:81-104,330-368`。
7. 对一个 DWC 模块遍历 `P.1.3.2.3.1003.1.2` 至 `.13`，核对复合索引 `(dynamicUserModuleIndex, linkChannelIndex)`、SFP 功率整数单位和 `freeze` 布尔值。依据：`ccdm/GUD-CCDMDWC-MIB.txt:354-489`。
8. 用 Trap 接收器捕获 `1.3.6.1.4.1.32828.2.1.0.4`（如设备实际发出），确认 varbind 中存在 `.2` 的 `Integer32 level` 和 `.3` 的 `DisplayString message`；不要预先给 level 映射严重度。依据：`ccdm/GUD-GENERALTRAPS-MIB.txt:30-54`。
9. 对任一表 root、entry 或索引（如 `fanTable`、`fanTableEntry`、`fanIndex`）发起单独 GET，确认其 `not-accessible`，而对可读列进行 walk；这验证 UI/采集器没有把索引误作可轮询数据点。依据：`ccdm/GUD-CCDM-MIB.txt:299-328`。
10. 对 `P.2.1000.1.0`、`.2.0` 做能力探测；若返回 `noSuchObject`，记录为 optional error group 不支持，不发起 SET 或将其视为设备错误。依据：`ccdm/GUD-CCDM-MIB.txt:1014-1024,1068-1075`。
