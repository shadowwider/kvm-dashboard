# KVM 多设备监控改造总开发方案

> 状态：已确认需求，进入实施
> 日期：2026-08-01
> 适用仓库：`H:\WORK\I\kvm-dashboard`

## 1. 已确认的现场口径

1. SNMP 统一使用 v2c，本期不实现 SNMPv3。
2. 自动发现仅扫描管理员配置的 IPv4 CIDR，典型范围为 `/24`。
3. 精确识别到受支持设备后直接加入监控，不增加人工预览步骤。
4. 现场设备统一向宿主机 UDP 162 发送 Trap。
5. 所有新告警都可以播放声音，不只限于 critical。
6. 保留现有端点矩阵视图；删除 Dashboard 的拓扑视图入口，并在原位置提供设备列表。
7. 前端和后端在独立 worktree 中并行开发，主任务负责接口审查、集成、模拟器验证和最终验收。

## 2. 项目目标

将当前以 `ccdc_legacy` 为中心的固定矩阵监控系统改造成 Profile 驱动的多设备监控系统。生产系统必须支持：

| Profile | 精确 `sysObjectID` | 产品角色 |
|---|---|---|
| `ccdc_legacy` | `1.3.6.1.4.1.32828.3.257.16` | 历史 CCDC 兼容矩阵 |
| `ccdm_matrix` | `1.3.6.1.4.1.32828.3.257.10` | CCDM / CC160 中心矩阵 |
| `dp12_mux_atc` | `1.3.6.1.4.1.32828.3.1792.17` | DP1.2-MUX-ATC 通道设备 |
| `visionxs_con` | `1.3.6.1.4.1.32828.3.769.768` | VisionXS 独立 CON |
| `visionxs_cpu` | `1.3.6.1.4.1.32828.3.768.768` | VisionXS 独立 CPU |

CC160 与 CCDM 使用同一个 `ccdm_matrix` 协议 Profile，不建立重复协议定义。

## 3. 唯一协议资料入口

开发人员必须按以下顺序阅读，不能根据旧页面字段反推厂商协议：

1. `docs/reference/GD_MIB_DIFF_REGISTER.md`
2. `docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md`
3. `docs/reference/docs/devices/*.md`
4. `docs/reference/docs/evidence/*.md`
5. `backend/simulator/catalog/l2_profiles.json`
6. `backend/simulator/catalog/l2_default_fixtures.json`
7. `backend/simulator/profile_model.py`
8. `backend/simulator/profile_catalog.py`

生产采集器与模拟器必须共用同一份 Profile 目录。禁止复制 OID、枚举、复合索引和 optional group 后形成第二套定义。

## 4. 总体架构

```text
Configured IPv4 CIDR
  -> bounded concurrent sysObjectID GET
  -> exact Profile match
  -> auto import
  -> reachability probe / profile poll plan / trap receiver
  -> raw + normalized state persistence
  -> REST + authenticated WebSocket
  -> matrix / device list / profile-driven detail / alerts / admin
```

### 4.1 数据层

新增通用实体状态模型，至少表达：

- `device_id`
- `profile_id`、`profile_version`
- `table_id`
- 稳定的 `entity_key`
- `index_key` JSON，保留索引名、顺序和值
- `raw_values` JSON
- `normalized_values` JSON
- 字段级 `supported`、`present`、`status`、`updated_at`
- 实体级 `present`、`stale`、首次和最近出现时间

原 `Endpoint` 表暂时保留，作为 CCDM/CCDC CPU、CON、DWC 的兼容投影。不能把 VisionXS 或 DP 通道伪装成旧矩阵 endpoint。

### 4.2 采集层

采集分为三条独立路径：

1. 可达性：只 GET `sysObjectID.0`，负责整机离线/恢复。
2. Profile 快速状态：按 Profile 读取少量关键状态，目标周期 2-5 秒。
3. Profile 完整轮询：标量和表的完整采集、归档、阈值和实体对账。

完整表采集必须按 MIB 中定义的索引顺序解析实例 OID。不能继续只取 OID 最后一段。

### 4.3 Trap

- 设备发送目标：宿主机 UDP 162。
- 容器推荐监听 UDP 10162，由 Docker 映射 `162:10162/udp`。
- 配置拆分为 `SNMP_TRAP_HOST_PORT` 与 `SNMP_TRAP_LISTEN_PORT`。
- 正式通知 OID：`1.3.6.1.4.1.32828.2.1.0.4`。
- 原始 level：`1.3.6.1.4.1.32828.2.1.0.2`。
- 原始 message：`1.3.6.1.4.1.32828.2.1.0.3`。

所有 Trap 必须保存来源、通知 OID、原始 level、message 和全部 varbind。`.32828.5.*` 只作为旧模拟器兼容格式。

### 4.4 自动发现

发现流程固定为：

1. 管理员保存 CIDR、community、SNMP 端口、timeout、并发和启用状态。
2. 后台任务枚举可用 IPv4 地址，不扫描网络地址和广播地址。
3. 并发 GET `1.3.6.1.2.1.1.2.0`，禁止在发现阶段完整 WALK。
4. 只接受表中五个精确 `sysObjectID`。
5. 读取 Profile 定义的少量身份标量。
6. 按 host、Profile、序列号和 MAC 去重。
7. 自动新增或更新已识别设备。
8. 新增设备立即执行首次完整采集。
9. 扫描、识别、跳过、导入和失败均写审计日志。

启动扫描必须在应用可用后异步执行，不能阻塞 FastAPI lifespan。

## 5. API 边界

后端提供以下新接口，前端只依赖这些稳定 DTO：

```text
GET    /api/v1/devices
GET    /api/v1/devices/{id}/details
GET    /api/v1/devices/{id}/entities
GET    /api/v1/profiles

GET    /api/v1/discovery/config
PUT    /api/v1/discovery/config
POST   /api/v1/discovery/scan
GET    /api/v1/discovery/jobs
GET    /api/v1/discovery/jobs/{id}

GET    /api/v1/audit-logs
GET    /api/v1/audit-logs/export
```

`GET /devices` 不得返回 community。详情字段统一包含 `raw`、`value`、`unit`、`status`、`supported`、`present` 和 `updated_at`。

WebSocket 的新增事件必须引用已经持久化的记录 ID：

```text
device_update
entity_update
alert_created
trap_received
discovery_job_update
```

## 6. 前后端并行规则

### 后端 worktree

- 只修改 `backend/**`、数据库迁移、根目录部署配置及后端文档。
- 以 `tasks/BACKEND_MULTI_PROFILE_WORK.md` 为交付契约。
- 负责生成 OpenAPI 和固定 API fixture，供前端开发使用。

### 前端 worktree

- 只修改 `frontend/**`。
- 以 `tasks/FRONTEND_MULTI_PROFILE_WORK.md` 为交付契约。
- 后端未完成时使用任务书中的 DTO fixture，不自行改变字段含义。

### 主任务

- 管理共享协议和接口边界。
- 审查两个 worktree 的改动，不接受跨边界重构。
- 统一解决冲突、运行迁移和端到端验证。
- 不增加 FastAPI worker 数；生产继续使用单 worker。

## 7. 实施阶段

1. Profile 共用包、Alembic 和通用实体模型。
2. 五 Profile 采集器、兼容投影和详情 API。
3. 快速离线/恢复、Trap 持久化、风扇语义。
4. `/24` 自动发现、启动扫描和审计。
5. 设备列表、全状态详情、键鼠明细和告警声音。
6. Admin 审计/发现页面、凭据脱敏和 WebSocket 鉴权。
7. SQLite/PostgreSQL、五 Profile 模拟器和浏览器端到端验收。

## 8. 迁移与回滚

- 建立正式 Alembic baseline，SQLite 和 PostgreSQL 都必须可升级。
- 使用 expand/migrate/contract：先新增表和双写，再切换 API/UI，最后才允许清理旧字段。
- 保留 legacy poller 回退开关，直到五 Profile 验收完成。
- 自动发现可通过配置关闭，但手工设备和已有监控数据不得受影响。
- Trap 新端口变量上线时兼容读取旧 `SNMP_TRAP_PORT` 一版，并记录弃用日志。
- 任何失败回滚不得删除旧 `devices`、`endpoints`、`alerts` 和历史指标。

## 9. 完成定义

只有满足 `docs/MULTI_PROFILE_ACCEPTANCE_PLAN.md` 的自动化测试、模拟器验证、浏览器检查和部署检查，任务才算完成。单独通过后端单测或前端构建不视为整体完成。
