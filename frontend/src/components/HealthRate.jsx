import React from 'react';
import { useStore } from '../store/mainStore';

const HealthRate = () => {
    const stats = useStore((state) => state.stats);
    const totalDevices = stats?.total_devices || 0;
    const totalEndpoints = stats?.total_endpoints || 0;
    const onlineDevices = stats?.online_devices || 0;
    const onlineEndpoints = stats?.online_endpoints || 0;
    const total = totalDevices + totalEndpoints;
    const online = onlineDevices + onlineEndpoints;
    const percent = (total > 0 ? (online / total) * 100 : 100).toFixed(1);

    const isHealthy = percent >= 95;

    return (
        <div className="health-rate-container" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '2px', marginBottom: '2px' }}>
                System Health
            </div>
            <div
                className="health-number"
                style={{
                    fontSize: '28px',
                    fontWeight: 'bold',
                    color: isHealthy ? 'var(--status-online)' : 'var(--status-critical)',
                    textShadow: `0 0 15px ${isHealthy ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'center',
                    gap: '4px'
                }}
            >
                {percent}<span style={{ fontSize: '16px' }}>%</span>
            </div>
            <div className="health-bar-wrapper" style={{ width: '150px', height: '4px', background: 'rgba(255,255,255,0.1)', margin: '0 auto', borderRadius: '2px', overflow: 'hidden', marginTop: '4px' }}>
                <div
                    className="health-bar-fill"
                    style={{
                        width: `${percent}%`,
                        height: '100%',
                        background: isHealthy ? 'var(--status-online)' : 'var(--status-critical)',
                        transition: 'width 1s cubic-bezier(0.4, 0, 0.2, 1)'
                    }}
                />
            </div>
        </div>
    );
};

export default HealthRate;
