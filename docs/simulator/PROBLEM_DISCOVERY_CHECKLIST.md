# KVM SNMP 模拟器问题发现清单

> 状态：当前工作区审查基线
> 更新日期：2026-07-31
> 范围：`backend/simulator/`、`backend/app/api/simulator.py`、Dashboard SNMP/Trap 集成、`simulator-ui/`、启动文档与模拟器测试
> 原则：本清单记录已核对事实、可复现问题和验收缺口；不把历史问题直接当成当前事实，也不把静态 MIB 检查当成实机验证。

## 1. 用途

本清单用于回答三个问题：

1. 当前模拟器已经具备什么；
2. 哪些问题会阻断下一层开发；
3. 每个问题必须用什么证据关闭，而不是仅凭“测试通过”或“页面能打开”关闭。

问题关闭后保留原记录，将状态改为 `已关闭`，并附修复提交、验证命令和验收证据。不要删除历史问题。

## 2. 证据等级

| 等级 | 含义 | 可用于什么结论 |
|---|---|---|
| E0 | 需求、设计设想或假设 | 只能用于规划，不能证明实现正确 |
| E1 | 静态代码或文档对照 | 可证明实现结构或明显冲突 |
| E2 | 单元测试、模型验证、纯函数探针 | 可证明局部契约 |
| E3 | 真实 HTTP/WS/UDP/SNMP 进程内或进程间测试 | 可证明协议链路 |
| E4 | Dashboard + Simulator + UI 的端到端测试 | 可证明本地联调 |
| E5 | 厂家设备 GET/WALK/Trap 样本 | 才能证明与目标设备/固件的兼容性 |

## 3. 当前已有能力

以下能力当前已经存在，但“存在”不等于“达到验收条件”：

- FastAPI 模拟器服务、拓扑/运行时/Trap API 和 WebSocket 端点；
- CCDC、CCDM、VisionXS CPU、VisionXS CON、DP12 MUX 五种 Profile 声明；
- 每设备独立 UDP SNMP Agent；
- `ScenarioState`、revision、事件记录、暂停/断开/下电/恢复动作；
- Dashboard bridge session、manifest reconciliation 和模拟设备注册；
- JSON TopologyStore 和五个内置拓扑 preset；
- React Flow Simulator UI、详情抽屉、Trap 面板、事件时间线；
- 模拟器后端测试和前端 build/lint；
- MIB 差异台账和 CCDM、VisionXS、DP 的设备字典快照。

本次验证确认：

- 使用正确的 PowerShell 环境变量时，Dashboard `/health` 正常；
- `all-profiles` 能启动五个本地 Agent；
- Simulator bridge 能向 Dashboard 注册五个绑定；
- 24 项当前模拟器测试通过；
- Simulator UI build 和 lint 通过；
- 基本 UDP GET、WALK 和正式 Trap 可以传输。

## 4. 严重程度

| 严重度 | 定义 |
|---|---|
| P0 | 直接导致启动、协议、数据正确性或核心控制功能不可用；必须先修 |
| P1 | 会造成状态丢失、残留、错归属、拓扑失真或明显性能问题；进入 UI 正式开发前必须修 |
| P2 | 可维护性、安全边界、可观测性或非主路径缺口；发布前必须处理 |
| P3 | 文案、体验或低风险一致性问题 |

## 5. 问题登记表

### 5.1 启动与环境

#### SIM-ENV-001：PowerShell 执行 CMD `set` 不会设置环境变量

- 严重度：P0
- 所属层：L0 基线与运行环境
- 状态：已修复（Windows 本地支持矩阵）
- 证据：E2
- 位置：`docs/simulator_startup_connection_guide.md`、`backend/kvm_simulator_README.md`
- 发现：
  - 文档命令使用 `set DB_MODE=sqlite` 等 CMD 语法；
  - 在 PowerShell 中该命令不会写入 `$env:DB_MODE`；
  - 当前用户环境和项目主要操作环境是 PowerShell。
- 影响：
  - Dashboard bridge 实际仍关闭；
  - Simulator 回退到默认 `8888`、`ccdc-regression` 和 Dashboard `8000`；
  - Trap 端口、前端代理和 token 全部可能错位。
- 关闭条件：
  - CMD、PowerShell、Docker 三套命令分开；
  - 启动前打印最终生效配置，但 token 只显示“已配置/未配置”；
  - 自动 smoke test 验证端口、健康状态、活动拓扑和 bridge 状态。

#### SIM-ENV-002：启动成功但 bridge 失败时缺少显式反馈

- 严重度：P1
- 所属层：L6 Bridge 与 Dashboard 集成
- 状态：底层已修复，UI 顶部呈现待 L8
- 证据：E1
- 位置：`backend/simulator/main.py::_start_definition`
- 发现：初始 `bridge.reconcile(runtime)` 返回值被丢弃。
- 影响：Simulator 页面可打开，但 Dashboard 没有设备；操作员只能猜 token、URL 或 bridge 开关。
- 关闭条件：
  - `/api/v1/status` 返回 runtime、Agent、bridge、Dashboard 和 Trap receiver 的分项状态；
  - UI 顶部显示 bridge 正常、禁用或失败原因；
  - 初始 reconcile 失败必须有结构化日志和可重试操作。

### 5.2 MIB、Profile 与 OID

#### SIM-MIB-001：CCDM 机框包含当前 MIB 快照不支持的公共标量

- 严重度：P0
- 所属层：L1 MIB golden、L2 Profile 模型
- 状态：L1 事实已固化；L2 schema 根因已关闭，L4 真实协议验证待完成
- 证据：E1
- 位置：`backend/simulator/profiles.py:COMMON_SCALARS`、`ProfileId.CCDM_MATRIX`
- 发现：CCDM 复用了 `.2.3.1/.2/.3` 的 `main_power/redundant_power/temperature1`；当前 CCDM 厂家字典从 `.2.3.4/.5` 定义 switch/controller 温度，电源状态位于 powerSupplyTable。
- 影响：模拟器返回不存在或无厂家依据的 CCDM OID，导致错误兼容结论。
- 关闭条件：
  - CCDM Profile 逐项匹配独立 golden manifest；
  - 不再用跨产品 `COMMON_SCALARS` 推导事实；
  - 未验证字段必须明确标记为 fixture-only 或删除。

#### SIM-MIB-002：CCDM CPU 默认值违反厂家枚举

- 严重度：P0
- 所属层：L1、L2
- 状态：L2 fixture 已改为显式静态值且全量校验通过；L3 PATCH 共用验证器待完成
- 证据：E1
- 位置：`backend/simulator/profiles.py:CCDM_CPU_MODULE_COLUMNS`
- 发现：
  - `targetUsbHid=3`，厂家范围为 `0..2`；
  - `targetVideoCable* = 5`，厂家 ConnectionStatus 只能为 `0/1`。
- 影响：即使 OID 正确，返回值仍不是合法 MIB 值。
- 关闭条件：
  - 每个 enum/range 字段有独立 golden 断言；
  - 默认 fixture 通过全字段值域校验；
  - REST PATCH 和 SNMP 渲染共用同一验证器。

#### SIM-MIB-003：CCDM 仍缺少 5 张表和 CON 列 30

- 严重度：P0
- 所属层：L1、L2
- 状态：L2 已达到 20 表/142 可读叶、缺 0/多 0；L4 真实 UDP WALK 待完成
- 证据：E1
- 位置：`backend/simulator/profiles.py`
- 缺失：
  - CPU fanTable；
  - CPU gpioTable；
  - CON fanTable；
  - CON gpioTable；
  - DWC fanTable；
  - CON `networkInterface0` 列 30。
- 影响：“全参数”声明不成立。
- 关闭条件：
  - 20 张 CCDM 表全部进入独立 manifest；
  - 每张表记录 table/entry/index/可读列/复合索引/MAX-ACCESS；
  - 真实 UDP WALK 与 golden 的对象定义和 fixture 实例一致。

#### SIM-MIB-004：把索引最大范围当作实际存在的设备行

- 严重度：P1
- 所属层：L2 Profile、L3 状态实例
- 状态：L2 已分离定义/范围/显式 fixture 行并删除最大范围展开；L3/L4 实例与缺失对象行为待完成
- 证据：E1、E3
- 发现：CCDM 默认创建 19 张卡及每卡 16 个端口等最大范围实例。
- 影响：
  - 伪造并不存在的硬件库存；
  - 单个 CCDM fixture 渲染约 4480 个 OID；
  - 当前机器完整 WALK 约 4.99 秒。
- 关闭条件：
  - 明确区分“对象定义”“索引允许范围”“该 fixture 实际存在行”；
  - fixture 行必须由拓扑/设备配置显式创建；
  - optional group 和缺失行返回正确的 noSuchObject/EndOfMibView 行为。

#### SIM-MIB-005：Profile 测试从被测声明生成 expected

- 严重度：P0
- 所属层：L1、L12 验收
- 状态：L1 已关闭；独立 JSON Golden、生成校验和静态测试已建立
- 证据：E1
- 位置：`backend/tests/test_simulator_profiles.py`
- 发现：expected OID 来自 `PROFILE_DEFINITIONS`，无法发现定义自身错误、缺表或重复 OID。
- 影响：测试全绿仍不能证明 MIB 正确。
- 关闭条件：
  - golden manifest 与运行时代码分离；
  - 测试禁止从 Profile renderer 反向生成预期；
  - 每个 Profile 有固定锚点 OID、类型、权限、枚举和索引断言。

### 5.3 运行时状态与 PATCH

#### SIM-STATE-001：RuntimeFieldPatch.value 为 Any

- 严重度：P0
- 所属层：L3 状态模型
- 状态：未修复
- 证据：E2、E3
- 位置：`backend/simulator/models.py`、`backend/simulator/state.py`
- 发现：没有按 Profile 验证类型、枚举、范围、只读字段和结构字段。
- 已复现：把整数型 `main_power` 写成字符串后 API 成功，但 SNMP GET 超时。
- 关闭条件：
  - patch 先完整 validate，再一次性 commit；
  - 失败时 state、revision、events、OID snapshot 均不变；
  - 禁止修改 ID、row、index、profile、host 等结构字段。

#### SIM-STATE-002：ports/endpoints 路径可写入不影响 OID 的任意字段

- 严重度：P0
- 所属层：L3
- 状态：未修复
- 证据：E3
- 已复现：`ports[1].sfpRxPower` 返回 200，但渲染 OID 完全不变。
- 影响：产生“页面显示修改成功、SNMP 没变化”的假成功。
- 关闭条件：
  - 所有可写路径由实例化 Profile metadata 生成；
  - 不在路径索引中的字段必须 422；
  - 成功响应必须包含受影响的规范路径、revision 和新值。

#### SIM-STATE-003：状态字段与 Profile 命名不一致

- 严重度：P1
- 所属层：L2、L3
- 状态：L2 三层命名和双向 alias 已建立；L3 状态键/API 路径迁移待完成
- 示例：`temperature`/`temperature1`、`main_power`/`mainPower`、`powerCurrent` 等命名混杂。
- 影响：UI fallback、设备动作和 Profile 渲染容易写入不同字段。
- 关闭条件：
  - 定义规范字段名和厂家对象名的双向映射；
  - 内部字段名统一；
  - API 只暴露规范路径，MIB 名作为 metadata。

### 5.4 SNMP Agent 与 Trap 编码

#### SIM-SNMP-001：Agent 吞掉渲染和编码异常

- 严重度：P0
- 所属层：L4 协议引擎
- 状态：未修复
- 证据：E3
- 位置：`backend/simulator/snmp_agent.py::_run`
- 影响：非法状态表现为静默超时，无法判断是网络问题、类型错误还是代码异常。
- 关闭条件：
  - 编码错误进入结构化日志和 simulator event；
  - Agent health 暴露最后错误；
  - 已验证状态不应在请求路径发生类型转换异常。

#### SIM-SNMP-002：每个请求重新生成并排序完整 OID 树

- 严重度：P1
- 所属层：L4
- 状态：未修复
- 证据：E1、E3
- 影响：CCDM 4480 OID 在每个 GET/GETBULK 上重复构建和排序，增加健康探测超时风险。
- 关闭条件：
  - OID snapshot 按 revision 缓存；
  - patch 后只重建受影响设备；
  - 给 5 Profile 建立 GET、WALK、并发请求性能预算。

#### SIM-TRAP-001：port 模式下多设备 Trap 无法按源 IP 唯一归属

- 严重度：P0
- 所属层：L4、L6
- 状态：未修复
- 证据：E1
- 位置：`backend/app/snmp/trap_receiver.py`
- 发现：五台设备均为 `127.0.0.1`，接收器按 host 查询并使用 `scalar_one_or_none()`。
- 影响：通用消息可能产生多结果异常或错误归属。
- 关闭条件：
  - 形成 Trap 身份 ADR；
  - loopback 和 port 模式分别定义来源识别策略及能力限制；
  - 多设备同 host 的正式/legacy Trap 都有端到端测试。

#### SIM-TRAP-002：把厂家未枚举 level 映射成固定严重度

- 严重度：P1
- 所属层：L1、L6、L9
- 状态：L1 已固定 raw level/无枚举事实；L6/L9 实现未修
- 证据：E1
- 发现：UI 和 Dashboard 把 2/3/5 映射为 critical/warning/info；厂家 MIB 只定义未枚举 Integer32。
- 关闭条件：
  - 保存并展示 raw level；
  - 若保留严重度映射，标记为 `platform-policy` 并单独配置；
  - 不再在代码注释中声称该映射来自厂家 MIB。

#### SIM-TRAP-003：legacy 通知 OID 与项目历史证据不一致

- 严重度：P1
- 所属层：L1、L4
- 状态：L1 legacy fixture 已固定；L4 编码和 L6 接收实现未修
- 发现：实现使用 `.32828.5.1.0.4`，历史记录为通知 `.32828.5.0.4`、变量 `.32828.5.1.0.{2,3}`。
- 关闭条件：
  - legacy fixture 来自独立捕获样本；
  - formal 与 legacy 的 notification OID 和 varbind 分开断言；
  - Dashboard 接收器同时验证 `snmpTrapOID.0` 和变量组合。

### 5.5 生命周期、持久化与 Bridge

#### SIM-LIFE-001：拓扑切换不是 prepare/commit/rollback

- 严重度：P0
- 所属层：L5 生命周期
- 状态：未修复
- 证据：E3
- 已复现：旧拓扑运行时，注入第二个新 Agent 启动失败，最终 `state=None`、`agents=[]`。
- 关闭条件：
  - 新 runtime 和 Agent 全部 ready 后才切换活动指针；
  - 失败时旧 runtime、Agent、bridge manifest 完全不变；
  - 端口重叠切换需要明确的 staged handover 方案。

#### SIM-LIFE-002：Simulator stop 后 Dashboard 保留活跃设备

- 严重度：P0
- 所属层：L5、L6
- 状态：未修复
- 证据：E4
- 已复现：Simulator 关闭后 Dashboard 仍保留 5 个 active 模拟设备和 1 个 run。
- 关闭条件：
  - 正常 stop、进程退出和崩溃超时三种清理语义明确；
  - bridge token 有受限的 session cleanup/lease API；
  - 不依赖管理员 JWT 才能清理本 session 资源。

#### SIM-STORE-001：Topology JSON 非原子写入且损坏文件静默跳过

- 严重度：P1
- 所属层：L5、L10
- 状态：未修复
- 位置：`backend/simulator/topology_store.py`
- 关闭条件：
  - 临时文件写入、flush、原子 replace；
  - 损坏文件进入显式错误列表；
  - 并发 CRUD 有锁和版本冲突处理。

#### SIM-STORE-002：可以删除当前运行的用户拓扑

- 严重度：P1
- 所属层：L5、L10
- 状态：未修复
- 关闭条件：
  - 删除 active topology 返回 409；
  - stop 后才允许删除；
  - active topology 状态由后端单一事实源提供。

### 5.6 Dashboard 集成

#### SIM-DASH-001：定时轮询仍把全局 CCDC OID 计划套到所有 Profile

- 严重度：P0
- 所属层：L6
- 状态：未修复
- 证据：E1
- 位置：`backend/app/snmp/poller.py::run_poll_cycle`
- 发现：所有 active 模拟设备都会进入全局 OIDRegistry 轮询。
- 影响：
  - README 所称“非 CCDC 仅注册展示”不准确；
  - CCDM、VisionXS、DP 可能收到不适用 OID；
  - 超时、空数据或字段碰撞被误认为设备异常。
- 关闭条件：
  - manifest 明确 `profile_id` 和 `poll_mode`；
  - 在 Dashboard Profile poll plan 完成前，非 CCDC 只做已批准的 identity/health 探测；
  - 不允许 unknown Profile 回退到 CCDC。

### 5.7 API 与 WebSocket

#### SIM-API-001：缺少统一运行状态与错误模型

- 严重度：P1
- 所属层：L7 API/WS
- 状态：未修复
- 发现：UI 需要分别猜测 active topology、running、Agent、bridge 和 Trap 状态。
- 关闭条件：
  - 定义 `/api/v1/status`；
  - 错误分类至少包含 validation、conflict、bind、bridge、protocol、persistence；
  - 500 不用于可预期的端口/状态冲突。

#### SIM-WS-001：并非所有改变都发送 snapshot 或要求 revision refetch

- 严重度：P1
- 所属层：L7
- 状态：部分修复
- 发现：runtime patch 已带 snapshot，但 topology started/stopped、reset、legacy reachability 等事件仍可能只发摘要。
- 关闭条件：
  - 统一选择“完整 snapshot”或“revision + 强制 refetch”；
  - 双浏览器测试覆盖 start、stop、reset、patch、action、Trap 和 topology CRUD。

### 5.8 Simulator UI 参数页面

#### SIM-UI-001：详情抽屉错误解包 Profile metadata

- 严重度：P0
- 所属层：L8、L9
- 状态：未修复
- 证据：E2、E3
- 位置：`simulator-ui/src/components/DetailsDrawer.jsx`、`profileFields.js`
- 发现：`metadataToGroups(profileMeta)` 的参数形状不符合函数契约，始终返回 fallback。
- 关闭条件：
  - 组件测试使用真实 `/profiles` payload；
  - 每个 Profile 至少验证一个 scalar、一个单索引表和一个复合索引表字段；
  - 不允许 fallback 字段提交未声明路径。

#### SIM-UI-002：初始 running/activeTopologyId 与后端不一致

- 严重度：P0
- 所属层：L8
- 状态：未修复
- 证据：E3
- 已复现：
  - 后端运行 `all-profiles`；
  - UI 默认 fallback 是 `ccdc-regression`；
  - 首次 Stop 返回 409；
  - 首次 Start 可能把运行拓扑切成第一个 preset。
- 关闭条件：
  - 初始状态完全来自 `/status`；
  - Start/Stop 操作使用 server-reported active topology；
  - 刷新和第二浏览器保持一致。

#### SIM-UI-003：Profile metadata 体积与渲染模型不可用

- 严重度：P1
- 所属层：L2、L9
- 状态：L2 schema metadata 已关闭实例展开根因；L9 当前 fixture 实例列表、搜索/分页仍未实现
- 证据：E2
- 已测：当前 metadata 约 1.05 MB，CCDM 有 4428 个字段。
- 关闭条件：
  - metadata 只返回当前 fixture 实际实例；
  - 分组、分页、搜索或虚拟列表；
  - 大型 Profile 首屏和交互性能有预算。

### 5.9 拓扑领域模型与画布

#### SIM-TOPO-001：Palette 没有矩阵下挂 CPU/CON 模块建模

- 严重度：P1
- 所属层：L10、L11
- 状态：未修复
- 发现：Palette 只有整机 Profile；CPU/CON 模块没有父矩阵、槽位和端口归属操作。
- 关闭条件：
  - 先完成拓扑领域模型，再提供模块/端口操作；
  - 独立 VisionXS CPU/CON 与矩阵下挂 CPU/CON 必须是不同实体类型。

#### SIM-TOPO-002：保存时过滤 endpoint-to-endpoint 路由

- 严重度：P1
- 所属层：L10、L11
- 状态：未修复
- 位置：`simulator-ui/src/App.jsx::buildTopologyPayload`
- 影响：CPU→CON simulation-declared 路由在保存时可能丢失。
- 关闭条件：
  - route edge 有明确 schema；
  - 保存、重载、启动、WS 和画布渲染往返无损。

#### SIM-TOPO-003：后端只校验引用存在，不校验端口语义

- 严重度：P1
- 所属层：L10
- 状态：未修复
- 缺失：
  - 全局节点 ID 唯一；
  - 端口存在和方向；
  - endpoint/profile/edge kind 兼容性；
  - 重复占用；
  - 自环和非法跨设备连接；
  - 物理连线与 simulation-declared route 的区分。
- 关闭条件：
  - 拓扑语义契约和 validator 先于 React Flow 交互完成；
  - 所有非法连线有后端和前端共同 fixture。

### 5.10 安全与可观测性

#### SIM-SEC-001：任意 topology host 可进入 Dashboard 轮询

- 严重度：P1
- 所属层：L6、L7
- 状态：未修复
- 影响：Simulator API 一旦监听非 loopback，可能被用于内网探测。
- 关闭条件：
  - 默认只允许 loopback；
  - 非 loopback 使用 allowlist；
  - REST/WS 有认证和 Origin 策略；
  - host、token、community 不进入日志和前端 payload。

#### SIM-OBS-001：缺少每设备 Agent 和协议错误状态

- 严重度：P2
- 所属层：L4、L5、L7
- 状态：未修复
- 关闭条件：
  - 每设备显示 bound/ready/paused/powered_off/error；
  - 记录最近请求、编码错误、Trap 发送错误和 bridge 错误；
  - 不记录 community/token。

### 5.11 测试与发布

#### SIM-TEST-001：当前测试缺少独立真实链路

- 严重度：P0
- 所属层：L12
- 状态：未修复
- 当前缺失：
  - 独立 MIB golden；
  - 所有 Profile 的真实 UDP GET/GETNEXT/GETBULK/WALK/SET；
  - 多 repeater、EndOfMibView、非法 bulk 参数；
  - 双 WebSocket 客户端；
  - 真实浏览器参数编辑；
  - Agent 启动失败、切换失败、restore 失败；
  - stop/崩溃后的 Dashboard cleanup；
  - port/loopback 两种 Trap 归属；
  - JSON 并发/损坏/恢复；
  - Windows CMD、PowerShell 和 Docker smoke test。
- 关闭条件：详见 `LAYERED_DEVELOPMENT_PLAN.md` 的逐层 Gate 和最终发布 Gate。

## 6. 已改善问题

以下旧问题在当前工作区已有改善，后续测试应防止回归：

- UI runtime PATCH 已转换成 `[{path, value}]`；
- Trap UI 已发送整数 level；
- preset 使用 Save As，不再直接覆盖只读 preset；
- Agent start 会等待 ready/error；
- 本地 stop 会清空 `state` 和 Agent；
- power off 会停止对应 Agent，restore 会重启；
- runtime `_after_change` 已广播 snapshot；
- topology-to-scenario 已保留顶层 edges；
- 多 patch 使用 working copy，后续路径失败不会提交前面修改；
- 基本 formal/legacy Trap UDP 捕获和基本 GETBULK 已有测试。

这些改善不等于对应层已经验收，例如 Agent ready 不代表拓扑切换具备事务回滚，snapshot 也尚未覆盖所有 WS 事件。

## 7. 当前验收判断

| 层 | 当前判断 | 是否允许正式开发上一层 |
|---|---|---:|
| L0 环境与基线 | 已通过（Windows local port mode） | 是，允许 L1 |
| L1 MIB golden | 已通过（local curated device dictionary snapshot） | 是，允许准备 L2 |
| L2 Profile 模型 | 已通过；实现与证据基线为 `f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | 是，允许 L3 |
| L3 状态模型 | 部分原子、缺强校验 | 否 |
| L4 SNMP/Trap | 基本可通信、协议错误仍在 | 否 |
| L5 生命周期/存储 | 非事务、清理不完整 | 否 |
| L6 Dashboard 集成 | bridge 可注册、Profile/Trap 边界错误 | 否 |
| L7 API/WS | API 原型存在、状态契约不完整 | 否 |
| L8 UI 只读运行视图 | 原型存在、状态错位 | 否 |
| L9 参数编辑 | 不可用 | 否 |
| L10 拓扑领域模型 | 只有引用模型 | 否 |
| L11 拓扑画布交互 | 原型存在、不能验收 | 否 |
| L12 端到端发布 | 未达到 | 否 |

L2 Profile 的代码、静态 catalog/fixture、全语义 drift、99 项后端回归和
独立复审已经通过；实际工件由
`f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` 固定。L2 已 Accepted，L3
可以正式开发。
