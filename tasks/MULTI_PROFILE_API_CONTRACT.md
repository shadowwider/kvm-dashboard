# 多 Profile 前后端 API 契约

> 版本：`v1-draft-1`
> 日期：2026-08-01
> 基础路径：`/api/v1`

本文冻结本次并行开发使用的 DTO。后端可以增加向后兼容字段，前端不得依赖本文未定义的内部数据库字段。

## 1. 通用规则

- 时间统一为 UTC ISO 8601。
- 稳定业务 key 使用英文 snake_case。
- 中文和英文 label 由前端 i18n key 渲染，后端返回 `label_key`。
- `raw` 是设备原始值，`value` 是标准化值。
- unsupported、absent、stale 和 fault 是不同状态。
- 所有分页接口使用 `items`、`total`、`page`、`page_size`。
- 所有管理员接口需要 admin 权限。
- 所有读响应禁止包含 community。

统一字段状态：

```json
{
  "key": "fan_speed",
  "label_key": "fields.fan_speed",
  "raw": "3200 RPM",
  "value": 3200,
  "unit": "RPM",
  "status": "ok",
  "supported": true,
  "present": true,
  "stale": false,
  "updated_at": "2026-08-01T08:00:00Z"
}
```

`status` 允许：

```text
ok
info
warning
critical
offline
unknown
unsupported
absent
stale
```

## 2. 设备摘要

### `GET /devices`

保留旧的数组响应兼容期，但本次前端同时兼容分页对象。目标响应：

```json
{
  "items": [
    {
      "id": "sim-ccdm-01",
      "name": "SIM / CCDM Matrix",
      "host": "127.0.0.1",
      "port": 11162,
      "location": null,
      "description": null,
      "profile": {
        "id": "ccdm_matrix",
        "version": "1.0.0",
        "evidence_version": "schema=1;sha256=...",
        "label_key": "profiles.ccdm_matrix",
        "role": "matrix"
      },
      "system_oid": "1.3.6.1.4.1.32828.3.257.10",
      "model_name": "ControlCenter-Digital",
      "serial_number": "SIM-CCDM-0001",
      "credential_configured": true,
      "is_active": true,
      "reachability": {
        "status": "online",
        "last_check": "2026-08-01T08:00:00Z",
        "latency_ms": 12
      },
      "data_freshness": {
        "status": "fresh",
        "last_full_poll": "2026-08-01T07:59:45Z",
        "age_seconds": 15
      },
      "health": {
        "status": "warning",
        "warning_count": 1,
        "critical_count": 0
      },
      "endpoint_count": 2,
      "entity_count": 12,
      "active_alert_count": 1,
      "created_at": "2026-08-01T07:00:00Z",
      "updated_at": "2026-08-01T08:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 100
}
```

兼容要求：前端能从旧 `last_status`、`last_health_check`、`last_poll` 生成临时 reachability/freshness；后端不得在旧 DTO 中继续返回 community。

## 3. 设备详情

### `GET /devices/{device_id}/details`

```json
{
  "device": {
    "id": "sim-vcpu-01",
    "name": "SIM / VisionXS CPU",
    "profile": {
      "id": "visionxs_cpu",
      "version": "1.0.0",
      "label_key": "profiles.visionxs_cpu",
      "role": "independent_cpu"
    },
    "reachability": {"status": "online", "last_check": "..."},
    "data_freshness": {"status": "fresh", "last_full_poll": "..."}
  },
  "sections": [
    {
      "key": "identity",
      "label_key": "detail.sections.identity",
      "order": 10,
      "status": "ok",
      "fields": [
        {
          "key": "serial_number",
          "label_key": "fields.serial_number",
          "raw": "SIM-VISION-CPU-0001",
          "value": "SIM-VISION-CPU-0001",
          "unit": null,
          "status": "ok",
          "supported": true,
          "present": true,
          "stale": false,
          "updated_at": "..."
        }
      ],
      "entities": []
    },
    {
      "key": "links",
      "label_key": "detail.sections.links",
      "order": 80,
      "status": "ok",
      "fields": [],
      "entities": [
        {
          "entity_key": "link_channel_table:link_channel_index=1",
          "entity_type": "link_channel",
          "label": "Link 1",
          "index_key": [
            {"name": "link_channel_index", "value": 1}
          ],
          "status": "ok",
          "present": true,
          "stale": false,
          "updated_at": "...",
          "fields": []
        }
      ]
    }
  ]
}
```

`sections` 允许但不限于：

```text
identity
health
power
environment
network
modules
video
usb_hid
links
cards_ports
errors
```

## 4. 通用实体

### `GET /devices/{device_id}/entities`

Query：

```text
table_id
entity_type
present
page
page_size
```

响应使用通用分页对象，item 使用详情接口中的 entity 结构，并增加 `table_id`、`profile_id`。

## 5. Profile metadata

### `GET /profiles`

```json
{
  "items": [
    {
      "id": "visionxs_cpu",
      "version": "1.0.0",
      "evidence_version": "schema=1;sha256=...",
      "product": "VisionXS CPU",
      "role": "independent_cpu",
      "system_oid": "1.3.6.1.4.1.32828.3.768.768",
      "label_key": "profiles.visionxs_cpu",
      "section_keys": ["identity", "power", "environment", "network", "video", "usb_hid", "links", "errors"]
    }
  ]
}
```

## 6. 自动发现

### `GET /discovery/config`

```json
{
  "cidr": "192.168.1.0/24",
  "snmp_port": 161,
  "timeout_seconds": 0.5,
  "retries": 0,
  "concurrency": 64,
  "enabled": true,
  "scan_on_startup": true,
  "credential_configured": true,
  "updated_at": "..."
}
```

### `PUT /discovery/config`

community 可选；省略表示保留原凭据：

```json
{
  "cidr": "192.168.1.0/24",
  "community": "private-value",
  "snmp_port": 161,
  "timeout_seconds": 0.5,
  "retries": 0,
  "concurrency": 64,
  "enabled": true,
  "scan_on_startup": true
}
```

响应不得回显 community。

### `POST /discovery/scan`

返回 HTTP 202：

```json
{
  "job_id": 42,
  "status": "queued"
}
```

### `GET /discovery/jobs`

### `GET /discovery/jobs/{job_id}`

```json
{
  "id": 42,
  "status": "running",
  "cidr": "192.168.1.0/24",
  "total_hosts": 254,
  "scanned_hosts": 128,
  "responded_hosts": 5,
  "recognized_hosts": 5,
  "imported_devices": 4,
  "updated_devices": 1,
  "unsupported_devices": 0,
  "no_response_hosts": 123,
  "error_count": 0,
  "started_at": "...",
  "finished_at": null,
  "last_error": null
}
```

任务状态：

```text
queued
running
completed
failed
```

## 7. 审计日志

### `GET /audit-logs`

Query：

```text
actor_id
action
target_type
target_id
result
date_from
date_to
page
page_size
```

```json
{
  "items": [
    {
      "id": 1001,
      "actor": {"id": 1, "username": "admin", "role": "admin"},
      "action": "discovery.scan",
      "target": {"type": "discovery_job", "id": "42"},
      "result": "success",
      "request_id": "req-...",
      "ip_address": "127.0.0.1",
      "user_agent": "Mozilla/5.0",
      "change_summary": {
        "cidr": "192.168.1.0/24",
        "imported_devices": 4
      },
      "created_at": "..."
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

### `GET /audit-logs/export`

使用同样筛选参数，返回 CSV。

## 8. 告警

告警对象至少包含：

```json
{
  "id": 105,
  "device_id": "sim-ccdm-01",
  "endpoint_id": null,
  "entity_key": null,
  "oid_name": "reachability",
  "alert_type": "offline",
  "severity": "critical",
  "message": "Device is offline",
  "raw_value": null,
  "trap_level": null,
  "trap_oid": null,
  "is_resolved": false,
  "created_at": "..."
}
```

## 9. WebSocket

连接：

```text
WS /api/v1/ws/monitor?token=<JWT>
```

统一 envelope：

```json
{
  "type": "alert_created",
  "event_id": "alert:105",
  "timestamp": "2026-08-01T08:00:00Z",
  "data": {}
}
```

事件 data：

```text
device_update       -> {"device": <device summary>}
entity_update       -> {"device_id": "...", "entity": <entity>}
alert_created       -> {"alert": <alert>}
trap_received       -> {"alert": <alert>, "trap": {"level": 3, "message": "...", "notification_oid": "..."}}
discovery_job_update-> {"job": <discovery job>}
```

兼容期内前端继续识别旧 `new_alerts`、顶层 `device_id/status` 和顶层 `alerts`，但声音只对带持久化 Alert ID 的新事件播放。

## 10. 错误响应

```json
{
  "detail": {
    "code": "validation_error",
    "message": "CIDR contains too many hosts",
    "fields": {"cidr": "Maximum 256 usable hosts"},
    "retryable": false
  }
}
```

至少支持：

```text
validation_error
not_found
unsupported_profile
discovery_already_running
forbidden
unauthorized
poll_failed
internal_error
```
