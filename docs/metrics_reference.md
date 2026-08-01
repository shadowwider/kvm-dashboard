# KVM 监控大屏指标与状态说明

> 版本：v2.0
> 更新时间：2026-08-01
> 适用范围：五 Profile 多设备监控版本

本文记录 Dashboard、设备详情、告警和底部状态区的真实数据来源与计算语义。旧版固定温度、双电源、六风扇和 SVG 拓扑说明已经废止。

## 1. 数据边界

Dashboard 使用以下稳定接口：

```text
GET /api/v1/stats
GET /api/v1/devices
GET /api/v1/devices/{device_id}/details
GET /api/v1/endpoints?device_id={device_id}
GET /api/v1/alerts
GET /api/v1/metrics/history
GET /api/v1/profiles
WS  /api/v1/ws/monitor?token={JWT}
```

五个受支持的 Profile：

| Profile | 产品角色 | `sysObjectID` |
|---|---|---|
| `ccdc_legacy` | 历史 CCDC 兼容矩阵 | `1.3.6.1.4.1.32828.3.257.16` |
| `ccdm_matrix` | CCDM / CC160 中心矩阵 | `1.3.6.1.4.1.32828.3.257.10` |
| `dp12_mux_atc` | DP1.2-MUX-ATC 通道设备 | `1.3.6.1.4.1.32828.3.1792.17` |
| `visionxs_con` | VisionXS 独立 CON | `1.3.6.1.4.1.32828.3.769.768` |
| `visionxs_cpu` | VisionXS 独立 CPU | `1.3.6.1.4.1.32828.3.768.768` |

CC160 与 CCDM 共享 `ccdm_matrix` 协议 Profile，不作为第六个 Profile。

## 2. 顶栏指标

### 2.1 系统健康率

系统健康率按受管设备计算：

```text
健康设备数 / 设备总数 * 100
```

健康设备同时满足：

- `online_status == online`
- `health_status` 不是 `critical` 或 `offline`

没有设备时显示 `100.0%`，仅表示当前没有已知故障对象，不表示网络已完成发现。

### 2.2 KPI

| 指标 | 计算方式 |
|---|---|
| 总设备 | `devices.length` |
| 在线 | `online_status == online` 的设备数 |
| 离线 | `online_status == offline` 的设备数 |
| 告警 | 优先使用 `stats.active_alerts`，缺失时统计前端未解决告警 |

KPI 是设备维度，不再沿用旧版终端维度数字。

### 2.3 实时连接

| 显示 | 条件 |
|---|---|
| 绿色“实时连接” | WebSocket `readyState == OPEN` |
| 红色“连接断开” | 其他状态 |

WebSocket 断开时前端自动重连，并继续依赖 60 秒 HTTP 刷新作为保底。

## 3. 左侧设备卡片

设备卡片直接使用 `GET /devices` 的设备摘要，不再为每张卡单独请求固定 OID。

| 字段 | DTO 来源 |
|---|---|
| 名称 | alias 覆盖后的 `device.name` |
| 地址 | `host:port` |
| Profile | `profile.id`、`profile.label_key` |
| 可达性 | `reachability.status` |
| 健康 | `health.status` |
| 数据新鲜度 | `data_freshness.status` |
| 实体数 | `entity_count` |
| 活跃告警 | `active_alert_count` |

卡片不假定设备一定有温度、双电源、固定风扇数量或 CPU/CON 表。

## 4. 中心视图

中心区域保留两个模式：

1. `MatrixView`：旧矩阵 endpoint 兼容投影。
2. `DeviceTable`：替换原拓扑 Tab，显示全部五 Profile 设备。

### 4.1 矩阵

矩阵只显示可投影为旧 `Endpoint` 的矩阵设备。VisionXS 和 DP 设备不伪装成矩阵端点。

终端状态按 `last_status.ep_device_status` 计算：

```text
缺失或 offline -> offline
ready           -> ready
online 且目标电源关闭 -> warning
其他 online     -> online
```

点击 CPU 或 CON 方块打开 `EndpointDetail`。详情分别显示 PS/2、USB 键盘、USB 鼠标和 HID 状态。

### 4.2 设备表格

设备表格至少显示：

- 设备名称和型号
- Profile
- 设备角色
- SNMP 地址
- 可达性
- 数据新鲜度
- 健康状态
- 实体数
- 活跃告警数
- 最近健康检查
- 最近完整采集

支持关键字、Profile、状态筛选以及名称和地址排序。宽屏直接显示完整表格；窄屏只在表格容器内部横向滚动，不能撑宽整个 Dashboard。

## 5. 设备完整详情

设备详情来自 `GET /devices/{id}/details`，按后端 Profile metadata 定义的 section 顺序渲染。前端不根据中文名称猜测协议含义。

一个字段的标准结构：

```json
{
  "key": "fan_speed",
  "label_key": "fields.fan_speed",
  "raw": "3200 RPM",
  "value": 3200,
  "unit": "RPM",
  "status": "ok",
  "supported": true,
  "present": true,
  "stale": false,
  "updated_at": "2026-08-01T08:00:00Z"
}
```

### 5.1 状态语义

| 状态 | 含义 |
|---|---|
| `ok` | 已支持、存在、新鲜且正常 |
| `info` | 有效信息状态，不代表故障 |
| `warning` | 可访问但有异常 |
| `critical` | 严重异常 |
| `offline` | 设备不可达 |
| `unknown` | 原始值存在但无法可靠解释，或尚未采集 |
| `unsupported` | MIB/Profile 标明或设备返回不支持 |
| `absent` | 完整成功采集后确认对象缺失 |
| `stale` | 保留最后值，但数据已经过期 |

`unsupported`、`absent` 和 `stale` 不得使用正常绿色，也不能互相替代。

### 5.2 实体与复合索引

板卡、端口、风扇、链路、CPU、CON 和通道等表对象使用稳定 `entity_key`。`index_key` 保留 MIB 定义的完整索引名、顺序和值。前端 React key 必须包含实体和字段位置，不能只使用可能重复的 `fan_speed`。

## 6. 风扇

风扇来源于设备详情中 key 包含 fan 且表示 speed/RPM 的字段，数量由 Profile 和设备实际返回决定。

| 输入 | 页面语义 |
|---|---|
| 正数 RPM | 存在并显示实际转速 |
| 合法 `0` | 保留风扇，显示停止或异常 |
| `noSuchObject` | `unsupported`，不是故障 |
| 完整 WALK 后连续缺行 | `absent` |
| 设备离线或数据过期 | 保留最后值并标记 `stale` |
| 字符串无法解析 | 保留 `raw`，标准值为 `unknown` |

风扇不得因为转速为零、设备离线或临时采集失败而从详情中删除。

## 7. 键盘、鼠标和 HID

可区分的枚举按以下方式显示：

| 枚举 | 键盘 | 鼠标 |
|---|---|---|
| `none` | 未连接 | 未连接 |
| `keyboard` | 已连接 | 未连接 |
| `mouse` | 未连接 | 已连接 |
| `keyboardMouse` | 已连接 | 已连接 |

PS/2 与 USB 来源分别显示。`targetUsbHid` 的 `connected` 或 `initialized` 只证明 HID 链路状态，页面必须标明“设备类型未区分”，不能推断键盘和鼠标都已连接。

## 8. 告警与 Trap

告警列表同时展示轮询告警、掉线/恢复告警和 Trap 告警。

告警对象包含：

- 持久化 Alert ID
- `device_id`、可选 `endpoint_id`、可选 `entity_key`
- `severity`、`alert_type`
- `message`、`raw_value`
- Trap 的 `trap_level` 和 `trap_oid`
- `created_at` 和解决状态

正式 Trap notification OID 为 `1.3.6.1.4.1.32828.2.1.0.4`。现场链路：

```text
设备 -> 宿主机 UDP 162 -> Docker 162:10162/udp -> 后端监听 10162
```

### 8.1 告警声音

- 仅对实时收到、带持久化 ID 的新告警播放。
- 首次载入历史告警不播放。
- 同一 Alert ID 在重连或重复事件中只播放一次。
- info、warning、critical、trap 和 offline 默认都允许播放。
- 支持总静音、按严重度开关和短时节流。
- 使用 Web Audio 本地合成音，不依赖外部音频文件。

## 9. 底部状态区

### 9.1 温度趋势

- 数据源：`GET /metrics/history?oid_name=temperature&device_id={id}&hours=24`
- 只绘制可以转换为有限数值的点。
- 未选设备时展示所有有数据设备；选中后只展示该设备。
- 没有真实历史数据时显示“暂无真实历史数据”，不生成随机曲线。

### 9.2 风扇状态

- 数据源：目标设备已经加载的完整详情。
- 目标设备优先级：当前选中设备、第一台在线设备、设备列表第一台。
- 展示所有匹配的风扇字段及其实际状态。
- 不使用固定六风扇或固定满量程仪表盘。

### 9.3 当前可用率快照

这不是 24 小时历史图：

```text
有 endpoint 时：当前 online/ready endpoint 数 / endpoint 总数
无 endpoint 时：当前在线设备数 / 设备总数
```

页面明确标注为当前快照，不生成随机历史柱。

## 10. 后端摘要状态

### 10.1 可达性

`reachability.status` 主要来自快速健康探测：

- `online`
- `offline`
- `unknown`

`last_health_check` 与 `latency_ms` 表示最近一次快速探测结果。

### 10.2 数据新鲜度

默认规则：

```text
age_seconds <= max(poll_interval * 2, 120) -> fresh
否则 -> stale
```

若完整采集结果明确为 `failed` 或 `unsupported`，新鲜度使用对应状态。

### 10.3 健康状态

设备摘要优先级：

```text
存在未解决 critical -> critical
否则存在未解决 warning -> warning
否则设备在线 -> ok
否则沿用可达性状态
```

## 11. 刷新策略

| 数据 | 方式 |
|---|---|
| stats、devices、endpoints、alerts、profiles、aliases、OID 配置 | 登录后初始拉取，随后每 60 秒刷新 |
| `device_update` | WebSocket 实时更新设备摘要 |
| `entity_update` | WebSocket 更新通用实体 |
| `alert_created`、兼容 `new_alerts`、`trap_received` | WebSocket 更新告警；声音仅消费带 ID 的新告警 |
| `discovery_job_update` | WebSocket 更新发现任务进度 |
| 设备完整详情 | 点击设备时按需获取，可手工刷新 |
| endpoint 温度历史 | 打开 endpoint 详情时按需获取 |

WebSocket 重连后会重新拉取摘要，避免断线期间事件丢失。

## 12. 维护要求

1. 新字段先加入 Profile metadata 和后端标准 DTO，再增加前端 i18n。
2. 不在 JSX 中硬编码某个型号的 OID 或固定实体数量。
3. 不把 VisionXS/DP 对象写入旧矩阵 endpoint。
4. 不把 unsupported、absent、stale 当成 offline。
5. 不生成随机监控数据。
6. community、密码和 JWT 不得进入设备读接口、日志或截图。
