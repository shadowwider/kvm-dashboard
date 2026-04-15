import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useStore } from '../store/mainStore';
import { useTranslation } from '../i18n';
import useSystemWebSocket from '../hooks/useSystemWebSocket';
import DeviceCard from '../components/DeviceCard';
import MatrixView from '../components/MatrixView';
import TopoView from '../components/TopoView';
import AlertStream from '../components/AlertStream';
import BottomCharts from '../components/BottomCharts';
import './Dashboard.css';

// countUp 动画
function useCountUp(target, duration = 1200) {
    const [value, setValue] = useState(0);
    useEffect(() => {
        if (!target) return;
        let v = 0;
        const step = target / (duration / 16);
        const timer = setInterval(() => {
            v += step;
            if (v >= target) { setValue(target); clearInterval(timer); return; }
            setValue(Math.floor(v));
        }, 16);
        return () => clearInterval(timer);
    }, [target]);
    return value;
}

const Dashboard = () => {
    const navigate = useNavigate();
    const { token, logout, user } = useAuthStore();
    const {
        stats, devices, alerts,
        selectedDeviceId, viewMode,
        setSelectedDevice, setViewMode,
        fetchAll, fetchEndpoints, fetchTopology,
        getDisplayName,
    } = useStore();
    const { t, locale, toggleLocale } = useTranslation();

    const { readyState } = useSystemWebSocket();
    const [clock, setClock] = useState('');
    const [filterDeviceId, setFilterDeviceId] = useState('all');

    // 时钟
    useEffect(() => {
        const tick = () => {
            const n = new Date();
            const pad = v => String(v).padStart(2, '0');
            setClock(`${pad(n.getHours())}:${pad(n.getMinutes())}:${pad(n.getSeconds())}`);
        };
        tick();
        const timer = setInterval(tick, 1000);
        return () => clearInterval(timer);
    }, []);

    // 初始加载
    useEffect(() => {
        fetchAll();
        const interval = setInterval(fetchAll, 60000);
        return () => clearInterval(interval);
    }, []);

    // devices加载完成后，确保全部终端数据被抉取
    const { fetchAllEndpoints, endpoints } = useStore();
    useEffect(() => {
        if (devices.length > 0) {
            fetchAllEndpoints();
        }
    }, [devices.length]);

    // 切换设备时拉对应数据
    useEffect(() => {
        if (selectedDeviceId && selectedDeviceId !== 'all') {
            fetchEndpoints(selectedDeviceId);
            fetchTopology(selectedDeviceId);
        }
    }, [selectedDeviceId]);

    // 筛选处理
    const handleFilter = (id) => {
        setFilterDeviceId(id);
        if (id !== 'all') {
            setSelectedDevice(id);
        } else {
            setSelectedDevice(null);
        }
    };

    // 健康率 + KPI：统一用终端 (endpoints) 计算
    const { endpoints: allEps } = useStore();
    const isEpActive = ep => {
        const devSt = (ep.last_status || {}).ep_device_status;
        return devSt === 'online' || devSt === 'ready';
    };
    const isEpOffline = ep => {
        const devSt = (ep.last_status || {}).ep_device_status;
        return !devSt || devSt === 'offline';
    };

    // 终端分类数
    const epTotal = allEps.length > 0 ? allEps.length : (stats?.total_endpoints || 0);
    const epActive = allEps.length > 0 ? allEps.filter(isEpActive).length : (stats?.online_endpoints || 0);
    const epOffline = allEps.length > 0 ? allEps.filter(isEpOffline).length : Math.max(epTotal - epActive, 0);
    const activeAlerts = stats?.active_alerts || alerts.filter(a => !a.is_resolved).length || 0;

    // 健康率
    const healthPct = epTotal > 0 ? ((epActive / epTotal) * 100).toFixed(1) : '100.0';

    // 设备卡点击
    const handleDeviceClick = (dev) => {
        setSelectedDevice(dev.id);
        setFilterDeviceId(dev.id);
    };

    return (
        <div className="dashboard-app">
            {/* ─── 顶栏 ─── */}
            <header className="topbar">
                <div className="sys-title">
                    <div className="lbl">SHA / PVGL / CTRL-OPS</div>
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
                        <div className="kpi-val">{epTotal}</div>
                        <div className="kpi-lbl">{t('dashboard.kpi_total')}</div>
                    </div>
                    <div className="kpi-card online">
                        <div className="kpi-val">{epActive}</div>
                        <div className="kpi-lbl">{t('dashboard.kpi_active')}</div>
                    </div>
                    <div className="kpi-card offline">
                        <div className="kpi-val">{epOffline}</div>
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
                        <button className="ua-btn" onClick={toggleLocale} title={locale === 'zh-CN' ? 'English' : '中文'}>
                            {locale === 'zh-CN' ? 'EN' : '中'}
                        </button>
                        {user?.role === 'admin' && (
                            <button className="ua-btn" onClick={() => navigate('/admin')} title={t('admin.title')}>
                                ⚙
                            </button>
                        )}
                        <button className="ua-btn logout" onClick={() => { logout(); navigate('/login'); }} title="Logout">
                            ⏻
                        </button>
                    </div>
                </div>
            </header>

            {/* ─── 中间三栏 ─── */}
            <div className="dashboard-main">
                {/* 左栏：设备卡片 */}
                <aside className="panel">
                    <div className="panel-hdr">
                        <span className="panel-hdr-title">{t('dashboard.devices_panel')}</span>
                        <span className="panel-hdr-badge">{devices.length} {t('dashboard.devices_unit')}</span>
                    </div>
                    <div className="device-list">
                        {devices.map(dev => (
                            <DeviceCard
                                key={dev.id}
                                device={dev}
                                isActive={selectedDeviceId === dev.id}
                                onClick={() => handleDeviceClick(dev)}
                            />
                        ))}
                    </div>
                </aside>

                {/* 中间：矩阵/拓扑 */}
                <section className="panel" style={{ overflow: 'hidden' }}>
                    {/* 顶部标题+切换 */}
                    <div className="center-hdr">
                        <span className="panel-hdr-title">
                            {viewMode === 'grid' ? t('dashboard.matrix_title') : t('dashboard.topo_title')}
                        </span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ fontSize: '9px', color: 'var(--text-dim)' }}>
                                {filterDeviceId === 'all'
                                    ? t('dashboard.all_devices')
                                    : getDisplayName(filterDeviceId, devices.find(d => d.id === filterDeviceId)?.name)}
                            </span>
                            <div className="view-toggle">
                                <button
                                    className={`vt-btn ${viewMode === 'grid' ? 'active' : ''}`}
                                    onClick={() => setViewMode('grid')}
                                >{t('dashboard.view_matrix')}</button>
                                <button
                                    className={`vt-btn ${viewMode === 'topology' ? 'active' : ''}`}
                                    onClick={() => setViewMode('topology')}
                                >{t('dashboard.view_topo')}</button>
                            </div>
                        </div>
                    </div>

                    {/* 设备 chip 过滤条 */}
                    <div className="device-band">
                        <button
                            className={`db-chip ${filterDeviceId === 'all' ? 'active' : ''}`}
                            onClick={() => handleFilter('all')}
                        >
                            <span className="chip-dot" />{t('dashboard.filter_all')}
                        </button>
                        {devices.map(dev => {
                            const st = dev.last_status;
                            const dotCls = st === 'warning' ? 'warn' : st === 'offline' ? 'dead' : '';
                            return (
                                <button
                                    key={dev.id}
                                    className={`db-chip ${filterDeviceId === dev.id ? 'active' : ''}`}
                                    onClick={() => handleFilter(dev.id)}
                                >
                                    <span className={`chip-dot ${dotCls}`} />
                                    {getDisplayName(dev.id, dev.name)}
                                </button>
                            );
                        })}
                    </div>

                    {/* 视图区域 */}
                    {viewMode === 'grid' && (
                        <MatrixView filterDeviceId={filterDeviceId} />
                    )}
                    {viewMode === 'topology' && (
                        <TopoView filterDeviceId={filterDeviceId} devices={devices} />
                    )}
                </section>

                {/* 右栏：告警流 */}
                <aside className="panel">
                    <div className="panel-hdr">
                        <span className="panel-hdr-title">{t('dashboard.alerts_panel')}</span>
                        <span className="panel-hdr-badge">{activeAlerts} {t('dashboard.alerts_unit')}</span>
                    </div>
                    <AlertStream />
                </aside>
            </div>

            {/* ─── 底栏图表 ─── */}
            <footer className="bottom-bar">
                <BottomCharts devices={devices} selectedDeviceId={selectedDeviceId} endpoints={endpoints} />
            </footer>
        </div>
    );
};

export default Dashboard;
