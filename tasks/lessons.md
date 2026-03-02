# 经验教训 (Lessons Learned)

## 模式识别 (Pattern Recognition)

- 初始创建项目时，遵循用户定义的任务管理流程。

## 🔴 核心教训：数据源可信度优先级 (2026-02-26)

**犯的错误**: 在做 OID 映射和模拟器时，没有首先要求并阅读 KVM 产品的 MIB 说明书（权威文件），而是依赖了用户自写的模拟器代码（不完全可信）。这导致了可能有基于错误假设的 OID 映射。

**正确做法**:
1. **永远先确认数据源可信度等级**:
   - 🟢 L1 最高: MIB 规范文件、厂商官方文档
   - 🟢 L2 高: 真实设备的原始日志
   - 🟡 L3 中: 官方使用教程
   - 🔴 L4 低: 自编模拟器代码
2. **有冲突时，以高优先级数据源为准**
3. **在开始任何 OID 相关工作前，先阅读完所有 MIB 文件**
4. **模拟器必须严格基于 MIB 定义，不能自行推测**

## pysnmp v6 迁移关键差异 (2026-02-26)

1. **`pysnmp.carrier.asyncore` 已移除** → 用 `pysnmp.carrier.asyncio` 或 socket 替代
2. **`bulkCmd` 不再是 async iterator** → 是单次 `async` 调用，返回 `tuple`，需手动循环实现 WALK
3. **`bulkCmd` 返回结构**: `var_bind_table` 是 `list[list[ObjectType]]`（嵌套一层 list）
4. **`ObjectType[0]` 是 `ObjectIdentity`**，`str()` 返回 MIB 名称，**不是数字 OID**。用 `ObjectIdentity.getOid()` 获取 `ObjectName`，再 `tuple()` 转数字元组
5. **`endOfMibView` → `EndOfMibView`**, **`noSuchObject` → `NoSuchObject`** (大写)
6. **这些是类而不是实例**，需要 `EndOfMibView()` 和 `NoSuchObject()` 加括号实例化
7. **`passlib` + `bcrypt>=5.0` 不兼容**，需要 pin `bcrypt==4.0.1`

## SQLite 兼容性注意事项

- PostgreSQL 的 `JSONB` → 通用 `JSON`
- 复合主键在 SQLite 中不支持 nullable → 改用自增 `id`
- TimescaleDB hypertable 必须条件跳过

## 生产级架构教训 (2026-02-26)

### 1. 并发轮询必须限流
500 台设备 `asyncio.gather(*)` 会瞬间打爆 SNMP 和数据库连接。**必须用 `asyncio.Semaphore` 限制并发上限（20-30 台/批）**。

### 2. SnmpEngine 不能每次创建
`SnmpEngine()` 创建开销很大（初始化 MIB Controller + Transport Dispatcher）。**必须用对象池复用**。

### 3. 数据库写入必须批量
`for m in list: db.add(Model(**m))` 在 1 万条时极慢。**必须用 `insert(Table).values(list)` 批量插入**。

### 4. 告警必须去重
没有去重 → 同一个异常每分钟产生一条告警 → 一小时 60 条。**查询最近 N 分钟内同设备同指标未解决告警，存在则跳过**。

### 5. APScheduler + Uvicorn multi-worker = 灾难
多 worker 时，每个 worker 各自启动一个 APScheduler 实例 → 重复轮询。**单 worker 或独立轮询进程**。

### 6. 数据库连接池要匹配并发量
`pool_size=10` 在 500 设备场景下不够。**推荐 pool_size=20, max_overflow=40, pool_recycle=1800s**。

## 运行及部署教训 (2026-02-26)

### 1. 后端依赖启动的虚拟环境路径
当手动启动后端服务时，**必须**使用它在目录下的专属虚拟环境 Python 可执行文件，否则会出现找不到如 `apscheduler` 等依赖。
`H:\WORK\I\kvm-dashboard\backend\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`

## Admin 与用户页面必须是一体化的 (2026-03-02)

### 1. Admin 配置必须在用户页面生效
Admin 的别名管理、OID 开关等配置如果只存进数据库但用户页面不读取，就是**割裂的假功能**。正确做法：
- mainStore 在 `fetchAll()` 时一并拉取 aliases 和 oidConfigs
- 提供 `getDisplayName(id, fallback)` 全局 helper
- DeviceCard / AlertStream / BottomCharts / Dashboard 芯片条 全部使用别名
- DeviceCard 根据 `display_enabled` 动态显隐指标

### 2. SnmpEngine 池污染问题
首次连接失败后，引擎内部 TransportDispatcher 进入坏状态。放回池中 → 后续所有请求都失败。**连接失败时必须 discard 而非复用**。

### 3. API 调用必须符合参数约束
后端 `device_id = Query(...)` 标记为必填参数，前端调用时漏掉会直接 422。**写 API 调用前先检查后端签名**。

### 4. 每个页面都需要退出按钮
没有退出按钮 = 普通用户被困在 Dashboard 无法切换账号。所有受保护页面（Dashboard、Admin）都必须提供退出入口。

