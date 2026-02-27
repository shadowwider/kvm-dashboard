import React from 'react';
import { useStore } from '../store/mainStore';

const SEVERITY_LABEL = {
    critical: '紧急',
    warning: '警告',
    info: '信息',
};

// 健壮的时间格式化：兼容 ISO8601、无 T/Z 的字符串、数字时间戳
function safeFormatTime(raw) {
    if (!raw) return '--:--:--';
    try {
        // 处理没有 T/Z 的格式（如 '2026-02-27 10:07:00'）
        const normalized = typeof raw === 'string' ? raw.replace(' ', 'T') : raw;
        const dt = new Date(normalized);
        if (isNaN(dt.getTime())) return '--:--:--';
        const h = String(dt.getHours()).padStart(2, '0');
        const m = String(dt.getMinutes()).padStart(2, '0');
        const s = String(dt.getSeconds()).padStart(2, '0');
        return `${h}:${m}:${s}`;
    } catch {
        return '--:--:--';
    }
}

const AlertStream = () => {
    const alerts = useStore(state => state.alerts);

    if (alerts.length === 0) {
        return (
            <div style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text-dim)',
                fontSize: '10px',
                letterSpacing: '2px',
            }}>
                暂无告警
            </div>
        );
    }

    return (
        <div className="alert-list">
            {alerts.map((alert, idx) => {
                const severity = alert.severity || 'info';
                const isNew = idx === 0;
                const timeStr = safeFormatTime(alert.created_at);

                return (
                    <div
                        key={alert.id ?? idx}
                        className={`alert-item ${severity}${isNew ? ' is-new' : ''}`}
                    >
                        <div className="alert-time">{timeStr}</div>
                        <div className="alert-header">
                            <span className={`alert-badge ${severity}`}>
                                {SEVERITY_LABEL[severity] || severity}
                            </span>
                            <span className="alert-device">
                                {alert.device_id || '—'}
                            </span>
                        </div>
                        <div className="alert-msg">{alert.message || '—'}</div>
                    </div>
                );
            })}
        </div>
    );
};

export default AlertStream;
