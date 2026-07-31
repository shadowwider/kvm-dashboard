# cc160 MIB 原文证据台账

本台账服务于 `access-draft.md`：逐模块列出对象、通知、表索引和原文行号。行号均相对于原始 `cc160` 目录的未修改 `*-MIB.txt`。不使用网页或产品经验补值。

## 1. 资料清单与计数

| 原文 | 原文版本（行） | SHA-256 | `OBJECT-TYPE` | 通知 |
|---|---|---|---:|---:|
| `cc160/GUD-SMI-MIB.txt` | Rev. 1.6，`8-20` | `3d2d24835286b8f874fcd7291d6a0d7c80decdebe130c557f35d2b1fedebd476` | 0 | 0 |
| `cc160/GUD-CCDM-MIB.txt` | Rev. 1.5，`14-26` | `7c02e8f43d7f2fe327bfddcaf6b8929e9563e9d8711ad3290e05d4fb3d442f82` | 86 | 0 |
| `cc160/GUD-CCDMCON-MIB.txt` | Rev. 1.1，`14-26` | `5ff037bc86f801c05190f01447cd3ad486270f1e5d120fbf0c49a76afea3ab33` | 42 | 0 |
| `cc160/GUD-CCDMCPU-MIB.txt` | Rev. 1.0，`14-26` | `61a5b63829177285d8f3c3607496d54fd2ebbc4810d8952b7b85f6e55e455135` | 36 | 0 |
| `cc160/GUD-CCDMDWC-MIB.txt` | Rev. 1.0，`14-26` | `dbfdb891ce5f175a4050234ace17def73f75a328301de695e255e7ef1b9ed715` | 38 | 0 |
| `cc160/GUD-GENERALTRAPS-MIB.txt` | Rev. 1.0，`16-28` | `d575b112175e1e23b98f98afb97e053bc86ad4fe2a10df8d137f595c160fc1e9` | 2 | 1 |

合计为 6 个 MIB、204 个 `OBJECT-TYPE`（包含表、Entry、不可访问索引和可读叶对象）以及 1 个 `NOTIFICATION-TYPE`。全部 `OBJECT-TYPE` 的 `MAX-ACCESS` 只有 `read-only` 或 `not-accessible`；未检出 `read-write`、`read-create`、`write-only`。

## 2. OID 推导与数值边界

`GUD-SMI-MIB` 仅把 `enterprises` 从 `SNMPv2-SMI` 导入（`cc160/GUD-SMI-MIB.txt:4-6`），且未在随附原文中给出该符号的数值根。因此以下是从原文可复算的“符号根 + 数值尾段”，而非引用外部标准得出的完整纯数值 OID。

| 符号 | 原文父子声明 | 可复算 OID |
|---|---|---|
| `gudEnterprise` | `{ enterprises 32828 }`，`cc160/GUD-SMI-MIB.txt:26-31` | `enterprises.32828` |
| `gudTrap` / `gudGeneralTrap` | `{ gudEnterprise 2 }` / `{ gudTrap 1 }`，`cc160/GUD-SMI-MIB.txt:36-40,54-58` | `enterprises.32828.2` / `.2.1` |
| `gudProduct` / `gudDIGITALMATRIXSWITCH` / `gudCCDM` | `{ gudEnterprise 3 }` / `{ gudProduct 257 }` / `{ gudDIGITALMATRIXSWITCH 10 }`，`cc160/GUD-SMI-MIB.txt:45-49,90-94,108-112` | `enterprises.32828.3.257.10`（记为 `E`） |
| `gudCCDMMIB` / `gudCCDMCON` / `gudCCDMCPU` / `gudCCDMDWC` | `{ gudCCDM 1 }`、`{ gudCCDMMIB 1/2/3 }`，`cc160/GUD-CCDM-MIB.txt:14-30` | `E.1` / `E.1.1` / `E.1.2` / `E.1.3` |
| 通用对象根 | `objects { gudCCDM 2 }`，其下 `identify 1`、`info 2`、`status 3`、`errormessages 1000`，`cc160/GUD-CCDM-MIB.txt:132-167` | `E.2.1`、`E.2.2`、`E.2.3`、`E.2.1000` |
| CON/CPU/DWC 对象根 | 各模块 `objects { gudCCDMCON/CPU/DWC 2 }`、`status { objects 3 }`，`cc160/GUD-CCDMCON-MIB.txt:102-113`、`cc160/GUD-CCDMCPU-MIB.txt:129-140`、`cc160/GUD-CCDMDWC-MIB.txt:92-103` | CON `E.1.1.2.3`；CPU `E.1.2.2.3`；DWC `E.1.3.2.3` |
| 通知根 | `gudGeneralTrapMIB { gudGeneralTrap 1 }`、`gudGeneralNotifications { gudGeneralTrap 0 }`，`cc160/GUD-GENERALTRAPS-MIB.txt:16-30` | `enterprises.32828.2.1.1`、`enterprises.32828.2.1.0` |

复算示例：`generalNotification ::= { gudGeneralNotifications 4 }`（`GUD-GENERALTRAPS:48-54`），代入通知根得到 `enterprises.32828.2.1.0.4`；`ioCardFiberRxPower ::= { ioCardFiberPortEntry 4 }`（`GUD-CCDM:660-666`），且端口 Entry 为 `{ ioCardFiberPortTable 1 }`、表为 `{ status 1005 }`（`611-626`），故列 OID 为 `E.2.3.1005.1.4.<ioCardFiberIndex>.<ioCardFiberPortIndex>`。

## 3. `GUD-CCDM-MIB` 逐对象证据（86）

### 3.1 通用文本约定和标量

| 对象（原文行；原始 OID 声明） | 语法/访问与说明的原文证据 |
|---|---|
| `deviceId` (`193-199`; `{ identify 1 }`), `deviceCl` (`201-207`; `{ identify 2 }`), `deviceType` (`209-215`; `{ identify 3 }`), `serialNumber` (`217-223`; `{ identify 4 }`) | 均 `DisplayString`、`read-only`；ID/类别/类型/序列号分别在相应块的 DESCRIPTION 给出。 |
| `etherAddress0` (`225-231`; `{ identify 5 }`), `etherAddress1` (`233-239`; `{ identify 6 }`) | 均 `PhysAddress`、`read-only`；分别为 first/second ethernet port MAC address。 |
| `firmwareVersion` (`243-249`; `{ info 1 }`) | `DisplayString`、`read-only`；Firmware version。 |
| `switchTemperature` (`253-260`; `{ status 4 }`), `controllerTemperature` (`262-269`; `{ status 5 }`) | `DisplayString`、`read-only`；原文只有被注释掉的 `UNITS "Deg C"`，分别为 switch/controller board temperature。 |
| `raidStatusDevice1` (`271-277`; `{ status 6 }`), `raidStatusDevice2` (`279-285`; `{ status 7 }`) | `RaidStatus`、`read-only`；枚举 `failure(0),resync(1),recover(2),check(3),repair(4),ok(5)` 在 `115-126`。 |
| `functionSwitch` (`287-293`; `{ status 9 }`) | `FunctionStatus`、`read-only`；`failure(0),ok(1)` 在 `97-104`。 |
| `powerCurrent` (`968-975`; `{ status 500 }`) | `DisplayString`、`read-only`；原文注释 `UNITS "A"`，描述为 power supplies current。 |
| `networkInterface0` (`977-983`; `{ status 506 }`), `networkInterface1` (`985-991`; `{ status 507 }`) | `NetworkInterfaceStatus`、`read-only`；`down(0),up(1)` 在 `46-53`。 |
| `generalErrorCode` (`994-1000`; `{ errormessages 1 }`), `generalErrorMessage` (`1002-1008`; `{ errormessages 2 }`) | `Integer32` / `DisplayString`、`read-only`；error code / describing message。可选 `errorGroup` 在 `1014-1024,1068-1075`。 |

### 3.2 表、Entry、索引和列

| 表（表、Entry、索引的原文行） | 可读叶对象（每项的原文行；列号） | 索引与语法事实 |
|---|---|---|
| `fanTable` `299-305`; `fanTableEntry` `307-314`; `fanIndex` `322-328` | `fanName` `330-336`（2），`fanSpeed` `338-344`（3） | `INDEX { fanIndex }`；`fanIndex Integer32(1..20)`，结构对象 `not-accessible`，叶对象 read-only；转速说明 RPM。 |
| `powerSupplyTable` `350-356`; `powerSupplyTableEntry` `358-365`; `powerSupplyIndex` `375-381` | `powerSupplyStatus` `383-389`（2），`powerSupplyTemperature` `391-397`（3），`powerSupplyVoltage` `399-405`（4），`powerSupplyFanFunction` `407-413`（5） | `INDEX { powerSupplyIndex }`；索引 `Integer32(1..3)`；`PowerSupplyStatus` 枚举见 `35-44`，`FunctionStatus` 见 `97-104`。 |
| `ioCardCatTable` `419-425`; `ioCardCatEntry` `427-434`; `ioCardCatIndex` `445-451` | `ioCardCatId` `453-459`（2），`ioCardCatStatus` `461-467`（3），`ioCardCatFunction` `469-475`（4），`ioCardCatTemperature` `477-483`（5），`ioCardCatMatrixSlot` `485-491`（6） | `INDEX { ioCardCatIndex }`；索引 1..19；`DeviceStatus`=`offline(0)/online(1)` 在 `106-113`，`FunctionStatus` 在 `97-104`。 |
| `ioCardCatPortTable` `494-500`; `ioCardCatPortEntry` `502-509`; `ioCardCatPortIndex` `516-522` | `ioCardCatPortStatus` `524-530`（2） | `INDEX { ioCardCatIndex, ioCardCatPortIndex }`；端口索引 1..16；`CatPortStatus down(0)/up(1)` 在 `55-62`。 |
| `ioCardFiberTable` `536-542`; `ioCardFiberEntry` `544-551`; `ioCardFiberIndex` `562-568` | `ioCardFiberId` `570-576`（2），`ioCardFiberStatus` `578-584`（3），`ioCardFiberFunction` `586-592`（4），`ioCardFiberTemperature` `594-600`（5），`ioCardFiberMatrixSlot` `602-608`（6） | `INDEX { ioCardFiberIndex }`；索引 1..19；状态/功能枚举同 CAT。 |
| `ioCardFiberPortTable` `611-617`; `ioCardFiberPortEntry` `619-626`; `ioCardFiberPortIndex` `636-642` | `ioCardFiberPortStatus` `644-650`（2），`ioCardFiberTxPower` `652-658`（3），`ioCardFiberRxPower` `660-666`（4），`ioCardFiberSfpType` `668-674`（5） | `INDEX { ioCardFiberIndex, ioCardFiberPortIndex }`；端口索引 1..16；`FiberPortStatus noModule(0)/deactivated(1)/down(2)/up(3)` 在 `64-73`。 |
| `ioCardMultiTable` `680-686`; `ioCardMultiEntry` `688-695`; `ioCardMultiIndex` `706-712` | `ioCardMultiId` `714-720`（2），`ioCardMultiStatus` `722-728`（3），`ioCardMultiFunction` `730-736`（4），`ioCardMultiTemperature` `738-744`（5），`ioCardMultiMatrixSlot` `746-752`（6） | `INDEX { ioCardMultiIndex }`；索引 1..19；状态/功能枚举同 CAT。 |
| `ioCardMultiPortTable` `755-761`; `ioCardMultiPortEntry` `763-770`; `ioCardMultiPortIndex` `780-786` | `ioCardMultiPortStatus` `788-794`（2），`ioCardMultiTxPower` `796-802`（3），`ioCardMultiRxPower` `804-810`（4），`ioCardMultiSfpType` `812-818`（5） | `INDEX { ioCardMultiIndex, ioCardMultiPortIndex }`；端口索引 1..16；`MultiPortStatus noModule(0)/deactivated(1)/down(2)/up(3)` 在 `75-84`。 |
| `ioCardTrunkTable` `824-830`; `ioCardTrunkEntry` `832-839`; `ioCardTrunkIndex` `850-856` | `ioCardTrunkId` `858-864`（2），`ioCardTrunkStatus` `866-872`（3），`ioCardTrunkFunction` `874-880`（4），`ioCardTrunkTemperature` `882-888`（5），`ioCardTrunkMatrixSlot` `890-896`（6） | `INDEX { ioCardTrunkIndex }`；索引 1..19；状态/功能枚举同 CAT。 |
| `ioCardTrunkPortTable` `899-905`; `ioCardTrunkPortEntry` `907-914`; `ioCardTrunkPortIndex` `924-930` | `ioCardTrunkPortStatus` `932-938`（2），`ioCardTrunkTxPower` `940-946`（3），`ioCardTrunkRxPower` `948-954`（4），`ioCardTrunkSfpType` `956-962`（5） | `INDEX { ioCardTrunkIndex, ioCardTrunkPortIndex }`；端口索引 1..16；`TrunkPortStatus noModule(0)/deactivated(1)/down(2)/up(3)` 在 `86-95`。 |

上表所有 Table、Entry、Index 明示 `MAX-ACCESS not-accessible`；所有列明示 `read-only`。各 `SEQUENCE` 的列顺序也在相应 Entry 后的行内给出，例如 CAT `436-443`、FIBER `553-560`、MULTI `697-704`、TRUNK `841-848`。

## 4. `GUD-CCDMCPU-MIB` 逐对象证据（36）

模块文本约定：`PowerStatus off(0)/on(1)` `32-39`；`DeviceStatus offline(0)/online(1)/ready(2)` `41-49`；`ConnectionStatus notConnected(0)/connected(1)` `51-58`；`KeyboardMouseStatus none(0)/keyboard(1)/mouse(2)/keyboardMouse(3)` `60-69`；`UsbHidStatus notConnected(0)/connected(1)/initialized(2)` `71-79`；`AccessStatus local(0)/remote(1)/localExclusive(2)/remoteExclusive(3)` `81-90`；`VideoType none(0)/vga(1)/dvisl(2)/dvidl(3)/dmdp(4)/dp(5)/hdmi(6)` `92-104`；`GpioValue inactive(0)/low(1)/high(2)` `106-114`；`NetworkInterfaceStatus down(0)/up(1)` `116-123`。

| 结构/索引证据 | 逐叶对象（原文行；列号） |
|---|---|
| `targetModuleTable` `166-172`; `targetModuleEntry` `174-181`; `targetModuleIndex` `210-216`；索引为 `targetModuleIndex`、范围 1..2000，结构对象不可访问 | `id` `218-224`（2）；`cl` `226-232`（3）；`name` `234-240`（4）；`deviceStatus` `242-248`（5）；`mainPower` `250-256`（6）；`redundantPower` `258-264`（7）；`temperature1` `266-272`（8）；`consolePS2Connection` `274-280`（9）；`consoleUSBConnection` `282-288`（10）；`targetPS2Connection` `290-296`（11）；`targetUsbHid` `298-304`（12）；`targetVideoCable` `306-312`（13）；`targetVideoCable1` `314-320`（14）；`targetVideoCable2` `322-328`（15）；`targetVideoSignal` `330-336`（16）；`targetVideoSignal1` `338-344`（17）；`targetVideoSignal2` `346-352`（18）；`targetPower` `354-360`（19）；`targetAccess` `362-368`（20）；`sfpTxPower` `370-376`（21）；`sfpRxPower` `378-384`（22）；`sfpType` `386-392`（23）；`networkInterface0` `394-400`（24）。 |
| `fanTable` `406-412`; Entry `414-421`; `fanIndex` `429-435`；复合索引 `targetModuleIndex,fanIndex`，fanIndex 1..10，结构对象不可访问 | `fanName` `437-443`（2，`DisplayString`）；`fanSpeed` `445-451`（3，`Integer32(0..10000)`，RPM）。 |
| `gpioTable` `457-463`; `gpioTableEntry` `465-472`; `gpioIndex` `480-486`；复合索引 `targetModuleIndex,gpioIndex`，gpioIndex 1..4，结构对象不可访问 | `gpioName` `488-494`（2，`DisplayString`）；`gpioValue` `496-502`（3，`GpioValue`）。 |

所有上述叶对象块都写有 `MAX-ACCESS read-only`；完整强制对象集可交叉核对 `cc160/GUD-CCDMCPU-MIB.txt:508-529`。

## 5. `GUD-CCDMCON-MIB` 逐对象证据（42）

模块文本约定：`Boolean false(0)/true(1)` `31-38`；`PowerStatus` `40-47`；`NetworkInterfaceStatus` `49-56`；`DeviceStatus` `58-66`；`ConnectionStatus` `68-75`；`KeyboardMouseStatus` `77-86`；`GpioValue` `88-96`。除 `Boolean` 外，枚举与 CPU 同名类型含义一致，但以本模块原文为准。

| 结构/索引证据 | 逐叶对象（原文行；列号） |
|---|---|
| `userModuleTable` `138-144`; `userModuleEntry` `146-153`; `userModuleIndex` `188-194`；索引范围 1..2000，结构不可访问 | `id` `196-202`（2）；`cl` `204-210`（3）；`name` `212-218`（4）；`deviceStatus` `220-226`（5）；`mainPower` `228-234`（6）；`redundantPower` `236-242`（7）；`temperature1` `244-250`（8）；`consolePS2Connection` `252-258`（9）；`consoleUSBConnection` `260-266`（10）；`displayConnection` `268-274`（11）；`displayConnection1` `276-282`（12）；`displayConnection2` `284-290`（13）；`displayType` `292-298`（14）；`displayType1` `300-306`（15）；`displayType2` `308-314`（16）；`freeze` `316-322`（17）；`freeze1` `324-330`（18）；`freeze2` `332-338`（19）；`sfpTxPower` `340-346`（20）；`sfpTxPower1` `348-354`（21）；`sfpTxPower2` `356-362`（22）；`sfpRxPower` `364-370`（23）；`sfpRxPower1` `372-378`（24）；`sfpRxPower2` `380-386`（25）；`sfpType` `388-394`（26）；`sfpType1` `396-402`（27）；`sfpType2` `404-410`（28）；`activeTransmissionPort` `412-418`（29，`Integer32(1..2)`）；`networkInterface0` `420-426`（30）。 |
| `fanTable` `432-438`; Entry `440-447`; `fanIndex` `455-461`；索引 `userModuleIndex,fanIndex`，fanIndex 1..10，结构不可访问 | `fanName` `463-469`（2）；`fanSpeed` `471-477`（3，`Integer32(0..10000)`，RPM）。 |
| `gpioTable` `483-489`; `gpioTableEntry` `491-498`; `gpioIndex` `506-512`；索引 `userModuleIndex,gpioIndex`，gpioIndex 1..4，结构不可访问 | `gpioName` `514-520`（2）；`gpioValue` `522-528`（3，`GpioValue`）。 |

所有叶对象原文均为 `MAX-ACCESS read-only`；强制 status group 可交叉核对 `cc160/GUD-CCDMCON-MIB.txt:534-559`。

## 6. `GUD-CCDMDWC-MIB` 逐对象证据（38）

模块文本约定：`Boolean false(0)/true(1)` `31-38`；`PowerStatus` `40-47`；`NetworkInterfaceStatus` `49-56`；`DeviceStatus` `58-66`；`ConnectionStatus` `68-75`；`KeyboardMouseStatus` `77-86`。

| 结构/索引证据 | 逐叶对象（原文行；列号） |
|---|---|
| `dynamicUserModuleTable` `128-134`; `dynamicUserModuleEntry` `136-143`; `dynamicUserModuleIndex` `159-165`；索引范围 1..2000，结构不可访问 | `id` `167-173`（2）；`cl` `175-181`（3）；`name` `183-189`（4）；`deviceStatus` `191-197`（5）；`mainPower` `199-205`（6）；`redundantPower` `207-213`（7）；`temperature1` `215-221`（8）；`consoleUSBConnection` `223-229`（9）；`networkInterface0` `231-237`（10）；`networkInterface1` `239-245`（11）。 |
| `fanTable` `251-257`; Entry `259-266`; `fanIndex` `274-280`；索引 `dynamicUserModuleIndex,fanIndex`，fanIndex 1..10，结构不可访问 | `fanName` `282-288`（2）；`fanSpeed` `290-296`（3，`Integer32(0..10000)`，RPM）。 |
| `videoChannelTable` `302-308`; `videoChannelEntry` `310-317`; `videoChannelIndex` `325-331`；索引 `dynamicUserModuleIndex,videoChannelIndex`，channel 1..4，结构不可访问 | `displayConnection` `333-339`（2，`ConnectionStatus`）；`displayType` `341-347`（3，`DisplayString`）。 |
| `linkChannelTable` `354-360`; `linkChannelEntry` `362-369`; `linkChannelIndex` `387-393`；索引 `dynamicUserModuleIndex,linkChannelIndex`，channel 1..8，结构不可访问 | `conid` `395-401`（2）；`concl` `403-409`（3）；`conname` `411-417`（4）；`linkChannelStatus` `419-425`（5，`DeviceStatus`）；`activeTransmissionPort` `427-433`（6，`Integer32(1..2)`）；`sfpTxPower1` `435-441`（7）；`sfpTxPower2` `443-449`（8）；`sfpRxPower1` `451-457`（9）；`sfpRxPower2` `459-465`（10）；`sfpType1` `467-473`（11）；`sfpType2` `475-481`（12）；`freeze` `483-489`（13，`Boolean`）。 |

所有叶对象原文均为 `MAX-ACCESS read-only`；强制 status group 可交叉核对 `cc160/GUD-CCDMDWC-MIB.txt:495-518`。

## 7. `GUD-GENERALTRAPS-MIB` 通知证据

| 对象/通知 | 原文、OID 与可验证事实 |
|---|---|
| `level` | `cc160/GUD-GENERALTRAPS-MIB.txt:32-38`；`Integer32`、`read-only`、`{ gudGeneralNotifications 2 }`，只说明为 notification level，未定义枚举。推导 OID `enterprises.32828.2.1.0.2`。 |
| `message` | `cc160/GUD-GENERALTRAPS-MIB.txt:40-46`；`DisplayString`、`read-only`、`{ gudGeneralNotifications 3 }`，说明为 message text。推导 OID `enterprises.32828.2.1.0.3`。 |
| `generalNotification` | `cc160/GUD-GENERALTRAPS-MIB.txt:48-54`；`NOTIFICATION-TYPE`，`OBJECTS { level, message }`，OID 声明 `{ gudGeneralNotifications 4 }`。推导 OID `enterprises.32828.2.1.0.4`。描述仅为 G&D general notification。 |

原文没有任何其他 `NOTIFICATION-TYPE`/`TRAP-TYPE`，也没有恢复通知、严重度枚举、触发条件、通知地址或接收配置对象。合规声明要求该通知和两个通知对象，见 `cc160/GUD-GENERALTRAPS-MIB.txt:64-86`。

## 8. 可复算性结论

1. 标量对象以其 `OBJECT-TYPE` 的 `{ parent child }` OID 加 `.0` 形成实例；MIB 对象本身不把 `.0` 写在定义中。这适用于通用 CCDM 标量和 Trap varbind 对象。
2. 表的实例必须以 MIB `INDEX` 指定的一个或多个索引附在列 OID 后；CPU/CON/DWC 的多张表明确为复合索引，底盘 I/O 端口表亦明确为“卡索引 + 端口索引”。
3. `not-accessible` 仅出现在结构对象和索引，不是可读数据点；所有可读叶对象都已在本台账列出为 `read-only`。
4. 完整数值根不在原文，不应以本台账为依据把 `enterprises` 替换为一个未经同包原文支撑的数字；现场解析器可加载其标准 `SNMPv2-SMI` 依赖后完成解析。
