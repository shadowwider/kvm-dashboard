import { useEffect, useMemo, useState } from 'react';
import { Languages, LogOut, Settings } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AlertStream from '../components/AlertStream';
import BottomCharts from '../components/BottomCharts';
import DeviceCard from '../components/DeviceCard';
import DeviceTable from '../components/DeviceTable';
import MatrixView from '../components/MatrixView';
import SoundControl from '../components/SoundControl';
import ClientOverview from '../components/ClientOverview';
import useAlertSound from '../hooks/useAlertSound';
import useSystemWebSocket from '../hooks/useSystemWebSocket';
import { useTranslation } from '../i18n';
import { useAuthStore } from '../store/authStore';
import { useStore } from '../store/mainStore';
import { isMatrixProfile } from '../utils/multiProfile';
import './Dashboard.css';

export default function Dashboard() {
    const navigate = useNavigate();
    const logout = useAuthStore((state) => state.logout);
    const user = useAuthStore((state) => state.user);
    const stats = useStore((state) => state.stats);
    const devices = useStore((state) => state.devices);
    const endpoints = useStore((state) => state.endpoints);
    const alerts = useStore((state) => state.alerts);
    const selectedDeviceId = useStore((state) => state.selectedDeviceId);
    const viewMode = useStore((state) => state.viewMode);
    const fetchAll = useStore((state) => state.fetchAll);
    const getDisplayName = useStore((state) => state.getDisplayName);
    const setSelectedDevice = useStore((state) => state.setSelectedDevice);
    const setViewMode = useStore((state) => state.setViewMode);
    const { t, locale, toggleLocale } = useTranslation();
    const { readyState } = useSystemWebSocket();
    useAlertSound();

    const [clock, setClock] = useState('');
    const [filterDeviceId, setFilterDeviceId] = useState('all');
    const [dashboardPresentation, setDashboardPresentation] = useState(() => (
        window.localStorage.getItem('dashboard-presentation') === 'overview'
            ? 'overview'
            : 'classic'
    ));

    useEffect(() => {
        const tick = () => {
            const now = new Date();
            setClock(now.toLocaleTimeString(locale, { hour12: false }));
        };
        tick();
        const timer = window.setInterval(tick, 1000);
        return () => window.clearInterval(timer);
    }, [locale]);

    useEffect(() => {
        fetchAll();
        const timer = window.setInterval(fetchAll, 60000);
        return () => window.clearInterval(timer);
    }, [fetchAll]);

    const activeAlerts = stats?.active_alerts
        ?? alerts.filter((alert) => !alert.is_resolved).length;
    const onlineDevices = devices.filter((device) => device.online_status === 'online').length;
    const offlineDevices = devices.filter((device) => device.online_status === 'offline').length;
    const healthyDevices = devices.filter((device) => (
        device.online_status === 'online'
        && !['critical', 'offline'].includes(device.health_status)
    )).length;
    const healthPct = devices.length > 0
        ? ((healthyDevices / devices.length) * 100).toFixed(1)
        : '100.0';

    const tabDevices = useMemo(() => (
        viewMode === 'grid' ? devices.filter(isMatrixProfile) : devices
    ), [devices, viewMode]);

    const handleFilter = (id) => {
        setFilterDeviceId(id);
        setSelectedDevice(id === 'all' ? null : id);
    };

    const handleDeviceClick = (device) => {
        if (viewMode === 'grid' && !isMatrixProfile(device)) {
            setViewMode('devices');
        }
        handleFilter(device.id);
    };

    const handleViewChange = (mode) => {
        setViewMode(mode);
        if (
            mode === 'grid'
            && filterDeviceId !== 'all'
            && !isMatrixProfile(devices.find((device) => device.id === filterDeviceId))
        ) {
            handleFilter('all');
        }
    };

    const handlePresentationChange = (presentation) => {
        window.localStorage.setItem('dashboard-presentation', presentation);
        setDashboardPresentation(presentation);
    };

    const openClassicView = (mode = 'devices') => {
        handleViewChange(mode);
        handlePresentationChange('classic');
    };

    const openDeviceFromOverview = (device) => {
        handleFilter(device.id);
        openClassicView('devices');
    };

    return (
        <div className={`dashboard-app ${dashboardPresentation === 'overview' ? 'client-dashboard' : ''}`}>
            <header className="topbar">
                <div className="sys-title">
                    <div className="lbl">{t('dashboard.system_code')}</div>
                    <div className="name">{t('dashboard.title')}</div>
                    <div className="sub">{t('dashboard.subtitle')}</div>
                </div>

                <div className="health-center">
                    <div className="health-label">{t('dashboard.health_label')}</div>
                    <div className="health-pct">{healthPct}%</div>
                    <div className="health-bar">
                        <div className="health-bar-fill" style={{ width: `${healthPct}%` }} />
                    </div>
                </div>

                <div className="kpi-strip">
                    <div className="kpi-card total">
                        <div className="kpi-val">{devices.length}</div>
                        <div className="kpi-lbl">{t('dashboard.kpi_total')}</div>
                    </div>
                    <div className="kpi-card online">
                        <div className="kpi-val">{onlineDevices}</div>
                        <div className="kpi-lbl">{t('dashboard.kpi_active')}</div>
                    </div>
                    <div className="kpi-card offline">
                        <div className="kpi-val">{offlineDevices}</div>
                        <div className="kpi-lbl">{t('dashboard.kpi_offline')}</div>
                    </div>
                    <div className="kpi-card alert">
                        <div className="kpi-val">{activeAlerts}</div>
                        <div className="kpi-lbl">{t('dashboard.kpi_alerts')}</div>
                    </div>
                    <div className="conn-block">
                        <div className={`conn-dot ${readyState === 1 ? '' : 'disconnected'}`} />
                        <div>
                            <div className="clock-text">{clock}</div>
                            <div>{readyState === 1 ? t('dashboard.ws_connected') : t('dashboard.ws_disconnected')}</div>
                        </div>
                    </div>
                    <div className="user-actions">
                        <div className="client-view-switch" role="group" aria-label={t('dashboard.client_view_switch')}>
                            <button
                                className={dashboardPresentation === 'classic' ? 'active' : ''}
                                onClick={() => handlePresentationChange('classic')}
                            >
                                {t('dashboard.client_classic_view')}
                            </button>
                            <button
                                className={dashboardPresentation === 'overview' ? 'active' : ''}
                                onClick={() => handlePresentationChange('overview')}
                            >
                                {t('dashboard.client_overview')}
                            </button>
                        </div>
                        <SoundControl />
                        <button
                            className="ua-btn"
                            onClick={toggleLocale}
                            title={t('common.switch_language')}
                            aria-label={t('common.switch_language')}
                        >
                            <Languages size={16} />
                        </button>
                        {user?.role === 'admin' && (
                            <button
                                className="ua-btn"
                                onClick={() => navigate('/admin')}
                                title={t('admin.title')}
                                aria-label={t('admin.title')}
                            >
                                <Settings size={16} />
                            </button>
                        )}
                        <button
                            className="ua-btn logout"
                            onClick={() => {
                                logout();
                                navigate('/login');
                            }}
                            title={t('common.logout')}
                            aria-label={t('common.logout')}
                        >
                            <LogOut size={16} />
                        </button>
                    </div>
                </div>
            </header>

            {dashboardPresentation === 'overview' ? (
                <ClientOverview
                    devices={devices}
                    endpoints={endpoints}
                    alerts={alerts}
                    stats={stats}
                    readyState={readyState}
                    onOpenDevice={openDeviceFromOverview}
                    onOpenClassic={openClassicView}
                />
            ) : (
                <>
            <div className="dashboard-main">
                <aside className="panel">
                    <div className="panel-hdr">
                        <span className="panel-hdr-title">{t('dashboard.devices_panel')}</span>
                        <span className="panel-hdr-badge">{devices.length} {t('dashboard.devices_unit')}</span>
                    </div>
                    <div className="device-list">
                        {devices.map((device) => (
                            <DeviceCard
                                key={device.id}
                                device={device}
                                isActive={selectedDeviceId === device.id}
                                onClick={() => handleDeviceClick(device)}
                            />
                        ))}
                    </div>
                </aside>

                <section className="panel center-panel">
                    <div className="center-hdr">
                        <span className="panel-hdr-title">
                            {viewMode === 'grid'
                                ? t('dashboard.matrix_title')
                                : t('dashboard.device_table_title')}
                        </span>
                        <div className="center-hdr-actions">
                            <span className="current-filter-label">
                                {filterDeviceId === 'all'
                                    ? t('dashboard.all_devices')
                                    : getDisplayName(
                                        filterDeviceId,
                                        devices.find((device) => device.id === filterDeviceId)?.name
                                    )}
                            </span>
                            <div className="view-toggle">
                                <button
                                    className={`vt-btn ${viewMode === 'grid' ? 'active' : ''}`}
                                    onClick={() => handleViewChange('grid')}
                                >
                                    {t('dashboard.view_matrix')}
                                </button>
                                <button
                                    className={`vt-btn ${viewMode === 'devices' ? 'active' : ''}`}
                                    onClick={() => handleViewChange('devices')}
                                >
                                    {t('dashboard.view_devices')}
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="device-band">
                        <button
                            className={`db-chip ${filterDeviceId === 'all' ? 'active' : ''}`}
                            onClick={() => handleFilter('all')}
                        >
                            <span className="chip-dot" />{t('dashboard.filter_all')}
                        </button>
                        {tabDevices.map((device) => {
                            const status = device.online_status;
                            const dotClass = ['warning', 'critical'].includes(device.health_status)
                                ? 'warn'
                                : status === 'offline'
                                    ? 'dead'
                                    : '';
                            return (
                                <button
                                    key={device.id}
                                    className={`db-chip ${filterDeviceId === device.id ? 'active' : ''}`}
                                    onClick={() => handleFilter(device.id)}
                                >
                                    <span className={`chip-dot ${dotClass}`} />
                                    {getDisplayName(device.id, device.name)}
                                </button>
                            );
                        })}
                    </div>

                    {viewMode === 'grid' && <MatrixView filterDeviceId={filterDeviceId} />}
                    {viewMode === 'devices' && <DeviceTable filterDeviceId={filterDeviceId} />}
                </section>

                <aside className="panel">
                    <div className="panel-hdr">
                        <span className="panel-hdr-title">{t('dashboard.alerts_panel')}</span>
                        <span className="panel-hdr-badge">{activeAlerts} {t('dashboard.alerts_unit')}</span>
                    </div>
                    <AlertStream />
                </aside>
            </div>

            <footer className="bottom-bar">
                <BottomCharts
                    devices={devices}
                    selectedDeviceId={selectedDeviceId}
                    endpoints={endpoints}
                />
            </footer>
                </>
            )}
        </div>
    );
}
