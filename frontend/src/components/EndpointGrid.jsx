import React from 'react';
import { useStore } from '../store/mainStore';

const EndpointGrid = () => {
    const { endpoints, selectedDeviceId } = useStore();

    if (!selectedDeviceId) {
        return (
            <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                Please Select a KVM Switch from the Left Panel
            </div>
        );
    }

    if (endpoints.length === 0) {
        return (
            <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                Pulling Endpoints or Empty Switch...
            </div>
        );
    }

    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(40px, 1fr))',
            gap: '8px',
            padding: '16px',
            alignContent: 'start',
            overflowY: 'auto',
            height: '100%'
        }}>
            {endpoints.map(ep => {
                // 解析 last_status 取色逻辑 (模拟的)
                const epState = ep.last_status?.ep_online === 'yes' ? 'online' : 'offline';

                const color = epState === 'online' ? 'var(--status-online)' : 'var(--status-offline)';

                return (
                    <div
                        key={ep.id}
                        title={`${ep.name || ep.id}
Temperature: ${ep.last_status?.temperature || '--'}
Video: ${ep.last_status?.video_cable || '--'}`}
                        style={{
                            aspectRatio: '1/1',
                            backgroundColor: `color-mix(in srgb, ${color} 20%, transparent)`,
                            border: `1px solid ${color}`,
                            borderRadius: '6px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '10px',
                            color: '#fff',
                            fontWeight: 'bold'
                        }}
                    >
                        {ep.index}
                    </div>
                )
            })}
        </div>
    );
};

export default EndpointGrid;
