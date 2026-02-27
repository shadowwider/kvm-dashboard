# 任务清单 (Tasks)

- [x] 创建 Python 3.10 虚拟环境 (使用 uv) 
- [x] 重构后端目录结构，引入 FastAPI + SQLAlchemy
- [x] 兼容 SQLite（测试用）和 TimescaleDB（生产用）
- [x] 重写 SNMP 模拟器兼容 pysnmp v6 (剥离 asyncore，改用 pure socket + rfc1905 PDU)
- [x] **查阅官方 MIB / 日志验证 OID 树权威性，修正映射和测试**
- [x] 重构 oid_map 消除 Hardcode，实现 sysObjectID 探测
- [x] 拓展 OID 模型，增加自由存档标志(archive_enabled)
- [x] 新增端点 /api/topology 用于渲染动态拓扑图结构
- [ ] 提交当前重构及前端脚手架代码 (backend & frontend)
- [ ] 完善定时轮询任务的健壮度
- [ ] 开发前端管理界面（基础配置、验证）

## Phase 2.1 — 脚手架 (Frontend Scaffold)
- [x] 初始化 React Vite 项目: `npx create-vite frontend --template react`
- [x] 安装依赖：`react-router-dom, zustand, axios, echarts, echarts-for-react, @xyflow/react, lucide-react`
- [x] 搭建大屏 CSS 主题框架 (`index.css` & theme variables)
- [x] 配置 `vite.config.js` (`/api` proxy)
- [x] 搭建 i18n 框架 (`src/i18n`)

## Phase 2.2 — 核心组件 (Core Components)
- [x] Login 页与 JWT 鉴权拦击 (`authStore.js`, `api.js`, `ProtectedRoute.jsx`)
- [x] Dashboard 布局框架 (顶栏 + 三列中心 + 底栏的基础 Flex/Grid 架子)
- [x] HealthRate 组件 (大屏全局健康度)
- [x] StatsBar 组件 (KPI 统计栏)
- [x] DeviceCard 组件 (左侧 KVM 卡片列表)
- [x] DeviceMatrix 组件 (热力网格主视图)
- [x] EndpointGrid 组件 (第二层矩阵)

## Phase 2.3 — 高级可视化与实时集成 (Advanced Viz & WS)
- [x] TopologyView 组件（React Flow 拓扑图 — 第二层）
- [x] EndpointDetail 侧边抽屉（第三层）
- [x] MetricChart 底栏 ECharts 历史趋势图
- [x] WebSocket 实时数据推送集成 (Zustand 派发更新)

# 任务回顾 (Review)

- `2026-02-26 (Phase 2.3)`:
  - 成功开发 `TopologyView` (`@xyflow/react`) 拓扑视图。解析了后端的节点和连线对象，并构建了一套**基于数学运算的弧形 Radial Layout** 算法，动态计算并散开终端节点，不再依赖后端坐标或手动拖拽。
  - 引入了 `echarts-for-react`，完成了底栏 `MetricChart` 用于展示 KVM 设备的最近 24 小时温度历史流。
  - 完成了真实响应后端的 WebSockets `useSystemWebSocket.js` 自定义 hook，挂载至 Dashboard 并在前端完成了毫秒级的状态更新 (Device 修改与 Alert 进流，Zustand 自动完成差异更新和 DOM 切绘)。
  - 接入了 Zustand `persist` 中间件与 axios 拦截器，打造了标准的 `Bearer Token` 验证及自动过期注销流程。
  - 实现 `/login` 组件：根据预设暗蓝极客风，手写了粒子悬浮动效 (`particle`)与卡片淡入的登录视图 (并正确获取用户信息)。
  - 利用 `react-router-dom` 的 `<Outlet>` 完成了路由守卫 `ProtectedRoute`。
  - 完成了 `/dashboard` 的大屏 100vh 无滚动骨架实现：完美拉伸出顶栏 (Header)、状态栏 (StatsBar)、中心三块区域 (Left/Center/Right Panel) 及底部 EChart 预留区。

- `2026-02-26 (Phase 2.1)`:
  - 完整阅读了设计方案与后端 API、SQL，基于 `React 18 + Vite` 在 `frontend` 目录拉起了项目脚手架。
  - 按照要求安装了全套 UI、图表、路由、状态管理等依赖。
  - `src/index.css` 中注入了预定义的深色渐变大屏 CSS 变量、重置样式及 `.glass-card` 毛玻璃效果。
  - 配置好了 `vite.config.js` (`/api` 反向代理至 8000 端口) 以及基础的 i18n 多语言 Zustand 架构。

- `2026-02-26`:
  - 根据权威的 `GUD-CCDC-MIB`、`GUD-CCDCCPU-MIB` 文件和真机实测 `kvm_snmp_monitor.log`，对 `oid_map.py` 的设备标量、`portTable` (端口状态)、`targetModuleTable` (CPU终端模块状态) 进行了完整、正向推导验证。
  - 测试通过证明当前系统能够一次性精准地获取设备层数据（含稀疏编号的 fan 和 net接口）、提取出所有的终端数量，并正确落库。
  - 核心痛点解决：`pysnmp v6` 的 `bulkCmd` 手动 WALK 逻辑重构完成。
  - 总结了“数据源可信度优先级”教训，不再在有权威 MIB 文档的情况下依赖自研模拟环境盲目修改映射。
