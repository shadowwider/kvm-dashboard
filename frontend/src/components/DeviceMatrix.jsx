import React, { useEffect } from 'react';
import { useStore } from '../store/mainStore';
import { Activity } from 'lucide-react';

const DeviceMatrix = () => {
    const { devices, selectedDeviceId, setSelectedDevice } = useStore();

    if (!devices || devices.length === 0) {
        return <div className="empty-state">No Devices Discovered. Check Backend SNMP Poller.</div>
    }

    return (
        <div className="device-matrix" style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(40px, 1fr))',
            gap: '8px',
            padding: '16px',
            alignContent: 'start',
            overflowY: 'auto',
            height: '100%'
        }}>
            {devices.map(dev => {
                const color = dev.last_status === 'online' ? 'var(--status-online)'
                    : dev.last_status === 'warning' ? 'var(--status-warning)'
                        : 'var(--status-offline)';

                const isSelected = selectedDeviceId === dev.id;

                return (
                    <div
                        key={dev.id}
                        onClick={() => setSelectedDevice(dev.id)}
                        title={`${dev.name || dev.id} (${dev.last_status})`}
                        style={{
                            aspectRatio: '1/1',
                            backgroundColor: color,
                            opacity: isSelected ? 1 : 0.8,
                            borderRadius: '4px',
                            cursor: 'pointer',
                            boxShadow: isSelected ? `0 0 0 2px var(--bg-primary), 0 0 0 4px ${color}` : 'none',
                            transition: 'transform 0.1s, opacity 0.2s',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}
                        onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.1)'}
                        onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
                    >
                        {isSelected && <Activity size={14} color="#fff" />}
                    </div>
                )
            })}
        </div>
    );
};

export default DeviceMatrix;
