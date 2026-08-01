# L05 前端完成与发布层验证报告

> 状态：UI shell 技术验证通过；完整 L5 Gate 等待 L4 Accepted API fixture
> 日期：2026-08-01
> 前置：L0–L3 Accepted；L4 与 L5 并行开发中

## 1. 本次交付

`simulator-ui` 已从“原型页面”改为 API-contract 驱动的控制台骨架：

- 状态栏读取 `/status` 的 running、revision、Agent 和 Bridge，不再以本地
  `running` 或首个 preset 猜测；
- WebSocket 首包、revision 乱序丢弃、gap 强制 REST refetch、断线重连已实现；
- 参数抽屉只从每设备实际 `path_registry.paths` 渲染 scalar/单索引/复合索引
  字段；无 registry 时明确提示 L4 契约未提供实例，绝不回退到
  `profileFields.js` 的 OID/path/enum/range 硬编码；
- PATCH 发送 canonical `[{path,value}]` 和 `expected_revision`，展示 committed /
  idempotent / conflict / field error，并在成功后只采纳服务器 snapshot；
- Trap 目标仅限 runtime device，level 原样发送，formal/legacy 可选，未将
  level 伪称为厂家严重度枚举；
- 画布区分 physical edge 与 `simulation_route`，且 topology payload 不再过滤
  endpoint-to-endpoint route；Profile palette 由 `/profiles` metadata 生成。

## 2. 自动验证

在 `H:\WORK\I\kvm-dashboard\simulator-ui` 执行：

```powershell
npm ci
npm run lint
npm test
npm run build
```

结果：`npm ci` 成功安装 206 packages；ESLint 0 errors；Node contract tests
2/2 passed；Vite production build passed。contract fixture 位于
`simulator-ui/tests/fixtures/api-v1-draft.json`，并独立断言 L4 Draft 的
revision/active topology，以及 L3 scalar 和复合索引 path 的渲染和值读取。

## 3. 真实浏览器验证

本地以如下命令启动当前 Simulator（端口隔离，未访问现场设备）：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn simulator.main:app --host 127.0.0.1 --port 18888
```

以 Chrome headless 打开 `http://127.0.0.1:18888/`，等待 5 秒并读取渲染 DOM；
同时使用 Chrome screenshot 目检。实际观察：

| 操作 | 预期 | 实际 |
|---|---|---|
| 首次打开 | 显示 REST/WS runtime 状态 | 显示 `Running`、`WS online`、`rev 1`、`Agent 1/1`、Bridge disabled |
| 切换 `all-profiles` | 五 Profile 与五 Agent 一致 | API start 后浏览器显示 `rev 2`、`Agent 5/5`，画布出现 CCDC、CCDM、Vision CPU/CON、DP12 |
| scalar + 复合索引 PATCH | 一次 commit 返回规范 path/revision | 对 `sim-ccdm-01` 写 `scalars.switch_temperature=42.0` 和 `tables.gud_ccdmdwc_mib_fan_table[1,1].fan_speed=3201`，响应 `revision=2`、两条 changed/committed values、`idempotent=false` |
| 画布 | simulation route 不能伪装为物理线 | 已显示“实物链路 / 模拟路由（非 SNMP OID）”图例，当前 existing route 使用虚线 `simulation route` |

浏览器截图临时文件：`C:\tmp\kvm-simulator-ui.png`（不纳入仓库）。

## 4. 尚未可宣称通过的场景

本报告初测时 L4 API Draft 尚未在 `/state` 或 metadata 提供每设备实例化
`path_registry`，因此当时真实浏览器中的参数抽屉正确显示等待提示，未使用硬编码替代。
后续 L4 垂直切片已补齐该字段；根验收已在真实服务确认 all-profiles 的五个实例均带
`path_registry`，且 PATCH 响应带 `state` 和 committed values，并以 Chrome headless
确认页面显示 `Running`、`WS online`、`rev 2` 与 `Agent 5/5`。不过尚未用自动化浏览器
逐一点击设备并完成字段编辑，因此以下仍保留给 L5 最终 Gate：

- P1：字段抽屉的真实点击编辑、409/422 details 的端到端浏览器接线；
- P1：端口语义、physical edge validator、拓扑 Save/Reload/Start 无损 round trip；
- P1：双浏览器 conflict、WS gap/reconnect、disconnect/power_off/restore 的真实
  交互；
- P1：formal/legacy Trap 的逐目标 Dashboard 接收状态；
- P2：窄屏/中英文、虚拟化大表、可访问性和发布 smoke。

本报告不是 L5 Accepted 结论。当前 UI shell 的 P0=0；上列 P1 均是 L4 未冻结
公共契约造成的明确阻塞，不以 mock 或本地字段 fallback 掩盖。

## 5. 后续收口增量（2026-08-01）

前端已改为将 L4 `runtime_instances.devices[].path_registry` 合并到对应 runtime
device；不再因 registry 位于独立实例区而显示空参数抽屉。根验收通过 Chrome CDP
真实点击 CCDM 节点，抽屉渲染 162 个服务器实例字段，并在页面修改
`scalars.switch_temperature` 后从 `/state` 验证 committed 值为 `67.7`。

页面也已移除到 legacy `scenarios/reachability/endpoints` 写接口的 fallback；物理边
只能从设备实际 port Handle 建立、route 只能在 endpoint 间建立，保存含 topology
revision 以拒绝并发静默覆盖。仍须完成双浏览器冲突、Trap Dashboard 回执、端口拖拽
round trip、窄屏/i18n/可访问性与完整发布 Gate，故 L5 继续保持 Candidate。
