# KVM Simulator Pro — 使用说明

可配置的 G&D KVM SNMP 模拟器，用于验证 kvm-dashboard 前后端是否正常工作。

---

## 快速启动

```bash
# 在 backend 目录下，使用项目虚拟环境
cd /path/to/kvm-dashboard/backend

# Windows
.venv\Scripts\python.exe kvm_simulator.py

# Linux / macOS
.venv/bin/python kvm_simulator.py
```

启动后：
- **Web 控制台**：http://localhost:8888
- **SNMP 第 1 台交换机**：UDP 11161
- **Trap 发送目标**：127.0.0.1:10162（后端监听端口）

---

## 环境变量（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SIM_BASE_PORT` | `11160` | SNMP 端口从 BASE_PORT+1 开始分配 |
| `SIM_WEB_PORT` | `8888` | Web 控制台端口 |
| `TRAP_TARGET_HOST` | `127.0.0.1` | Trap 发送目标 IP |
| `SNMP_TRAP_PORT` | `10162` | Trap 发送目标端口 |
| `SNMP_COMMUNITY` | `public` | SNMP 社区字符串 |

```bash
# 示例：自定义端口
SIM_BASE_PORT=20000 SIM_WEB_PORT=9000 .venv/bin/python kvm_simulator.py
```

---

## 对接 KVM Dashboard

模拟器启动后，需要在 KVM Dashboard 管理后台手动添加设备：

1. 打开 http://localhost:8000/admin（或 Dashboard 的管理页面）
2. 添加设备：
   - **Host**：`127.0.0.1`
   - **Port**：`11161`（第 1 台），`11162`（第 2 台）……
   - **Community**：`public`
3. 保存后，后端轮询器会自动开始采集数据

---

## Web 控制台使用

### 添加 / 删除交换机

- 点击右上角 **＋ 添加交换机** → 输入名称（留空自动命名）
- 新交换机会自动分配下一个可用 SNMP 端口
- 点击左侧列表中交换机右上角的 **✕** 删除

### 修改交换机系统状态

选中交换机后，在 **交换机状态** 区块中可直接修改：

| 字段 | 可操作内容 |
|------|-----------|
| 温度 (°C) | 直接输入数值 |
| 主电源 / 冗余电源 | ON / OFF |
| 网口 | UP / DOWN |
| 风扇 1-4 (RPM) | 直接输入数值 |

**快捷预设按钮**：
- **模拟断电**：主电源 + 冗余电源同时断开
- **模拟过温**：温度设为 72°C（超出告警阈值 55°C）
- **恢复正常**：电源恢复、温度 45°C、风扇 3200 RPM

### 插入 / 拔出 CPU 和 CON

- 点击端点列表底部的 **＋ 插入 CPU** 或 **＋ 插入 CON**
- 系统自动分配下一个空闲 Row 号（对应 SNMP 表行索引）
- 点击端点右上角的 **✕ 拔出** 移除该端点

### 实时修改端点字段

插入后可立即通过下拉框修改所有关键字段：

**CPU 端点可控字段**：

| 字段 | 可选值 | 说明 |
|------|--------|------|
| 在线状态 | online / ready / offline | deviceStatus |
| 目标电源 | on / off | targetPower |
| 视频线缆 | connected / notConnected | targetVideoCable |
| 视频信号 | DP / HDMI / DVI-SL / DVI-DL / VGA / none | targetVideoSignal |
| USB HID | initialized / connected / notConnected | targetUsbHid |
| 访问状态 | local / remote / localExclusive / remoteExclusive | targetAccess |
| 温度 | 数值输入 | temperature1 |
| 网口 | up / down | networkInterface0 |

**CON 端点可控字段**：

| 字段 | 可选值 | 说明 |
|------|--------|------|
| 在线状态 | online / ready / offline | deviceStatus |
| PS/2 键鼠 | 键盘+鼠标 / 仅键盘 / 仅鼠标 / none | consolePS2Connection |
| USB 键鼠 | 键盘+鼠标 / 仅键盘 / 仅鼠标 / none | consoleUSBConnection |
| 显示器连接 | connected / notConnected | displayConnection |
| 显示器型号 | 文本输入 | displayType |
| 画面冻结 | false / true | freeze |
| 活跃 TX 口 | 1 / 2 | activeTransmissionPort |
| 温度 | 数值输入 | temperature1 |
| 网口 | up / down | networkInterface0 |

### 发送 Trap 告警

**手动发送**：
1. 选择 Level（3=ERROR 常用，对应 Dashboard 的 warning 级别）
2. 填入消息文本
3. 点击 **发送 Trap**

**快捷按钮**（自动填充常用消息）：

| 按钮 | Level | 消息格式 |
|------|-------|---------|
| CPU 掉线 | 3 ERROR | `CPU module CPU-{sw_id}-001 went offline` |
| CPU 上线 | 5 NOTICE | `CPU module CPU-{sw_id}-001 came online` |
| CON 掉线 | 3 ERROR | `CON module CON-{sw_id}-001 went offline` |
| CON 上线 | 5 NOTICE | `CON module CON-{sw_id}-001 came online` |
| 温度告警 | 4 WARNING | `Temperature too high on KVM-SIM-{sw_id}: 72.0C` |
| 电源告警 | 3 ERROR | `Main power failure on KVM-SIM-{sw_id}` |

> **注意**：Trap 消息里的 `CPU-{sw_id}-001` 对应的是 SNMP 表的 `ep_id`（Column 2），后端 `trap_receiver.py` 通过匹配 `last_status.ep_id` / `last_status.con_id` 字段来定位端点并加上设备名称。要让告警显示完整的"交换机名/端点名"格式，需要先通过轮询让后端建立端点记录。

---

## Trap Level 含义

| Level | 名称 | Dashboard 严重度 |
|-------|------|----------------|
| 0 | EMERGENCY | critical |
| 1 | ALERT | critical |
| 2 | CRITICAL | critical |
| 3 | ERROR | warning |
| 4 | WARNING | warning |
| 5 | NOTICE | info |

---

## OID 对应关系（供调试）

| SNMP OID | 字段 |
|----------|------|
| `1.3.6.1.4.1.32828.3.257.16.2.3.1.0` | 主电源 |
| `1.3.6.1.4.1.32828.3.257.16.2.3.3.0` | 温度 |
| `1.3.6.1.4.1.32828.3.257.16.1.2.2.3.1000.1.{col}.{row}` | CPU 端点表 |
| `1.3.6.1.4.1.32828.3.257.16.1.1.2.3.1000.1.{col}.{row}` | CON 端点表 |
| Trap Notification OID | `1.3.6.1.4.1.32828.2.1.0.4` |
| Trap level varbind | `1.3.6.1.4.1.32828.2.1.0.2` |
| Trap message varbind | `1.3.6.1.4.1.32828.2.1.0.3` |

---

## 常见验证场景

### 验证端点状态采集

1. 模拟器启动 → Dashboard 添加设备 → 等待轮询（15-45 秒）
2. Web 控制台将某个 CPU 的"在线状态"改为 `offline`
3. 在 Dashboard 的矩阵视图中观察该 CPU 是否变红

### 验证键鼠状态显示

1. 将某个 CON 的 USB 键鼠改为 `仅键盘`
2. 点击 Dashboard 中该 CON 查看详情
3. 键鼠状态应显示"部分连接（警告）"

### 验证 Trap 告警接收

1. 确保后端已监听 Trap 端口（`SNMP_TRAP_PORT=10162`）
2. 点击"CPU 掉线"快捷按钮
3. Dashboard 右侧告警流应立即出现新告警，消息格式为"KVM-SIM-1/CPU-HOST-SW1-001 went offline"

### 验证温度告警阈值

1. 点击"模拟过温"预设（温度设为 72°C）
2. 等待下次轮询后，Dashboard 设备卡片状态应变为 warning

### 验证电源故障

1. 点击"模拟断电"预设
2. 轮询后设备状态变 warning；同时手动发送"电源告警"Trap 验证告警流
