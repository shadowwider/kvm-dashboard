# L02 Profile 模型验证报告

> 状态：Accepted
> 更新日期：2026-07-31
> 当前结论：Profile catalog、显式 fixture、专项测试、全回归、独立复审和可审计 Git 基线均已完成。

## 1. 验证范围

- L1 Golden → L2 Profile 等价投影；
- `ccdc_legacy` vendor Profile 保持 0 objects，历史 OID 与
  project-legacy compatibility adapter 隔离；
- 五个 Profile 的精确 sysObjectID、证据状态和版本；
- vendor / canonical / UI label key 三层命名；
- OID、限定名、内部 ID 和同表列号唯一性；
- enum/range 与 fixture 初始值；
- optional 默认关闭；
- fixture 显式 scalar/table rows；
- schema-only metadata 的大小和生成时间；
- Profile 模块不依赖 state/runtime、socket、FastAPI、WebSocket 或 UI。

不包括：

- L3 运行时状态、PATCH 和事务；
- L4 真实 UDP、ASN.1 和 Trap 编码；
- L5+ 生命周期、Bridge、API、UI 或拓扑交互；
- 原始 MIB、仓库外 evidence 或现场设备复核。

## 2. 下层证据固定

下层状态、当前工作树边界和七份 L1 Golden SHA-256 见
`layers/L02_PROFILE_MODEL_CONTRACT.md` 1 节。

L0/L1/L2 工件提交：

```text
f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc
```

该提交包含本报告所验证的 L0/L1/L2 代码、catalog、fixture、golden、测试和
文档工件，是 L3 的实现与证据基线。

## 3. L1 起始差异

L1 已记录：

| Profile | 当前/Golden 表数 | 当前/Golden 可读叶 | 缺失 | 多余 | 非法初始值 |
|---|---:|---:|---:|---:|---:|
| `ccdm_matrix` | 15/20 | 134/142 | 11 | 3 | 4 |
| `visionxs_cpu` | 2/2 | 28/28 | 0 | 0 | 0 |
| `visionxs_con` | 2/2 | 27/27 | 0 | 0 | 0 |
| `dp12_mux_atc` | 4/4 | 35/35 | 0 | 0 | 0 |

CCDC Golden 故意为 0 对象、0 表。L2 的目标不是给 CCDC 补对象，而是保留
`legacy-unverified` 边界。现有历史 OID 只能存在于
`project-legacy-compatibility` adapter，不得进入 vendor Profile 投影。

`L01_PROFILE_DRIFT.json` 只比较 L2 修改前的 OID、表数和字面初始值，作为
历史起点保持 `ok=false`。L2 当前结果必须另写
`L02_PROFILE_CATALOG_DRIFT.json`，并完成 syntax、max-access、enum、range、
unit、index、optional 和 evidence 的全字段投影比较。

## 4. 实际验收命令

从：

```text
H:\WORK\I\kvm-dashboard\backend
```

执行 L2 专项：

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\test_simulator_profile_model.py `
  tests\test_simulator_profile_golden_drift.py `
  tests\test_simulator_profiles.py -q
```

重新生成 drift：

```powershell
.\.venv\Scripts\python.exe tools\report_simulator_profile_drift.py `
  --output ..\docs\simulator\verification\L02_PROFILE_CATALOG_DRIFT.json
```

执行 L1/L2 工件一致性与全部后端测试：

```powershell
.\.venv\Scripts\python.exe tools\build_simulator_mib_golden.py --check
.\.venv\Scripts\python.exe tools\build_simulator_profile_catalog.py --check
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m compileall -q simulator tools tests
```

以上命令均由根 Agent 在 `H:\WORK\I\kvm-dashboard\backend` 实际执行。

## 5. 实际结果

| 检查 | 命令/测试 | 结果 | 证据 |
|---|---|---|---|
| 五 Profile 定义可加载 | `test_simulator_profiles.py` | `PASS` | 5 个 exact sysObjectID；catalog SHA `fd0eabdc…dd1ce7d` |
| L1 等价投影 | L2 专项 + drift | `PASS` | objects/tables 全字段相等，`L02_PROFILE_CATALOG_DRIFT.json ok=true` |
| CCDM 20 表/142 叶 | drift + catalog test | `PASS` | 当前/Golden 均为 `20/142` |
| 缺失/多余/重复 OID | drift + model invariants | `PASS` | 五 Profile 均为 0 |
| 非法 fixture 初始值 | fixture 全量加载 + 对抗测试 | `PASS` | 0 validation errors；旧四项为 `2/1/1/1` |
| 三层命名唯一性 | `test_simulator_profile_model.py` | `PASS` | vendor / canonical / `ui_label` i18n key 分离 |
| optional 默认关闭 | fixture 对抗测试 | `PASS` | 四个 vendor fixture 的 enabled groups 均为空 |
| fixture 行显式 | 静态 fixture + drift | `PASS` | fixture SHA `57e63493…5503a57`；implicit derived tables 为 0 |
| metadata 行数不变性 | metadata 对抗测试 | `PASS` | metadata 不含 rows/fixture/path，行数变化不改变 schema |
| metadata 大小/时间 | 根 Agent 本机测量 | `PASS` | API `197,069` bytes；热生成约 `0.95 ms/次` |
| 分层导入边界 | loader I/O spy + import audit | `PASS` | 生产只读两个 runtime catalog；无 state/socket/UI 导入 |
| CCDC vendor / project legacy 隔离 | catalog/renderer test | `PASS` | vendor 0 objects；adapter=`project-legacy-compatibility` |
| L0/L1/L2 全回归 | `python -m pytest tests -q` | `PASS` | `99 passed, 2 warnings in 2.29s` |
| 独立 Agent 审计 | 第二轮发现 6 P1 后修复；第三轮复审 | `PASS` | 最终无 P0/P1；Git commit Gate 单独保留 |

### 5.1 Metadata 预算

| Profile | schema 叶数 | 紧凑 JSON 字节 | 生成耗时 |
|---|---:|---:|---:|
| `ccdc_legacy` | 0 | 690 | 计入合计 |
| `ccdm_matrix` | 142 | 127,324 | 计入合计 |
| `visionxs_cpu` | 28 | 20,759 | 计入合计 |
| `visionxs_con` | 27 | 20,162 | 计入合计 |
| `dp12_mux_atc` | 35 | 27,787 | 计入合计 |
| API 合计 | 232 | 197,069 | 约 0.95 ms/次 |

预算：

- 单 Profile `<=256 KiB`；
- 五 Profile 合计 `<=512 KiB`；
- 热进程一次生成五 Profile `<=100 ms`；
- 0 行和大量行 fixture 的 schema metadata 字节完全相同。

迁移前精确基线：

```text
CCDM bytes=975114
CCDM fields=4428
generation≈4.09ms
```

验收输出必须只含 schema + row-key template；不能以生成时间仍较快为理由
保留实例展开。

## 6. 问题关闭证据

| 问题 | L2 要关闭的根因 | 当前状态 |
|---|---|---|
| `SIM-MIB-001` | CCDM 无错误跨产品公共 scalar | L2 根因已关闭 |
| `SIM-MIB-002` | fixture 初始值全部合法 | L2 根因已关闭 |
| `SIM-MIB-003` | CCDM 20 表、CON 列 30 全部进入 Profile | L2 根因已关闭 |
| `SIM-MIB-004` | 定义、范围、实际行分离 | L2 根因已关闭；L3/L4 行为待验 |
| `SIM-STATE-003` | 三层命名和显式映射 | L2 schema 根因已关闭；L3 状态迁移待验 |
| `SIM-UI-003` | metadata schema-only，不展开实例 | L2 schema 根因已关闭；L9 实例 UI 待验 |

这些只关闭 L2 根因。L3 runtime、L4 协议和 L9 UI 未完成时不得把问题的其他
层级整体标记为关闭。

## 7. 未验证边界

- 未重新核验原始 MIB 或仓库外 evidence；
- 未做现场设备 GET/WALK/Trap；
- 未证明 CCDC 厂家对象；
- 未执行真实 UDP Profile 全量 WALK；
- 未执行 L3 PATCH、事务或运行时实例化；
- 未执行 L4 Trap/SNMP 编码；
- 未证明页面参数编辑、拓扑或拉线可用；
- 未重新进行原始 MIB、现场设备和真实 UDP L4 验收。

## 8. Gate 判断

当前判断：`Accepted`。

代码、静态工件、专项测试和独立审计已经通过；实际工件由
`f9e91a1cc35bc8fc8e0cdd33f483b4b60ef74abc` 固定。L2 Gate 已满足，允许
开始 L3；原始 MIB、现场设备和 L4 UDP/ASN.1 能力仍不属于本结论。
