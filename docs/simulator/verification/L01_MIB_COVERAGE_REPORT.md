# L1 MIB Golden 覆盖与验证报告

> 状态：Accepted for local curated device dictionary snapshot
> 更新日期：2026-07-31
> 当前结论：五份对象 manifest、两份 Trap fixture、独立静态测试、
> Profile drift 诊断和问题清单更新均已完成；独立 Agent 复核无 P0/P1。
> 来源保证：`local-curated-snapshot-not-verified-against-original-mib-in-this-run`。

## 1. 验证范围

本报告覆盖：

- CCDM、VisionXS CPU、VisionXS CON、DP12 MUX/ATC、CCDC legacy 对象
  manifest；
- formal G&D 通用通知；
- `legacy-dashboard-simulator-v1` 历史兼容通知；
- 对象定义、索引允许范围和 fixture 实际行的边界；
- L1 静态验证，不包括 Simulator runtime 或真实 UDP 协议行为。

## 2. 来源约束复核

| 检查 | 当前结果 |
|---|---|
| 厂家对象事实只引用本仓库 `docs/reference/docs/devices/*.md` | 通过 |
| 未从 `PROFILE_DEFINITIONS` 生成 golden | 通过 |
| 未把仓库外原始 MIB 作为运行依赖 | 通过 |
| CCDC 保持 `legacy-unverified` | 通过；manifest 故意为空 |
| formal/legacy Trap 分离 | 已完成 |

`docs/reference/GD_MIB_DIFF_REGISTER.md` 用于理解历史修订和资料缺口；
`docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md` 用于多 Profile 交互及 Trap
证据分类。逐对象事实以本仓库设备字典为准。

## 3. 对象 manifest 覆盖

以下计数必须由最终 JSON 和独立测试直接计算，不手工填写猜测值：

| Profile | 证据状态 | manifest 对象 | 表 | 可 GET 叶 | not-accessible | read-write 事实 | 当前状态 |
|---|---|---:|---:|---:|---:|---:|---|
| `ccdm_matrix` | `local-device-dictionary-snapshot` | 202 | 20 | 142 | 60 | 0 | Static test passed |
| `visionxs_cpu` | `local-device-dictionary-snapshot` | 34 | 2 | 28 | 6 | 0 | Static test passed |
| `visionxs_con` | `local-device-dictionary-snapshot` | 33 | 2 | 27 | 6 | 0 | Static test passed |
| `dp12_mux_atc` | `local-device-dictionary-snapshot` | 47 | 4 | 35 | 12 | 6 | Static test passed |
| `ccdc_legacy` | `legacy-unverified` | 0 | 0 | 0 | 0 | 0 | Static test passed / intentionally empty |

这些是当前 JSON 顶层审计计数，并已与数组长度做只读解析比对。DP 的 35 个
可 GET 对象包含 29 个 read-only 与 6 个 read-write 事实；L1 记录权限但不授权
Simulator/Dashboard 发出 SET。

CCDC 的 `0` 表示“当前 manifest 故意不伪造对象”，不表示目标设备没有对象。
独立测试已验证顶层计数与数组内容一致。L1 是否通过仍由主 Agent 按本报告、
问题清单和独立复核共同决定。

## 4. Trap 覆盖

| fixture | notification | 变量 | 证据等级 | 当前结果 |
|---|---|---|---|---|
| `trap_formal.json` | `.32828.2.1.0.4` | `.32828.2.1.0.2` level、`.0.3` message | 本仓库设备字典 + 已分类现场捕获 | JSON 已建立 |
| `trap_legacy_dashboard_v1.json` | `.32828.5.0.4` | `.32828.5.1.0.2` level、`.0.3` message | 本仓库历史 loopback 模拟器捕获 | JSON 已建立 |

formal fixture 还锁定：

- `level` 为未枚举 `Integer32`；
- `severity_mapping=null`；
- 标准 `sysUpTime.0`/`snmpTrapOID.0` 与厂家 `OBJECTS` 分开；
- 必须同时匹配 notification 和两项厂家 varbind；
- 未知 varbind 原样保留。

legacy fixture 还锁定：

- 分类名为 `legacy-dashboard-simulator-v1`；
- 厂家 MIB 适用集合为空；
- `.32828.5.1.0.4` 被记录为现有实现的不兼容 notification；
- 捕获消息仅为项目兼容观察，不是厂家触发/恢复语义。

## 5. 当前可复现的静态检查

工作目录：

```text
H:\WORK\I\kvm-dashboard
```

JSON 解析：

```powershell
$files = @(
  'backend\tests\golden\simulator\trap_formal.json',
  'backend\tests\golden\simulator\trap_legacy_dashboard_v1.json'
)
foreach ($file in $files) {
  Get-Content -LiteralPath $file -Raw | ConvertFrom-Json | Out-Null
}
```

预期：

- exit code `0`；
- 两份 JSON 均可解析；
- 命令不访问 Simulator runtime。

对象与 Trap golden 合并测试：

```powershell
Set-Location H:\WORK\I\kvm-dashboard\backend
.venv\Scripts\python.exe -m pytest `
  tests\test_simulator_mib_golden.py `
  tests\test_simulator_trap_golden.py `
  tests\test_simulator_profile_golden_drift.py -q
```

本轮实际结果：

```text
...........................                                              [100%]
27 passed in 0.31s
```

- exit code：`0`
- object manifest 测试和 Trap fixture 测试均不导入 Simulator runtime/Profile；
- 已验证来源约束、计数、OID/访问/索引/表结构、CCDM 20 表、DP 六项
  read-write 事实和 CCDC 空 manifest 边界。
- 本地设备字典未记录的 table/Entry ASN.1 行类型显式为 `syntax=null`，
  不按对象名推造类型。
- 只有单独的 drift 测试导入当前 Profile，用于锁定 L2 待修差异；它不参与
  golden 生成，也不改变 golden expected。

Trap golden 独立测试：

```powershell
Set-Location H:\WORK\I\kvm-dashboard\backend
.venv\Scripts\python.exe -m pytest tests\test_simulator_trap_golden.py -q
```

本轮实际结果：

```text
...                                                                      [100%]
3 passed in 0.05s
```

- exit code：`0`
- 测试只加载 `trap_formal.json` 和 `trap_legacy_dashboard_v1.json`；
- 未导入 Simulator runtime 或 `PROFILE_DEFINITIONS`；
- 已断言 formal/legacy 精确 OID、level 无 enum/severity、来源保证分离及禁止
  仓库外/raw-MIB provenance。

### 5.1 当前 Profile 与 L1 Golden 的明确差异

诊断入口：

```powershell
Set-Location H:\WORK\I\kvm-dashboard\backend
.venv\Scripts\python.exe tools\report_simulator_profile_drift.py `
  --output ..\docs\simulator\verification\L01_PROFILE_DRIFT.json
```

实际退出码：`1`。这是预期结果，表示当前 L2 Profile 尚未匹配 L1 Golden，
不是 L1 Golden 自身失败。机器可读结果保存在 `L01_PROFILE_DRIFT.json`：

| Profile | 当前/Golden 表数 | 当前/Golden 叶定义 | 缺失 OID | 多余 OID | 非法默认值 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `ccdm_matrix` | 15/20 | 134/142 | 11 | 3 | 4 | L2 待修 |
| `visionxs_cpu` | 2/2 | 28/28 | 0 | 0 | 0 | 定义层匹配 |
| `visionxs_con` | 2/2 | 27/27 | 0 | 0 | 0 | 定义层匹配 |
| `dp12_mux_atc` | 4/4 | 35/35 | 0 | 0 | 0 | 定义层匹配 |

CCDM 的三个多余定义是错误复用的公共 `.2.3.1/.2/.3`；四个非法默认值是
`targetUsbHid=3` 和三个 `targetVideoCable*=5`。缺失集合覆盖五张缺表的可读列
及 CON 列 30。该诊断显式满足“用 Golden 让当前 Profile 差异可见”，但不在
L1 越层修改 Profile。

### 5.2 L0 + L1 + 现有 Simulator 全回归

从 `backend` 收集全部 `tests/test_simulator*.py`，再加入
`test_trap_receiver_startup.py`、`test_health_probe.py` 执行：

```text
69 passed, 2 warnings in 2.94s
```

- exit code：`0`
- 两个 warning 是 pysnmp/pysmi 上游弃用提示；
- `build_simulator_mib_golden.py --check` 输出
  `checked 5 object manifests`，exit code `0`；
- L1 两个工具和三份新增测试均通过 `py_compile`；
- `git diff --check` exit code `0`，只显示现有 LF/CRLF 提示。

## 6. 问题映射

| 问题 | L1 当前处理 | 仍需上层完成 |
|---|---|---|
| SIM-MIB-001 | CCDM 正确对象集合和 3 个多余 OID 已固定 | L2 删除错误公共复用 |
| SIM-MIB-002 | enum/range 与 4 个非法默认值已固定 | L2 默认 fixture，L3 PATCH 验证 |
| SIM-MIB-003 | CCDM 20 表、11 个缺失 OID和 CON 列 30 已固定 | L2 补齐 Profile |
| SIM-MIB-004 | 契约和 manifest 已分离定义/范围/实际行 | L2/L3 显式实例 |
| SIM-MIB-005 | 独立 golden、生成校验和测试已完成 | L1 事实已关闭 |
| SIM-TRAP-002 | 厂家 level 未枚举事实已固定 | L6/L9 保存 raw level、分离平台策略 |
| SIM-TRAP-003 | legacy 捕获布局已固定 | L4 修复编码，L6 接收组合验证 |

这些问题只能关闭各自的“L1 事实部分”。runtime、协议或 UI 尚未修复时，问题
整体仍不得标为完成。

## 7. 未验证边界

- 未做真实设备 GET/WALK/Trap 的新一轮现场验证；
- 未验证任一目标固件是否启用 formal Trap；
- 未获得 CCDC/CCC 厂家对象字典；
- 未验证厂家 `level` 严重度、触发、恢复或确认语义；
- 未验证设备侧 SNMP 版本、端口、认证、ACL 或 Trap 目标配置；
- 未运行 L4 的原始 BER formal/legacy UDP 矩阵；
- 未修改 Simulator Profile、状态、Agent、Dashboard 和前端；仅执行 Profile
  对 Golden 的只读 drift 诊断。

因此，本报告只能证明 L1 静态事实源的构建进度，不能宣称现场兼容性或 L4
协议通过。

## 8. L1 Gate 当前判断

当前判断：`Accepted for local curated device dictionary snapshot`。

接受证据：

1. 五份 object manifest、两份 Trap fixture 均可独立解析和审查；
2. L1 专项 `27 passed`，全回归 `69 passed`；
3. generator `--check`、`py_compile`、`git diff --check` 通过；
4. Profile drift 以预期 exit code `1` 明确隔离为 L2 待修，不污染 L1 真值；
5. 独立 Agent 复核后，table/Entry 猜测 SYNTAX、README 过度声明、CCDC
   authority 和 Gate 状态问题均已修复，最终无 P0/P1；
6. CCDC、固件、实机 GET/WALK/Trap 和原始 MIB 未复核边界继续保留。

该 Accepted 只证明本仓库本地整理设备字典的 L1 静态事实底座已经可重复审查，
不等于厂家原始 MIB、现场固件或真实设备兼容性重新验收通过。
