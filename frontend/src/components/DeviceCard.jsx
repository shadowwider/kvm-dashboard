import React from 'react';
import { useStore } from '../store/mainStore';
import { Power, ThermometerSun, AlertCircle } from 'lucide-react';

const DeviceCard = ({ device }) => {
    const { selectedDeviceId, setSelectedDevice } = useStore();
    const isSelected = selectedDeviceId === device.id;

    const statusColor = device.last_status === 'online' ? 'var(--status-online)'
        : device.last_status === 'warning' ? 'var(--status-warning)'
            : 'var(--status-offline)';

    return (
        <div
            className={`device-card glass-card ${isSelected ? 'selected' : ''}`}
            onClick={() => setSelectedDevice(device.id)}
            style={{
                padding: '12px',
                marginBottom: '10px',
                cursor: 'pointer',
                borderLeft: `3px solid ${statusColor}`,
                transition: 'all 0.2s',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                background: isSelected ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
                borderColor: isSelected ? 'var(--accent)' : 'var(--border)'
            }}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '15px', margin: 0 }}>{device.name || device.id}</h3>
                <span style={{
                    width: '8px', height: '8px', borderRadius: '50%', backgroundColor: statusColor,
                    boxShadow: `0 0 8px ${statusColor}`
                }}></span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', color: 'rgba(255, 255, 255, 0.85)', marginTop: '4px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><ThermometerSun size={14} /> {device.last_status === 'online' ? '42.0 °C' : '-- °C'}</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: statusColor }}>
                    <Power size={14} /> {device.last_status}
                </span>
            </div>
        </div>
    );
};

export default DeviceCard;
