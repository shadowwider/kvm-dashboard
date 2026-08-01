# 后端开发任务书：五 Profile 采集、发现、告警与审计

## 1. 任务目标

把生产后端从固定 CCDC OID 轮询改造成 Profile 驱动采集平台，并保持旧矩阵功能可用。必须完整支持：

| Profile | `sysObjectID` |
|---|---|
| `ccdc_legacy` | `1.3.6.1.4.1.32828.3.257.16` |
| `ccdm_matrix` | `1.3.6.1.4.1.32828.3.257.10` |
| `dp12_mux_atc` | `1.3.6.1.4.1.32828.3.1792.17` |
| `visionxs_con` | `1.3.6.1.4.1.32828.3.769.768` |
| `visionxs_cpu` | `1.3.6.1.4.1.32828.3.768.768` |

CC160 是 `ccdm_matrix` 的型号资料，不是第六个协议 Profile。

## 2. 必读参考资料

实现前必须阅读：

```text
docs/MULTI_PROFILE_DEVELOPMENT_MASTER_PLAN.md
docs/GD_MIB_COMPATIBILITY_AND_PROFILE_PLAN.md
docs/reference/GD_MIB_DIFF_REGISTER.md
docs/reference/docs/devices/cc160-controlcenter-digital.md
docs/reference/docs/devices/ccdm-controlcenter-digital.md
docs/reference/docs/devices/dp12-mux-atc.md
docs/reference/docs/devices/visionxs-cpu-con.md
backend/simulator/profile_model.py
backend/simulator/profile_catalog.py
backend/simulator/catalog/l2_profiles.json
backend/simulator/catalog/l2_default_fixtures.json
docs/simulator/decisions/ADR-003-OPTIONAL-GROUP-AND-FIXTURE-ROWS.md
docs/simulator/decisions/ADR-004-STATE-KEYS-AND-COMPOSITE-INDEXES.md
```

`l2_profiles.json` 是机器可读协议目录；设备字典和 evidence 文件是协议事实来源。禁止从旧 `oid_map.py` 推导新设备 OID。

## 3. 写入范围

允许修改：

- `backend/**`
- Alembic 配置和迁移文件
- `.env.example`、`.env.production`、`docker-compose.yml`
- 与本任务直接相关的后端文档

不得修改 `frontend/**`。不得撤销当前工作区已有的 poller、health probe、模拟器和日志相关改动。

## 4. 数据模型

### 4.1 Device 扩展

增加：

- `profile_id`
- `profile_version`
- `profile_evidence_version`
- `serial_number`
- `mac_addresses` JSON
- `discovery_source`
- `last_discovered_at`
- `last_full_poll_status`

API 输出不得包含 community。community 只允许在管理员写接口中传入，读接口返回布尔值 `credential_configured`。

### 4.2 DeviceEntity

新增通用实体表：

- 主键
- `device_id`
- `profile_id`
- `table_id`
- `entity_type`
- `entity_key`
- `index_key` JSON
- `raw_values` JSON
- `normalized_values` JSON
- `field_states` JSON
- `is_present`
- `is_stale`
- `first_seen_at`
- `last_seen_at`
- `updated_at`

唯一约束必须覆盖 `(device_id, profile_id, table_id, entity_key)`。

### 4.3 ProfileFieldState 或等价结构

设备标量和实体字段都必须表达：

```json
{
  "raw": "3200 RPM",
  "value": 3200,
  "unit": "RPM",
  "status": "ok",
  "supported": true,
  "present": true,
  "updated_at": "2026-08-01T08:00:00Z"
}
```

可以使用 JSON 存储，但必须有稳定 schema 和测试。

### 4.4 DiscoveryConfig / DiscoveryJob

配置至少包含：

- IPv4 CIDR
- SNMP v2c community
- UDP 端口，默认 161
- timeout
- retries
- concurrency
- enabled
- scan_on_startup

任务至少记录总地址数、已扫描、已识别、已导入、已更新、未知 G&D、无响应、错误、开始和结束时间。

### 4.5 AuditLog

记录：

- actor ID、用户名、角色
- action
- target type、target ID
- result
- request ID、IP、User-Agent
- 脱敏后的 change summary
- timestamp

禁止记录密码、community、JWT、SNMPv3 secret。登录、用户管理、设备 CRUD、发现、导入、手工轮询、OID/阈值、告警确认和别名修改必须覆盖。

## 5. 数据库迁移

1. 引入 Alembic，并为当前 schema 建立可重复 baseline。
2. 新表、新列和索引使用迁移创建，不能继续只依赖 `create_all` 或 `main.py` 手写补列。
3. SQLite 和 PostgreSQL 均运行升级测试。
4. 旧表保留，先双写 `Endpoint` 兼容投影。
5. 不在本任务中删除旧数据列。

## 6. Profile 运行时

将模拟器 Profile 目录抽到中立包，例如 `backend/app/snmp/profiles/` 或 `backend/kvm_profiles/`，生产采集器和模拟器共同导入。

Profile 运行时必须支持：

- 精确 `sysObjectID`
- 标量 `.0`
- 单索引表
- 复合索引表
- syntax、enum、unit
- mandatory / optional group
- read-only / read-write 元数据
- raw 到 normalized 转换
- 显示 section 元数据

本期生产系统只读。DP Profile 中存在的可写 OID 不允许通过通用 OID 页面或采集器执行 SET。

## 7. 采集器

### 7.1 Profile 识别

设备首次加入或 Profile 未确认时：

1. GET `sysObjectID.0`
2. 完整 OID 精确匹配
3. 读取身份标量
4. 保存 Profile 和证据版本
5. 未匹配设备标记 unsupported，不回退到 `ccdc_legacy`

### 7.2 Poll plan

- 可达性任务只 GET `sysObjectID.0`。
- 快速状态任务按 Profile 选择少量关键字段。
- 完整任务按 Profile 的 scalar/table 定义采集。
- 表解析必须验证返回 OID 属于列根，并按定义数量提取索引。
- 单轮完整 WALK 成功后才进行实体 absent 对账。
- 设备超时、列失败或 optional group 不支持时，不删除既有实体。

### 7.3 风扇

- 合法 `0`：存在但停止，应产生状态而不是删除。
- `noSuchObject`：字段或 optional group 不支持。
- 缺行：只有完整表 WALK 成功后才能进入缺失计数。
- 设备离线：保留最后值并标记 stale。
- DisplayString：保留 raw；能可靠提取数字时另存 normalized，解析失败为 unknown。

### 7.4 键盘和鼠标

`none/keyboard/mouse/keyboardMouse` 标准化为：

```json
{"keyboard": true, "mouse": true, "source": "console_usb_connection"}
```

PS/2、USB 分开保存。`targetUsbHid=connected/initialized` 只表示 HID 状态，不能伪造为确定的键盘或鼠标。

## 8. 快速离线、告警和 Trap

- 健康循环不执行 legacy 表 WALK。
- 默认目标：256 台受管设备时掉线识别 2-3 秒，并暴露容量退化指标。
- offline/recovery 必须创建持久化 Alert，提交成功后再广播。
- WebSocket 告警事件包含真实 Alert ID。
- 阈值告警继续使用去重窗口；offline/recovery 不得被错误吞掉。
- Trap 保存全部 raw varbind，并同时生成持久化 Alert。
- level 到 severity 使用平台配置；无配置时保留原始 level，并使用稳定默认值。

## 9. 自动发现

- 只接受 IPv4 CIDR，限制最大 host 数，默认允许 `/24`。
- 并发只执行 `sysObjectID.0` GET，不做完整 WALK。
- 精确匹配五 Profile 后直接自动导入。
- 使用 host、Profile、serial、MAC 防止重复。
- 未知 G&D 记录为 unsupported，不自动套用 Profile。
- 启动扫描在应用启动完成后创建后台任务。
- 同一时刻只允许一个扫描任务，重复请求返回当前任务。
- community 在 API、日志、异常和审计中全部脱敏。

## 10. REST 与 WebSocket

按总方案实现：

- Profile 列表
- 设备摘要
- Profile 驱动详情
- 通用实体列表
- 发现配置和任务
- 审计日志和 CSV

WebSocket 必须鉴权。推荐使用短期 ticket 或 bearer token query parameter，并验证用户状态；不能继续允许匿名生产连接。

详情 DTO 的 section 和 field 顺序由 Profile metadata 决定。后端必须提供稳定 key，前端不根据中文 label 写业务判断。

## 11. 测试要求

至少新增：

- 五 Profile 精确识别测试
- 所有 Profile scalar/table 采集测试
- CCDM 卡/端口、CPU/CON 风扇等复合索引测试
- optional/noSuchObject 测试
- 风扇 0、缺行、离线 stale 测试
- 键鼠枚举和 HID 未区分测试
- offline/recovery 持久化与 WebSocket 顺序测试
- Trap 正式 OID、旧模拟器 OID、raw level 测试
- `/24` 发现、去重、未知设备、启动扫描测试
- community 脱敏和审计脱敏测试
- SQLite/PostgreSQL 迁移测试

保持现有测试全部通过。提交交付说明时列出修改文件、迁移版本、测试命令和结果。

## 12. 后端完成定义

五个模拟器实例可以被自动发现、自动导入、完整采集，并通过详情 API 返回各自不同的全部状态；断网、恢复和 Trap 都先持久化后推送；任何读 API 都不泄露 community；数据库可以从旧 schema 升级且不丢数据。
