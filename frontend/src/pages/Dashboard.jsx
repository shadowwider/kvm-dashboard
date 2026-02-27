import React, { useEffect } from 'react';
import { useAuthStore } from '../store/authStore';
import { useStore } from '../store/mainStore';
import HealthRate from '../components/HealthRate';
import StatsBar from '../components/StatsBar';
import DeviceCard from '../components/DeviceCard';
import DeviceMatrix from '../components/DeviceMatrix';
import EndpointGrid from '../components/EndpointGrid';
import TopologyView from '../components/TopologyView';
import AlertStream from '../components/AlertStream';
import MetricChart from '../components/MetricChart';
import useSystemWebSocket from '../hooks/useSystemWebSocket';
import './Dashboard.css';

const Dashboard = () => {
    const logout = useAuthStore((state) => state.logout);
    const user = useAuthStore((state) => state.user);
    const { fetchAll, devices, viewMode, setViewMode } = useStore();

    useEffect(() => {
        fetchAll();
        const interval = setInterval(fetchAll, 60000); // 1 min poll fallback
        return () => clearInterval(interval);
    }, []);

    const { readyState } = useSystemWebSocket();

    return (
        <div className="dashboard-container">
            {/* 顶栏 */}
            <header className="dashboard-header glass-card">
                <div className="header-left">
                    <h1>KVM Dashboard</h1>
                    <span className="live-clock">{new Date().toLocaleTimeString()}</span>
                </div>
                <div className="header-center">
                    <HealthRate />
                </div>
                <div className="header-right">
                    <div className="ws-status" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
                        <span style={{
                            width: '8px', height: '8px', borderRadius: '50%',
                            background: readyState === 1 ? 'var(--status-online)' : 'var(--status-offline)'
                        }}></span>
                        {readyState === 1 ? 'Live' : 'WS Disconnected'}
                    </div>
                    <div className="user-info">
                        Welcome, {user?.username || 'Admin'}
                    </div>
                    <button className="logout-btn" onClick={() => logout()}>
                        Logout
                    </button>
                </div>
            </header>

            {/* KPI 一排统计 */}
            <StatsBar />

            {/* 中心三栏布局 */}
            <main className="dashboard-main">
                {/* 左栏 (25%) */}
                <aside className="left-panel glass-card">
                    <h2>Devices</h2>
                    <div style={{ flex: 1, overflowY: 'auto', paddingRight: '4px' }}>
                        {devices.map(dev => (
                            <DeviceCard key={dev.id} device={dev} />
                        ))}
                    </div>
                </aside>

                {/* 中心区域 (50%) */}
                <section className="center-panel glass-card">
                    <div className="panel-header">
                        <h2>Endpoint Status</h2>
                        <div className="view-toggles">
                            <button
                                className={viewMode === 'grid' ? 'active' : ''}
                                onClick={() => setViewMode('grid')}
                            >Matrix</button>
                            <button
                                className={viewMode === 'topology' ? 'active' : ''}
                                onClick={() => setViewMode('topology')}
                            >Topology</button>
                        </div>
                    </div>
                    <div style={{ flex: 1, overflow: 'hidden' }}>
                        {viewMode === 'grid' && <EndpointGrid />}
                        {viewMode === 'topology' && <TopologyView />}
                        {viewMode === 'global' && <DeviceMatrix />} {/* Will be mapped later */}
                    </div>
                </section>

                {/* 右栏 (25%) */}
                <aside className="right-panel glass-card">
                    <h2>Active Alerts</h2>
                    <div style={{ flex: 1, overflow: 'hidden' }}>
                        <AlertStream />
                    </div>
                </aside>
            </main>

            {/* 底栏: ECharts 历史图表 */}
            <footer className="dashboard-footer glass-card">
                <MetricChart />
            </footer>
        </div>
    );
};

export default Dashboard;
