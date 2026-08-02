# KVM Dashboard — 部署手册

> 版本：v1.1
> 最后更新：2026-08-02

---

## 一、系统要求

| 组件 | 最低版本 |
|------|----------|
| Docker | 24.0+ |
| Docker Compose | v2.20+ |
| 磁盘空间 | 10GB+（含数据库） |
| 内存 | 2GB+ |
| 网络 | SNMP 设备可达 |

---

## 二、快速部署

### 1. 克隆代码

```bash
git clone <your-repo-url> kvm-dashboard
cd kvm-dashboard
git checkout feat/full-refactor
```

### 2. 配置环境变量

将生产环境文件保存在受控位置并限制宿主机读取权限；不要将实际密码、JWT 密钥或 SNMP community 复制到命令历史、工单或聊天记录中。默认文件名为 `.env.production`，也可使用项目外的私有文件。

**必须修改的字段**：
- `POSTGRES_PASSWORD` — 数据库密码
- `SECRET_KEY` — JWT 签名密钥（建议 32+ 位随机字符串）
- `ADMIN_PASSWORD` — 初始管理员密码

### 环境文件与 Compose 插值

`docker-compose.yml` 中的 `KVM_ENV_FILE` 只用来选择 `postgres` 和 `backend` 服务的运行时 `env_file`，默认值为 `.env.production`。服务的 `env_file` 会在容器创建时注入变量（包括机密），但 **不会** 为 Compose 文件中的 `${VARIABLE}` 提供插值值。

端口映射、`TZ` 和 Trap 监听端口等 `${VARIABLE:-default}` 会在容器创建前由 Compose 客户端解析。生产部署应将同一个私有文件同时传给 `KVM_ENV_FILE` 和 `--env-file`，以避免端口配置悄然回退到 Compose 的默认值：

```powershell
# PowerShell：路径本身不含机密；文件内容不要输出或提交。
$env:KVM_ENV_FILE = '.\kvm.production.env'
docker compose --env-file $env:KVM_ENV_FILE config --quiet
docker compose --env-file $env:KVM_ENV_FILE up --detach --build
```

```bash
# POSIX shell
export KVM_ENV_FILE=./kvm.production.env
docker compose --env-file "$KVM_ENV_FILE" config --quiet
docker compose --env-file "$KVM_ENV_FILE" up --detach --build
```

若使用默认文件，将上述文件参数替换为 `.env.production` 即可。`config --quiet` 仅校验 Compose 配置而不打印展开后的环境变量；不要执行并外发不带 `--quiet` 的 `docker compose config`、`docker inspect` 或 `config --environment` 输出，它们可能包含机密。

### 基础镜像版本

TimescaleDB 基础镜像已固定为经过本项目“空数据卷 + 初始化 SQL + Alembic 迁移”验收的 digest，避免 `latest-pg16` 在不经测试时发生隐式升级。升级该 digest 前，必须在隔离的空卷中完整执行本手册的启动、健康检查、迁移和备份恢复验证；不要直接把 `latest` 改回 Compose 文件。

### 3. 构建并启动

以下示例使用默认环境文件；使用私有文件时将 `.env.production` 替换为上一步的 `$env:KVM_ENV_FILE` / `$KVM_ENV_FILE`。

```bash
# 先做不输出机密的 Compose 校验，再构建并后台启动 3 个容器
docker compose --env-file .env.production config --quiet
docker compose --env-file .env.production up --detach --build

# 查看启动状态
docker compose --env-file .env.production ps
```

### 4. 验证部署

```bash
# 检查所有容器健康状态
docker compose --env-file .env.production ps

# 预期输出：
# kvm_postgres   ... (healthy)
# kvm_backend    ... (healthy)
# kvm_frontend   ... (healthy)

# 经 Nginx 读取详细健康检查；响应不包含密码、JWT 或 community。
docker compose --env-file .env.production exec -T frontend \
  wget -qO- http://localhost/api/v1/health
```

除 `status: "ok"` 和 `database: "connected"` 外，生产验收应确认 `database_capacity.warning` 为 `false`，且 `health_probe.capacity_degraded` 为 `false`。前者是数据库容量预警，后者表示当前活跃设备数、SNMP 超时/重试和并发度已无法在配置的探测周期内完成；两者均不应只凭容器处于 `healthy` 就忽略。

浏览器访问 **http://\<服务器IP\>** 即可进入系统。

首次登录使用环境文件中配置的 `ADMIN_USERNAME` / `ADMIN_PASSWORD`；上线后应立即轮换初始密码。

---

## 三、环境变量说明

完整的环境变量参考见 [`docs/ENV_VARS.md`](./ENV_VARS.md)，以下为常用变量速查：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_DB` | kvm_monitor | 数据库名 |
| `POSTGRES_USER` | kvm_user | 数据库用户 |
| `POSTGRES_PASSWORD` | change_me | ⚠️ 数据库密码 |
| `SECRET_KEY` | — | ⚠️ JWT 签名密钥 |
| `ADMIN_USERNAME` | admin | 初始管理员用户名 |
| `ADMIN_PASSWORD` | admin123 | ⚠️ 初始管理员密码 |
| `SNMP_DEFAULT_COMMUNITY` | public | SNMP 默认 Community |
| `SNMP_TRAP_HOST_PORT` | 162 | 现场设备发送到宿主机的 Trap UDP 端口 |
| `SNMP_TRAP_LISTEN_PORT` | 10162 | 后端容器实际监听的 Trap UDP 端口 |
| `SNMP_POLL_INTERVAL` | 45 | 旧版兼容变量，不再控制完整轮询调度入口 |
| `SNMP_RAW_LOG_ENABLED` | false（生产模板） | 原始 SNMP 日志；仅排障时临时开启 |
| `DATABASE_SIZE_WARNING_MB` | 10240 | 数据库容量预警阈值，不是硬性配额 |
| `LOG_LEVEL` | INFO | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `TZ` | Asia/Shanghai | 系统时区 |
| `FRONTEND_PORT` | 80 | 前端访问端口 |

完整轮询调度器每秒检查一次，实际采集周期由每台设备的 `poll_interval` 决定。

---

## 四、架构说明

```
                       ┌──────────────────┐
   用户浏览器 ──80──▶  │  Nginx (前端)     │
                       │  + 静态文件        │
                       │  + /api 反代       │
                       │  + /ws  反代       │
                       └────────┬─────────┘
                                │ :8000
                       ┌────────▼─────────┐
                       │  FastAPI (后端)   │
                       │  + SNMP Poller    │
                       │  + WebSocket Hub  │
                       │  + APScheduler    │
                       └────────┬─────────┘
                                │ :5432
                       ┌────────▼─────────┐
                       │  PostgreSQL 16    │
                       │  + TimescaleDB   │
                       └──────────────────┘
```

---

## 五、日常运维

下列命令使用默认 `.env.production`。如使用 `KVM_ENV_FILE`，先按上文在当前 shell 设置它，并将每处 `.env.production` 替换为同一文件路径。

### 查看日志

```bash
# 查看后端日志（实时跟踪）
docker compose --env-file .env.production logs -f backend

# 查看前端 Nginx 日志
docker compose --env-file .env.production logs -f frontend

# 查看数据库日志
docker compose --env-file .env.production logs -f postgres
```

### 日志、保留与容量边界

Compose 为三个容器都设置 Docker `local` 日志驱动，`max-size=20m`、`max-file=5`；因此每个容器的 Docker stdout/stderr 日志名义上最多约 100 MiB。这与应用的原始 SNMP 文件日志是两套机制：后者位于宿主机 `./logs/`，由 `SNMP_RAW_LOG_MAX_MB` 和 `SNMP_RAW_LOG_BACKUP_COUNT` 轮转，默认每类保留当前文件和 5 个备份（约 60 MiB），Trap 与轮询两类合计约 120 MiB。

数据保留任务首次在应用成功启动约 24 小时后执行，之后每 24 小时清理一次：状态指标默认 90 天、Trap 原始事件 180 天、审计记录与已解决告警 365 天；未解决告警不会自动删除。`METRICS_RETENTION_DAYS` 还会配置 TimescaleDB 的指标保留策略；将 `DATA_RETENTION_CLEANUP_ENABLED=false` 只会关闭应用的每日清理，并不会取消已经配置的 TimescaleDB 指标策略。

`postgres_data` 是 Docker `local` 命名卷。Compose 没有跨 Linux、Docker Desktop 和不同存储驱动都可移植的命名卷硬配额；`DATABASE_SIZE_WARNING_MB` 仅通过 `/api/v1/health` 预警，不能阻止写入，也不涵盖宿主机文件系统、Docker 镜像或 `./logs/`。生产环境须在宿主机/存储平台配置磁盘监控和适用的卷配额（例如受平台支持的 LVM、ZFS 或云盘策略），并先在目标平台验证。

### 重启服务

```bash
# 重启所有服务
docker compose --env-file .env.production restart

# 仅重启后端
docker compose --env-file .env.production restart backend

# 重建并重启（代码更新后）
docker compose --env-file .env.production up --detach --build
```

### 数据备份

```bash
# 备份 PostgreSQL 数据
docker compose --env-file .env.production exec -T postgres \
  sh -ec 'exec pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > backup_$(date +%Y%m%d).sql

# 恢复
cat backup_20260302.sql | docker compose --env-file .env.production exec -T postgres \
  sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

PowerShell 恢复时可将 `cat backup_20260302.sql` 替换为 `Get-Content -Raw backup_20260302.sql`。备份完成后应先在隔离数据库执行一次恢复，再视为可用备份。

### 停止和清理

```bash
# 停止所有容器（保留数据卷）
docker compose --env-file .env.production down

# 停止并删除数据卷（危险！会丢失数据）
docker compose --env-file .env.production down -v
```

### 5. 数据库自动迁移

后端在数据库初始化、种子数据和调度器启动之前自动执行 `alembic upgrade head`。空数据库会创建完整结构；已有旧版 SQLite 或 PostgreSQL 数据库会先登记旧版基线，再执行多 Profile 扩展迁移。

部署升级后先查看后端日志，确认出现“数据库 Alembic 迁移完成”。迁移失败时后端会停止启动，不会在旧结构上继续运行。生产环境仍保持单个 FastAPI worker，避免进程内 APScheduler 重复执行轮询和启动发现任务。

### 6. Trap 端口

现场设备统一向服务器 UDP 162 发送 Trap。Compose 默认使用 `162:10162/udp`：宿主机监听 162，后端容器监听非特权端口 10162。确认服务器防火墙已开放 `162/udp`，并且不要横向扩容后端服务。

---

## 六、关键逻辑说明：物理端口映射
为了保证大屏显示与机架面板完全一致，本系统采用了 **硬件物理索引优先** 的策略：
1. **OID 映射**：轮询器会读取 SNMP Table 的第 1 列（物理 Index）。
2. **位置匹配**：前端渲染时，不再按照数据返回顺序排列，而是根据物理 Index 将终端分配到 1-32 号槽位。
3. **视觉反馈**：未插入模块的槽位会显示为虚线空置状态，方便一眼看出交换机还有几个空余接口。
   详见文档：[`docs/port_mapping_logic.md`](./port_mapping_logic.md)

---

## 七、故障排查

### 1. 前端页面白屏 / 404

- 检查 Nginx 容器是否运行：`docker compose --env-file .env.production ps frontend`
- 检查 Nginx 日志：`docker compose --env-file .env.production logs frontend`
- 确认 `try_files` 配置正确（SPA 回退到 index.html）

### 2. API 返回 502 Bad Gateway

- 后端容器可能未启动或崩溃：`docker compose --env-file .env.production ps backend`
- 检查后端日志：`docker compose --env-file .env.production logs backend`
- 确认 `backend:8000` 网络可达

### 3. WebSocket 连接失败

- 检查 Nginx 配置中的 `Upgrade` 和 `Connection` 头
- 检查是否有外部代理/负载均衡器拦截 WS 连接
- 超时日志：`proxy_read_timeout` 应设为 86400s

### 4. 数据库连接失败

- 确认 PostgreSQL 容器健康：`docker compose --env-file .env.production ps postgres`
- 确认 `.env.production` 中的连接参数与 `docker-compose.yml` 一致
- 检查 `init.sql` 是否正确执行：`docker compose --env-file .env.production logs postgres | grep "init"`

---

## 七、HTTPS 配置（可选）

如需启用 HTTPS，在 `docker-compose.yml` 的 `frontend` 服务中挂载 SSL 证书并修改 Nginx 配置：

```yaml
frontend:
  volumes:
    - /path/to/ssl/cert.pem:/etc/nginx/ssl/cert.pem:ro
    - /path/to/ssl/key.pem:/etc/nginx/ssl/key.pem:ro
  ports:
    - "443:443"
```

然后在 `nginx.conf` 中添加 SSL 配置块。

---

## 八、性能调优建议

| 项目 | 建议 |
|------|------|
| 数据库连接池 | `pool_size=20, max_overflow=40` |
| SNMP 并发限流 | Semaphore 上限 20-30 |
| 日志轮转 | 配置 logrotate 或 Docker `--log-opt max-size=50m` |
| 轮询间隔 | 调度器每秒检查到期设备；按设备规模分别配置 `Device.poll_interval`，避免大量设备同时执行完整 WALK |
| TimescaleDB 压缩 | 开启 30 天以上数据自动压缩 |
