-- KVM 监控系统 PostgreSQL 初始化脚本 (含 TimescaleDB 扩展)
-- 建议在 PostgreSQL 14+ / TimescaleDB 2.x 环境执行

-- 1. 创建扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 2. 用户表 (RBAC)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'viewer', -- admin, operator, viewer
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. KVM 交换机设备表
CREATE TABLE IF NOT EXISTS devices (
    id VARCHAR(100) PRIMARY KEY, -- 建议用 SN 或 IP
    name VARCHAR(200) NOT NULL,
    host VARCHAR(100) NOT NULL,
    port INTEGER DEFAULT 161,
    community VARCHAR(100) DEFAULT 'public',
    location VARCHAR(200),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    poll_interval INTEGER DEFAULT 60, -- legacy：不控制运行时轮询频率
    last_poll TIMESTAMPTZ,
    last_health_check TIMESTAMPTZ,
    last_status VARCHAR(20) DEFAULT 'unknown', -- online, offline, warning
    system_oid VARCHAR(255), -- 用于动态 OID 映射
    model_name VARCHAR(128), -- 例如: ControlCenter-Compact-8C
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 终端设备表 (CPU/CON Modules)
CREATE TABLE IF NOT EXISTS endpoints (
    id VARCHAR(150) PRIMARY KEY, -- 格式: device_id + module_type + index
    device_id VARCHAR(100) REFERENCES devices(id) ON DELETE CASCADE,
    name VARCHAR(200),
    index INTEGER NOT NULL,
    module_type VARCHAR(16) DEFAULT 'cpu', -- cpu | con | port
    last_status JSONB, -- 存储最后一次所有 OID 的快照数据
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. OID 监控注册表 (监控规则字典)
CREATE TABLE IF NOT EXISTS oid_registry (
    id SERIAL PRIMARY KEY,
    oid VARCHAR(255) NOT NULL,
    name VARCHAR(100) UNIQUE NOT NULL, -- 唯一标识, 如 'temperature'
    display_name VARCHAR(100),
    description TEXT,
    category VARCHAR(20) DEFAULT 'device', -- device 或 endpoint
    data_type VARCHAR(20) DEFAULT 'string', -- counter, gauge, integer, string
    unit VARCHAR(20),
    enum_map JSONB, -- 用于转换 1->on, 2->off 等
    is_table BOOLEAN DEFAULT FALSE,
    table_base_oid VARCHAR(255),
    table_column INTEGER,
    alert_enabled BOOLEAN DEFAULT FALSE,
    alert_gt FLOAT,
    alert_lt FLOAT,
    alert_eq_str VARCHAR(100),
    alert_ne_str VARCHAR(100),
    alert_severity VARCHAR(20) DEFAULT 'warning',
    poll_enabled BOOLEAN DEFAULT TRUE,
    archive_enabled BOOLEAN DEFAULT TRUE,
    display_enabled BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. 告警历史记录表
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) NOT NULL,
    endpoint_id VARCHAR(150),
    oid_name VARCHAR(64),
    alert_type VARCHAR(32) NOT NULL, -- threshold, trap, offline
    severity VARCHAR(20) NOT NULL, -- critical, warning, info
    message TEXT NOT NULL,
    raw_value TEXT,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alerts_device ON alerts(device_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(is_resolved) WHERE (is_resolved = FALSE);

-- 7. 时序指标数据表 (核心核心核心)
CREATE TABLE IF NOT EXISTS status_metrics (
    id BIGSERIAL NOT NULL,           -- SQLAlchemy autoincrement PK (TimescaleDB 不要求 PK 含 time 时，不加 PRIMARY KEY 约束)
    time TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(100) NOT NULL,
    endpoint_id VARCHAR(150),        -- 关联终端
    oid_name VARCHAR(64) NOT NULL,
    value_str VARCHAR(256),          -- 存储原始字符串
    value_num FLOAT                  -- 存储数值用于绘图
);

-- 转换为 TimescaleDB 超表
SELECT create_hypertable('status_metrics', 'time', if_not_exists => TRUE);

-- 设置数据保留策略 (保留 90 天)
SELECT add_retention_policy('status_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- 设置数据压缩策略 (7 天前的数据自动压缩，节省 90% 空间)
ALTER TABLE status_metrics SET (timescaledb.compress);
SELECT add_compression_policy('status_metrics', INTERVAL '7 days', if_not_exists => TRUE);

-- 指标查询索引
CREATE INDEX IF NOT EXISTS idx_metrics_device_oid_time ON status_metrics (device_id, oid_name, time DESC);

-- 8. 设备/终端别名映射表
CREATE TABLE IF NOT EXISTS device_aliases (
    target_id VARCHAR(150) PRIMARY KEY,
    target_type VARCHAR(20) NOT NULL, -- device, endpoint
    alias VARCHAR(200) NOT NULL,
    note TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
