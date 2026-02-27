# 🤝 KVM Dashboard 工作交接手册 (Handover Document)

你好，我是负责起草 KVM 监控系统的上一任全栈 AI 开发者。
你看到这份文档时，恭喜你接手了一个非常纯粹、性能强悍且极具极客风格的现代实时大屏监控项目。

以下是我为你精心整理的项目当前状态、大坑预警以及全流程测试指南。请务必仔细阅读！

---

## 1. 我们的工作进度 (What is done)

目前，整个从协议底层到前端高层的数据流**已经完全打通**：
- **[底层驱动]**：重构了 SNMP 解析端。采用最新的 `pysnmp v6`（兼容纯 asyncio），并实现了基于原生厂商 MIB的自由轮询架构。支持大批量提取（GETBULK/WALK），引入了并发信号量防洪，和引擎池(Engine Pool)复用。
- **[数据库]**：使用 FastAPI + SQLAlchemy 2.0 构建。在测试环境使用轻量级 `SQLite`，在生产环境直接无缝切换至支持高性能时序压缩聚合的 `PostgreSQL + TimescaleDB` 套件。
- **[前端架构]**：搭建好了 `React 18 + Vite`，设计好了毛玻璃 (glassmorphism) 的顶级炫酷深色 UI。引入了全局状态管理库 `Zustand`，并完成了完整的 Token 拦截登录和状态维持。
- **[实时图表]**：核心的可视化面板已经 100% 竣工。包含了基于 `lucide-react` 的信息流栏，结合 `ReactFlow` 所手写的一套数学 Radial 树状拓扑图展开，以及底部集成 `ECharts` 用来展现实时温度流面积图。
- **[WebSocket 实时传输]**：封装了原生的 WebSocket，结合 Zustand，成功实现了后端轮询的设备状况和突发告警能在 1 秒内无刷新地推送到大屏的 DeviceCard 和右侧 AlertStream 组件中！

---

## 2. 还有什么没做 (What is NOT done)

**⚠️ 下面的任务是你接手后需要第一优先完成的：**

- **后台管理与配置面板 (Admin Dashboard)**
  目前整个大屏主要是数据 **消费与展示层**。但是作为管理员，需要一个能够对系统底层数据进行增删改查的独立后台页面：
  1. 开发一个路由比如 `/admin`，进入管理页。
  2. 需要能够实现：设备的自定义名称修改，对各个 OID 参数的自由启停（即配置表 `oid_map`）。能够切换语言（中英文）。切换暗黑和白天模式，用户列表和密码管理。
  3. 配置全局设定的控制开关（告警启用等）。

---

## 3. 测试指南 (How to spin up the system)

为了测试全链路的大流量性能和 UI 展示，我在后端专门为你写了一个能强悍模拟 **3台大容量交换机 + 60个外挂终端负载并发**的独立程序。请按照以下三个步骤（分别开启三个控制台窗口）来启动整个生态：

1. **启动后端服务 (FastAPI API + Scheduler + WebSocketHub)**
   ```bash
   cd h:\WORK\I\kvm-dashboard\backend
   .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   *备注：每次启动都会清理并初始化种子数据库内容。由于我们暂不连 TimescaleDB，因此使用的测试库名为 `kvm_test.db`。如果想彻底重建新库，直接删除该文件即可。*

2. **启动虚拟 SNMP 机房 (Simulators)**
   这个脚本必须保持运行，它是我们海量设备测试的数据源！
   ```bash
   cd h:\WORK\I\kvm-dashboard\backend
   .venv\Scripts\python run_simulators_large.py
   ```
   *启动后，主服务会通过 APScheduler 自动开始每 60 秒（或者第一秒立刻）向该模拟器进行大规模并发数据请求。*

3. **启动前端大屏 (React + Vite)**
   ```bash
   cd h:\WORK\I\kvm-dashboard\frontend
   npm run dev -- --force
   ```
   *前端入口在 `http://localhost:3000`。你可以使用默认的 `admin` / `admin123` 登录！*
   *(这里的 `--force` 是一个防止 Vite 依赖预加载抽风失效的小技巧)*

---

## 4. 💣 最重要的三个坑预警 (Major Pitfalls)

为了解决这三个隐藏极深的 BUG，我已经帮你踩完了泥潭。当你后续改动代码时，**千万不要重蹈覆辙**：

1. **pysnmp 底层类型嗅探灾难**
   **问题**: 最新的 `pysnmp v6` 对于入参类型检查非常严格。如果 SNMP 对象接受的是 OID（比如 `1.3.6.1...`），而模拟器或者我们的入参返回了字符串 `OctetString`，它会因为把小数点当成特殊字符导致在控制台疯狂抛出：`Malformed Object ID (49, '46') at ObjectName` 或 `TypeError("unsupported operand type(s) for +: 'int' and 'str'")` 的连环报错并彻底弄穿整个 asyncio 的底线。
   **解决**: `poller.py` 中，调用 `ObjectType(ObjectIdentity(tuple))` 时必须传元组 `(1,3,6,...)` 或完全合法的解包对象，且模拟器的返回值必须手动转换为原生的 `pMod.ObjectIdentifier()`。

2. **数据库兼容性语法与时间类型的拉跨**
   **问题**: 我们后端代码本来是用 Postgres(Timescale DB) 写的，里面的 `INTERVAL '24 hours'` 这种原生字面量写入 SQLite 这个本地开发库时会无情报 500！
   **解决**: 所有涉及时间对比查询 API (如 `metrics/history`)，都已经在 SQLAlchemy 侧用上了原生的 `datetime(timezone.utc)` 和 `>= cutoff_time`。以后切忌在 Python 中直通字符串原生 SQL 进行时间运算。还有，因为前端 `date-fns` 解析 `alert.created_at` 如果遇到异常时会产生白屏崩溃，所以请始终保持使用 `isValid()` 作为兜底时间显示的判断机制。

3. **并发死锁导致的轮询队列雪崩**
   **问题**: APScheduler 由于是同步单例机制执行的。如果有设备已经离线、拔网线或者配错了 IP，那么针对该设备复杂的 WALK （尤其是拥有数百个终端），将会导致这个协程由于 Timeout 不断重试而阻塞整整 60 秒！这会导致下一个 60 秒到来时该任务实例还在跑，就会触发可怕的 `skipped: maximum number of running instances reached` 警告，新数据不再进库。
   **解决**: 在 `poller.py` 前半段针对最基础的 `sysObjectID` 读取一旦遇到超时判定，系统将立刻 `Early Return`，放弃后续长流水线的轮询，并将该设备标为 `offline`。同时把所有的并行的 SNMP 走访全部使用 `asyncio.gather` 多开出去。请一定要维持当前的超时及协程打扫逻辑，否则后患无穷！

---

## 💌 给继任者的信

嗨，来自未来的全栈同学：

接下这个盘子，意味着你要开始操刀真正能够承受成百上千次刷新、并且绝不能出错崩溃的生产力核心工具了。

从最初的 Python 烂代码缝缝补补，到目前这一版的严谨架构，我们已经跨越了最难的基础建设（SNMP 解析，引擎锁流，状态缓存，WebSocket推送，React 骨架）。现在呈现给你的是一套高速运转、充满深色玻璃与发光霓虹特效赛博朋克风的高能大屏！

接下来的重中之重就是将“可维护性”拉满——让我们的普通系统管理员也能通过图形化的管理面板，来自由调度这些复杂的设备和指标，再也不必跑到命令行里调库表配置了。

加油，我相信你一定会对这套代码感到满意并且能做出令人惊艳的新功能。这个系统就放手交给你了！

—— 上一位抗压通过全部 BUG 测试的 Antigravity AI
