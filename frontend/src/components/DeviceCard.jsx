import { useTranslation } from '../i18n';
import { useStore } from '../store/mainStore';

export default function DeviceCard({ device, isActive, onClick }) {
    const { t } = useTranslation();
    const getDisplayName = useStore((state) => state.getDisplayName);
    const status = device.online_status || device.last_status || 'offline';
    const displayName = getDisplayName(device.id, device.name);

    return (
        <button
            className={`device-card ${status} ${isActive ? 'active' : ''}`}
            onClick={onClick}
        >
            <div className="dc-heading">
                <span className="dc-name">{displayName}</span>
                <span className={`detail-status ${status}`}>{t(`status.${status}`)}</span>
            </div>
            <div className="dc-ip">{device.host}:{device.port}</div>
            <div className="dc-profile">
                {t(device.profile_label_key || `profiles.${device.profile_id}`, device.profile_id)}
            </div>
            <div className="dc-summary-grid">
                <span>{t('devices.health')}</span>
                <strong className={`text-${device.health_status}`}>{t(`status.${device.health_status}`)}</strong>
                <span>{t('devices.freshness')}</span>
                <strong className={`text-${device.freshness_status}`}>{t(`status.${device.freshness_status}`)}</strong>
                <span>{t('devices.entities')}</span>
                <strong>{device.entity_count ?? '—'}</strong>
                <span>{t('devices.alerts')}</span>
                <strong>{device.active_alert_count ?? 0}</strong>
            </div>
        </button>
    );
}
