# KVM Dashboard — 部署手册

> 版本：v1.0  
> 最后更新：2026-03-02

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

```bash
# 编辑生产配置（必须修改！）
vi .env.production
```

**必须修改的字段**（搜索 `CHANGE_ME`）：
- `POSTGRES_PASSWORD` — 数据库密码
- `SECRET_KEY` — JWT 签名密钥（建议 32+ 位随机字符串）
- `ADMIN_PASSWORD` — 初始管理员密码

> `docker-compose.yml` 通过 `env_file: .env.production` 直接加载此文件，请勿重命名。

### 3. 构建并启动

```bash
# 构建镜像
docker compose build

# 后台启动 3 个容器
docker compose up -d

# 查看启动状态
docker compose ps
```

### 4. 验证部署

```bash
# 检查所有容器健康状态
docker compose ps

# 预期输出：
# kvm_postgres   ... (healthy)
# kvm_backend    ... (healthy)
# kvm_frontend   ... (healthy)
```

浏览器访问 **http://\<服务器IP\>** 即可进入系统。

默认登录账号：`admin` / `admin123`（请登录后立即修改密码）

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
| `SNMP_RAW_LOG_ENABLED` | true | 开启原始 SNMP 数据日志（logs/ 目录） |
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

### 查看日志

```bash
# 查看后端日志（实时跟踪）
docker compose logs -f backend

# 查看前端 Nginx 日志
docker compose logs -f frontend

# 查看数据库日志
docker compose logs -f postgres
```

### 重启服务

```bash
# 重启所有服务
docker compose restart

# 仅重启后端
docker compose restart backend

# 重建并重启（代码更新后）
docker compose up -d --build
```

### 数据备份

```bash
# 备份 PostgreSQL 数据
docker compose exec postgres pg_dump -U kvm_user kvm_monitor > backup_$(date +%Y%m%d).sql

# 恢复
cat backup_20260302.sql | docker compose exec -T postgres psql -U kvm_user kvm_monitor
```

### 停止和清理

```bash
# 停止所有容器（保留数据卷）
docker compose down

# 停止并删除数据卷（危险！会丢失数据）
docker compose down -v
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

- 检查 Nginx 容器是否运行：`docker compose ps frontend`
- 检查 Nginx 日志：`docker compose logs frontend`
- 确认 `try_files` 配置正确（SPA 回退到 index.html）

### 2. API 返回 502 Bad Gateway

- 后端容器可能未启动或崩溃：`docker compose ps backend`
- 检查后端日志：`docker compose logs backend`
- 确认 `backend:8000` 网络可达

### 3. WebSocket 连接失败

- 检查 Nginx 配置中的 `Upgrade` 和 `Connection` 头
- 检查是否有外部代理/负载均衡器拦截 WS 连接
- 超时日志：`proxy_read_timeout` 应设为 86400s

### 4. 数据库连接失败

- 确认 PostgreSQL 容器健康：`docker compose ps postgres`
- 确认 `.env.production` 中的连接参数与 `docker-compose.yml` 一致
- 检查 `init.sql` 是否正确执行：`docker compose logs postgres | grep "init"`

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
