# KVM SNMP Simulator 开发参考文件登记表

> 状态：Active
> 日期：2026-07-31
> 用途：后端和前端接手前先按本表确认资料是否存在、是否有权威性、是否允许读取。

## 1. 厂家事实与底层契约

| 文件 | 状态 | 谁必须读 | 用途 |
|---|---|---|---|
| `docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md` | 已有 | 后端必读，前端了解边界 | 五类设备、兼容性和 Profile 总体约束 |
| `docs/reference/GD_MIB_DIFF_REGISTER.md` | 已有 | 后端必读 | 历史差异和资料缺口登记，不代替 Golden |
| `docs/reference/docs/devices/ccdm-controlcenter-digital.md` | 已有 | 后端必读 | CCDM 整理后设备字典 |
| `docs/reference/docs/devices/visionxs-cpu-con.md` | 已有 | 后端必读 | VisionXS CPU/CON 整理后设备字典 |
| `docs/reference/docs/devices/dp12-mux-atc.md` | 已有 | 后端必读 | DP12 MUX/ATC 整理后设备字典 |
| `docs/reference/docs/devices/cc160-controlcenter-digital.md` | 已有 | 后端必读 | CCDC/CC160 本地整理边界 |
| `backend/tests/golden/simulator/*.objects.json` | L1 Accepted | 后端必读 | OID、SYNTAX、MAX-ACCESS、INDEX 独立机器真值 |
| `backend/tests/golden/simulator/trap_*.json` | L1 Accepted | 后端必读 | formal/legacy Trap 布局真值 |
| `backend/simulator/catalog/l2_profiles.json` | L2 Accepted | 后端必读，前端不得直接复制 | typed Profile schema |
| `backend/simulator/catalog/l2_default_fixtures.json` | L2 Accepted | 后端必读 | 显式实例，不允许按 range 生成库存 |

来源硬边界：后续开发只使用上述仓库内整理文件、Accepted Golden 和 typed
catalog/fixture。不得转去仓库外原始 MIB、`docs/reference/docs/evidence`、现场
日志或网络自行“重新解释”厂家对象。需要新事实时，先修改 L1/L2 和对应 Gate。

## 2. 已完成层文档

后端必须依次读 L0–L3；前端至少读 L2/L3 和两阶段计划：

- `docs/simulator/layers/L00_BASELINE_AND_ENVIRONMENT.md`
- `docs/simulator/decisions/ADR-001-LOCAL_ADDRESS_MODES.md`
- `docs/simulator/verification/L00_CURRENT_REPRODUCTIONS.md`
- `docs/simulator/layers/L01_MIB_GOLDEN_CONTRACT.md`
- `docs/simulator/layers/L01_TRAP_EVIDENCE_CONTRACT.md`
- `docs/simulator/verification/L01_MIB_COVERAGE_REPORT.md`
- `docs/simulator/layers/L02_PROFILE_MODEL_CONTRACT.md`
- `docs/simulator/decisions/ADR-002-PROFILE-NAMING-AND-VERSIONING.md`
- `docs/simulator/decisions/ADR-003-OPTIONAL-GROUP-AND-FIXTURE-ROWS.md`
- `docs/simulator/verification/L02_PROFILE_MODEL_REPORT.md`
- `docs/simulator/layers/L03_RUNTIME_STATE_CONTRACT.md`
- `docs/simulator/layers/L03_PATCH_PATH_AND_TRANSACTION_CONTRACT.md`
- `docs/simulator/decisions/ADR-004-STATE-KEYS-AND-COMPOSITE-INDEXES.md`
- `docs/simulator/verification/L03_RUNTIME_STATE_REPORT.md`
- `docs/simulator/PROBLEM_DISCOVERY_CHECKLIST.md`

## 3. 产品、运行和集成资料

| 文件 | 状态 | 说明 |
|---|---|---|
| `README.md` | 已有 | 整体项目启动与架构入口 |
| `backend/kvm_simulator_README.md` | 已更新到 L3 | Simulator 能力、人工测试和安全边界 |
| `docs/simulator_startup_connection_guide.md` | 已更新到 L3 | Dashboard/Simulator/UI 连接方式 |
| `tasks/api_docs.md` | 已有但不是 Simulator 最终契约 | Dashboard 现有 API 背景，不得代替 L4 API contract |
| `docs/metrics_reference.md` | 已有 | Dashboard 指标含义和计算口径 |
| `frontend/README.md` | 已有 | Dashboard 前端开发入口 |
| `docs/simulator/api/SIMULATOR_API_V1_CONTRACT.md` | 本轮补建，Draft | L4 必须冻结，L5 只能按其 Accepted 版本接入 |

仓库 `AGENTS.md` 曾提到 `docs/HANDOVER.md` 和 `tasks/lessons.md`，当前工作树中
这两个文件不存在。它们不是本次 Simulator 的事实来源，也不要求开发人员到
仓库外寻找；相关 Simulator 交接内容已经由本登记表、两份任务手册和各层验证
报告承接。若未来恢复这两个通用文件，应更新登记表后再引用。

## 4. 当前新增的接手手册

- 后端：`docs/simulator/layers/L04_BACKEND_COMPLETION_TASK_MANUAL.md`
- 前端：`docs/simulator/layers/L05_FRONTEND_COMPLETION_TASK_MANUAL.md`
- 总计划：`docs/simulator/TWO_STAGE_COMPLETION_PLAN.md`

接手人不需要从聊天记录还原任务。三份文件必须始终同步记录当前完成状态、
剩余范围、验收命令和上层边界。

## 5. `Agent` 术语不要混淆

- `backend/simulator/snmp_agent.py` 的 **SNMP Agent** 是网络协议术语：它监听
  UDP SNMP 请求并模拟一台设备的响应，不是人工智能。Dashboard 必须能轮询
  它，所以产品运行时需要它。
- Codex 的 **子 Agent** 是开发过程中的并行 AI 工作单元，用来分工实现或做
  独立审计；它们共享工作区、完成后退出，不会被部署到 Simulator 后端，也
  不会在软件后面长期运行一个“智能服务”。

文档写 `Agent` 时必须加限定词：`SNMP Agent`、`Agent Supervisor` 或
`Codex 子 Agent`，不能混写。
