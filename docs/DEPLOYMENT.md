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
# 复制生产模板
cp .env.production .env.production.local

# 编辑敏感配置（必须修改！）
vi .env.production.local
```

**必须修改的字段**：
- `POSTGRES_PASSWORD` — 数据库密码
- `SECRET_KEY` — JWT 签名密钥（建议 32+ 位随机字符串）
- `ADMIN_PASSWORD` — 初始管理员密码

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

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_DB` | kvm_monitor | 数据库名 |
| `POSTGRES_USER` | kvm_user | 数据库用户 |
| `POSTGRES_PASSWORD` | change_me | ⚠️ 数据库密码 |
| `SECRET_KEY` | — | ⚠️ JWT 签名密钥 |
| `ADMIN_USERNAME` | admin | 初始管理员用户名 |
| `ADMIN_PASSWORD` | admin123 | ⚠️ 初始管理员密码 |
| `SNMP_DEFAULT_COMMUNITY` | public | SNMP 默认 Community |
| `SNMP_TRAP_PORT` | 10162 | SNMP Trap 监听端口 |
| `LOG_LEVEL` | INFO | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `TZ` | Asia/Shanghai | 系统时区 |
| `FRONTEND_PORT` | 80 | 前端访问端口 |

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

---

## 六、故障排查

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
| 轮询间隔 | 生产环境建议 60s+，避免过多 SNMP 请求 |
| TimescaleDB 压缩 | 开启 30 天以上数据自动压缩 |
