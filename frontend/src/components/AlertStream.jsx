import React from 'react';
import { useStore } from '../store/mainStore';
import { useTranslation } from '../i18n';

// 健壮的时间格式化
function safeFormatTime(raw) {
    if (!raw) return '--:--:--';
    try {
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
    const getDisplayName = useStore(state => state.getDisplayName);
    const { t } = useTranslation();

    const SEVERITY_LABEL = {
        critical: t('dashboard.severity_critical'),
        warning: t('dashboard.severity_warning'),
        info: t('dashboard.severity_info'),
    };

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
                {t('dashboard.no_alerts')}
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
                                {getDisplayName(alert.device_id, alert.device_id)}
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
