# KVM 监控系统 — 后端 API 交互文档

> 基础路径 (Base URL): `/api/v1`
> 认证方式: Bearer Token (JWT)

---

## 1. 认证模块 (Auth)

### 1.1 登录获取 Token
- **POST** `/auth/login`
- **Content-Type**: `application/x-www-form-urlencoded`
- **Body**: `username=admin&password=admin123`
- **Response**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
    "token_type": "bearer"
  }
  ```

### 1.2 获取当前用户信息
- **GET** `/auth/me`
- **Headers**: `Authorization: Bearer <token>`
- **Response**:
  ```json
  {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "is_active": true
  }
  ```

---

## 2. 大屏统计模块 (Stats)

### 2.1 获取全局统计数字 (顶部 4 个 KPI)
- **GET** `/stats/dashboard`
- **Response**:
  ```json
  {
    "total_devices": 10,
    "online_devices": 9,
    "offline_devices": 1,
    "total_endpoints": 320,
    "online_endpoints": 315,
    "active_alerts": 3,
    "timestamp": "2026-02-26T12:00:00Z"
  }
  ```

---

## 3. 设备与终端模块 (Devices & Endpoints)

### 3.1 获取所有 KVM 交换机 (第一层热力图)
- **GET** `/devices`
- **Query**: `skip=0`, `limit=100`
- **Response**:
  ```json
  [
    {
      "id": "CCDC-01",
      "name": "核心机房-KVM1",
      "host": "192.168.1.10",
      "last_status": "online", 
      "last_poll": "2026-02-26T12:05:00Z",
      "last_metrics": {
        "ports": {
          "1": { "port_status": "3", "ep_id": "0x0005F9EF", "ep_name": "CPU-1" },
          "2": { "port_status": "1" },
          "3": { "port_status": "1" }
        }
      }
    }
  ]
  ```

### 3.2 手动触发某台设备轮询
- **POST** `/devices/{device_id}/poll`
- **Response**: `{"status": "polling_started"}`

### 3.3 获取某台 KVM 下的所有终端
- **GET** `/endpoints`
- **Query**: `device_id=CCDC-01`
- **Response**:
  ```json
  [
    {
      "id": "CCDC-01_1",
      "device_id": "CCDC-01",
      "name": "塔台协同终端",
      "index": 1,
      "last_status": {
        "ep_name": "操作员终端-A",
        "ep_online": "yes",
        "con_console_usb": "none", // 新增：即使未连接也会返回 'none' 而非空
        "con_display_conn": "connected",
        "temperature": "38.5"
      },
      "updated_at": "2026-02-26T12:05:00Z"
    }
  ]
  ```

---

## 4. 拓扑图模块 (Topology)

### 4.1 获取单台设备的拓扑树结构 (第二层 React Flow 数据)
- **GET** `/topology/{device_id}`
- **Response**:
  ```json
  {
    "nodes": [
      {
        "id": "CCDC-01",
        "type": "kvmSwitch",
        "data": { "label": "核心机房-KVM1", "status": "online" }
      },
      {
        "id": "CCDC-01_1",
        "type": "endpoint",
        "data": { "label": "塔台协同终端", "status": "online", "video_signal": "dp" }
      }
    ],
    "edges": [
      {
        "id": "e_CCDC-01_CCDC-01_1",
        "source": "CCDC-01",
        "target": "CCDC-01_1",
        "animated": true,
        "style": { "stroke": "#22c55e" } // 连接正常为绿色实线，断开为红色虚线
      }
    ]
  }
  ```

---

## 5. 别名管理模块 (Aliases) 🌟 (Admin 专用)

### 5.1 获取所有别名
- **GET** `/aliases`
- **Query**: `target_type=device` 或 `target_type=endpoint` (可选)
- **Response**:
  ```json
  [
    {
      "target_id": "CCDC-01_1",
      "target_type": "endpoint",
      "alias": "塔台协同终端",
      "note": "2号楼4层"
    }
  ]
  ```

### 5.2 创建或更新别名 (Inline 编辑用)
- **PUT** `/aliases/{target_id}`
- **Body**:
  ```json
  {
    "target_type": "endpoint",
    "alias": "塔台协同终端-改",
    "note": "测试"
  }
  ```
- **Response**: 返回更新后的完整对象。

---

## 6. 告警管理模块 (Alerts)

### 6.1 获取告警列表 (右侧滑动面板区)
- **GET** `/alerts`
- **Query**: `is_resolved=false`, `limit=50`
- **Response**:
  ```json
  [
    {
      "id": 105,
      "device_id": "CCDC-01",
      "endpoint_id": "CCDC-01_1",
      "oid_name": "temperature",
      "severity": "critical",
      "message": "核心机房-KVM1 终端温度异常: 65.5°C",
      "is_resolved": false,
      "created_at": "2026-02-26T12:00:00Z"
    }
  ]
  ```

### 6.2 导出告警日志 (CSV 下载)
- **GET** `/alerts/export`
- **Query**: `device_id=CCDC-01`, `severity=critical` (皆可选)
- **Response**: 返回 `.csv` 文件流。

### 6.3 确认单条/批量告警
- 单条：**PATCH** `/alerts/{alert_id}/resolve`
- 批量：**POST** `/alerts/resolve-all` （可按 `device_id` 过滤）

---

## 7. 历史指标图表 (Metrics / ECharts)

### 7.1 获取 ECharts 历史曲线数据
- **GET** `/metrics/history`
- **Query**: `oid_name=temperature`, `device_id=CCDC-01`, `endpoint_id=CCDC-01_1` (可选), `hours=24`
- **Response**:
  ```json
  [
    {
      "time": "2026-02-26T10:00:00Z",
      "value_num": 42.5
    },
    {
      "time": "2026-02-26T11:00:00Z",
      "value_num": 43.1
    }
  ]
  ```

---

## 8. 实时数据流 (WebSocket)

### 8.1 建立连接
- **URL**: `ws://<backend_host>/api/v1/ws/monitor`
- (目前暂未加 JWT 鉴权，直接连即可，需生产环境前端加上 token url parameter)

### 8.2 数据抛出格式

#### 场景 1：设备/终端状态刷新
```json
{
  "type": "device_update",
  "device_id": "CCDC-01",
  "status": {
    "temperature": "45.0°C",
    "main_power": "on"
  },
  "timestamp": "2026-02-26T12:00:00Z"
}
```

#### 场景 2：新告警触发 (包含主动轮询发现和被动 Trap 推送)
```json
{
  "type": "new_alerts",
  "alerts": [
    {
      "device_id": "CCDC-01",
      "severity": "critical",
      "message": "电源掉电！"
    }
  ],
  "timestamp": "2026-02-26T12:00:05Z"
}
```
