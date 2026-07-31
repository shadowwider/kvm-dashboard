# L05 前端完成与发布层任务手册

> 状态：Ready for UI shell; write integration waits for L4 fixtures
> 负责人：`simulator-ui` 前端开发人员
> 合并旧范围：原 L8 只读页、L9 参数编辑、L10 拓扑模型、L11 画布、L12 发布
> 最终交付：可直接使用的 Simulator 控制台和发布候选

## 1. 开工前必须读什么

前端必须读：

1. `docs/simulator/TWO_STAGE_COMPLETION_PLAN.md`
2. `docs/simulator/REFERENCE_FILE_REGISTER.md`
3. `docs/simulator/layers/L05_FRONTEND_COMPLETION_TASK_MANUAL.md`
4. `docs/simulator/api/SIMULATOR_API_V1_CONTRACT.md`
5. `docs/simulator/layers/L03_RUNTIME_STATE_CONTRACT.md`
6. `docs/simulator/layers/L03_PATCH_PATH_AND_TRANSACTION_CONTRACT.md`
7. `docs/simulator/layers/L02_PROFILE_MODEL_CONTRACT.md`
8. `docs/simulator/layers/L04_BACKEND_COMPLETION_TASK_MANUAL.md`
9. `backend/kvm_simulator_README.md`
10. `docs/simulator_startup_connection_guide.md`
11. `docs/simulator/PROBLEM_DISCOVERY_CHECKLIST.md`
12. `simulator-ui/src/` 当前原型代码

前端不需要阅读原始 MIB，也不得从设备字典复制 OID/enum/range 到 JavaScript。
所有字段、实例、枚举、范围、只读/可写和 optional 能力必须来自 L4 API
metadata；所有运行状态来自 state/WS revision。

## 2. 当前已经完成到哪里

可以保留的现有原型：

- React + Vite + `@xyflow/react` 工程；
- `App.jsx` 页面骨架；
- `TopologySidebar`、`RuntimeToolbar`、`SimulatorNode`；
- `DetailsDrawer`、`TrapPanel`、`EventTimeline`；
- API client、Vite proxy、build 后由 FastAPI 托管；
- 当前 topology/state/action/trap 的基本请求方向。

但现有页面不是正式契约实现。已知需要改造：

- `profileFields.js` 等硬编码字段不能作为事实源；
- 页面不能发送旧 `ports[...]`、`endpoints[...]` 或厂家别名作为通用 PATCH；
- active topology、running、revision 只能使用服务器报告值；
- 写操作必须展示 committed values/idempotent/conflict，不以 HTTP 200 简化判断；
- endpoint/domain state 与 SNMP-observable Profile state 必须有清楚标签；
- topology 画布当前引用模型不足以证明端口语义和无损保存。

## 3. 现在可以做什么

无需等待 L4 全部完成即可开始：

- 页面信息架构、主题、响应式布局和可访问性；
- API adapter 层和 contract fixture test；
- 只读 status、active topology、device/Agent/Bridge 健康卡片；
- metadata 驱动的字段 renderer/form component；
- topology node/port/edge 视觉组件；
- loading/empty/degraded/disconnected/conflict/error 状态；
- Playwright 测试骨架和 mock server。

必须等待对应 L4 fixture 冻结后接入：

- 实际 runtime PATCH；
- power_off/restore/start/switch/stop；
- topology 保存和拉线；
- WS revision/gap/reconnect；
- Trap 多设备发送结果；
- Dashboard Bridge 状态和跨系统跳转。

## 4. 要交付的前端功能

### A. 运行总览

- active topology、running、revision、WS 连接状态；
- Agent expected/running/ready/error 和 host/port；
- Bridge、Dashboard、Trap receiver 状态；
- degraded 原因、最近事件和可执行恢复操作；
- Start/Stop/Switch 按服务器状态禁用或确认，不维护本地假状态。

### B. 全参数查看与编辑

- Profile schema 与当前 path registry 分离展示；
- 只显示当前 fixture 实际实例，不按 INDEX range 生成成千上万字段；
- scalar/table/row/index 层级、搜索、筛选、分页或虚拟化；
- enum select、range、字符串 byte 上限和只读原因由 metadata 生成；
- runtime writable 与 vendor SNMP writable 分开展示；
- batch 编辑预览、expected revision、字段级错误、冲突刷新；
- 成功后以 committed values/WS revision 更新，不自行乐观伪造；
- domain-only endpoint 字段明确标注“不代表 SNMP OID 已改变”。

### C. Trap 控制台

- 当前 topology 内单/多设备选择；
- preset/custom、level、formal/legacy；
- 不提供任意 host/port 输入；
- 显示逐目标成功/失败、event/revision 和 Dashboard 接收验证状态；
- 防重复提交、消息长度和频率限制提示。

### D. 拓扑领域与画布

- device、CPU/CON module、physical port、physical edge、simulation route
  使用不同实体和视觉；
- 全局唯一 ID、Profile 兼容、端口方向/容量/占用规则；
- 节点挂载、拖拽、缩放、搜索、自动布局；
- Handle 必须对应真实 port ID，不使用通用无语义 Handle；
- 连线前本地预校验，保存时仍以服务器 validator 为准；
- 删除节点前展示受影响端口、边、route 和 runtime；
- preset 使用 Save As，active topology 禁止危险覆盖/删除；
- load → edit → save → reload → start round trip 无损。

### E. 实时与错误恢复

- WS 首包 snapshot；
- 严格按 revision 应用，发现 gap/乱序立即 refetch；
- 断线重连、后台标签页、双浏览器和慢客户端；
- 409 conflict 保留用户未提交表单并提供刷新/比较；
- 422 显示字段/path details；503 显示 lifecycle/Bridge degraded；
- 任何失败不把按钮留在永久 loading 或页面假成功状态。

### F. 发布

- `npm ci`、lint、unit、build、Playwright 全通过；
- built/dev 两种模式连接正确；
- Windows port mode 一键按文档启动；
- 空状态、5 Profile、大表、窄屏和中英文 UI 检查；
- 用户手册含启动、组网、参数、Trap、故障恢复和安全边界。

## 5. 前端代码规则

- 所有 UI 文案进入项目 i18n/集中资源，不在组件散落硬编码；
- API 只通过 `src/api/` adapter，组件不直接拼 URL/response shape；
- metadata 和 state 使用独立 store slice，不能把 schema 当 instance；
- OID 只用于只读审查显示，不作为 React key、field path 或提交字段；
- server ID/path 原样保存，label/alias 只显示；
- 禁止把 token/community 放进 localStorage、日志或错误 toast；
- 不使用运行时代码生成测试 expected，contract fixtures 必须由 L4 固定。

## 6. 必须新增或更新的文件

前端至少新增：

```text
simulator-ui/src/api/contracts/
simulator-ui/src/store/
simulator-ui/src/components/fields/
simulator-ui/src/components/topology/
simulator-ui/src/pages/
simulator-ui/tests/
docs/simulator/verification/L05_FRONTEND_COMPLETION_REPORT.md
```

必须更新：

```text
simulator-ui/src/api/client.js
simulator-ui/src/App.jsx
simulator-ui/src/profileFields.js  # 删除事实硬编码，改为 metadata adapter 或移除
backend/kvm_simulator_README.md
docs/simulator_startup_connection_guide.md
docs/simulator/PROBLEM_DISCOVERY_CHECKLIST.md
```

## 7. 必须验收的浏览器场景

- 首次打开、刷新、无 active topology、后端未启动、WS 断开；
- all-profiles 五设备只读展示；
- scalar、单索引 table、复合索引 table 编辑；
- 只读/disabled optional/不存在 row/非法 enum/range/超长 string；
- 100 项 batch 与 101 项前端预拒绝；
- 两浏览器 revision conflict、WS gap、断线重连；
- disconnect/power_off/restore 和失败恢复；
- formal/legacy Trap；
- topology 新建、Save As、端口拉线、非法连线、删除影响、无损 reload；
- start/switch/stop 故障时页面与服务器最终状态一致；
- API GET、WS、SNMP GET 对同一修改返回一致结果。

## 8. Definition of Done

只有同时满足以下条件才可标记 L5 Accepted/发布候选：

1. 页面没有 OID/Profile/path/enum/range 的第二份硬编码真值；
2. 只读、参数、Trap、拓扑和实时交互全部使用 Accepted L4 API；
3. unit、contract、Playwright、build/lint、真实后端和 Dashboard E2E 通过；
4. 失败、冲突、断线和生命周期回滚不会产生页面假成功；
5. 问题清单 P0/P1=0，P2 有明确接受结论；
6. 验证报告、运行手册和真实 Git commit 完成；
7. 未做现场设备验证的边界继续明确展示。

L5 完成即结束本次 Simulator 改造，不再新增后续层。
