# Handoff v3

本文件用于下一轮修改前快速对齐目标、事实边界、阅读顺序和实施计划。核心原则：先修确定问题，不把无法证明的 SNMP 字段解释成真实物理接口。

## 目标边界

本轮要解决三个核心问题：

1. CON 键鼠连接状态显示和判定不准。
2. CPU / CON 要能在页面上清楚表达属于哪台交换机、落在哪个位置。
3. 矩阵视图和拓扑视图都改成三层结构：上排 CPU，中间交换机，下排 CON，避免圆形放射和纯方块网格。

同时要清掉当前明显阻塞验证的构建问题：`frontend/src/pages/Dashboard.css` CSS 语法错误。

## 已确认事实

### SNMP 字段语义

MIB 里的 CPU/CON Column 1 不是已确认的真实交换机物理接口。

- CPU 表 Column 1 是 `targetModuleIndex`。
- CON 表 Column 1 是 `userModuleIndex`。
- 两者更像模块表索引 / table index / slot index。
- 不能继续无条件命名成“物理端口”并当作真实接口展示。

真实可用的数据分三类：

- CPU/CON 模块表：告诉我们某台交换机下有哪些 CPU/CON，以及每个模块自身状态。
- `portTable`：告诉我们交换机物理传输端口 1..N 的链路状态。
- 当前缺口：暂未发现可靠的“CPU/CON 模块 -> portTable 物理端口”的厂商字段。

除非后续发现新 OID 或新增人工映射表，否则 UI 只能展示“模块索引/槽位”，不能承诺“真实物理接口”。

### CON 键鼠字段

CON 键鼠字段数据源存在，问题主要在展示和状态判定。

- `con_console_ps2`：CON 表第 9 列。
- `con_console_usb`：CON 表第 10 列。
- 枚举值：`none`、`keyboard`、`mouse`、`keyboardMouse`。

当前前端只看 `con_console_usb`，会误判以下情况：

- PS/2 有键鼠、USB 为 `none` 时被标 warning。
- USB 只有 `keyboard` 或只有 `mouse` 时可能被当作正常。
- `none` 曾经被隐藏，导致用户以为没有采集 USB 状态。

### 当前实现风险

`port_occupancy` 当前用单个 index 作为 key，CPU 和 CON index 相同会互相覆盖。应避免继续使用 `port -> one endpoint` 的结构表达 CPU/CON 占用。

建议拆成：

- `module_occupancy.cpu[index]`
- `module_occupancy.con[index]`
- `ports[index]` 单独表示 `portTable` 链路状态

## 推荐实现策略

### 1. 后端语义修正

保留 `endpoints.index` 作为排序和布局位置，但 UI 文案避免叫“物理端口”。更合适的命名是：

- 模块位
- 模块索引
- 表索引
- Slot

`ep_port` / `con_port` 如果保留，应在注释和文档中说明它来自表索引，未证明等于真实物理接口。

### 2. CON 键鼠逻辑修复

新增一个统一判定逻辑，复用在 `MatrixView`、`TopoView`、`EndpointDetail`。

建议规则：

- 任一接口为 `keyboardMouse`：完整键鼠 OK。
- 一个接口为 `keyboard`，另一个接口为 `mouse`：完整键鼠 OK。
- 只有 `keyboard` 或只有 `mouse`：部分连接，warning。
- 两个都是 `none` / 空：未连接，warning。
- 字段缺失：unknown，不要误判为 OK。

详情页应明确展示：

- PS/2 状态
- USB 状态
- 综合键鼠状态

不要隐藏 `none`，要显示“未连接”。

### 3. 三层视图重构

`MatrixView` 和 `TopoView` 统一改成三层结构：

```text
CPU modules
    |
KVM switch / switches
    |
CON modules
```

全局模式 `filterDeviceId='all'`：

- 多台交换机并排。
- 每台交换机只连接自己的 CPU/CON。
- 超大规模时可以启用紧凑模式，但仍保持 CPU / switch / CON 三层语义。

单台交换机模式：

- 中间只显示当前交换机。
- 上方显示该交换机 CPU。
- 下方显示该交换机 CON。
- 模块卡片显示 `#index`，但标签用“模块位/索引”，不要叫物理端口。

### 4. 设备卡片状态修正

设备卡片可以展示两种不同信息，但不要混淆：

- 模块占用：CPU/CON 的模块索引状态。
- 物理链路：`portTable` 的 port 1..N 链路状态。

如果没有可靠映射，不要把 CPU/CON 直接塞到 `portTable` 端口格子上。

### 5. 数据库迁移补漏

`Device` 模型已有 `endpoint_count`，但启动迁移里需要确认旧库能自动补列。若缺失，补到 `_migrate_columns()`。

### 6. 构建修复

修复 `Dashboard.css` 未闭合块，并清理重复/冲突样式。之后必须跑前端构建验证。

## 渐进式阅读顺序

只按需要展开，不要一开始读全仓库。

### 第一层：必须先看

#### `backend/app/snmp/oid_map.py`

只看：

- `ENDPOINT_COLUMNS`
- `CON_COLUMNS`
- `PORT_COLUMNS`
- `ENUM_MAPS`
- `SEED_OID_REGISTRY`

目的：确认字段名、列号、枚举映射。

#### `backend/app/snmp/poller.py`

只看 `poll_device()` 内以下部分：

- table walk
- endpoint upsert
- `last_metrics` 聚合
- WebSocket broadcast

目的：修正索引语义、避免 CPU/CON 覆盖、调整 `last_metrics` 结构。

#### `frontend/src/components/MatrixView.jsx`

主改造点。只关注：

- endpoint 分组
- 状态判定
- 三层布局渲染
- 点击打开 `EndpointDetail`

#### `frontend/src/components/TopoView.jsx`

主改造点。只关注：

- 当前圆形 / 放射布局
- 全局设备视图
- 单设备拓扑视图
- endpoint 点击和详情面板

#### `frontend/src/components/EndpointDetail.jsx`

只关注：

- CON 字段展示
- PS/2 / USB / 综合键鼠状态
- `none` 是否被隐藏

### 第二层：需要时再看

#### `frontend/src/pages/Dashboard.css`

只在以下情况打开：

- 修 CSS 构建错误
- 新增三层布局样式
- 清理重复冲突样式

#### `frontend/src/i18n/zh-CN.json`
#### `frontend/src/i18n/en-US.json`
#### `frontend/src/i18n/index.js`

只处理：

- 新增文案
- `t()` fallback 问题
- “模块位/索引”“综合键鼠状态”等标签

#### `backend/app/models/device.py`
#### `backend/app/api/devices.py`
#### `backend/app/main.py`

只处理：

- `last_metrics`
- `endpoint_count`
- 自动迁移
- API 输出字段

### 第三层：事实核对时才看

#### `help/GUD-CCDCCPU-MIB.txt`

只查 CPU 表字段定义。

#### `help/GUD-CCDCCON-MIB.txt`

只查 CON 表字段定义，尤其第 9、10 列键鼠。

#### `help/GUD-CCDC-MIB.txt`

只查 `portTable`。

#### `backend/logs/poll_raw.log.2`

只用于验证 2026-04-22 真机日志里的字段值，不全量阅读。

## 不要优先看

除非被明确需要，不要打开这些内容：

- legacy 组件：`DeviceMatrix`、`EndpointGrid`、`MetricChart`、`TopologyView`、`EndpointNode`、`HealthRate`、`StatsBar`
- `node_modules`
- 未提到的文档
- 临时调试脚本
- 大体积日志全文

## 建议提交顺序

1. 修 CSS 构建错误和 i18n fallback，小范围保障能 build。
2. 增加 CON 键鼠状态工具逻辑，并复用到 `MatrixView`、`TopoView`、`EndpointDetail`。
3. 修后端 `last_metrics` 结构，避免 CPU/CON 覆盖，并补 `endpoint_count` migration。
4. 改 `MatrixView` 三层布局。
5. 改 `TopoView` 三层布局。
6. 跑验证。

## 验证清单

后端语法：

```bash
cd backend
python -m py_compile app/main.py app/models/device.py app/api/devices.py app/snmp/poller.py
```

前端构建：

```bash
cd frontend
npm run build
```

如需页面人工验证：

```bash
cd frontend
npm run dev
```

重点观察：

- CON 详情页显示 PS/2、USB、综合键鼠状态。
- `none` 显示为未连接，而不是隐藏。
- CPU/交换机/CON 三层布局清晰。
- 单交换机和全部交换机视图都能工作。
- UI 不再把未确认的 table index 叫成真实物理端口。
