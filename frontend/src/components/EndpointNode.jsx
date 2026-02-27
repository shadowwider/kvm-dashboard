import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { Monitor, ThermometerSun } from 'lucide-react';

const EndpointNode = ({ data }) => {
    const isOnline = data.status === 'online';
    const color = isOnline ? 'var(--status-online)' : 'var(--status-offline)';

    return (
        <div style={{
            background: 'var(--bg-secondary)',
            border: `1px solid ${color}`,
            boxShadow: `0 0 10px color-mix(in srgb, ${color} 20%, transparent)`,
            borderRadius: '8px',
            padding: '10px',
            minWidth: '120px',
            fontSize: '12px',
            color: 'var(--text-primary)'
        }}>
            <Handle type="target" position={Position.Top} style={{ background: color, border: 'none' }} />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 'bold' }}>{data.label}</span>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, boxShadow: `0 0 5px ${color}` }} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)', fontSize: '11px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Monitor size={12} /> {data.video_signal || 'None'}
                </span>

                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <ThermometerSun size={12} /> {data.temperature || '--'}°C
                </span>
            </div>
        </div>
    );
};

export default EndpointNode;
