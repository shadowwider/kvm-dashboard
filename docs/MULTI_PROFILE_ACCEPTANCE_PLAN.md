# KVM 多设备改造最终验收清单

> 验收负责人：主任务
> 日期：2026-08-01

## 1. 基线与迁移

- 记录实施前后端测试、前端 lint/build 结果。
- 从现有 SQLite 数据库副本执行 Alembic upgrade，旧设备、端点、告警和指标不丢失。
- 在 PostgreSQL/TimescaleDB 环境执行同一迁移。
- 新安装可以从空数据库启动。
- 生产仍为单 FastAPI worker。

## 2. 五 Profile 模拟器

使用 `backend/simulator` 和 `simulator-ui` 启动：

- `ccdc_legacy`
- `ccdm_matrix`
- `dp12_mux_atc`
- `visionxs_con`
- `visionxs_cpu`

每个实例验证：

1. `sysObjectID` 精确匹配。
2. 自动发现并直接加入。
3. 身份字段正确。
4. Profile 标量全部可读取。
5. 单索引和复合索引表全部聚合正确。
6. optional group 不支持时不判离线。
7. 详情 API 和页面显示一致。

## 3. 自动发现

- 配置一个 `/24` 测试网段。
- 只扫描该 CIDR 内可用地址。
- 发现阶段没有完整 WALK。
- 支持设备自动导入。
- 重复扫描不产生重复设备。
- 未知 G&D 和非 G&D 不导入。
- 扫描不阻塞 API 启动。
- 扫描任务可以查看进度、结果和错误。
- community 不出现在响应、普通日志和审计 change summary 中。

性能记录总耗时、并发、timeout、响应数和错误数，不以单个实验室时间作为硬编码超时。

## 4. UDP 161 / 162

- 后端向设备 UDP 161 发 GET/WALK。
- 现场/模拟设备向宿主机 UDP 162 发 Trap。
- Docker 映射为宿主机 162 到容器监听端口。
- 后端只有一个 Trap receiver 绑定容器监听端口。
- 防火墙开放入站 UDP 162。
- 正式 `.32828.2.1.0.4` Trap 可以接收、持久化和推送。
- 旧 `.32828.5.*` 只在兼容测试中使用。

## 5. 快速掉线和恢复

对至少 5 台模拟设备和容量测试环境执行：

- 断开 SNMP agent。
- 记录物理动作、后端状态落库、WebSocket 和页面变化时间。
- 恢复 agent 并记录同样时间。
- 不产生重复 offline/recovery。
- offline/recovery Alert 有数据库 ID。
- 页面刷新后告警仍存在。

目标：常规环境掉线识别 2-3 秒；256 地址容量环境不得出现未报告的容量退化。

## 6. Trap 和告警声音

- info、warning、critical、trap、offline 新告警都能播放。
- 首次加载历史告警不播放。
- WebSocket 重连不重复播放。
- 同一 Alert ID 只播放一次。
- 静音开关刷新后保持。
- 告警风暴时声音节流，告警记录不丢失。
- Trap raw level、message、notification OID 和完整 varbind 可查询。

## 7. 风扇

- 正常正数转速：present、fresh、正常显示。
- 合法 0：保留风扇，显示停止/异常。
- `noSuchObject`：显示不支持，不显示故障。
- 完整 WALK 成功后连续缺行：按策略标记 absent。
- 设备超时/离线：保留最后值并标记 stale，不删除。
- DisplayString 无法解析：保留 raw，normalized 为 unknown。

## 8. 键盘、鼠标和 HID

- none：键盘否、鼠标否。
- keyboard：键盘是、鼠标否。
- mouse：键盘否、鼠标是。
- keyboardMouse：键盘是、鼠标是。
- PS/2 与 USB 来源分别显示。
- HID connected/initialized 显示状态，但明确未区分键盘或鼠标。

## 9. Dashboard 和详情

- 现有矩阵仍可切换设备、打开 endpoint 详情并实时变色。
- 原拓扑 Tab 已替换为设备表格。
- 表格包含全部五 Profile 设备并可筛选、排序。
- VisionXS/DP 不被伪装成矩阵 endpoint。
- 每台设备详情显示该 Profile 的所有 supported/present 字段。
- unsupported、absent、stale、unknown 视觉含义不同。
- 没有随机生成的在线率数据。

## 10. Admin 和安全

- 自动发现配置、立即扫描、启动扫描开关可用。
- 审计覆盖登录、设备、发现、轮询、OID、告警、别名、用户管理。
- 审计可筛选、分页、查看详情、导出 CSV。
- 设备列表和详情不返回 community。
- WebSocket 未认证连接被拒绝。
- 非 admin 无法访问发现配置和审计日志。

## 11. 自动化与浏览器验收

必须通过：

```bash
cd backend
pytest

cd ../frontend
npm run lint
npm run build
```

最终启动后端、五 Profile 模拟器和前端，通过浏览器自动化完成：

1. 登录。
2. 自动发现。
3. 查看设备列表。
4. 逐台打开五种设备详情。
5. 切回矩阵并打开 CPU/CON。
6. 修改模拟器状态并观察实时更新。
7. 发送 Trap 并听到声音。
8. 查询审计日志。
9. 桌面和窄屏截图检查。

验收报告必须列出测试命令、结果、失败项、截图路径、已知限制和现场部署参数。

## 12. 2026-08-01 实测验收报告

### 12.1 验收结论

本次多设备改造已完成集成验收。五个 Profile 均可由同一套后端识别、
采集、持久化并在前端展示；原矩阵保留，原拓扑入口已替换为设备列表。
自动发现、快速健康探测、正式 Trap、告警声音、操作审计和完整设备详情
均已通过本地模拟环境验证。

生产部署必须继续保持单 FastAPI worker。轮询器的 `sysObjectID` 离线
early-exit 是快速识别和避免完整 WALK 阻塞的必要逻辑，不得删除。

### 12.2 自动化测试结果

| 范围 | 命令 | 结果 |
|---|---|---|
| 后端 | `cd backend && pytest` | `271 passed, 2 warnings` |
| 前端单元测试 | `cd frontend && npm test` | `18 passed` |
| 前端静态检查 | `cd frontend && npm run lint` | 通过 |
| 前端生产构建 | `cd frontend && npm run build` | 通过 |
| Simulator UI 单元测试 | `cd simulator-ui && npm test` | `2 passed` |
| Simulator UI 静态检查 | `cd simulator-ui && npm run lint` | 通过 |
| Simulator UI 生产构建 | `cd simulator-ui && npm run build` | 通过 |
| Git 差异检查 | `git diff --check` | 无空白错误，仅有 Windows LF/CRLF 提示 |

Alembic 已验证空库、已有 legacy 库、部分旧 schema 和重复执行 upgrade。
当前迁移采用向前升级策略，不提供 downgrade；生产回退依赖部署前数据库
备份和应用版本回滚。

### 12.3 五 Profile 采集结果

| Profile | 页面详情 | 通用实体 | 结果 |
|---|---:|---:|---|
| `ccdc_legacy` | 1 个分区、20 个兼容指标 | 0 | 在线、旧矩阵投影和旧指标兼容通过 |
| `ccdm_matrix` | 9 个分区、134 个字段 | 16 | 标量、单索引表、复合索引表和矩阵投影通过 |
| `dp12_mux_atc` | 10 个分区、35 个字段 | 4 | 通道、视频、键鼠和设备状态通过 |
| `visionxs_con` | 8 个分区、27 个字段 | 2 | CON、显示、键鼠和链路状态通过 |
| `visionxs_cpu` | 8 个分区、28 个字段 | 2 | CPU、视频、键鼠和链路状态通过 |

CCDM、DP12 和 VisionXS 详情可显示序列号及 Profile 支持的全部状态字段。
CCDM、DP12 显示 MIB 提供的风扇数据；VisionXS Profile 没有风扇字段时不
伪造风扇。合法 `0 RPM` 保留为停止/异常，超时保留最后值并标记 stale，
不因单次缺失删除实体。

`ccdc_legacy` 仍使用项目原有的兼容指标模型，因为当前资料没有完整的
厂家 CCDC 对象字典。不得从 CCDM MIB 推导或复制一套虚假的 CCDC Profile。

### 12.4 快速掉线和恢复

五台模拟设备同时参与健康探测：

- 掉线识别并更新状态：`4462 ms`。
- 恢复在线并更新状态：`2736 ms`。
- 恢复后健康探测：`5/5` 成功。
- offline/recovery 告警均有数据库 ID，刷新后仍存在。

掉线时间已经摆脱完整 WALK 和原 60 秒轮询周期的阻塞，但本次五设备实测
`4.462 s` 仍高于验收清单中理想的 2-3 秒目标。现场可通过健康探测周期、
SNMP timeout 和 retry 做受控调优，不能通过缩短完整 Profile WALK 周期
替代健康探测。

### 12.5 自动发现

- 仅使用 SNMP v2c。
- 只枚举管理员配置的 IPv4 CIDR。
- 发现阶段只读取身份和 `sysObjectID`，不执行完整 WALK。
- 精确匹配五个受支持 Profile 后直接加入，不经过预览。
- 首次扫描导入设备，再次扫描更新同一设备，不产生重复记录。
- 未知或不受支持设备不导入。
- community 在读 API、页面、普通日志和审计摘要中均不明文返回。
- Admin 页面可配置 CIDR、community、UDP 161、timeout、retry 和并发数，
  并可查看任务进度及新增、更新、不支持、错误统计。

浏览器联调使用回环测试网段完成直接导入和重复扫描。`/24` 枚举和边界由
自动化测试覆盖；尚未在 256 台真实响应设备的现场网络中执行吞吐基准。

### 12.6 Trap、UDP 162 和告警声音

现场链路固定为：

```text
设备 -> 宿主机 UDP 162 -> Docker 162:10162/udp -> 后端监听 10162
```

后端主动轮询仍访问设备 UDP 161，两条 UDP 路径互不冲突。正式通知 OID
`1.3.6.1.4.1.32828.2.1.0.4` 已通过真实 UDP 数据包验证。

最终声音联调发送一条新的 formal Trap：

- 页面只新增一条对应告警。
- Web Audio 只启动一次，使用 Trap 专用 `820 Hz` 音调。
- `alerts` 中 Trap 数量从 39 增至 40。
- `trap_events` 数量同步从 39 增至 40。
- raw level、source IP、notification OID、message 和完整 varbind JSON 均已落库。
- 刷新页面后历史告警仍显示，但音频调用次数为 0。

声音设置默认允许 info、warning、critical、trap、offline 五类新告警，
支持总静音、按类型关闭和本地试听；同一 Alert ID 不重复播放，告警风暴
期间只节流声音，不丢告警记录。

### 12.7 Dashboard、矩阵和完整详情

- Dashboard 显示五台设备，五台均在线。
- 原矩阵保留并显示 7 个 CPU/CON 终端。
- 原拓扑 Tab 已替换为设备列表，表格正好显示五台设备。
- 列表包含 Profile、角色、地址、可达性、数据新鲜度、健康、实体、告警和
  采集时间，并支持筛选和排序。
- 点击任意设备可打开 Profile 驱动的完整详情。
- CPU 明细分别显示控制台 PS/2、控制台 USB、目标 PS/2 和目标 USB HID。
- CON 明细分别显示键盘和鼠标状态。
- HID 只能表示通道连接或初始化时，页面明确说明无法区分键盘和鼠标。
- 页面没有补造随机在线率或历史趋势数据。

### 12.8 Admin 操作审计

Admin 操作审计页面已验证：

- 操作者、操作类型、目标类型、目标 ID、结果和时间范围筛选入口存在。
- 使用 `auth.login` 筛选后，44 条结果全部为该操作类型。
- 无筛选结果可从第 1 页切换到第 2 页，数据确实变化。
- 表格显示操作者、目标、结果、IP、变更摘要和 request ID。
- CSV 下载成功，文件包含表头和 58 条审计记录。
- discovery 配置变化中不会泄露 community。

### 12.9 浏览器和移动端结果

桌面浏览器完成登录、五设备列表、逐台详情、矩阵 CPU/CON 详情、自动发现、
操作审计、声音设置和实时 Trap 验收。全过程没有 console error 或 page error。

移动端使用 `390 x 844` 视口复测：

- Dashboard 页面级 `scrollWidth` 等于视口宽度。
- 设备表格和设备筛选芯片只在各自容器内横向滚动，不撑宽页面。
- 设备详情面板宽 372 px，内部没有横向溢出。
- CCDM 详情 9 个分区均可滚动查看。
- 没有文字重叠、控件遮挡或空白渲染。

截图目录：

```text
docs/acceptance-evidence/2026-08-01/
```

其中包括桌面 Dashboard、设备列表、五 Profile 详情、矩阵 CPU/CON 详情、
自动发现、操作审计、声音设置、实时 Trap，以及最终移动端 Dashboard、
设备列表和设备详情截图。

### 12.10 未实测和现场注意项

1. PostgreSQL 16 / TimescaleDB 生产容器未在本机执行完整迁移和 E2E；
   SQLite 自动化及本地集成已通过，生产上线前仍需在部署环境备份后演练。
2. 256 台真实 SNMP 响应设备的发现吞吐和交换机广播域影响未做现场压测。
3. Alembic downgrade 有意不支持，回退依赖数据库备份。
4. `ccdc_legacy` 继续使用旧兼容指标模型，直到取得厂家 CCDC MIB 或实机
   GET/WALK 证据后再升级为完整 Profile。
5. UDP 162 在 Linux 宿主机可能需要 root、`CAP_NET_BIND_SERVICE` 或端口
   映射；当前 Docker 方案使用宿主机 162 映射容器 10162。
