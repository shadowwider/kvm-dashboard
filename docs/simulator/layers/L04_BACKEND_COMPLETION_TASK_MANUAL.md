# L04 后端完成层任务手册

> 状态：Ready to start after L3 Accepted
> 负责人：Simulator/Dashboard 后端开发人员
> 合并旧范围：原 L4 协议、L5 生命周期、L6 Bridge、L7 API/WS
> 最终交付：一个无需 Simulator UI 也能完整验收的 SNMP 模拟服务器

## 1. 开工前必须读什么

先读总入口：

1. `docs/simulator/REFERENCE_FILE_REGISTER.md`
2. `docs/simulator/TWO_STAGE_COMPLETION_PLAN.md`
3. `docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md`
4. `docs/reference/GD_MIB_DIFF_REGISTER.md`
5. `docs/reference/docs/devices/` 下四份整理后设备字典
6. `docs/simulator/layers/L01_MIB_GOLDEN_CONTRACT.md`
7. `docs/simulator/layers/L01_TRAP_EVIDENCE_CONTRACT.md`
8. `docs/simulator/layers/L02_PROFILE_MODEL_CONTRACT.md`
9. `docs/simulator/layers/L03_RUNTIME_STATE_CONTRACT.md`
10. `docs/simulator/layers/L03_PATCH_PATH_AND_TRANSACTION_CONTRACT.md`
11. `docs/simulator/decisions/ADR-004-STATE-KEYS-AND-COMPOSITE-INDEXES.md`
12. `docs/simulator/verification/L03_RUNTIME_STATE_REPORT.md`
13. `docs/simulator/api/SIMULATOR_API_V1_CONTRACT.md`
14. `docs/simulator/PROBLEM_DISCOVERY_CHECKLIST.md`

机器真值必须直接使用：

```text
backend/tests/golden/simulator/*.objects.json
backend/tests/golden/simulator/trap_formal.json
backend/tests/golden/simulator/trap_legacy_dashboard_v1.json
backend/simulator/catalog/l2_profiles.json
backend/simulator/catalog/l2_default_fixtures.json
```

禁止去仓库外原始 MIB、`docs/reference/docs/evidence`、日志或网络重新验证。
需要改变 OID/type/access/index/Trap 时，先回到 L1；需要改变 Profile/fixture 时，
先回到 L2；需要改变 path/value/transaction 时，先回到 L3。

## 2. 当前已经完成到哪里

后端接手时可以直接依赖：

- Windows port 模式启动、doctor/smoke、状态诊断；
- 五份独立对象 Golden 和两份 Trap Golden；
- 五个 typed Profile，CCDM 为 20 表/142 可 GET 叶且零 drift；
- 显式 fixture row，无 index range 自动扩展；
- L3 typed runtime、canonical scalar/table/composite-index path；
- strict type/enum/range/string/optional 校验；
- 最多 100 项 batch、working copy、一次 revision/event；
- action/reset 状态机、幂等、故障零副作用和防御性 snapshot；
- 当前 REST/WS、每设备 `SnmpAgent`、Trap sender、Bridge 和 TopologyStore 原型。

不要重写上述底座。当前缺口集中在协议真实性、外部副作用事务、正式 API 和
Dashboard 多 Profile 集成。

## 3. 要交付的后端能力

### A. SNMP renderer 与 Agent

- `SnmpAgent` 每个请求只消费一个 `renderable_snapshot()` 和一个 revision；
- 从 L2 OID template + L3 numeric index tuple 构造 immutable OID snapshot；
- OID 数值排序，不按字符串排序；
- 正确实现 GET、GETNEXT、GETBULK、EndOfMibView；
- `nonRepeaters`、`maxRepetitions`、空/负/超量输入有上限和测试；
- scalar 使用 `.0`，table/Entry/index `not-accessible` 节点不伪装为可 GET；
- ASN.1 类型转换失败必须进入 Agent status/API/日志，不得静默超时；
- SNMP SET 统一返回 notWritable，除非未来单独建立授权层；
- connected/disconnected/powered_off 与 Agent 是否响应完全一致。

### B. Trap

- formal/legacy layout 逐字段与 L1 Golden 对齐；
- state-backed Trap 先提交 L3，再从同 revision 产生内容；
- target 只接受当前 topology 的 device ID，不接受任意 host；
- 多设备同 host/不同端口不调用单结果查询猜设备；
- 捕获 BER/varbind 顺序、notification OID、level/message、source identity；
- 发送失败可诊断，但不能回滚或伪造已经成功的 L3 commit。

### C. 生命周期与 TopologyStore

- start：validate → reserve bindings → build runtime → start Agent → wait ready
  → Bridge prepare/reconcile → commit active pointer；
- switch 失败时旧 topology/runtime/Agent/Bridge 保持可用；
- stop 等待 Agent 线程退出、释放 UDP、清理 Bridge ownership；
- power_off/restore 的 Agent 副作用失败有补偿或明确 degraded state；
- reset 不冒充 topology lifecycle transaction；
- store 使用 schema version、进程锁、临时文件 + atomic replace；
- preset 只读、active topology 禁删、保存无损、失败不破坏原 JSON；
- 进程退出、重复 stop、端口占用、bind 失败和半启动全部可重复测试。

### D. Dashboard Bridge 与采集

- manifest 明确 Profile ID/version、poll mode、host/port、endpoint/route 来源；
- Dashboard 不得把非 CCDC Profile 套进 CCDC OID 计划；
- session/epoch/revision 防止旧进程覆盖新进程；
- heartbeat/lease/正常 stop/崩溃超时有清理策略；
- Trap identity 与轮询 identity 使用相同 device/run/session 归属；
- Bridge token 只来自环境变量，status/异常/文档全部脱敏；
- Bridge 失败不影响本地 Simulator 自洽，但 status 明确 degraded。

### E. REST、OpenAPI 与 WebSocket

- 将 `api/SIMULATOR_API_V1_CONTRACT.md` 从 Draft 冻结为 Accepted；
- 去除或 deprecated 重复 `scenario/reachability` 产品入口；
- `/status`、profiles、topology CRUD、state、patch、action、trap、reset
  有固定 request/response/error fixture；
- 增加 expected revision 或明确冲突控制；
- 422/404/409/503 等统一为稳定错误 code/details/retryable；
- WS 首包 snapshot，后续事件按 revision，支持 gap/refetch 和断线重连；
- topology start/stop/reset、patch/action、Agent/Bridge/Trap 状态都有事件；
- 认证、Origin、host/port allowlist、rate/size limit 和 SSRF 边界有测试。

## 4. 推荐实施顺序

这不是四个新层。按垂直切片推进：

1. 先完成 immutable OID snapshot + 真实 UDP Golden；
2. 把 lifecycle prepare/commit/rollback 接到同一 snapshot/revision；
3. 冻结对应 REST/WS fixture，前端即可滚动接入；
4. 完成 Bridge、多 Profile 和安全；
5. 一次性执行 L4 全 Gate。

协议、生命周期、Bridge、API 可以由不同开发人员并行，但共享模型只能来自
L1–L3；任何人不得复制一份自己的 OID map、Profile 或 runtime dict。

## 5. 必须新增或更新的文件

必须新增：

```text
docs/simulator/verification/L04_BACKEND_COMPLETION_REPORT.md
backend/tests/golden/simulator/api/*.json
backend/tests/golden/simulator/udp/*.json
```

必须完成并更新：

```text
docs/simulator/api/SIMULATOR_API_V1_CONTRACT.md
docs/simulator/PROBLEM_DISCOVERY_CHECKLIST.md
backend/kvm_simulator_README.md
docs/simulator_startup_connection_guide.md
```

实现文件主要位于：

```text
backend/simulator/snmp_agent.py
backend/simulator/profiles.py
backend/simulator/state.py
backend/simulator/main.py
backend/simulator/bridge.py
backend/simulator/topology_store.py
backend/app/api/simulator.py
backend/app/snmp/*
```

## 6. 必须新增的验收测试

- 独立 Golden 驱动五 Profile UDP GET + WALK + GETBULK；
- composite index、numeric ordering、缺失 row、optional disabled；
- renderer/ASN.1 failure 可见且 Agent 继续服务或进入明确 failed；
- formal/legacy Trap UDP 捕获；
- start/switch/stop/power/restore 的 bind/start/stop/Bridge 故障注入；
- store 截断写、并发写、active delete、round trip；
- OpenAPI drift、所有 REST error、100/101 batch、revision conflict；
- 双 WS 客户端、断线、gap、慢客户端、乱序保护；
- Dashboard 五 Profile manifest/poll mode/cleanup；
- 端口、线程、Bridge ownership 和临时文件无泄漏。

## 7. Definition of Done

只有同时满足以下条件才可标记 L4 Accepted：

1. 不启动 UI 也能用脚本完成 topology CRUD、start、state patch、action、Trap、
   reset、switch、stop；
2. 同一次写入在 API、WS、SNMP 和 Bridge manifest 中观察一致；
3. 真实 UDP Golden、生命周期故障、API/WS 和 Dashboard 集成全通过；
4. 当前后端全回归无失败，新增测试不依赖运行时代码生成 expected；
5. 独立审计 P0=0、P1=0；
6. API contract、验证报告、问题清单、README 和真实 Git commit 完成；
7. 明确记录未做现场设备验证，静态/本地仿真不冒充厂家实机兼容。

L4 Accepted 后，前端不再读取 Python 实现猜接口，只依赖 Accepted API contract
和 Golden fixtures。
