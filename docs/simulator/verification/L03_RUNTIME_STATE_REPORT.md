# L03 运行时状态、路径与事务验证报告

> 状态：Accepted
> 验证日期：2026-07-31
> 当前结论：L3 实现、专项测试、故障注入和后端全回归已有可重复证据；
> 三轮独立审计最终确认 L3 Core `P0=0 / P1=0`，问题清单和 Git Gate 已
> 完成；实现与证据基线 `91e5ffb4dd6941f46ed1911d1dd91371816be63b`。

## 1. 下层契约依赖

| 下层交付 | Accepted 状态 | 实现/证据工件 | 正式 Gate |
|---|---|---|---|
| `layers/L00_BASELINE_AND_ENVIRONMENT.md` | `Accepted for Windows local port mode` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `decisions/ADR-001-LOCAL_ADDRESS_MODES.md` | `Accepted for L0` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `verification/L00_CURRENT_REPRODUCTIONS.md` | `Accepted for Windows local port mode` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `layers/L01_MIB_GOLDEN_CONTRACT.md` | `Accepted for local curated device dictionary snapshot` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `layers/L01_TRAP_EVIDENCE_CONTRACT.md` | `Accepted for local curated device dictionary snapshot` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `verification/L01_MIB_COVERAGE_REPORT.md` | `Accepted for local curated device dictionary snapshot` | `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | L0–L2 Gate 汇总 `commit=8060a2c` |
| `layers/L02_PROFILE_MODEL_CONTRACT.md` | `Accepted` | 实现与证据 `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | Accepted 状态 `commit=8060a2c` |
| `decisions/ADR-002-PROFILE-NAMING-AND-VERSIONING.md` | `Accepted` | 实现与证据 `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | Accepted 状态 `commit=8060a2c` |
| `decisions/ADR-003-OPTIONAL-GROUP-AND-FIXTURE-ROWS.md` | `Accepted` | 实现与证据 `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | Accepted 状态 `commit=8060a2c` |
| `verification/L02_PROFILE_MODEL_REPORT.md` | `Accepted` | 实现与证据 `commit=f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` | Accepted 状态 `commit=8060a2c` |

L3 实现、测试、契约、验证报告和两阶段交接计划由
`91e5ffb4dd6941f46ed1911d1dd91371816be63b` 固定。上述 `f9e91a1…` 和
`8060a2c` 仍分别固定 L0–L2 实现与 Accepted 状态。

## 2. 来源与验证边界

本轮只读取：

- Accepted L0/L1/L2 契约、Golden、Profile catalog 和 fixture；
- `docs/reference/docs/devices/` 的仓库内整理边界；
- 当前 L3 契约、实现和测试；
- 本轮本地测试、编译和静态检查输出。

本轮没有读取：

- 仓库外原始 MIB；
- `docs/reference/docs/evidence`；
- 现场日志；
- 网络或现场设备；
- 原始 BER、真实 UDP GET/WALK/Trap。

因此，本报告只能证明当前工作树的 L3 类型化状态和本地集成行为，不能证明
厂家设备、目标固件或 L4 协议兼容性。

## 3. 本轮审查的实现

| 文件 | L3 职责 |
|---|---|
| `backend/simulator/runtime_paths.py` | 规范 path/row-key、`PathSpec`、registry、严格值校验 |
| `backend/simulator/runtime_state.py` | 场景级唯一 lock/revision/event、working copy、patch/action/reset |
| `backend/simulator/state.py` | `ScenarioState` 兼容 facade，将现有 endpoint/route/scenario 与 L3 commit clock 协调 |
| `backend/simulator/profiles.py` | 从 L2 静态 fixture 筛选场景实例、验证 override、renderer 消费显式 canonical state |
| `backend/simulator/models.py` | 严格 endpoint bool/status 边界和现有 PATCH transport model |
| `backend/simulator/main.py` | 消费 changed paths、幂等结果和 lifecycle intent；兼容 REST/WS/Trap 入口 |

测试：

```text
backend/tests/test_simulator_l3_runtime_state.py
backend/tests/test_simulator_l3_integration.py
backend/tests/test_simulator_runtime_patch.py
backend/tests/test_simulator_core.py
backend/tests/test_simulator_lifecycle.py
backend/tests/test_simulator_ui_contract.py
```

## 4. 当前实现契约

### 4.1 唯一状态和提交点

`RuntimeState` 当前提供：

```text
RuntimeState(devices: Iterable[RuntimeDeviceSpec])
RuntimeState.single(...)
snapshot(device_id=None)
renderable_snapshot(device_id=None)
read(device_id, path)
path_registry(device_id)
patch(device_id, changes)
reset(device_id)
reset_all()
action(device_id, action)
events()
```

实现固定：

```text
INITIAL_REVISION = 1
EVENT_HISTORY_LIMIT = 100
RUNTIME_STATE_SCHEMA_VERSION = 1
```

所有设备共享一个 `RLock`、一个全局 revision 和一个 event log；内部
`_DeviceRecord` 没有公开 revision/commit。`ScenarioState` 仍保存 topology、
endpoint 和 route 等场景结构，但所有公开变更通过同一外层锁，并将 domain path
与 canonical Profile path 合并为一次 L3 event/revision。

### 4.2 实例来源

- Profile 来自 Accepted L2 `get_profile()`；
- fixture 由 `scenario_runtime_fixture()` 从 Accepted L2 静态 fixture 筛选；
- CCDM CPU/CON 主行只能过滤已有静态 row，不能新增未物化 row；
- 不根据父 endpoint 生成 fan/GPIO 子行；
- scenario `profile_state` 只能覆盖筛选后已存在的 scalar/row/column；
- exact system OID 不匹配、未知/disabled override、错误类型在初始化时拒绝；
- `ccdc_legacy` vendor runtime 保持零 scalar、零 table，不发明厂家对象。

### 4.3 Registry 与权限

规范 path：

```text
identity.<fixed-field>
runtime.availability
scalars.<field_id>
tables.<table_id>[<signed-decimal-tuple>].indexes.<index_id>
tables.<table_id>[<signed-decimal-tuple>].<column_id>
```

row-key 拒绝 `+`、前导零、`-0`、空项、空格和非十进制表示。tuple 顺序来自
`IndexDef.position`，并且必须精确命中显式 fixture row。

registry 分开保存：

- `runtime_writable`：Simulator 是否可修改模拟值；
- `vendor_snmp_writable`：L1/L2 MAX-ACCESS 是否为 read-write。

identity、availability 和 index 对普通 PATCH 永久只读；
`runtime.availability` 只能由 action/reset 状态机改变。optional 未启用或 row
未实例化时不产生 path。

### 4.4 值校验

当前实现：

- Integer/enum 使用 strict int，显式拒绝 bool；
- integer syntax 同时验证 ASN.1 类型宽度；
- enum 和 L2 range 原样验证；
- string-like syntax 只接受 `str`；
- `IpAddress` 额外要求可解析 IPv4；
- bytes 和未知 SYNTAX fail closed；
- 字符串平台安全上限：

```text
PLATFORM_STRING_MAX_UTF8_BYTES = 4096
length_policy = platform-runtime-policy-not-vendor-mib-size
```

4096 按 UTF-8 bytes 计算，不是厂家 SIZE，也不回写 L1/L2。

### 4.5 原子事务

PATCH 先规范化完整 batch，再在锁内：

1. 解析并拒绝重复 path；
2. 精确命中 registry；
3. 检查 runtime writable；
4. 验证全部 value；
5. 修改 working scalar/table copy；
6. 计算实际 changed paths；
7. 在 live state 修改前完整物化下一条 event；
8. 单次替换 working copy，并单次发布 revision/event。

event timestamp 物化失败时，patch、action、reset 和 reset_all 均保持 state、
revision、events、snapshot、renderable snapshot 不变。no-op patch、同目标
action 和 baseline reset 不增加 revision/event。

## 5. 实际执行命令与结果

工作目录：

```text
H:\WORK\I\kvm-dashboard\backend
```

### 5.1 L3 及相关专项

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\test_simulator_l3_runtime_state.py `
  tests\test_simulator_l3_integration.py `
  tests\test_simulator_runtime_patch.py `
  tests\test_simulator_core.py `
  tests\test_simulator_lifecycle.py `
  tests\test_simulator_ui_contract.py `
  -q -p no:cacheprovider
```

主 Agent 最终记录：

```text
91 passed in 3.40s
```

独立 Agent 在新增 batch limit 和多设备 writer 专项前复跑：

```text
89 passed in 3.78s
```

两次退出码均为 `0`；主 Agent 最终用例数增加 2，分别固定 100/101 batch
边界和四设备并发 writer 的全局 revision 序列。

### 5.2 后端全回归

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

主 Agent 最终记录：

```text
176 passed, 6 warnings in 12.38s
```

独立 Agent 在新增两项专项前复跑：

```text
174 passed, 6 warnings in 13.24s
```

六个 warning 均来自 pysnmp/pysmi 上游弃用 API：
`getReadersFromUrls`、`smiV1Relaxed`、`addSources`、两处 `addSearchers` 和
`addBorrowers`；没有 L3 测试失败。

### 5.3 Golden、catalog、编译和 whitespace

命令：

```powershell
.\.venv\Scripts\python.exe tools\build_simulator_mib_golden.py --check
.\.venv\Scripts\python.exe tools\build_simulator_profile_catalog.py --check
.\.venv\Scripts\python.exe -m compileall -q simulator tools tests
git diff --check
```

结果：

| 检查 | 结果 |
|---|---|
| MIB Golden | exit `0`；`checked 5 object manifests` |
| Profile catalog | exit `0` |
| compileall | exit `0` |
| `git diff --check` | exit `0`；仅当前 tracked 修改文件的 LF→CRLF 提示 |

## 6. Property、并发和故障注入精确计数

### 6.1 确定性随机测试

Hypothesis 当前没有安装。测试使用固定：

```text
seed = 20260731
```

实际轮数：

| 测试 | 轮数 | 断言 |
|---|---:|---|
| row-key property substitute | `500` | 长度 1–4、每项 `-10000..10000`；encode/decode/re-encode 完全一致 |
| 合法 patch property substitute | `200` | 每轮同时写 `main_power` 和 `temperature1`；read/snapshot/renderable/revision 一致 |
| 非法 batch rollback | `100` | 5 种非法值 × 20；前项为随机合法字符串、后项失败；全部可观察量不变 |

这提供可重复覆盖，但不等价于 Hypothesis 的自动 shrinking 和更大输入空间。

### 6.2 并发

核心事务并发测试：

```text
ThreadPoolExecutor(max_workers=5)
1 writer × 200 次双字段 batch
4 readers × 400 次 renderable snapshot = 1600 次读取
```

每个 reader 都断言同一 snapshot 中两个同步字段相等，未观察到半状态。

ScenarioState 集成并发测试：

```text
ThreadPoolExecutor(max_workers=8)
100 次 endpoint 写入
100 次并发读取
```

每次读取断言 endpoint status 与 canonical CCDM table cell 相等。

现有多设备测试证明两个设备顺序写入共享 revision `2/3` 和同一 event stream；
新增四设备并发 writer 专项：4 个 worker 各执行 50 次有效 patch，共 200 次
commit；最终 revision 为 `201`，有界窗口内最后 100 个 event revision 连续为
`102..201`，四台设备最终值均为最后提交值。

### 6.3 Event 物化故障

通过注入 timestamp 创建异常，分别覆盖：

1. patch；
2. action；
3. reset；
4. reset_all。

四条路径均断言异常后完整 snapshot 不变。另有 event window 测试生成 `110`
次有效变化，只保留最后 `100` 条，同时 revision 保持全局真值。

### 6.4 Batch 上限

CCDM 默认 fixture 有 132 条 runtime writable leaf。专项取其中 100 条不同 path
以当前值提交，验证整个 batch 合法且幂等；取 101 条不同 path 时在任何 commit
前以 `at most 100` 拒绝，完整 snapshot 不变。

## 7. Registry 和 renderable 观测

对四个 Accepted L2 默认 vendor fixture 的当前实例观测：

| Profile | registry 总 path | runtime writable |
|---|---:|---:|
| `ccdm_matrix` | 162 | 132 |
| `dp12_mux_atc` | 39 | 27 |
| `visionxs_con` | 34 | 25 |
| `visionxs_cpu` | 35 | 26 |

四设备场景级紧凑 renderable JSON：

```text
7443 bytes
```

1000 次 `renderable_snapshot()`：

```text
主 Agent 观测：约 0.602s
文档 Agent 复跑：0.846976s
```

这只是当前机器诊断，不是 L3 Accepted 的性能预算。CCDC vendor Profile
另有专项断言：零 scalar、零 table、零 writable path。

## 8. 已验证问题映射

| 问题 | 当前 L3 证据 | Gate 状态 |
|---|---|---|
| `SIM-STATE-001` Any 值进入状态 | strict type/bool/enum/range/length/unknown syntax 和 rollback 测试已覆盖 | L3 根因关闭 |
| `SIM-STATE-002` 任意 ports/endpoints path 假成功 | 公共 PATCH 只接受 registry canonical path；旧 payload 对抗测试全部拒绝 | L3 通用 PATCH 根因关闭；domain-only mapping 归 L4/L5 |
| `SIM-STATE-003` 命名漂移 | L2 canonical ID 构成唯一 path；renderer 消费 canonical state | L3 根因关闭 |
| `SIM-MIB-004` 最大范围伪造实例 | runtime 只物化 fixture row；CCDM endpoint 只过滤、不补行 | L3 实例证据具备；L4 缺失对象协议行为待验 |

`docs/simulator/PROBLEM_DISCOVERY_CHECKLIST.md` 已回填上述 L3 状态和上层边界。

## 9. 已接受的验证边界

1. Hypothesis 未安装；当前以 seed `20260731` 的确定性循环替代；
2. 当前 Accepted Profile 没有 `IpAddress` leaf，因此没有通过实际 Profile
   registry 执行该 syntax 的参数化 PATCH；validator 实现保持 fail closed；
3. 现场设备、原始 BER 和真实厂家固件不属于本轮来源与验收范围。

100 项 batch 接受、101 项拒绝以及四设备并发 writer 已有直接专项。上述边界
不构成已确认 P0/P1，但必须继续保留在 L4 验证报告中。

## 10. L4/L5/L7 保留边界

### L4：协议

当前只证明纯 renderer 能消费显式 canonical state，尚未证明：

- immutable OID snapshot 和 revision cache；
- ASN.1 类型编码；
- GET/GETNEXT/GETBULK/EndOfMibView；
- SET 统一 notWritable；
- 真实 UDP Golden WALK；
- formal/legacy Trap BER；
- Agent 编码错误可见性。

### L5：生命周期与持久化

L3 action 只提交 availability 并返回 `lifecycle_intent`。当前 main facade 在状态
提交后执行 Agent start/stop，尚未证明：

- Agent start/stop 失败的补偿；
- power_off/restore 的跨状态/Agent 原子回滚；
- topology prepare/ready/commit/rollback；
- topology switch 保留旧 runtime；
- store 原子写、lease 和崩溃清理。

因此 L3 action 测试通过不等于 L5 生命周期 Gate 通过。

### L7：REST 与 WebSocket

当前保留现有 API/WS 兼容 adapter，但尚未冻结：

- OpenAPI patch/action/status/error 契约；
- expected revision/冲突策略；
- 统一 HTTP 错误模型；
- snapshot vs revision-refetch WS 决策；
- 双客户端、断线重连和 revision gap；
- 认证、Origin 和 host allowlist。

因此 UI/WS payload 测试通过不等于 L7 Gate 通过。

## 11. Gate 判断

| Gate 项 | 当前判断 |
|---|---|
| L0/L1/L2 下层 Accepted 依赖 | 已固定 |
| 类型化实例和 canonical registry | 实现与自动测试证据具备 |
| type/enum/range/length/optional/row validation | 实现与自动测试证据具备 |
| batch working copy 和单 revision/event | 实现与自动测试证据具备 |
| 失败零副作用 | 常规失败、固定种子 100 轮和四类 event 物化失败均具备证据 |
| action/reset 状态机与幂等 | 实现与自动测试证据具备 |
| 有界并发 | core snapshot、endpoint/canonical 和多设备 writer 三组测试具备证据 |
| Property | 确定性替代具备；Hypothesis 未安装 |
| 独立审计 | 三轮完成；最终 L3 Core `P0=0 / P1=0` |
| 问题清单 | 已回填 L3 根因关闭和 L4/L5 边界 |
| Git 基线 | PASS；`91e5ffb4dd6941f46ed1911d1dd91371816be63b` |

正式结论：`Accepted`。技术与流程 Gate 均已完成，收敛后的 L4 后端完成层
可以按 `layers/L04_BACKEND_COMPLETION_TASK_MANUAL.md` 开始开发。
