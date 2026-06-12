# Handoff v4

本文件是本轮开发的完整交接手册，供下一位开发者快速上手。
阅读原则：**先看"已确认事实"和"已知边界"，再看代码。不要从模拟器日志推测真实设备行为。**

---

## 一、项目背景速览

G&D KVM 监控大屏系统，为上海机场 G&D ControlCenter-Compact 系列交换机设计。

- 后端：FastAPI + SQLAlchemy 2.0，双模式（SQLite 开发 / PostgreSQL+TimescaleDB 生产）
- SNMP：pysnmp 纯 asyncio，双通道（主动轮询 Pull + 被动 Trap 接收 Push）
- 前端：React 18 + Vite + Zustand

---

## 二、最重要的已确认事实（不可推翻）

### 2.1 真实设备的 SNMP 能力边界

基于真实机器日志 `logs/poll_raw.log`（IP: `172.31.224.1`，2026-04-15）验证：

| 数据表 | 是否支持 | 说明 |
|--------|---------|------|
| CPU 模块表 `.1.2.2.3.1000.1` | ✅ | 每台交换机下挂的 CPU 终端 |
| CON 模块表 `.1.1.2.3.1000.1` | ✅ | 每台交换机下挂的 CON 终端 |
| portTable `.2.3.1000.1` | ❓ **待确认** | MIB 有明确定义，真实日志里没有数据，原因不明 |

**portTable 的准确说明**：
- MIB（`GUD-CCDC-MIB.txt`）明确定义了 portTable，portIndex 范围 1..80
- `oid_map.py` 里的定义（OID 路径、列号、枚举）与 MIB **完全一致**，代码本身没有错
- 真实设备日志（`logs/poll_raw.log`）里没有 portTable 数据，**原因不确定**：
  - 可能是数据库 `oid_registry` 里该字段 `poll_enabled = false`（最可能）
  - 可能是设备固件版本不支持
  - 可能是当时网络/配置问题
- **不能断言"真实设备不支持 portTable"**，等有条件时直接 `snmpwalk` 真实设备验证

**portTable 能告诉你什么（物理层）**：
- 几号端口有没有插光纤（portStatus: noModule/up/down）
- 光模块状态（portSfpModule）
- 光功率是否正常（portSfpTxPower / portSfpRxPower，单位 uW）
- 光模块类型（portSfpType，如 LC-SMF）

**portTable 不能告诉你什么**：
- 几号端口连的是哪个 CPU 或 CON（业务路由层，只有厂商 XML API 的 `ownerPort` 能给）

### 2.2 关键字段语义

**CPU 表 Column 1（`ep_port` = `targetModuleIndex`）**：
- 这是模块在交换机内部表里的索引，**不等于**交换机物理端口号
- MIB 未证明它等于 portTable 的 portIndex

**CON 表 Column 29（`con_active_tx_port`）**：
- 值只有 1 或 2
- 含义：CON 设备自身有两个 SFP 接口，这个字段表示当前使用哪个接口传输
- **不是**交换机侧的物理端口号

**结论：通过 MIB/SNMP 无法得知"几号端口插着哪个 CPU/CON"。** 如需此功能，只能：
  1. 人工配置映射表
  2. 使用厂商专有 XML API（`ownerPort` 字段，见下文 2.4）

### 2.3 Trap OID（已修正，三处对齐）

之前代码用的是错误的 `.5.x.x` 路径，本轮已修正。

正确 OID（来自 `GUD-SMI-MIB` + `GUD-GENERALTRAPS-MIB` 推导）：

```
gudEnterprise       = 1.3.6.1.4.1.32828
gudTrap             = gudEnterprise.2       → .32828.2
gudGeneralTrap      = gudTrap.1             → .32828.2.1
gudGeneralNotifications = gudGeneralTrap.0  → .32828.2.1.0

Trap Notification OID  = .32828.2.1.0.4
level varbind OID      = .32828.2.1.0.2
message varbind OID    = .32828.2.1.0.3
```

涉及文件（三处保持一致）：
- `backend/app/snmp/trap_receiver.py`：`_LEVEL_OID_MARKER = '32828.2.1.0.2'`
- `backend/run_simulators_large.py`：`_TRAP_LEVEL_OID = "1.3.6.1.4.1.32828.2.1.0.2"`
- `backend/kvm_simulator.py`：`_TRAP_LEVEL_OID = "1.3.6.1.4.1.32828.2.1.0.2"`

### 2.4 Trap 日志不是真实设备产生的

`logs/trap_raw.log` 的来源是**模拟器**，不是真实设备：
- 真实设备 SNMP IP：`172.31.224.1`
- Trap 日志 source IP：`172.19.0.1`（Docker 内网网关）
- 真实设备只有 1 台交换机的模块（`CPU-1-xxx`，`CON-1-xxx`），而 Trap 日志有 3 台

**真实设备是否支持 Trap、Trap 消息的实际文本格式，目前没有真实样本可验证。**

Trap 消息里的模块名格式（`CPU module CPU-1-001 went offline`）是模拟器 `run_simulators_large.py` 生成的，不是 MIB 约束的固定格式。

### 2.5 厂商 XML API（有端口映射能力，尚未集成）

厂商软件抓包发现存在专有 XML API，包含 `ownerPort` 字段，能表达"该 CON 连接到交换机哪个端口"：

```xml
<DviConsole>
  <item>
    <id>0x0003D66F</id>
    <name>CON 0003D66F</name>
    <ownerId>0x00001243</ownerId>
    <ownerPort>7</ownerPort>    ← 连接到交换机 7 号端口
    <ownerName>CCC 00001243</ownerName>
  </item>
</DviConsole>
```

目前**未集成**该 API。如需实现端口映射功能，这是正确方向。

---

## 三、本轮完成的改动清单

### 3.1 后端

#### `backend/app/snmp/trap_receiver.py` — 重写 `_save_trap()`
- **修复 Trap OID**：`32828.5.x` → `32828.2.1.0.x`
- **修复设备查找逻辑**：原来用 `source_ip` 匹配 `Device.host`，在 Docker 环境下因网关 IP 不匹配而永远找不到设备
- **新逻辑**：从 Trap 消息解析 `ep_id`/`con_id`，通过 `Endpoint.last_status[id_field]` JSON 查询定位端点，再反查所属设备
- **别名支持**：设备和端点均查 `device_aliases` 表，有别名用别名
- **消息格式统一**：增强后格式 `{device_name}/{endpoint_name} {action}`，与轮询器告警格式对齐
- **降级路径**：找不到端点时 fallback 到 `device_name: 原始消息`，找不到设备时保留原始消息，不报错

#### `backend/app/api/devices.py` — 删设备时级联删端点
```python
await db.execute(sql_delete(Endpoint).where(Endpoint.device_id == device_id))
await db.delete(device)
```

#### `backend/app/api/endpoints.py` — 新增删除接口
```
DELETE /endpoints/{endpoint_id}  （需要 admin 权限）
```

#### `backend/app/main.py` — `_migrate_columns()` 补齐
新增：
```python
("alerts", "endpoint_id", "ALTER TABLE alerts ADD COLUMN endpoint_id VARCHAR(128)"),
```
PostgreSQL 旧库启动时会自动补列，保证 SQLite 和 PostgreSQL 结构一致。

#### `backend/run_simulators_large.py` — 修正两处
1. **Trap OID 修正**：`.5.x` → `.2.1.0.x`
2. **移除 portTable 幻觉**（已撤销）：本轮曾注释掉 `build_oid_map()` 中的 portTable 生成代码，理由是"真实设备不支持"。经 MIB 核查，该理由不成立——MIB 有明确定义，只是真实日志里暂无数据，原因待查。**已恢复**，两个模拟器均正常生成 portTable 数据。

### 3.2 前端

#### `frontend/src/components/EndpointDetail.jsx` — CON 键鼠显示简化
- 移除重复的 PS/2 状态行、USB 状态行
- 只保留一行**综合键鼠状态**（`getConKeyboardMouseState()` 计算结果）
- 判断逻辑不变，仍然同时考虑 PS/2 和 USB，但不单独显示

#### `frontend/src/pages/Dashboard.jsx` — KPI/健康率修复
三处 Bug 修复：
1. `stats?.online_endpoints` → 该字段后端从不返回，改为 fallback `0`
2. `stats.active_alerts || ...` → 改为 `??`，防止告警数为 0 时被缓存数据覆盖
3. fallback 路径的 `epOffline = epTotal - epActive` 逻辑不一致 → 统一改为 `0`

#### `frontend/src/components/admin/EndpointsTab.jsx` — 新增终端管理 Tab
功能：
- 列出所有 CPU/CON 端点，显示名称、所属交换机、类型、状态、更新时间
- 过滤器：按交换机 / 按类型（CPU/CON）/ 按状态
- 单个删除、勾选批量删除、一键清除当前过滤范围内所有离线终端

#### `frontend/src/pages/Admin.jsx` — 加入终端管理 tab
TABS 数组新增 `'endpoints'`，放在"设备管理"之后。

#### 翻译文件
- `zh-CN.json`：新增 `detail_keyboard_mouse`、`admin.tabs.endpoints`
- `en-US.json`：同步新增对应英文

### 3.3 新文件

#### `backend/kvm_simulator.py` — 可配置 KVM 模拟器
单文件，内嵌 Web UI，替代 `run_simulators_large.py` 用于功能验证。

功能：
- 动态增删交换机（每台独立 UDP SNMP Agent）
- 插拔 CPU/CON，实时修改所有字段
- 系统状态修改（温度、电源、风扇）
- 手动发 Trap（含快捷预设按钮）

启动：
```bash
cd backend
.venv/bin/python kvm_simulator.py
# Web 控制台: http://localhost:8888
# 第1台交换机 SNMP: UDP 11161
```

使用说明见 `backend/kvm_simulator_README.md`。

---

## 四、健康率与 KPI 的语义说明

**理解这个很重要，避免后续误判数据问题。**

顶部 4 个 KPI 统计的都是**终端（CPU/CON）维度**，不是交换机维度：

| KPI | 计算来源 | 分母说明 |
|-----|---------|---------|
| 总终端 | `endpoints` 表总行数 | 历史上曾轮询到的所有 CPU/CON 记录 |
| 活跃 | `last_status.ep/con_device_status = online 或 ready` | — |
| 离线 | `last_status = offline` | — |
| 告警 | `alerts.is_resolved = false` | — |

**分母的问题**：SNMP MIB 只上报"已插入的模块"，不上报"空槽位"，系统不知道交换机理论上有几个口。分母 = 数据库里存过的记录数。

**管理员的正确工作流**：
- 设备临时离线维护 → 管理后台禁用（`is_active = false`），不影响记录
- 设备彻底退役 → 管理后台删除该设备，**级联删除其下所有端点**，分母随之减少
- 某个 CPU/CON 被物理拔掉 → 管理后台 **终端管理** Tab → 过滤出离线 → 删除

---

## 五、OID 字段对照表（关键字段速查）

### CPU 端点表：`{sys_oid}.1.2.2.3.1000.1.{col}.{row}`

| Column | 字段名 | 说明 |
|--------|--------|------|
| 1 | `ep_port` | targetModuleIndex（模块索引，≠物理端口号）|
| 2 | `ep_id` | 设备 ID，**Trap 消息里用的就是这个** |
| 4 | `ep_name` | 显示名称，**前端和别名系统用的是这个** |
| 5 | `ep_device_status` | 0=offline 1=online 2=ready |
| 12 | `ep_target_usb_hid` | 0=notConnected 1=connected 2=initialized |
| 13 | `ep_target_video_cable` | 0=notConnected 1=connected |
| 16 | `ep_target_video_signal` | 0=none 1=vga 2=dvisl 3=dvidl 4=dmdp 5=dp 6=hdmi |
| 19 | `ep_target_power` | 0=off 1=on |

### CON 端点表：`{sys_oid}.1.1.2.3.1000.1.{col}.{row}`

| Column | 字段名 | 说明 |
|--------|--------|------|
| 1 | `con_port` | userModuleIndex（模块索引，≠物理端口号）|
| 2 | `con_id` | 设备 ID，**Trap 消息里用的就是这个** |
| 4 | `con_name` | 显示名称，**前端和别名系统用的是这个** |
| 5 | `con_device_status` | 0=offline 1=online 2=ready |
| 9 | `con_console_ps2` | 0=none 1=keyboard 2=mouse 3=keyboardMouse |
| 10 | `con_console_usb` | 同上 |
| 11 | `con_display_conn` | 0=notConnected 1=connected |
| 29 | `con_active_tx_port` | 1 或 2（CON 自身 SFP 接口，不是交换机端口）|

---

## 六、别名系统工作方式

数据库表 `device_aliases`，主键 `target_id`（可以是设备 ID 或端点 ID）。

**后端查询方式**：
```python
select(DeviceAlias).where(DeviceAlias.target_id == device.id)
```

**前端查询方式**（全局 store）：
```js
const { aliases } = get();           // { target_id -> alias_name }
return aliases[id] || fallbackName;  // 有别名用别名，否则用原始名
```

`trap_receiver.py` 的 `_save_trap()` 和 `poller.py` 的告警消息生成，都要走别名查询后再拼消息。

---

## 七、模拟器选择指南

| 场景 | 用哪个 | 说明 |
|------|--------|------|
| 自动化压力测试 | `run_simulators_large.py` | 多台交换机，状态自动随机漂移 |
| 手动功能验证 | `kvm_simulator.py` | Web 控制台，手动插拔、改字段、发 Trap |

两者 SNMP 通信协议完全一致（v2c，GET/GETNEXT/GETBULK，OID 结构相同）。

`run_simulators_large.py` 的默认配置：
```bash
SIM_NUM_CPU=12 SIM_NUM_CON=12 SIM_NUM_SWITCHES=3 SIM_BASE_PORT=11160
```

**注意**：`run_simulators_large.py` 会向数据库写入设备记录（自动注册），`kvm_simulator.py` **不写数据库**，需要手动在 Dashboard 管理后台添加设备。

---

## 八、数据库迁移说明

`backend/app/main.py` 的 `_migrate_columns()` 会在每次启动时自动检查并补列。

当前迁移列表（PostgreSQL 旧库适用）：

```python
("endpoints",      "module_type",   "ALTER TABLE endpoints ADD COLUMN module_type TEXT NOT NULL DEFAULT 'cpu'"),
("devices",        "model_name",    "ALTER TABLE devices ADD COLUMN model_name VARCHAR(128)"),
("devices",        "last_metrics",  "ALTER TABLE devices ADD COLUMN last_metrics TEXT"),
("devices",        "endpoint_count","ALTER TABLE devices ADD COLUMN endpoint_count INTEGER DEFAULT 0"),
("users",          "updated_at",    "ALTER TABLE users ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"),
("status_metrics", "id",            "ALTER TABLE status_metrics ADD COLUMN id BIGSERIAL"),
("alerts",         "endpoint_id",   "ALTER TABLE alerts ADD COLUMN endpoint_id VARCHAR(128)"),  ← 本轮新增
```

SQLite 用 `create_all` 直接建全表，不走这个列表。**两种数据库结构始终一致**。

---

## 九、下一轮可能要做的事（未完成）

优先级排序：

1. **Trap 消息格式待真实设备验证**  
   目前 `trap_receiver.py` 解析的 `"CPU module CPU-1-001 went offline"` 格式是模拟器生成的，真实 G&D 设备的 Trap message 内容未知。等有真实 Trap 样本后，可能需要调整正则。

2. **CON 键鼠状态判定**（HANDOFF_v3 遗留问题，已部分完成）  
   `getConKeyboardMouseState()` 逻辑已修正，前端显示已简化为单行。但 `MatrixView` 和 `TopoView` 里的状态着色是否完全一致，需要目视验证。

3. **三层拓扑视图**（HANDOFF_v3 遗留问题，未完成）  
   CPU → 交换机 → CON 三层布局的 `MatrixView` 和 `TopoView` 重构，v3 手册里有完整设计方案，本轮未动。

4. **端口映射功能**（如有需求）  
   方案：接入厂商 XML API 的 `ownerPort` 字段，或维护人工配置映射表。

5. **告警 is_resolved 自动化**  
   目前告警记录从不自动 resolve，需要手动操作。可以在轮询时检查设备/端点状态，自动 resolve 对应的 threshold 类型告警。

---

## 十、快速验证命令

```bash
# 后端语法
cd backend
python -m py_compile app/main.py app/api/devices.py app/api/endpoints.py app/snmp/trap_receiver.py app/snmp/poller.py

# 前端构建
cd frontend
npm run build

# 启动手动模拟器
cd backend
.venv/bin/python kvm_simulator.py
# 访问 http://localhost:8888

# 启动自动模拟器（写入数据库）
cd backend
DB_MODE=sqlite .venv/bin/python run_simulators_large.py
```

---

## 十一、不要踩的坑（历史教训）

1. **不要用 source_ip 查 Device.host**：Docker 环境下 Trap 来源 IP 是网关，不是设备 IP
2. **不要恢复 portTable**：真实设备不支持，已确认
3. **不要把 ep_port/con_port（Column 1）当物理端口展示**：这是模块表索引
4. **不要把 con_active_tx_port（值 1 或 2）当交换机端口号**：这是 CON 自身的 SFP 接口编号
5. **Trap OID 不要用 `.32828.5.x`**：MIB 里没有这个路径，正确是 `.32828.2.1.0.x`
6. **`stats.online_endpoints` 字段不存在**：后端 stats 接口只返回设备维度的统计，没有端点维度的在线数

---

**文档生成时间**：2026-05-18  
**对应代码版本**：git `bc803e5` 之后的本轮改动
