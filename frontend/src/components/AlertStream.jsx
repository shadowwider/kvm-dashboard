import React from 'react';
import { format, isValid } from 'date-fns';
import { AlertTriangle, Info, ShieldAlert } from 'lucide-react';
import { useStore } from '../store/mainStore';

const AlertStream = () => {
    const { alerts } = useStore();

    if (!alerts || alerts.length === 0) {
        return (
            <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                No Active Alerts
            </div>
        );
    }

    return (
        <div className="alert-stream" style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto', height: '100%', paddingRight: '4px' }}>
            {alerts.map(alert => {
                let Icon = Info;
                let color = 'var(--text-secondary)';
                let bgStyle = 'rgba(255,255,255,0.02)';

                if (alert.severity === 'critical') {
                    Icon = ShieldAlert;
                    color = 'var(--status-critical)';
                    bgStyle = 'rgba(220, 38, 38, 0.08)';
                } else if (alert.severity === 'warning') {
                    Icon = AlertTriangle;
                    color = 'var(--status-warning)';
                    bgStyle = 'rgba(245, 158, 11, 0.08)';
                }

                return (
                    <div key={alert.id} style={{
                        background: bgStyle,
                        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
                        borderLeft: `3px solid ${color}`,
                        padding: '10px',
                        borderRadius: '6px',
                        display: 'flex',
                        gap: '12px',
                        animation: 'slideInRight 0.3s ease-out'
                    }}>
                        <div style={{ marginTop: '2px' }}><Icon size={16} color={color} /></div>
                        <div style={{ flex: 1 }}>
                            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                                {isValid(new Date(alert.created_at)) ? format(new Date(alert.created_at), 'HH:mm:ss') : format(new Date(), 'HH:mm:ss')} • {alert.device_id}
                            </div>
                            <div style={{ fontSize: '13px', lineHeight: '1.4' }}>
                                {alert.message}
                            </div>
                        </div>
                    </div>
                )
            })}
        </div>
    );
};

export default AlertStream;
