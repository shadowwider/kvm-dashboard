# ADR-001：本地 Simulator 地址模式

状态：`Accepted for L0`
日期：2026-07-31
决策范围：本地进程的 HTTP、SNMP Agent 和 Trap 地址，不涉及厂家网络模型

## 1. 背景

Simulator 需要同时运行多台 SNMP Agent。当前实现提供两种地址模式：

1. 同一 IPv4 地址、不同 UDP 端口；
2. 不同 loopback IPv4 地址、相同 UDP 161 端口。

地址模式还影响 Dashboard bridge 写入的设备 host/port、Trap source host 的可模拟程度、Windows 权限、端口冲突和 Docker 可达性。

## 2. 决策

L0 默认并唯一推荐的本地验收模式是：

```text
SIM_ADDRESS_MODE=port
```

`all-profiles` 使用：

```text
127.0.0.1:11161/udp
127.0.0.1:11162/udp
127.0.0.1:11163/udp
127.0.0.1:11164/udp
127.0.0.1:11165/udp
```

`loopback` 只作为对 Trap source IP 或多地址行为的专项实验模式，不作为 L0 默认 Gate。

## 3. 原因

### 3.1 port 模式

优点：

- 不需要绑定 UDP 161 特权/保留端口；
- Windows 普通开发环境更稳定；
- 不依赖 `127.0.1.x` 在防火墙、VPN 或安全软件中的行为；
- 端口冲突可以由 doctor 在启动前精确定位；
- 最适合单机 Dashboard + Simulator 联调。

代价：

- 五台设备的 source IP 都是 `127.0.0.1`；
- Dashboard 必须保留每台设备自己的 SNMP port；
- 仅按 Trap source IP 无法区分五台设备；
- 与真实局域网“一设备一 IP”不完全一致。

### 3.2 loopback 模式

形状：

```text
127.0.1.1:161
127.0.1.2:161
...
```

优点：

- host/port 更接近真机的一设备一地址；
- Trap sender 可以 best-effort 绑定设备 host；
- 适合验证 source IP 归属问题。

代价：

- UDP 161 可能受权限、已有服务和安全策略影响；
- Windows、防火墙、VPN、容器运行时行为不一致；
- sender 绑定失败会回退，不能把 source IP 视为已保证；
- 容器内 loopback 仍只指向当前容器，不能解决跨容器访问。

## 4. 不采用的方案

### 4.1 依赖 `SIM_SNMP_PORT_BASE` 重映射 preset

不采用。

当前 built-in preset 保存显式端口 `11161..11165`，`SIM_SNMP_PORT_BASE` 不会改写它们。L0 doctor 会给出警告，但不在环境层擅自改变 topology/Profile 生成规则。

### 4.2 为 Docker 使用容器内 `127.0.0.1`

不采用。

Dashboard 容器、Simulator 容器和宿主机有各自的 loopback。把 `127.0.0.1` 写进 bridge manifest 不能跨边界访问。

### 4.3 使用 `network_mode: host` 作为默认修复

不采用。

该方案平台差异大，会绕过当前地址模型问题，也不提供可移植的生产式拓扑。Docker Simulator 的正式网络身份应在 L5/L6 设计。

### 4.4 自动杀死端口占用进程

不采用。

doctor 只读检查并返回精确地址。它不得终止未知进程，也不得清理用户的服务。

## 5. 运行规则

1. 每次启动前运行 doctor；
2. doctor 报告占用时，先人工确认进程所有权；
3. 不得通过自动 kill、`Stop-Process -Force` 或删除未知 PID 解决；
4. 端口检查必须覆盖 Simulator HTTP 和每个 SNMP UDP binding；
5. runtime 启动再次执行 UDP preflight，避免 doctor 与启动之间的竞争；
6. runtime 错误必须包含 `host:port`；
7. 切换 topology 前后的原子性属于 L5，不由本 ADR 保证。

## 6. Trap 说明

L0 只保证：

- Simulator status 显示 Trap target host/port；
- smoke 比较 Simulator target port 与 Dashboard 配置端口；
- Dashboard 进程按 `SNMP_TRAP_PORT` 启动 receiver。

L0 不保证：

- Trap notification OID 正确；
- level/message 枚举符合厂家；
- generic Trap 能按 source IP 精确归属五台 port-mode 设备；
- loopback sender 一定成功绑定源 IP；
- Trap 已被数据库保存并由 WebSocket 推送。

这些属于 L4/L6。

## 7. Docker 后果

本 ADR 的 port 模式只适用于 Dashboard 与 Simulator 在同一网络命名空间可访问 `127.0.0.1` 的情况，默认即 Windows 本地同机进程。

当前 Docker Compose 没有 Simulator service。即使新增 service，Dashboard 容器也无法通过自身 `127.0.0.1` 访问另一个容器中的 Agent。因此：

- L0 文档只给出 Dashboard Compose 的现状命令；
- Docker Simulator 全链标记为未支持；
- 上层不得根据本 ADR 推断 Docker bridge manifest 应使用什么 host；
- L5/L6 必须单独决定容器 DNS、端口暴露、Trap source 与清理边界。

## 8. 验证

自动测试：

```powershell
Set-Location 'H:\WORK\I\kvm-dashboard\backend'
.\.venv\Scripts\python.exe -m pytest tests\test_simulator_l0.py -q
```

关键断言：

- 已占用 TCP/UDP 返回非零；
- 诊断包含精确协议、host 和 port；
- secret 不出现在 JSON；
- preset 的 Agent 数和 binding 数由 smoke 精确比较。

真实运行证据记录在：

```text
docs/simulator/verification/L00_CURRENT_REPRODUCTIONS.md
```

## 9. 后续重新评估条件

出现任一情况时必须新增 ADR，不得静默修改本决策：

- built-in preset 端口改为真正可配置；
- Simulator 进入 Docker Compose；
- Dashboard poller 改为 Profile-aware；
- Trap 身份不再依赖 source IP；
- 需要同时运行多个 `all-profiles` run；
- 引入 IPv6、远程主机或真实测试 VLAN。
