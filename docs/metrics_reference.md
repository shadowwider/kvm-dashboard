# KVM 监控大屏 — 指标说明文档

> 版本：v1.1 · 更新时间：2026-03-02  
> 说明：本文档记录大屏所有显示指标的数据来源、计算逻辑与状态定义，供开发维护参考。

---

## 一、顶栏指标

### 1.1 系统健康率（中央大数字）

| 项目 | 说明 |
|---|---|
| **数据来源** | 前端 `mainStore.endpoints`（全量终端数据） |
| **计算公式** | `(活跃终端数 / 总终端数) × 100`，保留1位小数 |
| **"活跃"定义** | `ep.last_status.ep_device_status` 为 `'online'` 或 `'ready'` |
| **兜底** | `allEps.length = 0` 时回退到 `stats.online_endpoints / stats.total_endpoints`；`total = 0` 时显示 `100.0%` |
| **含义** | 所有终端设备中**在线+就绪**状态的占比，反映系统整体可用性 |

### 1.2 KPI 卡片（总终端 / 活跃 / 离线 / 告警）

| 卡片 | 数据来源 | 计算逻辑 |
|---|---|---|
| **总终端** | `mainStore.endpoints` | `allEps.length`（前端 store 中全量终端数）。兜底：`stats.total_endpoints` |
| **活跃** | `mainStore.endpoints` | `allEps.filter(ep => ep_device_status === 'online' \|\| 'ready').length`。兜底：`stats.online_endpoints` |
| **离线** | `mainStore.endpoints` | `allEps.filter(ep => !ep_device_status \|\| ep_device_status === 'offline').length`。兜底：`epTotal - epActive` |
| **告警** | `stats.active_alerts` | 后端返回的未解决告警数。兜底：`alerts.filter(a => !a.is_resolved).length` |

> [!IMPORTANT]
> v1.1 变更：KPI 已从**交换机维度**切换为**终端维度**。交换机一般不会离线，监控终端状态更有运维价值。  
> v1.1 变更：`useCountUp` 数字滚动动画已移除，避免每次 WebSocket 推送或轮询时数字从 0 闪烁归零。现在直接展示实时原始数值。

### 1.3 WebSocket 连接状态

| 状态 | 含义 |
|---|---|
| 绿点「实时连接」 | `WebSocket.readyState === 1`（OPEN），正在接收实时推送 |
| 红点「连接断开」 | 其他状态，前端自动重连，期间依靠轮询保底 |

---

## 二、左侧设备卡片（DeviceCard）

每张卡片展示一台 KVM 交换机的关键指标。

### 数据来源

- **设备基础信息**：`GET /devices` 返回的 `Device` 对象
  - `id`：设备唯一标识（如 `CCDC-01`）
  - `name`：设备显示名（可在别名管理中修改）
  - `host`：设备 IP 地址
  - `last_status`：字符串，`online` / `offline` / `warning`
- **温度 / 电源 / 风扇**：通过 `GET /metrics/history?oid_name=<字段>&device_id=<id>&hours=1` 单独拉取，取最后一条记录

### 各指标定义

| 指标 | OID 名 | 单位 | 状态阈值 |
|---|---|---|---|
| 温度 | `temperature` | °C | ≤45 绿色 / 45-55 橙色 / >55 红色 |
| 主电源 | `main_power` | — | `1`/`on` = ✓绿色，否则 ✗红色 |
| 冗余电源 | `redundant_power` | — | 同上 |
| 网口0 | `net_if0` | — | `1`/`up` 绿点，否则红点 |
| 网口1 | `net_if1` | — | 同上 |
| 终端数 | — | 台 | `device.endpoint_count`（数据库维护的计数，非实时统计） |
| 风扇1~6 | `fan1`~`fan6` | RPM | `0` = 故障（死点红色），>0 = 正常（绿点脉冲） |

### 设备状态（左边框颜色）

| `last_status` 值 | 边框颜色 | 含义 |
|---|---|---|
| `online` | 绿色 | 设备正常响应 SNMP 轮询 |
| `warning` | 橙色 | 有告警但仍在线（如温度超阈值） |
| `offline` | 红色 | 无法访问或 SNMP 超时 |

---

## 三、中间面板

### 3.1 终端状态矩阵（MatrixView）

#### 数据来源
- `GET /endpoints?device_id=<id>` 拉取每台设备的终端列表
- 全部模式下，`fetchAllEndpoints()` 对所有设备并发拉取并合并到 store
- 终端的 `last_status` 字段为 JSON 对象（由 SNMP 采集写入，包含多个子字段）

#### 终端状态判断逻辑（前端计算）

```
ep.last_status.ep_device_status:
  undefined / "offline" → offline（红色，闪烁）
  "ready"               → ready（蓝色）
  "online":
    ep_target_power = "off" → warning（橙色，慢闪）
    否则                    → online（绿色）
```

#### 交互方式

> [!IMPORTANT]
> v1.1 变更：矩阵视图已从 **hover tooltip** 改为 **点击弹出 EndpointDetail 面板**。  
> 原因：hover tooltip 在容器 overflow 裁剪时会被遮挡/截断，点击面板更可靠且支持显示更多信息（含温度趋势图）。

#### 图例计数

图例中的在线/就绪/离线/告警数字是**当前 list 的实时计数**，使用上述判断逻辑在前端统计，不依赖后端统计接口。

#### 列数自适应

| 终端总数 | 列数 |
|---|---|
| ≤32 | 16列 |
| ≤64 | 24列 |
| ≤128 | 32列 |
| >128 | 40列 |

### 3.2 拓扑图（TopoView）

> [!NOTE]
> 拓扑图使用**纯 SVG + DOM 手写渲染**，不依赖 React Flow 或 D3.js。所有节点通过 `document.createElement` 创建，连线通过 SVG `<path>` 绘制，粒子动画通过 `requestAnimationFrame` 驱动。

#### 全局总览模式（filterDeviceId = 'all'）

- 顶部 `🌐 KVM 网络` 根节点（仅前端展示，无后端数据）
- 根节点通过贝塞尔曲线虚线连接到**每一台**设备
- 每台设备显示为卡片，展示：活跃终端数 / 总终端数 / 设备状态颜色
- **活跃终端**：`online` 或 `ready` 状态（v1.1 修复：之前仅统计 `online`）
- 点击设备卡片 → 下钻到单设备拓扑

#### 单设备拓扑模式（filterDeviceId = device_id）

- 数据来源：`GET /endpoints?device_id=<id>` 中的终端列表
- 终端状态颜色：同矩阵视图判断逻辑
- 连线：
  - **实线**（绿/蓝/橙）= 终端在线/就绪/告警
  - **虚线红**= 终端离线
  - **VIDEO LOST 标注** = `ep_target_video_cable = "notConnected" / "disconnected"`
- 粒子动画：仅对**非离线**连线显示流动光点，速度随机（0.3%~0.6%/帧）
- 支持**鼠标滚轮缩放** + **拖拽平移**

#### 终端详情面板（EndpointDetail 组件）

- 矩阵视图和拓扑视图**共享同一组件** `EndpointDetail.jsx`
- 点击终端节点/格子后弹出
- 温度迷你折线图：来自 `GET /metrics/history?oid_name=ep_temperature&endpoint_id=<id>&hours=12`
- **无历史数据时不显示图表**（而非显示空白）

| 字段 | 数据来源 |
|---|---|
| 终端名称 | `ep.name` 或别名 |
| 所属设备 | 关联的 `device.name` |
| 端口号 | `ep.index` |
| 视频信号 | `ep.last_status.ep_target_video_signal`（枚举转中文） |
| 当前温度 | `ep.last_status.ep_temperature`（°C） |
| 访问状态 | `ep.last_status.ep_target_access` |
| SFP 发/收 | `ep.last_status.ep_sfp_tx/rx_power`（uW，有则显示） |

---

## 四、右侧实时告警（AlertStream）

- **数据来源**：`GET /alerts?is_resolved=false&limit=50`，由初始加载 + WebSocket 实时推送更新
- **告警对象字段**：
  - `severity`：`critical` / `warning` / `info`
  - `device_id`：关联设备
  - `message`：告警描述
  - `created_at`：UTC 时间（前端转本地 `HH:mm:ss`）
  - `is_resolved`：是否已处理

| 徽标颜色 | severity 值 | 含义 |
|---|---|---|
| 红色「紧急」 | `critical` | 电源/温度等严重异常 |
| 橙色「警告」 | `warning` | 超阈值但未宕机 |
| 蓝色「信息」 | `info` | 状态变更通知 |

> [!IMPORTANT]
> v1.1 变更：WebSocket `trap_received` 消息现在强制添加 `created_at` 兜底（使用推送时的当前时间 ISO 字符串），确保每条告警都有时间戳显示。  
> 告警来源有两种：**SNMP 主动轮询发现**（poller 写入），和**SNMP Trap 被动接收**（trapd 写入）。前端无法区分，统一展示。

---

## 五、底栏图表

底栏使用**纯 SVG 手绘图表**（`BottomCharts.jsx`），不依赖 ECharts。

### 5.1 温度趋势折线图（TempChart）

| 项目 | 说明 |
|---|---|
| **数据来源** | `GET /metrics/history?oid_name=temperature&device_id=<id>&hours=24` |
| **展示设备** | 未选中时：全部设备各一条线；选中设备时：仅该设备 |
| **颜色** | 第1条青色实线，第2条绿色虚线，第3条橙色虚线，第4+条红色虚线 |
| **警戒线** | 55°C 红色虚线（固定，来自 G&D 设备规格书） |
| **Y轴范围** | 固定 28°C ~ 65°C（前端硬编码，反映设备工作范围） |

### 5.2 风扇转速仪表盘（FanGauges）

| 项目 | 说明 |
|---|---|
| **数据来源** | `GET /metrics/history?oid_name=fan1~fan6&device_id=<id>&hours=1`（取最后一条） |
| **展示设备** | 选中设备 > 第一台在线设备 > 设备列表第一台 |
| **圆弧满量程** | 4500 RPM（前端定义，基于设备额定转速经验值） |
| **颜色规则** | RPM=0 红色（故障）/ >80%量程 橙色（高速） / 其余青色 |

### 5.3 24H 在线率柱状图（OnlineRate）

| 项目 | 说明 |
|---|---|
| **历史柱状** | `GET /metrics/history?oid_name=ep_device_status&hours=24`（取最近24条） |
| **当前率（大数字）** | 优先从前端 `endpoints` 计算 `活跃终端/总终端`；无终端数据时回退到 `devices` 在线比例 |
| **Y轴起点** | 90%（因实际系统一般高于90%，从90起步视觉区分度更好） |
| **兜底** | 历史数据拉取失败时默认显示24条98%高度的柱子 |

---

## 六、状态说明汇总

### 设备状态（`Device.last_status`）

| 值 | 来源 | 含义 |
|---|---|---|
| `online` | SNMP 轮询成功，无告警 | 正常运行 |
| `warning` | SNMP 轮询成功，有活跃告警 | 有问题但仍可访问 |
| `offline` | SNMP 轮询超时/失败 | 无法通信 |

### 终端状态（`Endpoint.last_status.ep_device_status`）

| 值 | 含义 |
|---|---|
| `online` | 终端设备上电且被服务器访问 |
| `ready` | 终端已连接但目标主机未开机或待机 |
| `offline` | 终端设备不可达 |

> [!NOTE]
> 终端 `last_status` 是由 SNMP 采集器解析 OID 后写入数据库的 **JSON 字符串**，前端在 `getEpStatus()` 函数中解析并映射到显示状态。

### 视频信号类型（`ep_target_video_signal`）

| 后端值 | 显示 |
|---|---|
| `none` | 无信号 |
| `vga` | VGA |
| `dvisl` | DVI-SL |
| `dvidl` | DVI-DL |
| `dmdp` | MDP |
| `dp` | DP |
| `hdmi` | HDMI |

---

## 七、数据刷新策略

| 数据 | 刷新方式 | 频率 |
|---|---|---|
| 设备列表 / KPI / 告警 | HTTP 轮询 (`fetchAll`) | 60秒/次 |
| 全量终端数据 | `fetchAllEndpoints`（在 devices 加载后自动触发） | 60秒/次 + devices 变化时 |
| 设备状态更新 | WebSocket `device_update` 事件 | 实时推送 |
| 新告警 | WebSocket `new_alerts` / `trap_received` 事件 | 实时推送 |
| 风扇数据 | 设备卡片 `useEffect` 按需拉取 | 设备切换时 |
| 温度历史 | TempChart `useEffect` | 60秒/次 |
| 终端温度历史 | EndpointDetail 打开时拉取 | 一次性 |
