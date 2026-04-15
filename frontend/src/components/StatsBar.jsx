import React from 'react';
import { useStore } from '../store/mainStore';
import { Server, Monitor, AlertTriangle } from 'lucide-react';

const StatsBar = () => {
    const stats = useStore((state) => state.stats);

    if (!stats) return <div className="stats-bar"><div className="stat-card glass-card">Loading KPI...</div></div>;

    return (
        <div className="stats-bar">
            <div className="stat-card glass-card stat-total" style={{ gap: '12px' }}>
                <Server className="stat-icon" size={24} color="var(--text-secondary)" />
                <div className="stat-info" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="stat-label" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Total Devices</span>
                    <span className="stat-value" style={{ fontSize: '20px', fontWeight: 'bold' }}>{stats.total_devices || 0}</span>
                </div>
            </div>

            <div className="stat-card glass-card stat-online" style={{ gap: '12px' }}>
                <Monitor className="stat-icon" size={24} color="var(--status-online)" />
                <div className="stat-info" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="stat-label" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Online Endpoints</span>
                    <span className="stat-value" style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--status-online)' }}>
                        {stats.online_endpoints || 0} <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>/ {stats.total_endpoints || 0}</span>
                    </span>
                </div>
            </div>

            <div className="stat-card glass-card stat-alerts" style={{
                gap: '12px',
                borderColor: stats.active_alerts > 0 ? 'rgba(245, 158, 11, 0.3)' : 'var(--border)'
            }}>
                <AlertTriangle
                    className="stat-icon"
                    size={24}
                    color={stats.active_alerts > 0 ? "var(--status-warning)" : "var(--text-secondary)"}
                    style={{ animation: stats.active_alerts > 0 ? 'pulse 2s infinite' : 'none' }}
                />
                <div className="stat-info" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="stat-label" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Active Alerts</span>
                    <span className="stat-value" style={{
                        fontSize: '20px', fontWeight: 'bold',
                        color: stats.active_alerts > 0 ? 'var(--status-warning)' : 'var(--text-primary)'
                    }}>
                        {stats.active_alerts || 0}
                    </span>
                </div>
            </div>
        </div>
    );
};

export default StatsBar;
