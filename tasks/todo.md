# 任务清单 (Tasks)

- [x] 创建 Python 3.10 虚拟环境 (使用 uv) 
- [x] 重构后端目录结构，引入 FastAPI + SQLAlchemy
- [x] 兼容 SQLite（测试用）和 TimescaleDB（生产用）
- [x] 重写 SNMP 模拟器兼容 pysnmp v6 (剥离 asyncore，改用 pure socket + rfc1905 PDU)
- [x] **查阅官方 MIB / 日志验证 OID 树权威性，修正映射和测试**
- [x] 重构 oid_map 消除 Hardcode，实现 sysObjectID 探测
- [x] 拓展 OID 模型，增加自由存档标志(archive_enabled)
- [x] 新增端点 /api/topology 用于渲染动态拓扑图结构
- [x] 提交当前重构及前端脚手架代码 (backend & frontend)
- [x] 完善定时轮询任务的健壮度
- [ ] 开发前端管理界面（Admin Dashboard：基础配置、验证、开关）

## Phase 3 — 生产级 Docker 部署与交付 (Production Deployment)
- [ ] 编写前端多阶段构建的 `frontend/Dockerfile` (Node.js Build + Nginx)
- [ ] 编写 `frontend/nginx.conf` 支撑 SPA 路由 fallback 并反代 `/api` 和 `/ws`
- [ ] 补全并调优根目录的 `docker-compose.yml` (时区 TZ、依赖关系、挂载点)
- [ ] 制作用于最终交付运维人员的部署手册 `docs/DEPLOYMENT.md`

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
- [x] TopoView 组件（纯 SVG+DOM 手写拓扑图，含粒子动画、缩放平移，不依赖 React Flow）
- [x] EndpointDetail 终端详情面板（矩阵/拓扑共享，点击弹出）
- [x] BottomCharts 纯 SVG 底栏图表（温度折线 + 风扇仪表盘 + 24H在线率）
- [x] WebSocket 实时数据推送集成 (Zustand 派发更新)

## Phase 2.4 — KPI 指标优化 (2026-03-02)
- [x] KPI 卡片从交换机维度切换为终端维度（总终端/活跃/离线/告警）
- [x] 移除 useCountUp 动画，避免 WS 推送时数字归零闪烁
- [x] 健康率、在线率、拓扑终端计数统一口径（online + ready = 活跃）
- [x] 告警时间戳兼容：WebSocket trap_received 强制添加 created_at 兜底

# 任务回顾 (Review)

- `2026-03-02`:
  - **文档同步大整理**：全量审计并修正了 README / Refactor Plan / todo / HANDOVER / metrics_reference / frontend_plan 中与代码不一致的描述。
  - 关键变更记录：拓扑图从 React Flow 改为纯 SVG+DOM；底栏图表从 ECharts 改为纯 SVG；KPI 从交换机改为终端维度；矩阵从 hover 改为点击详情。
  - 创建了综合交接文档 `docs/HANDOVER.md`（已完全同步）和 Implementation Plan（存入 artifact 供下一 session 使用）。

- `2026-02-27`:
  - 成功解决了在 SNMP 通讯、React 流中遭遇的各种 "Invalid date" 及 Canvas 染色越界 BUG。全面排查并重置了后端多台超规模模拟器的吞吐限制，保证系统安全起飞。
  - 完成并整理工作移交手册 `docs/HANDOVER.md`，交接剩余的管理后台 (Admin Panel) 页面开发任务给下一任。
  - 整理并提交了后端的生产级 SNMP 轮询器重构（含复用引擎池、批量写入、告警去重）、Metrics API、以及前端 React Vite 脚手架源码至 `feat/full-refactor` 分支。
  - 保持了 `tasks/todo.md` 和 `tasks/lessons.md` 的同步更新。

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
