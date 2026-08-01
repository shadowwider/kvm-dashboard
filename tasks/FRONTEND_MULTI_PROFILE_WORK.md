# 前端开发任务书：设备列表、全状态详情、声音与 Admin

## 1. 任务目标

在保留现有矩阵视图的前提下，将 Dashboard 原拓扑视图替换成设备列表，并支持五个后端 Profile 的动态状态展示。前端不能继续假定所有设备都有固定双电源、六个风扇或 CPU/CON 表。

## 2. 写入范围

只允许修改 `frontend/**`。不得修改后端、模拟器、Docker 或数据库文件。

后端尚未完成时，使用本任务书 DTO 和本地 fixture 开发。不得为了页面方便私自改变 API 字段含义。

## 3. Dashboard 视图

保留两个切换项：

1. 矩阵：继续使用现有 `MatrixView`，用于 CCDC/CCDM CPU、CON、DWC 兼容投影。
2. 设备列表：替换现有 `TopoView` 入口，展示全部受管设备。

设备列表至少包含：

- 设备名称
- Profile / 型号
- IP
- 设备角色
- 在线状态
- 健康状态
- 当前未确认告警数
- 数据新鲜度
- 最后健康检查
- 最后完整采集

支持状态、Profile、关键字筛选和排序。点击任意设备打开设备完整详情。

VisionXS 和 DP 作为独立设备出现在设备列表中，不放入旧矩阵方块。

## 4. 设备详情

调用 `GET /devices/{id}/details`，按后端 section 顺序动态渲染：

- 身份
- 健康和数据新鲜度
- 电源
- 温度和风扇
- 网络
- CPU / CON / DWC
- 视频和通道
- USB / HID / PS2
- SFP 和链路
- 板卡和端口
- 错误对象

字段统一显示：

- label
- normalized value
- unit
- raw value查看入口
- status
- supported / unsupported
- present / absent / stale
- updated_at

不支持字段不显示为故障；stale 值不能使用健康绿色。

实体表必须支持复合索引的稳定 key，不能用数组位置作为 React key。

## 5. 键盘和鼠标明细

对明确的 `none/keyboard/mouse/keyboardMouse`：

- 分别显示键盘是否连接
- 分别显示鼠标是否连接
- 分开标注 PS/2 和 USB 来源

对 `targetUsbHid`：

- 显示未连接、已连接或已初始化
- 明确显示“设备类型未区分”
- 不把 initialized 自动显示为键盘和鼠标都连接

所有文字进入 CN/EN i18n 文件，不在 JSX 中硬编码。

## 6. 告警声音

所有 `alert_created` 新告警均允许播放，包括 info、warning、critical、trap、offline。

实现要求：

- 用户首次点击页面后初始化 AudioContext。
- 提供全局静音开关并持久化。
- 可按严重度单独启用/禁用，默认全部启用。
- 以持久化 Alert ID 去重。
- 页面重连和首次拉取历史告警时不补播。
- 短时间告警风暴进行节流，但不能丢失页面告警记录。
- 浏览器禁止自动播放时给出不干扰监控的启用状态提示。
- 使用简单本地音效或 Web Audio 合成音，不依赖外部 CDN。

## 7. WebSocket

- 使用认证后的 WebSocket URL。
- 处理 `device_update`、`entity_update`、`alert_created`、`trap_received` 和 `discovery_job_update`。
- WebSocket 事件只更新 store；复杂 UI 不直接处理网络消息。
- 重连后重新获取摘要数据，避免丢事件。
- 不依赖没有 ID 的临时告警对象。

## 8. Admin 页面

新增：

### 8.1 自动发现

- 配置 CIDR、community、端口、timeout、retries、concurrency、启动扫描开关。
- community 输入使用密码框，读取时只显示已配置状态。
- 保存配置、立即扫描、显示任务进度和导入结果。
- 本期不提供预览/逐项确认，因为已确认精确识别后直接加入。

### 8.2 操作日志

- 按时间、用户、action、target、result 筛选。
- 分页。
- 查看脱敏 change summary。
- 导出 CSV。

设备管理页面不得显示明文 community。

## 9. 图表和状态

- 删除 `BottomCharts.jsx` 中随机生成的在线率。
- 无真实历史数据时显示无数据状态。
- 温度、风扇只对后端提供有效 normalized 数值的数据作图。
- raw 字符串无法解析时在详情中显示，不强行画图。
- fan speed `0` 显示停止/异常，不从列表移除。
- stale 风扇显示最后值和过期时间。

## 10. 设计和可用性

- 延续现有监控大屏视觉体系，保持信息密度和扫描效率。
- 设备列表使用真正的表格，不使用卡片矩阵伪装列表。
- 按钮使用现有 Lucide 图标，未知图标提供 tooltip。
- 不嵌套卡片。
- 1920x1080、1366x768 和移动窄屏不得重叠或溢出。
- 详情字段很多时使用 tabs/sections 和表格，不把所有内容塞入单一长卡片。

## 11. 测试与验证

至少覆盖：

- 五 Profile 的设备详情 fixture
- 设备列表筛选、排序和详情打开
- 矩阵功能保持可用
- 键盘/鼠标四种枚举
- HID 未区分文案
- 风扇 0、unsupported、absent、stale
- Alert ID 声音去重、重连不补播、静音持久化
- Admin 发现配置和任务进度
- 审计筛选和 CSV

必须运行：

```bash
npm run lint
npm run build
```

使用 Playwright 或等价浏览器自动化检查主要流程，并保存桌面和窄屏截图。现有 lint 问题应在所触及文件中清理，不能新增 lint 错误。

## 12. 前端完成定义

矩阵视图保持原功能；拓扑入口已经变成全部设备表格；五种设备点击后都能显示 Profile 对应的完整状态；所有新告警可以发声且可静音；Admin 可以配置自动发现并查询管理员操作日志；页面不泄露 community。
