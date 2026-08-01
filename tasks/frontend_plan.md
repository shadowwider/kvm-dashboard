# KVM 监控大屏 — 前端设计方案

> 分支: `feat/full-refactor` | 最后更新: 2026-03-02
> 后端 API 基础地址: `/api/v1` (通过 Nginx 反代)
>
> **历史文档警告（2026-08-01）**：本文记录单一 CCDC 矩阵时期的原始设计，仅保留作背景资料，不再作为当前开发契约。当前实现保留矩阵，但已将拓扑入口替换为五 Profile 设备表格；完整状态详情、自动发现、告警声音和审计日志的有效任务书分别是 `tasks/FRONTEND_MULTI_PROFILE_WORK.md`、`tasks/MULTI_PROFILE_API_CONTRACT.md` 和 `docs/MULTI_PROFILE_DEVELOPMENT_MASTER_PLAN.md`。

---

## 一、技术栈

| 层 | 技术 | 理由 |
|----|------|------|
| 框架 | **React 18 + Vite 5** | 快速 HMR，组件化 |
| 路由 | **React Router v6** | Login / Dashboard / Admin |
| 状态 | **Zustand** | 轻量全局状态（WebSocket 数据流） |
| 拓扑图 | **纯 SVG + DOM 手写渲染** | 拓扑图动态渲染，含粒子动画 + 缩放/平移（不依赖 React Flow） |
| 仪表图表 | **纯 SVG 手绘** | 温度折线图、风扇仪表盘、在线率柱状图（不依赖 ECharts） |
| 样式 | **Vanilla CSS + CSS Variables** | 暗色大屏主题，无框架依赖 |
| 字体 | **Inter** (Google Fonts) | 现代感数据展示字体 |
| HTTP | **axios** + 拦截器 | JWT 自动注入 + 401 跳转 |
| 实时推送 | **WebSocket** (原生) | 状态变更实时更新 |
| 图标 | **Lucide React** | 轻量 SVG 图标库 |

---

## 二、页面结构与路由

```
/login          → 登录页（暗蓝背景 + 登录卡片动效）
/dashboard      → 监控大屏（默认页，需登录）
/dashboard/topo → 拓扑视图模式
/admin          → 管理员面板（需 admin 角色）
```

---

## 三、页面详细设计

### 3.1 /login — 登录页

- 纯暗蓝渐变背景 + 居中卡片
- 卡片内：用户名 / 密码 / 登录按钮
- 登录成功后存 JWT 到 Zustand + localStorage，跳转 /dashboard
- 动效：卡片淡入 + 背景微粒子流动

### 3.2 /dashboard — 监控大屏（核心）

#### 布局（1920×1080 分辨率优先设计）

```
┌─────────────────────────────────────────────────────────────┐
│ 顶栏: 系统标题 | 实时时钟 | 总/在线/离线/告警 4个统计数字    │
├────────────────┬──────────────────────────┬──────────────────┤
│  左栏 (25%)    │   中心区域 (50%)          │  右栏 (25%)      │
│                │                          │                  │
│  KVM 设备卡片  │   终端状态矩阵            │  实时告警流       │
│  (上下滚动)    │   (点阵网格/拓扑 切换)    │  (最新在上)       │
│                │                          │                  │
│  · 温度        │   每个格子=1个终端        │  · 时间           │
│  · 电源状态    │   颜色=状态              │  · 级别           │
│  · 风扇转速    │   悬浮=快速详情          │  · 设备名         │
│  · 网口状态    │   点击=展开完整面板      │  · 告警内容       │
│                │                          │                  │
├────────────────┴──────────────────────────┴──────────────────┤
│ 底栏: ECharts 历史趋势图（温度 / 风扇 / 在线率 可切换）       │
└─────────────────────────────────────────────────────────────┘
```

#### 顶栏统计数字
- 4 个发光数字卡片：**总终端数**、**活跃终端**（绿色）、**离线终端**（红色）、**告警数**（橙色脉冲）
- 数字直接展示实时值（已移除 countUp 动画，避免 WS 推送时归零闪烁）
- 数据源：前端 `mainStore.endpoints` 计算（兜底 `GET /api/v1/stats`）

#### 左栏 — KVM 设备卡片
- 每台 KVM 交换机一张卡片（从 `GET /api/v1/devices` 拉取）
- 显示：
  - 设备名称（可被别名覆盖）
  - 在线/离线状态指示灯
  - 温度（带色值：绿<45°C，黄45-55°C，红>55°C）
  - 主/冗余电源状态（✓/✗ 图标）
  - 风扇转速（迷你条形图或 6 个小圆点）
  - 网口 0/1 状态
- 点击设备卡片 → 中心区域切换为该设备的终端视图

#### 中心区域 — 终端状态矩阵
- **默认视图：点阵网格**
  - 每个终端是一个小色块（约 40×40px）
  - 颜色：绿=online, 蓝=ready, 红=offline, 橙=告警
  - 悬浮：显示终端名（别名优先）、title 提示
  - **点击**：弹出 EndpointDetail 终端详情面板（与拓扑图共享同一组件）
  - 数据源：`GET /api/v1/endpoints?device_id=xxx`

- **可切换视图：拓扑图** 🌟
  - 中心大节点 = KVM 交换机
  - 放射状连线 → 终端节点（纯 SVG `<path>` 贝塞尔曲线 + 流光粒子动画）
  - 每个终端节点 = DOM 元素卡片：
    - 状态指示灯 + 终端名 + 视频信号类型
  - 线的样式：
    - 实线绿色 = 视频线已连接
    - 虚线红色 = 视频线断开
    - VIDEO LOST 标注 = 视频线物理未插
  - 支持缩放、拖拽平移
  - 数据源：`GET /api/v1/endpoints?device_id=xxx`（不依赖后端 topology API 节点/连线结构）

#### 右栏 — 实时告警流
- 最新告警在最上方
- 每条告警：时间、级别徽标（info/warning/critical）、设备>终端名、消息
- 新告警滑入动画
- 数据源：`GET /api/v1/alerts?limit=50` + WebSocket 推送新告警

#### 底栏 — ECharts 历史图表
- Tab 切换：温度趋势 | 风扇转速 | 在线率
- 温度趋势：纯 SVG 折线图，X=时间，Y=温度，多设备叠加
- 风扇转速：纯 SVG 圆弧仪表盘，6 个扇区
- 在线率：纯 SVG 柱状图，24h 内在线终端百分比
- 数据源：`GET /api/v1/metrics/history?oid_name=temperature&hours=24`

### 3.3 /admin — 管理员面板

#### Tab 1: 设备管理
- 表格：设备ID | 名称 | IP | 端口 | Community | 轮询间隔 | 状态 | 操作
- 操作：编辑 / 删除 / 启用禁用
- 新增设备：弹窗表单
- API: `GET/POST/PATCH/DELETE /api/v1/devices`

#### Tab 2: 设备别名 ⭐ 新需求
- 表格：原始SNMP名称 | 自定义别名 | 对象类型(device/endpoint) | 操作
- **支持 inline 编辑**：点击别名列直接变成输入框，失焦自动保存
- API: `GET/PATCH /api/v1/aliases`（后端新增 aliases 表）

#### Tab 3: OID 配置
- 表格：指标名 | 显示名 | 类别 | 轮询开关 | 归档开关 | 告警开关 | 阈值 | 操作
- 开关列用 Toggle 组件，切换即时生效
- API: `GET/PATCH /api/v1/oids`

#### Tab 4: 告警管理
- 表格：时间 | 设备 | 终端 | 指标 | 级别 | 消息 | 状态(待处理/已确认) | 操作
- 操作：确认 / 批量确认
- 筛选：按级别、按设备、按时间范围
- API: `GET/PATCH /api/v1/alerts`

#### Tab 5: 用户管理
- 表格：用户名 | 角色 | 状态 | 创建时间 | 操作
- 操作：编辑角色 / 启用禁用 / 重置密码
- API: `GET/POST/PATCH /api/v1/users`（仅 admin 可见）

---

## 四、设计美学

### 配色方案（暗色大屏主题）
```css
:root {
  /* 背景 */
  --bg-primary:    #0a0e1a;    /* 极深靛蓝 */
  --bg-secondary:  #111827;    /* 卡片背景 */
  --bg-tertiary:   #1f2937;    /* 悬浮/选中 */

  /* 文字 */
  --text-primary:  #f0f4ff;
  --text-secondary: #94a3b8;
  --text-muted:    #64748b;

  /* 状态色 */
  --status-online:  #22c55e;   /* 翠绿 */
  --status-ready:   #3b82f6;   /* 靛蓝 */
  --status-offline: #ef4444;   /* 红 */
  --status-warning: #f59e0b;   /* 琥珀 */
  --status-critical:#dc2626;   /* 深红 */

  /* 强调色 */
  --accent:        #6366f1;    /* 靛紫 */
  --accent-glow:   rgba(99, 102, 241, 0.3);

  /* 边框 */
  --border:        rgba(255, 255, 255, 0.08);
  --border-hover:  rgba(99, 102, 241, 0.4);
}
```

### 视觉元素
- **Glassmorphism 卡片**：`backdrop-filter: blur(12px)` + 半透明背景
- **发光效果**：在线设备的状态灯使用 `box-shadow` 呼吸动画
- **微动画**：数字变化的 countUp、新告警滑入、状态切换渐变
- **拓扑图流光**：连线上的流动光点动画（React Flow 支持 animated edges）
- **字体**：`Inter` 用于数据，`Outfit` 用于标题

---

## 五、数据流架构

```
                     ┌──────────────────┐
                     │  Zustand Store   │
                     │  ├ authStore     │ ← login/logout
                     │  ├ deviceStore   │ ← devices + endpoints
                     │  ├ alertStore    │ ← alerts
                     │  └ configStore   │ ← oid_registry + aliases
                     └────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         首次加载          WebSocket        用户操作
         GET /stats       ws://host/ws      PATCH /aliases
         GET /devices                       PATCH /oids
         GET /endpoints                     POST /devices
         GET /alerts
```

### WebSocket 消息格式
```json
{
  "type": "device_update" | "alert_new" | "metric_update",
  "data": { ... }
}
```

---

## 六、后端待补充（前端开始前）

1. ~~**aliases 表 + API** — 设备/终端别名映射~~ ✅ 已完成
2. ~~**用户管理 API** — `GET/POST/PATCH /users`~~ ✅ 已有 (auth.py)
3. ~~**stats API 增强** — 返回总数/在线/离线/告警的汇总数字~~ ✅ 已有 (stats.py)
4. ~~**日志导出 API** — `GET /alerts/export` CSV 下载~~ ✅ 已完成
5. ~~**OIDUpdate archive_enabled** — 补齐字段~~ ✅ 已完成

---

## 七、500-2000 节点的拓扑图策略

**不能把 2000 个节点塞进一张图。** 采用分层下钻设计：

### 第一层：全局总览（设备健康矩阵）
- 所有 KVM 交换机 = 色块网格（类似热力图）
- 每个色块 = 1 台 KVM，颜色 = 健康状态（绿/黄/红）
- 支持 500 台设备一屏展示（25×20 网格）
- 悬浮：显示设备名、在线终端数、告警数
- **这是领导一眼看的：全绿=一切正常**

### 第二层：单设备拓扑（React Flow）
- 点击某台 KVM → 下钻到该设备的终端拓扑
- 中心大节点 = KVM 交换机
- 放射连线 → 该 KVM 下的 8-16 个终端
- 每次只渲染十几个节点，性能完美

### 第三层：终端详情面板
- 点击某个终端节点 → 侧边抽屉显示完整字段
- 温度历史趋势（ECharts 迷你折线图）

---

## 八、国际化 (i18n) 方案

采用标准的 key-value 方案，默认只写中文，但架构支持多语言：

```
frontend/src/i18n/
├── index.js          # useTranslation hook
├── zh-CN.json        # 中文（默认）
└── en-US.json        # 英文（预留空文件，后续填充）
```

所有前端可见文字用 `t('dashboard.online_count')` 取值。

---

## 九、VIP 大屏增强（省长视察级别）

### 顶部正中央：全局健康率大数字
```
         ╔══════════════════════╗
         ║     系统健康率        ║
         ║      99.8%           ║  ← 发光数字，绿色=正常，红色<95%
         ║   ■■■■■■■■■■□        ║  ← 进度条动画
         ╚══════════════════════╝
```

### 核心 KPI 一排
- **终端在线率** | **终端活跃/总数** | **今日告警** | **平均温度** | **网络可用率**
- 数字直接展示真实值（已移除 countUp 动画）

### 动态效果
- 数据刷新时的波纹动画
- 告警时屏幕边缘红色闪光
- 拓扑图连线上的流光粒子
- 状态变更的平滑过渡动画

---

## 十、Admin 面板补充

### Tab 6: 日志导出 ⭐ 新需求
- 按设备、级别、时间范围筛选
- 点击"导出 CSV"按钮下载
- API: `GET /api/v1/alerts/export?device_id=xxx&severity=warning`

---

## 十一、开发顺序

### Phase 2.1 — 脚手架
- [ ] `npx create-vite frontend --template react`
- [ ] 安装依赖：react-router-dom, zustand, axios, echarts, echarts-for-react, @xyflow/react, lucide-react
- [ ] 搭建 CSS 设计系统（index.css + theme tokens）
- [ ] 配置 vite.config.js（proxy → backend）
- [ ] 搭建 i18n 框架

### Phase 2.2 — 核心组件
- [ ] Login 页（动效 + JWT）
- [ ] Dashboard 布局框架（顶栏 + 三栏 + 底栏）
- [ ] HealthRate 组件（正中央大数字健康率）
- [ ] StatsBar 组件（KPI 一排统计）
- [ ] DeviceCard 组件（KVM 设备状态卡片）
- [ ] DeviceMatrix 组件（全局色块热力网格 — 第一层）
- [ ] EndpointGrid 组件（终端点阵矩阵）

### Phase 2.3 — 高级可视化 ✅
- [x] TopoView 组件（纯 SVG+DOM 拓扑图，含粒子动画 + 缩放平移）
- [x] EndpointDetail 组件（矩阵/拓扑共享，点击弹出）
- [x] AlertStream 组件（实时告警流 + 时间戳兜底）
- [x] BottomCharts 组件（纯 SVG 图表）
- [x] WebSocket 实时数据集成

### Phase 2.4 — Admin 面板
- [ ] Admin 路由保护
- [ ] DevicesTab（设备 CRUD）
- [ ] AliasesTab（inline 编辑别名）
- [ ] OIDRegistryTab（指标配置 toggle，含 archive_enabled）
- [ ] AlertsTab（告警确认/筛选 + CSV 导出按钮）
- [ ] UsersTab（用户管理）

### Phase 2.5 — 抛光
- [ ] 响应式适配（1080p/2K/4K 分辨率）
- [ ] 全局 loading / error 兜底
- [ ] 微动画打磨（countUp / 波纹 / 流光）
- [ ] 中文文案校对

