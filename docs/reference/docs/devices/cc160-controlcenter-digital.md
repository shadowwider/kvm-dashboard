# cc160（ControlCenter-Digital）SNMP 接入与监控字典

## 范围与证据

本文件只依据 `cc160` 随附的 MIB 原文整理。`GUD-SMI-MIB` 将 `gudCCDM` 描述为 ControlCenter-Digital 的子树；本包还提供其通用底盘、CPU、CON、DWC 三类监控对象，以及通用通知 MIB。资料中未将文件夹名 `cc160` 与某一具体硬件料号建立对应关系，因此本文以 MIB 所称的 ControlCenter-Digital / CCDM 为准。

| MIB 模块（相对原始目录） | 版本/更新时间（原文） | SHA-256 |
|---|---|---|
| `cc160/GUD-SMI-MIB.txt` | Rev. 1.6；202111110000Z | `3d2d24835286b8f874fcd7291d6a0d7c80decdebe130c557f35d2b1fedebd476` |
| `cc160/GUD-CCDM-MIB.txt` | Rev. 1.5；202307050800Z | `7c02e8f43d7f2fe327bfddcaf6b8929e9563e9d8711ad3290e05d4fb3d442f82` |
| `cc160/GUD-CCDMCON-MIB.txt` | Rev. 1.1；202301010100Z | `5ff037bc86f801c05190f01447cd3ad486270f1e5d120fbf0c49a76afea3ab33` |
| `cc160/GUD-CCDMCPU-MIB.txt` | Rev. 1.0；202009090800Z | `61a5b63829177285d8f3c3607496d54fd2ebbc4810d8952b7b85f6e55e455135` |
| `cc160/GUD-CCDMDWC-MIB.txt` | Rev. 1.0；202304010000Z | `dbfdb891ce5f175a4050234ace17def73f75a328301de695e255e7ef1b9ed715` |
| `cc160/GUD-GENERALTRAPS-MIB.txt` | Rev. 1.0；200901141407Z | `d575b112175e1e23b98f98afb97e053bc86ad4fe2a10df8d137f595c160fc1e9` |

`enterprises` 是从 `SNMPv2-SMI` 导入的符号，随附原文没有给出它的数值根。因此下文的 OID 均保留为“符号根 `enterprises` + 已由原文推导的数值尾段”，没有把外部标准值当作本包原文事实。推导主链为：`gudEnterprise ::= { enterprises 32828 }`、`gudProduct ::= { gudEnterprise 3 }`、`gudDIGITALMATRIXSWITCH ::= { gudProduct 257 }`、`gudCCDM ::= { gudDIGITALMATRIXSWITCH 10 }`，故公共根为 `enterprises.32828.3.257.10`。

源：`cc160/GUD-SMI-MIB.txt:26-31`、`cc160/GUD-SMI-MIB.txt:45-49`、`cc160/GUD-SMI-MIB.txt:90-94`、`cc160/GUD-SMI-MIB.txt:108-112`；模块版本见各文件 `:14-26`，完整逐对象证据见同目录 `evidence.md`。

## 接入方式与实施前提

随附 MIB **未说明** SNMP 版本、UDP 端口、团体字、SNMPv3 用户/认证/加密、访问控制、管理端配置步骤、Trap 接收地址配置或轮询周期。实施前须向厂商或现场管理员确认这些参数，并以现场可用的只读凭据开始验证。

对象表明本资料包含 SNMP 标量、表和 `NOTIFICATION-TYPE`，但不能仅据此断言设备启用了哪个 SNMP 版本。表可用 GETNEXT 遍历；只有在现场确认版本支持时才可使用 GETBULK。不要把 MIB 中 `not-accessible` 的表、Entry 或索引当成可独立 GET 的数据点。

## 发现与轮询数据字典

### 通用 CCDM 底盘与 I/O 卡（`GUD-CCDM-MIB`）

下表中的标量实例均应在对象 OID 后加 `.0`。`E` 代表 `enterprises.32828.3.257.10`，不是省略的未经证实数值根。

| 对象 | OID（标量实例） | SYNTAX / 值 | MAX-ACCESS；监控用途 | 事实出处 |
|---|---|---|---|---|
| `deviceId`、`deviceCl`、`deviceType`、`serialNumber` | `E.2.1.1.0`、`E.2.1.2.0`、`E.2.1.3.0`、`E.2.1.4.0` | `DisplayString` | read-only；设备标识、类别、类型、序列号 | 源：`cc160/GUD-CCDM-MIB.txt:193-223` |
| `etherAddress0`、`etherAddress1` | `E.2.1.5.0`、`E.2.1.6.0` | `PhysAddress` | read-only；第 1/第 2 以太网口 MAC 地址 | 源：`cc160/GUD-CCDM-MIB.txt:225-239` |
| `firmwareVersion` | `E.2.2.1.0` | `DisplayString` | read-only；固件版本 | 源：`cc160/GUD-CCDM-MIB.txt:243-249` |
| `switchTemperature`、`controllerTemperature` | `E.2.3.4.0`、`E.2.3.5.0` | `DisplayString`；原文注释为 Deg C，但未声明 `UNITS` | read-only；交换板、控制器板温度 | 源：`cc160/GUD-CCDM-MIB.txt:253-269` |
| `raidStatusDevice1`、`raidStatusDevice2` | `E.2.3.6.0`、`E.2.3.7.0` | `RaidStatus`: `failure(0)`,`resync(1)`,`recover(2)`,`check(3)`,`repair(4)`,`ok(5)` | read-only；两个 RAID 设备状态；界面必须显示原枚举，不能把中间态擅自归为故障或健康 | 源：`cc160/GUD-CCDM-MIB.txt:115-126`、`cc160/GUD-CCDM-MIB.txt:271-285` |
| `functionSwitch` | `E.2.3.9.0` | `FunctionStatus`: `failure(0)`,`ok(1)` | read-only；交换板功能状态 | 源：`cc160/GUD-CCDM-MIB.txt:97-104`、`cc160/GUD-CCDM-MIB.txt:287-293` |
| `powerCurrent` | `E.2.3.500.0` | `DisplayString`；原文注释为 A，但未声明 `UNITS` | read-only；电源电流 | 源：`cc160/GUD-CCDM-MIB.txt:968-975` |
| `networkInterface0`、`networkInterface1` | `E.2.3.506.0`、`E.2.3.507.0` | `NetworkInterfaceStatus`: `down(0)`,`up(1)` | read-only；两个网络接口链路状态 | 源：`cc160/GUD-CCDM-MIB.txt:46-53`、`cc160/GUD-CCDM-MIB.txt:977-991` |
| `generalErrorCode`、`generalErrorMessage` | `E.2.1000.1.0`、`E.2.1000.2.0` | `Integer32`、`DisplayString` | read-only；错误码与问题描述。该组在合规声明中是可选组 | 源：`cc160/GUD-CCDM-MIB.txt:993-1008`、`cc160/GUD-CCDM-MIB.txt:1014-1024` |

`fanTable`：表根 `E.2.3.1000`，Entry `E.2.3.1000.1`，索引 `fanIndex`（范围 1..20）。用 GETNEXT 遍历 `fanName`（`E.2.3.1000.1.2.<fanIndex>`，`DisplayString`）与 `fanSpeed`（`E.2.3.1000.1.3.<fanIndex>`，`Integer32(0..10000)`，原文说明 RPM）；索引、表和 Entry 都是 `not-accessible`。源：`cc160/GUD-CCDM-MIB.txt:299-344`。

`powerSupplyTable`：表根 `E.2.3.1001`，Entry `E.2.3.1001.1`，索引 `powerSupplyIndex`（1..3）。遍历 `powerSupplyStatus`（`E.2.3.1001.1.2.<index>`，`off(0)/on(1)/absent(2)/failure(3)`）、`powerSupplyTemperature`（`E.2.3.1001.1.3.<index>`，`DisplayString`）、`powerSupplyVoltage`（`E.2.3.1001.1.4.<index>`，`DisplayString`）和 `powerSupplyFanFunction`（`E.2.3.1001.1.5.<index>`，`failure(0)/ok(1)`）。全部叶对象只读；表/Entry/索引不可独立访问。源：`cc160/GUD-CCDM-MIB.txt:35-44`、`cc160/GUD-CCDM-MIB.txt:97-104`、`cc160/GUD-CCDM-MIB.txt:350-413`。

四类 I/O 卡都以“卡表 + 端口表”呈现，卡索引范围均为 1..19，端口索引范围均为 1..16；所有表/Entry/索引为 `not-accessible`，所有以下可监控列为 `read-only`。采用 GETNEXT 发现实际行，不应假定所有范围内行都存在。

| 类型 | 卡表/卡行索引；可轮询列（OID 后缀） | 端口表/复合索引；可轮询列（OID 后缀） | 枚举与用途；出处 |
|---|---|---|---|
| CAT | 卡表 `E.2.3.1002.1.<column>.<card>`；`ioCardCatId` `.2`（`Integer32`）、`ioCardCatStatus` `.3`（`offline(0)/online(1)`）、`ioCardCatFunction` `.4`（`failure(0)/ok(1)`）、`ioCardCatTemperature` `.5`（`DisplayString`）、`ioCardCatMatrixSlot` `.6`（`Integer32`） | `ioCardCatPortStatus`：`E.2.3.1003.1.2.<card>.<port>`（`down(0)/up(1)`） | 卡身份/在线/功能/温度/槽位，及 CAT 端口状态。源：`cc160/GUD-CCDM-MIB.txt:55-62`、`cc160/GUD-CCDM-MIB.txt:106-113`、`cc160/GUD-CCDM-MIB.txt:419-530` |
| FIBER | 卡表 `E.2.3.1004.1.<column>.<card>`；`ioCardFiberId` `.2`、`ioCardFiberStatus` `.3`、`ioCardFiberFunction` `.4`、`ioCardFiberTemperature` `.5`、`ioCardFiberMatrixSlot` `.6`（语法同上） | `ioCardFiberPortStatus` `E.2.3.1005.1.2.<card>.<port>`（`noModule(0)/deactivated(1)/down(2)/up(3)`）；`ioCardFiberTxPower` `.1.3.<card>.<port>`、`ioCardFiberRxPower` `.1.4.<card>.<port>`、`ioCardFiberSfpType` `.1.5.<card>.<port>`（后三者 `DisplayString`；均以前缀 `E.2.3.1005`） | 光纤卡及端口/SFP 信息。源：`cc160/GUD-CCDM-MIB.txt:64-73`、`cc160/GUD-CCDM-MIB.txt:536-674` |
| MULTI | 卡表 `E.2.3.1006.1.<column>.<card>`；`ioCardMultiId` `.2`、`ioCardMultiStatus` `.3`、`ioCardMultiFunction` `.4`、`ioCardMultiTemperature` `.5`、`ioCardMultiMatrixSlot` `.6`（语法同上） | `ioCardMultiPortStatus` `E.2.3.1007.1.2.<card>.<port>`（`noModule(0)/deactivated(1)/down(2)/up(3)`）；`ioCardMultiTxPower` `.1.3.<card>.<port>`、`ioCardMultiRxPower` `.1.4.<card>.<port>`、`ioCardMultiSfpType` `.1.5.<card>.<port>`（均以前缀 `E.2.3.1007`） | MULTI 卡及端口/SFP 信息。源：`cc160/GUD-CCDM-MIB.txt:75-84`、`cc160/GUD-CCDM-MIB.txt:680-818` |
| TRUNK | 卡表 `E.2.3.1008.1.<column>.<card>`；`ioCardTrunkId` `.2`、`ioCardTrunkStatus` `.3`、`ioCardTrunkFunction` `.4`、`ioCardTrunkTemperature` `.5`、`ioCardTrunkMatrixSlot` `.6`（语法同上） | `ioCardTrunkPortStatus` `E.2.3.1009.1.2.<card>.<port>`（`noModule(0)/deactivated(1)/down(2)/up(3)`）；`ioCardTrunkTxPower` `.1.3.<card>.<port>`、`ioCardTrunkRxPower` `.1.4.<card>.<port>`、`ioCardTrunkSfpType` `.1.5.<card>.<port>`（均以前缀 `E.2.3.1009`） | TRUNK 卡及端口/SFP 信息。源：`cc160/GUD-CCDM-MIB.txt:86-95`、`cc160/GUD-CCDM-MIB.txt:824-962` |

### CPU 受监控目标模块（`GUD-CCDMCPU-MIB`）

CPU 表的根为 `E.1.2.2.3.1000`，Entry 为 `.1000.1`，复用的 `targetModuleIndex` 为唯一索引（1..2000）。所有可轮询叶对象均为 `read-only`；以下 `.n` 指 Entry 列号，实例形式为 `E.1.2.2.3.1000.1.n.<targetModuleIndex>`。索引、表和 Entry 是 `not-accessible`，用 GETNEXT 发现目标模块。

| 列对象/后缀 | SYNTAX / 枚举 | 监控用途与事实出处 |
|---|---|---|
| `id` `.2`、`cl` `.3`、`name` `.4` | `DisplayString` | 目标设备 ID、类别、名称。源：`cc160/GUD-CCDMCPU-MIB.txt:210-240` |
| `deviceStatus` `.5` | `offline(0)/online(1)/ready(2)` | 目标在线状态；不能擅自将 `ready` 合并为 online。源：`cc160/GUD-CCDMCPU-MIB.txt:41-49`、`cc160/GUD-CCDMCPU-MIB.txt:242-248` |
| `mainPower` `.6`、`redundantPower` `.7` | `off(0)/on(1)` | 主/冗余电源状态。源：`cc160/GUD-CCDMCPU-MIB.txt:32-39`、`cc160/GUD-CCDMCPU-MIB.txt:250-264` |
| `temperature1` `.8` | `DisplayString` | 内部温度 1；原文未给单位。源：`cc160/GUD-CCDMCPU-MIB.txt:266-272` |
| `consolePS2Connection` `.9`、`consoleUSBConnection` `.10`、`targetPS2Connection` `.11` | `none(0)/keyboard(1)/mouse(2)/keyboardMouse(3)` | 键盘/鼠标连接状态。源：`cc160/GUD-CCDMCPU-MIB.txt:60-69`、`cc160/GUD-CCDMCPU-MIB.txt:274-296` |
| `targetUsbHid` `.12` | `notConnected(0)/connected(1)/initialized(2)` | 目标 USB HID 状态。源：`cc160/GUD-CCDMCPU-MIB.txt:71-79`、`cc160/GUD-CCDMCPU-MIB.txt:298-304` |
| `targetVideoCable` `.13`、`targetVideoCable1` `.14`、`targetVideoCable2` `.15` | `notConnected(0)/connected(1)` | 目标显示连接。源：`cc160/GUD-CCDMCPU-MIB.txt:51-58`、`cc160/GUD-CCDMCPU-MIB.txt:306-328` |
| `targetVideoSignal` `.16`、`targetVideoSignal1` `.17`、`targetVideoSignal2` `.18` | `none(0)/vga(1)/dvisl(2)/dvidl(3)/dmdp(4)/dp(5)/hdmi(6)` | 接入显示信号类型。源：`cc160/GUD-CCDMCPU-MIB.txt:92-104`、`cc160/GUD-CCDMCPU-MIB.txt:330-352` |
| `targetPower` `.19` | `off(0)/on(1)` | 连接设备电源状态。源：`cc160/GUD-CCDMCPU-MIB.txt:354-360` |
| `targetAccess` `.20` | `local(0)/remote(1)/localExclusive(2)/remoteExclusive(3)` | 访问状态。源：`cc160/GUD-CCDMCPU-MIB.txt:81-90`、`cc160/GUD-CCDMCPU-MIB.txt:362-368` |
| `sfpTxPower` `.21`、`sfpRxPower` `.22` | `Integer32`，原文说明 uW | SFP 收发功率。源：`cc160/GUD-CCDMCPU-MIB.txt:370-384` |
| `sfpType` `.23` | `DisplayString` | SFP 类型。源：`cc160/GUD-CCDMCPU-MIB.txt:386-392` |
| `networkInterface0` `.24` | `down(0)/up(1)` | 目标网络接口状态。源：`cc160/GUD-CCDMCPU-MIB.txt:116-123`、`cc160/GUD-CCDMCPU-MIB.txt:394-400` |

CPU 风扇表：`E.1.2.2.3.1001.1.2.<target>.<fan>` 为 `fanName`（`DisplayString`），`.3.<target>.<fan>` 为 `fanSpeed`（`Integer32(0..10000)`，RPM）；复合索引为 `targetModuleIndex(1..2000),fanIndex(1..10)`。GPIO 表：`E.1.2.2.3.1002.1.2.<target>.<gpio>` 为 `gpioName`，`.3.<target>.<gpio>` 为 `gpioValue`=`inactive(0)/low(1)/high(2)`；索引为 `targetModuleIndex,gpioIndex(1..4)`。两表的表/Entry/索引都不可单独访问。源：`cc160/GUD-CCDMCPU-MIB.txt:406-451`、`cc160/GUD-CCDMCPU-MIB.txt:457-502`、`cc160/GUD-CCDMCPU-MIB.txt:106-114`。

### CON 用户模块（`GUD-CCDMCON-MIB`）

CON 表根为 `E.1.1.2.3.1000`，Entry 为 `.1000.1`，索引 `userModuleIndex` 范围 1..2000；所有叶对象只读，实例为 `E.1.1.2.3.1000.1.n.<userModuleIndex>`。表、Entry、索引不可独立访问，需遍历。

| 列对象/后缀 | SYNTAX / 值 | 监控用途与事实出处 |
|---|---|---|
| `id` `.2`、`cl` `.3`、`name` `.4` | `DisplayString` | 用户模块识别。源：`cc160/GUD-CCDMCON-MIB.txt:188-218` |
| `deviceStatus` `.5` | `offline(0)/online(1)/ready(2)` | 用户模块在线状态。源：`cc160/GUD-CCDMCON-MIB.txt:58-66`、`cc160/GUD-CCDMCON-MIB.txt:220-226` |
| `mainPower` `.6`、`redundantPower` `.7` | `off(0)/on(1)` | 电源状态。源：`cc160/GUD-CCDMCON-MIB.txt:40-47`、`cc160/GUD-CCDMCON-MIB.txt:228-242` |
| `temperature1` `.8` | `DisplayString` | 内部温度 1；未给单位。源：`cc160/GUD-CCDMCON-MIB.txt:244-250` |
| `consolePS2Connection` `.9`、`consoleUSBConnection` `.10` | `none(0)/keyboard(1)/mouse(2)/keyboardMouse(3)` | PS/2、USB 键鼠连接。源：`cc160/GUD-CCDMCON-MIB.txt:77-86`、`cc160/GUD-CCDMCON-MIB.txt:252-266` |
| `displayConnection` `.11`、`displayConnection1` `.12`、`displayConnection2` `.13` | `notConnected(0)/connected(1)` | 显示器连接。源：`cc160/GUD-CCDMCON-MIB.txt:68-75`、`cc160/GUD-CCDMCON-MIB.txt:268-290` |
| `displayType` `.14`、`displayType1` `.15`、`displayType2` `.16` | `DisplayString` | 显示器类型。源：`cc160/GUD-CCDMCON-MIB.txt:292-314` |
| `freeze` `.17`、`freeze1` `.18`、`freeze2` `.19` | `false(0)/true(1)` | 设备及第 1/第 2 视频输出的冻结模式。源：`cc160/GUD-CCDMCON-MIB.txt:31-38`、`cc160/GUD-CCDMCON-MIB.txt:316-338` |
| `sfpTxPower` `.20`、`sfpTxPower1` `.21`、`sfpTxPower2` `.22`、`sfpRxPower` `.23`、`sfpRxPower1` `.24`、`sfpRxPower2` `.25` | `Integer32`，原文说明 uW | SFP 总体/传输线 1/2 的收发功率。源：`cc160/GUD-CCDMCON-MIB.txt:340-386` |
| `sfpType` `.26`、`sfpType1` `.27`、`sfpType2` `.28` | `DisplayString` | SFP 总体/传输线类型。源：`cc160/GUD-CCDMCON-MIB.txt:388-410` |
| `activeTransmissionPort` `.29` | `Integer32(1..2)` | 当前传输端口编号。源：`cc160/GUD-CCDMCON-MIB.txt:412-418` |
| `networkInterface0` `.30` | `down(0)/up(1)` | 网络接口状态。源：`cc160/GUD-CCDMCON-MIB.txt:49-56`、`cc160/GUD-CCDMCON-MIB.txt:420-426` |

CON 风扇表：`E.1.1.2.3.1001.1.2.<user>.<fan>`=`fanName`，`.3.<user>.<fan>`=`fanSpeed`（`Integer32(0..10000)`，RPM），索引 `userModuleIndex(1..2000),fanIndex(1..10)`。GPIO 表：`E.1.1.2.3.1002.1.2.<user>.<gpio>`=`gpioName`，`.3.<user>.<gpio>`=`gpioValue`（`inactive(0)/low(1)/high(2)`），索引 `userModuleIndex,gpioIndex(1..4)`；两表的结构对象不可单独访问。源：`cc160/GUD-CCDMCON-MIB.txt:432-477`、`cc160/GUD-CCDMCON-MIB.txt:483-528`、`cc160/GUD-CCDMCON-MIB.txt:88-96`。

### DWC 动态用户模块（`GUD-CCDMDWC-MIB`）

DWC 主表根为 `E.1.3.2.3.1000`，Entry 为 `.1000.1`，索引 `dynamicUserModuleIndex` 范围 1..2000；所有叶对象只读，实例为 `E.1.3.2.3.1000.1.n.<dynamicUserModuleIndex>`。表、Entry、索引不可独立访问。

| 列对象/后缀 | SYNTAX / 值 | 监控用途与事实出处 |
|---|---|---|
| `id` `.2`、`cl` `.3`、`name` `.4` | `DisplayString` | 动态用户模块识别。源：`cc160/GUD-CCDMDWC-MIB.txt:159-189` |
| `deviceStatus` `.5` | `offline(0)/online(1)/ready(2)` | 在线状态。源：`cc160/GUD-CCDMDWC-MIB.txt:58-66`、`cc160/GUD-CCDMDWC-MIB.txt:191-197` |
| `mainPower` `.6`、`redundantPower` `.7` | `off(0)/on(1)` | 主/冗余电源。源：`cc160/GUD-CCDMDWC-MIB.txt:40-47`、`cc160/GUD-CCDMDWC-MIB.txt:199-213` |
| `temperature1` `.8` | `DisplayString` | 内部温度；未给单位。源：`cc160/GUD-CCDMDWC-MIB.txt:215-221` |
| `consoleUSBConnection` `.9` | `none(0)/keyboard(1)/mouse(2)/keyboardMouse(3)` | USB 键鼠连接。源：`cc160/GUD-CCDMDWC-MIB.txt:77-86`、`cc160/GUD-CCDMDWC-MIB.txt:223-229` |
| `networkInterface0` `.10`、`networkInterface1` `.11` | `down(0)/up(1)` | 两个网络接口状态。源：`cc160/GUD-CCDMDWC-MIB.txt:49-56`、`cc160/GUD-CCDMDWC-MIB.txt:231-245` |

DWC 风扇表：`E.1.3.2.3.1001.1.2.<dwc>.<fan>`=`fanName`，`.3.<dwc>.<fan>`=`fanSpeed`（`Integer32(0..10000)`，RPM）；索引 `dynamicUserModuleIndex(1..2000),fanIndex(1..10)`。源：`cc160/GUD-CCDMDWC-MIB.txt:251-296`。

DWC 视频通道表：根 `E.1.3.2.3.1002`、Entry `.1002.1`、索引 `dynamicUserModuleIndex(1..2000),videoChannelIndex(1..4)`；`displayConnection` 是 `.2.<dwc>.<channel>`（`notConnected(0)/connected(1)`），`displayType` 是 `.3.<dwc>.<channel>`（`DisplayString`）。源：`cc160/GUD-CCDMDWC-MIB.txt:68-75`、`cc160/GUD-CCDMDWC-MIB.txt:302-347`。

DWC 链路通道表：根 `E.1.3.2.3.1003`、Entry `.1003.1`、索引 `dynamicUserModuleIndex(1..2000),linkChannelIndex(1..8)`；实例前缀为 `E.1.3.2.3.1003.1`：`conid` `.2`、`concl` `.3`、`conname` `.4`（均为 `DisplayString`），`linkChannelStatus` `.5`（`offline(0)/online(1)/ready(2)`），`activeTransmissionPort` `.6`（`Integer32(1..2)`），`sfpTxPower1` `.7`、`sfpTxPower2` `.8`、`sfpRxPower1` `.9`、`sfpRxPower2` `.10`（均 `Integer32`，原文说明 uW），`sfpType1` `.11`、`sfpType2` `.12`（`DisplayString`），`freeze` `.13`（`false(0)/true(1)`）。源：`cc160/GUD-CCDMDWC-MIB.txt:31-38`、`cc160/GUD-CCDMDWC-MIB.txt:354-489`。该表的表/Entry/索引不可独立访问。

## 告警与 Trap 接收

本包只有一个 `NOTIFICATION-TYPE`：`generalNotification`。其通知 OID 为 `enterprises.32828.2.1.0.4`（推导：`gudEnterprise.2`=`gudTrap`，`.1`=`gudGeneralTrap`，`.0`=`gudGeneralNotifications`，`.4`=通知）。变量为 `level`（`enterprises.32828.2.1.0.2`，`Integer32`）和 `message`（`.0.3`，`DisplayString`）。`level` 没有枚举或严重度对照表，必须原样保存，不得映射为严重/警告/恢复；`message` 是文本。

原文只描述其为 G&D general notification，未给出触发条件、恢复语义、恢复 Trap、Trap 目的地址配置对象、重试或确认机制，也未证明此 Trap 必由上述 CCDM 对象产生。告警列表应存储接收时间、来源地址、`snmpTrapOID`、`level`、`message` 和原始 varbind。建议（这是平台去重策略而非 MIB 语义）以“来源地址 + 通知 OID + `level` + `message`”构造短时间窗口去重键，并保留首次/最近接收时间。

源：`cc160/GUD-SMI-MIB.txt:26-31`、`cc160/GUD-SMI-MIB.txt:36-40`、`cc160/GUD-SMI-MIB.txt:54-58`；`cc160/GUD-GENERALTRAPS-MIB.txt:30-54`。

## 交互与写操作

本包所定义的所有 `OBJECT-TYPE` 叶对象均为 `MAX-ACCESS read-only`；表、Entry 和索引均为 `not-accessible`。检索到的 6 个 MIB 文件中没有 `read-write`、`read-create` 或 `write-only` 对象。因此该接入仅能执行发现、GET/GETNEXT（在现场版本支持时 GETBULK）和 Trap 接收，**没有可由本 MIB 证实的 SET 操作、值域、控制流程或回滚方式**。

特别地，`freeze`、`activeTransmissionPort`、GPIO 值及所有状态对象都是只读监控值，不能因其名称而在界面中提供控制按钮。源：各叶对象的 `MAX-ACCESS` 见 `cc160/GUD-CCDM-MIB.txt:193-1008`、`cc160/GUD-CCDMCON-MIB.txt:196-528`、`cc160/GUD-CCDMCPU-MIB.txt:218-502`、`cc160/GUD-CCDMDWC-MIB.txt:167-489`；表/索引访问级别见相应表定义。

## 监控界面落地建议

仅基于已证实对象，可实现下列页面；阈值、严重度和自动处置规则均留给现场策略，不能从此 MIB 推断。

| 页面 | 可展示的数据对象 |
|---|---|
| 设备概览卡 | `deviceId`、`deviceCl`、`deviceType`、`serialNumber`、`firmwareVersion`、`networkInterface0/1`、`functionSwitch`、`raidStatusDevice1/2`、`generalErrorCode/message` |
| 底盘资源页 | `switchTemperature`、`controllerTemperature`、`powerCurrent`；`fanTable` 风扇名称/转速；`powerSupplyTable` 状态、温度、电压、风扇功能 |
| I/O 卡与端口页 | 四类卡的 ID/在线状态/功能/温度/槽位；CAT、FIBER、MULTI、TRUNK 的端口状态及可用 SFP 收发功率/类型 |
| CPU/CON/DWC 模块清单 | 各模块表的 `id/cl/name/deviceStatus`、电源、温度、网络/输入输出连接、显示/SFP、访问状态、冻结状态、风扇/GPIO/视频/链路通道（按各模块实际存在的对象） |
| 告警列表 | `generalNotification` 的 OID、来源、`level`、`message` 原值；`generalErrorCode/message` 可作为轮询发现的错误信息，不能假定它与 Trap 一一对应 |

## 已知限制与待厂商确认项

1. 随附资料未说明 SNMP 版本、端口、凭据、SNMPv3 安全参数、访问控制、Trap 目的地址或轮询周期。
2. `enterprises` 数值根不在随附 MIB 原文中，本文未把外部标准库数值作为证据；现场应使用同一 MIB 依赖集解析完整数值 OID。
3. 温度、电流、电压及通用/卡端口光功率中，部分为 `DisplayString` 或仅有注释；格式、小数位和单位不能假定。CPU/CON/DWC 的若干 SFP 功率明确说明 uW。
4. `level` 没有枚举，Trap 不含触发条件、恢复或严重度；不得预设告警等级、关闭规则或通知与轮询值的因果关系。
5. 枚举 `ready`、`resync`、`recover`、`check`、`repair` 等只应按原值展示；MIB 没有健康评分、告警阈值或状态转换规则。
6. 表索引范围只是语法允许范围；实际行数、硬件是否配备某卡/端口及缺行含义需现场确认。
7. 所有对象只读，控制、切换、冻结解除或 GPIO 设定若需要，应另取厂商控制接口文档，不能通过本 MIB 的 SET 实现。

## 可执行核验清单

1. 使用现场同一套 MIB 依赖加载 `GUD-SMI-MIB` 与 `GUD-CCDM-MIB`，解析 `deviceId.0`；核对符号链为 `gudCCDM.objects.identify.deviceId.0`，并确认 GET 的标量实例含 `.0`。依据：`cc160/GUD-CCDM-MIB.txt:139-143,193-199`。
2. 对 `fanTable` 做一次 GETNEXT 遍历，记录返回 OID 的最后一段仅为 `fanIndex`，确认其值位于 1..20，并读取相同行的 `fanName`/`fanSpeed`；不要 GET `fanIndex` 本身。依据：`cc160/GUD-CCDM-MIB.txt:307-344`。
3. 对任一实际 CAT 卡的端口列做 GETNEXT，核对 `ioCardCatPortStatus` 实例的两个尾部索引为 `<ioCardCatIndex>.<ioCardCatPortIndex>`，且状态仅为 0 或 1。依据：`cc160/GUD-CCDM-MIB.txt:502-530`、`cc160/GUD-CCDM-MIB.txt:55-62`。
4. 从任一 CPU 行读取 `targetVideoSignal`，验证返回值只按 `none/vga/dvisl/dvidl/dmdp/dp/hdmi` 的 0..6 显示，不能将值当作显示连接布尔值。依据：`cc160/GUD-CCDMCPU-MIB.txt:92-104,330-352`。
5. 在受控测试环境触发或捕获一条 `generalNotification`，确认通知 OID 尾段为 `...2.1.0.4`，varbind 包含 `level`（`.2`）和 `message`（`.3`）；将 `level` 原数值入库。依据：`cc160/GUD-GENERALTRAPS-MIB.txt:30-54`。
6. 对 `freeze`、`gpioValue` 或 `activeTransmissionPort` 尝试配置前，先检查 MIB 解析结果中的 `MAX-ACCESS`；应为 read-only，界面不得发出 SET。依据：`cc160/GUD-CCDMCON-MIB.txt:316-338,412-418,522-528`。
7. 对 DWC 链路表遍历，验证复合索引为 `<dynamicUserModuleIndex>.<linkChannelIndex>`，并只接受 `activeTransmissionPort` 的 1 或 2。依据：`cc160/GUD-CCDMDWC-MIB.txt:362-393,427-433`。
