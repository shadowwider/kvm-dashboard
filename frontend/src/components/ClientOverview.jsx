import {
    AlertTriangle,
    ArrowRight,
    Boxes,
    Cable,
    Cpu,
    Monitor,
    Radio,
    Server,
    ShieldCheck,
    WifiOff,
} from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from '../i18n';
import { getEndpointStatus } from '../utils/endpointStatus';
import { getProfileMeta, isMatrixProfile } from '../utils/multiProfile';
import './ClientOverview.css';

const PROFILE_ORDER = [
    'ccdc_legacy',
    'ccdm_matrix',
    'visionxs_cpu',
    'visionxs_con',
    'dp12_mux_atc',
];

function formatTime(value, locale) {
    if (!value) return '—';
    const date = new Date(typeof value === 'string' ? value.replace(' ', 'T') : value);
    return Number.isNaN(date.getTime())
        ? '—'
        : date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
}

function normaliseStatus(status) {
    if (['online', 'ready', 'ok'].includes(status)) return 'online';
    if (status === 'critical') return 'critical';
    if (['warning', 'stale'].includes(status)) return 'warning';
    if (status === 'offline') return 'offline';
    return 'unknown';
}

function PanelHeader({ icon, title, suffix }) {
    return (
        <div className="client-panel-header">
            <div className="client-panel-heading">
                {icon}
                <h2>{title}</h2>
            </div>
            {suffix && <span className="client-panel-suffix">{suffix}</span>}
        </div>
    );
}

function MetricCard({ icon, label, value, tone = 'cyan', hint }) {
    return (
        <article className={`client-metric client-metric-${tone}`}>
            {icon}
            <div>
                <div className="client-metric-value">{value}</div>
                <div className="client-metric-label">{label}</div>
            </div>
            {hint && <span className="client-metric-hint">{hint}</span>}
        </article>
    );
}

export default function ClientOverview({
    devices,
    endpoints,
    alerts,
    stats,
    readyState,
    onOpenDevice,
    onOpenClassic,
}) {
    const { t, locale } = useTranslation();

    const overview = useMemo(() => {
        const online = devices.filter((device) => device.online_status === 'online').length;
        const offline = devices.filter((device) => device.online_status === 'offline').length;
        const attention = devices.filter((device) => (
            ['warning', 'critical', 'stale'].includes(device.health_status)
            || device.online_status === 'offline'
        )).length;
        const activeAlerts = stats?.active_alerts
            ?? alerts.filter((alert) => !alert.is_resolved).length;
        const profileCounts = new Map();
        devices.forEach((device) => {
            const profileId = device.profile_id || 'unknown';
            profileCounts.set(profileId, (profileCounts.get(profileId) || 0) + 1);
        });

        const endpointCounts = {
            cpu: 0,
            con: 0,
            online: 0,
            attention: 0,
        };
        endpoints.forEach((endpoint) => {
            if (endpoint.module_type === 'con') endpointCounts.con += 1;
            else endpointCounts.cpu += 1;

            const endpointStatus = getEndpointStatus(endpoint);
            if (['online', 'ready', 'ok'].includes(endpointStatus)) endpointCounts.online += 1;
            if (['offline', 'warning'].includes(endpointStatus)) endpointCounts.attention += 1;
        });

        const profiles = [...profileCounts.entries()]
            .sort(([left], [right]) => {
                const leftIndex = PROFILE_ORDER.indexOf(left);
                const rightIndex = PROFILE_ORDER.indexOf(right);
                return (leftIndex === -1 ? PROFILE_ORDER.length : leftIndex)
                    - (rightIndex === -1 ? PROFILE_ORDER.length : rightIndex);
            })
            .map(([profileId, count]) => ({ profileId, count }));

        return {
            activeAlerts,
            attention,
            endpointCounts,
            offline,
            online,
            profiles,
        };
    }, [alerts, devices, endpoints, stats?.active_alerts]);

    const recentAlerts = useMemo(
        () => alerts.slice(0, 5),
        [alerts]
    );
    const displayedDevices = useMemo(
        () => devices.slice().sort((left, right) => {
            const leftState = normaliseStatus(left.online_status || left.health_status);
            const rightState = normaliseStatus(right.online_status || right.health_status);
            const order = { critical: 0, offline: 1, warning: 2, unknown: 3, online: 4 };
            return order[leftState] - order[rightState];
        }).slice(0, 8),
        [devices]
    );
    const matrixCount = devices.filter(isMatrixProfile).length;
    const wsConnected = readyState === 1;
    const serverClients = Number.isFinite(stats?.ws_clients) ? stats.ws_clients : '—';

    return (
        <main className="client-overview" aria-label={t('dashboard.client_overview')}>
            <section className="client-hero" aria-labelledby="client-overview-title">
                <div className="client-hero-copy">
                    <span className="client-eyebrow">{t('dashboard.client_live_monitoring')}</span>
                    <h1 id="client-overview-title">{t('dashboard.client_overview')}</h1>
                    <p>{t('dashboard.client_overview_subtitle')}</p>
                </div>
                <div className={`client-live-state ${wsConnected ? 'online' : 'offline'}`}>
                    <Radio size={15} aria-hidden="true" />
                    <span>{wsConnected ? t('dashboard.ws_connected') : t('dashboard.ws_disconnected')}</span>
                </div>
            </section>

            <section className="client-metrics" aria-label={t('dashboard.client_system_metrics')}>
                <MetricCard icon={<Server size={17} aria-hidden="true" />} label={t('dashboard.kpi_total')} value={devices.length} />
                <MetricCard icon={<ShieldCheck size={17} aria-hidden="true" />} label={t('dashboard.kpi_active')} value={overview.online} tone="green" />
                <MetricCard icon={<WifiOff size={17} aria-hidden="true" />} label={t('dashboard.kpi_offline')} value={overview.offline} tone="red" />
                <MetricCard
                    icon={<AlertTriangle size={17} aria-hidden="true" />}
                    label={t('dashboard.kpi_alerts')}
                    value={overview.activeAlerts}
                    tone="amber"
                    hint={overview.attention > 0
                        ? `${overview.attention} ${t('dashboard.client_devices_need_attention')}`
                        : null}
                />
            </section>

            <section className="client-panel client-device-panel">
                <PanelHeader
                    icon={<Server size={15} aria-hidden="true" />}
                    title={t('dashboard.client_device_overview')}
                    suffix={`${devices.length} ${t('dashboard.devices_unit')}`}
                />
                <div className="client-device-list">
                    {displayedDevices.map((device) => {
                        const status = normaliseStatus(device.online_status || device.health_status);
                        return (
                            <button
                                className="client-device-row"
                                key={device.id}
                                onClick={() => onOpenDevice(device)}
                            >
                                <span className={`client-status-dot ${status}`} aria-hidden="true" />
                                <span className="client-device-name">
                                    <strong>{device.name || device.id}</strong>
                                    <small>{device.host ? `${device.host}:${device.port}` : device.id}</small>
                                </span>
                                <span className={`client-status-label ${status}`}>
                                    {t(`status.${device.online_status || device.health_status}`, device.online_status || device.health_status || '—')}
                                </span>
                                <ArrowRight size={14} aria-hidden="true" />
                            </button>
                        );
                    })}
                    {displayedDevices.length === 0 && (
                        <div className="client-empty">{t('dashboard.client_no_device_data')}</div>
                    )}
                </div>
                <button className="client-panel-action" onClick={() => onOpenClassic('devices')}>
                    {t('dashboard.client_open_device_list')}
                    <ArrowRight size={14} aria-hidden="true" />
                </button>
            </section>

            <section className="client-panel client-profile-panel">
                <PanelHeader
                    icon={<Boxes size={15} aria-hidden="true" />}
                    title={t('dashboard.client_profile_distribution')}
                    suffix={matrixCount > 0 ? `${matrixCount} ${t('profiles.roles.matrix')}` : null}
                />
                <div className="client-profile-list">
                    {overview.profiles.map(({ profileId, count }) => {
                        const profile = getProfileMeta(profileId);
                        const ratio = devices.length > 0 ? (count / devices.length) * 100 : 0;
                        return (
                            <div className="client-profile-row" key={profileId}>
                                <div className="client-profile-meta">
                                    <span>{t(profile.labelKey || `profiles.${profileId}`, profileId)}</span>
                                    <strong>{count}</strong>
                                </div>
                                <div className="client-profile-track" aria-hidden="true">
                                    <span style={{ width: `${ratio}%` }} />
                                </div>
                                <small>{t(profile.roleKey || 'profiles.roles.unknown')}</small>
                            </div>
                        );
                    })}
                    {overview.profiles.length === 0 && (
                        <div className="client-empty">{t('dashboard.client_no_device_data')}</div>
                    )}
                </div>
            </section>

            <section className="client-panel client-endpoint-panel">
                <PanelHeader
                    icon={<Cable size={15} aria-hidden="true" />}
                    title={t('dashboard.client_endpoint_status')}
                    suffix={endpoints.length > 0 ? `${endpoints.length} ${t('dashboard.ep_total_hint')}` : null}
                />
                <div className="client-endpoint-grid">
                    <div>
                        <Cpu size={17} aria-hidden="true" />
                        <span>{t('dashboard.client_cpu_modules')}</span>
                        <strong>{endpoints.length > 0 ? overview.endpointCounts.cpu : '—'}</strong>
                    </div>
                    <div>
                        <Monitor size={17} aria-hidden="true" />
                        <span>{t('dashboard.client_con_modules')}</span>
                        <strong>{endpoints.length > 0 ? overview.endpointCounts.con : '—'}</strong>
                    </div>
                    <div>
                        <ShieldCheck size={17} aria-hidden="true" />
                        <span>{t('dashboard.kpi_active')}</span>
                        <strong>{endpoints.length > 0 ? overview.endpointCounts.online : '—'}</strong>
                    </div>
                    <div>
                        <AlertTriangle size={17} aria-hidden="true" />
                        <span>{t('dashboard.client_attention')}</span>
                        <strong>{endpoints.length > 0 ? overview.endpointCounts.attention : '—'}</strong>
                    </div>
                </div>
                <button className="client-panel-action" onClick={() => onOpenClassic('grid')}>
                    {t('dashboard.client_open_matrix')}
                    <ArrowRight size={14} aria-hidden="true" />
                </button>
            </section>

            <section className="client-panel client-alert-panel">
                <PanelHeader
                    icon={<AlertTriangle size={15} aria-hidden="true" />}
                    title={t('dashboard.alerts_panel')}
                    suffix={`${overview.activeAlerts} ${t('dashboard.alerts_unit')}`}
                />
                <div className="client-alert-list">
                    {recentAlerts.map((alert, index) => {
                        const severity = normaliseStatus(alert.severity);
                        const target = devices.find((device) => device.id === alert.device_id);
                        return (
                            <button
                                className={`client-alert-row ${severity}`}
                                key={alert.id ?? `${alert.device_id}-${alert.created_at}-${index}`}
                                onClick={() => target && onOpenDevice(target)}
                                disabled={!target}
                            >
                                <span>{formatTime(alert.created_at, locale)}</span>
                                <strong>{alert.message || '—'}</strong>
                                <small>{target?.name || alert.device_id || '—'}</small>
                            </button>
                        );
                    })}
                    {recentAlerts.length === 0 && (
                        <div className="client-empty">{t('dashboard.no_alerts')}</div>
                    )}
                </div>
            </section>

            <section className="client-panel client-network-panel">
                <PanelHeader icon={<Radio size={15} aria-hidden="true" />} title={t('dashboard.client_realtime_status')} />
                <div className="client-network-state">
                    <div className={wsConnected ? 'online' : 'offline'}>
                        <span className="client-status-dot" aria-hidden="true" />
                        <span>{wsConnected ? t('dashboard.ws_connected') : t('dashboard.ws_disconnected')}</span>
                    </div>
                    <div>
                        <span>{t('dashboard.client_server_connections')}</span>
                        <strong>{serverClients}</strong>
                    </div>
                    <div>
                        <span>{t('dashboard.client_matrix_devices')}</span>
                        <strong>{matrixCount}</strong>
                    </div>
                </div>
            </section>
        </main>
    );
}
