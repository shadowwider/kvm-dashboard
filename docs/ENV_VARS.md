# KVM Dashboard — 环境变量参考

所有环境变量均通过 `.env.production`（Docker 部署）或 shell 环境变量注入，对应 `backend/app/config.py` 中的 `Settings` 类。

变量名不区分大小写（pydantic-settings 默认行为）。

---

## 数据库

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `DB_MODE` | string | `sqlite` | 数据库模式：`postgres`（生产）或 `sqlite`（本地测试） |
| `POSTGRES_HOST` | string | `localhost` | PostgreSQL 主机名（Docker 中为服务名 `postgres`） |
| `POSTGRES_PORT` | int | `5432` | PostgreSQL 端口 |
| `POSTGRES_DB` | string | `kvm_monitor` | 数据库名 |
| `POSTGRES_USER` | string | `kvm_user` | 数据库用户 |
| `POSTGRES_PASSWORD` | string | `change_me` | ⚠️ **必须修改** — 数据库密码 |
| `SQLITE_PATH` | string | `kvm_test.db` | SQLite 文件路径（仅 `DB_MODE=sqlite` 时生效） |

**生产部署必须设置 `DB_MODE=postgres`**，Docker Compose 已通过 `environment` 块覆盖此值。

---

## 认证

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `SECRET_KEY` | string | `change_me_to_a_random_64_char_string` | ⚠️ **必须修改** — JWT 签名密钥，建议 64 位随机字符串 |
| `ALGORITHM` | string | `HS256` | JWT 签名算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | `480` | JWT Token 有效期（分钟，默认 8 小时） |
| `ADMIN_USERNAME` | string | `admin` | 首次启动时创建的管理员用户名 |
| `ADMIN_PASSWORD` | string | `admin123` | ⚠️ **建议修改** — 管理员初始密码（登录后可在界面修改） |

生成随机 `SECRET_KEY`：
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## SNMP

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `SNMP_DEFAULT_COMMUNITY` | string | `public` | SNMP v2c Community 字符串（轮询时使用） |
| `SNMP_TRAP_PORT` | int | `10162` | SNMP Trap 监听 UDP 端口。Docker 中为容器内端口，宿主机侧同名变量控制映射端口 |
| `SNMP_POLL_INTERVAL` | int | `45` | **完整指标**轮询间隔（秒）：GET/WALK、时序归档和阈值告警。不要为了设备失联检测而降低此值。 |
| `SNMP_HEALTH_POLL_ENABLED` | bool | `true` | 是否启用轻量 SNMP 可达性探测。 |
| `SNMP_HEALTH_POLL_INTERVAL` | float | `1.0` | 交换机 `sysObjectID` 快速探测间隔（秒）。 |
| `SNMP_HEALTH_TIMEOUT` | float | `0.25` | 每次快速探测的 UDP 超时（秒）。 |
| `SNMP_HEALTH_RETRIES` | int | `1` | 快速探测重试次数；默认总请求预算约 0.5 秒。 |
| `SNMP_HEALTH_CONCURRENCY` | int | `20` | 同时快速探测的设备数；必须按设备规模核算。 |
| `SNMP_HEALTH_FAILURE_THRESHOLD` | int | `1` | 达到多少次失败探测后才将交换机置为离线。增加该值会降低误报，但可能超过 2 秒目标。 |
| `SNMP_ENDPOINT_STATUS_POLL_ENABLED` | bool | `true` | 每个健康周期额外读取 CPU、CON 和物理端口的**状态列**；不执行完整指标 WALK，端口与模块索引不会被假定为一一对应。 |

### 双速 SNMP 运行方式

- **整台交换机、管理网或交换机电源断开**：设备无法发送 Trap，因此由 `sysObjectID` 健康探测负责。默认 1 秒调度 + 约 0.5 秒 SNMP 重试预算，目标为 1–2 秒；实际结果受网络、设备数和并发容量限制。
- **CPU/CON 模块**：已识别的 `went offline` / `came online` Trap 会立即更新端点状态；每秒状态列探测和完整轮询用于复核。
- **物理端口/网线**：读取 `portTable.portStatus` 并实时推送 `up/down/noModule/moduleDeactivated` 变化。未取得真实设备 OID 对照样本前，系统不会将 portTable 行索引自动等同于 CPU/CON 模块索引。
- 管理界面旧的设备 `poll_interval` 字段不参与任何运行时调度，已从编辑界面移除；它不能用于设置一秒轮询。

容量估算：

```text
预计最坏扫描时间 = ceil(活跃设备数 / SNMP_HEALTH_CONCURRENCY)
                 × (SNMP_HEALTH_TIMEOUT × (SNMP_HEALTH_RETRIES + 1)
                    + SNMP_HEALTH_TIMEOUT)

第二项为每台设备可达后并行读取 CPU、CON 和物理端口三个状态列的一次无重试请求预算。
```

该值必须小于 `SNMP_HEALTH_POLL_INTERVAL`。`/api/v1/health` 的 `health_probe.capacity_degraded`、`estimated_scan_seconds` 和周期日志会报告无法满足该约束的部署。

> **SNMP Trap 端口说明**：G&D 设备默认发送到 UDP 162。生产环境一般使用非特权端口（如 10162）映射：
> - 宿主机防火墙将 `162/udp` 转发到 `10162/udp`，或直接用 `iptables PREROUTING`
> - `docker-compose.yml` 中映射规则：`${SNMP_TRAP_PORT:-10162}:10162/udp`

---

## 原始 SNMP 数据日志

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `SNMP_RAW_LOG_ENABLED` | bool | `true` | 是否将原始 SNMP 数据写入独立日志文件 |

启用后，日志文件写入容器内 `/app/logs/`（Docker Compose 已挂载到宿主机 `./logs/`）：

| 文件 | 内容 |
|------|------|
| `logs/trap_raw.log` | 每条收到的 Trap：源 IP、level、message、完整 varbind 列表 |
| `logs/poll_raw.log` | 每次轮询的 GET/WALK 原始返回值（OID 名称、pysnmp 类型、原始值） |

两个文件均采用轮转策略：单文件上限 20 MB，保留最近 10 个文件（最大占用约 200 MB）。

**关闭日志**（数据已入库，仅用于调试）：
```bash
# .env.production 中设置
SNMP_RAW_LOG_ENABLED=false
```

---

## 服务

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `BACKEND_HOST` | string | `0.0.0.0` | FastAPI 监听地址（Docker 中不需要修改） |
| `BACKEND_PORT` | int | `8000` | FastAPI 监听端口 |
| `LOG_LEVEL` | string | `INFO` | 应用日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## Docker Compose 专用变量

以下变量仅在 `docker-compose.yml` 中引用，不传入后端 `config.py`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FRONTEND_PORT` | `80` | 宿主机前端访问端口（映射到 Nginx 容器的 80） |
| `POSTGRES_PORT` | `5432` | 宿主机数据库暴露端口（仅开发时需要直连数据库） |
| `SNMP_TRAP_PORT` | `10162` | 宿主机 SNMP Trap UDP 端口（见上方 SNMP 说明） |
| `TZ` | `Asia/Shanghai` | 容器时区（同时注入到所有服务容器） |

---

## 完整 `.env.production` 示例

```ini
# ── 数据库 ──────────────────────────────────────────
DB_MODE=postgres
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=kvm_monitor
POSTGRES_USER=kvm_user
POSTGRES_PASSWORD=CHANGE_ME_TO_A_STRONG_PASSWORD   # ← 必须修改

# ── 认证 ────────────────────────────────────────────
SECRET_KEY=CHANGE_ME_TO_A_64_CHAR_RANDOM_STRING    # ← 必须修改
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123                              # ← 建议修改

# ── SNMP ────────────────────────────────────────────
SNMP_DEFAULT_COMMUNITY=public
SNMP_TRAP_PORT=10162
# 完整指标采集（不要因快速失联检测而降低）
SNMP_POLL_INTERVAL=45
# 快速交换机、模块和原始物理端口状态检测
SNMP_HEALTH_POLL_ENABLED=true
SNMP_HEALTH_POLL_INTERVAL=1
SNMP_HEALTH_TIMEOUT=0.25
SNMP_HEALTH_RETRIES=1
SNMP_HEALTH_CONCURRENCY=20
SNMP_HEALTH_FAILURE_THRESHOLD=1
SNMP_ENDPOINT_STATUS_POLL_ENABLED=true
SNMP_RAW_LOG_ENABLED=true

# ── 日志 ────────────────────────────────────────────
LOG_LEVEL=INFO

# ── 时区 ────────────────────────────────────────────
TZ=Asia/Shanghai

# ── Docker 端口映射 ─────────────────────────────────
FRONTEND_PORT=80
```
