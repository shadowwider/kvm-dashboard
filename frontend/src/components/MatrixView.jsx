import React, { useEffect, useState } from 'react';
import { useStore } from '../store/mainStore';
import { useTranslation } from '../i18n';
import EndpointDetail from './EndpointDetail';

const VIDEO_MAP = {
    none: 'No Signal', vga: 'VGA', dvisl: 'DVI-SL', dvidl: 'DVI-DL',
    dmdp: 'MDP', dp: 'DP', hdmi: 'HDMI',
};

// 从 endpoint 推断显示状态
function getEpStatus(ep) {
    const st = ep.last_status || {};
    const devSt = st.ep_device_status;
    if (!devSt || devSt === 'offline') return 'offline';
    if (devSt === 'ready') return 'ready';
    if (devSt === 'online') {
        if (st.ep_target_power === 'off') return 'warning';
        return 'online';
    }
    return 'offline';
}

const MatrixView = ({ filterDeviceId }) => {
    const { endpoints, devices, fetchEndpoints, getDisplayName } = useStore();
    const { t } = useTranslation();
    const [activeEp, setActiveEp] = useState(null);
    const [activeDev, setActiveDev] = useState(null);

    useEffect(() => {
        if (filterDeviceId === 'all') {
            devices.forEach(d => fetchEndpoints(d.id));
        } else if (filterDeviceId) {
            fetchEndpoints(filterDeviceId);
        }
    }, [filterDeviceId, devices.length]);

    const list = filterDeviceId === 'all'
        ? endpoints
        : endpoints.filter(ep => ep.device_id === filterDeviceId);

    const counts = { online: 0, ready: 0, offline: 0, warning: 0 };
    list.forEach(ep => {
        const st = getEpStatus(ep);
        if (counts[st] !== undefined) counts[st]++;
    });

    const total = list.length;
    const cols = total <= 32 ? 16 : total <= 64 ? 24 : total <= 128 ? 32 : 40;

    return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div className="matrix-wrap" style={{ overflowY: 'auto' }}>
                <div className="scan-line" />
                <div
                    className="matrix-grid"
                    style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
                >
                    {list.map(ep => {
                        const st = getEpStatus(ep);
                        // 终端名：优先用别名，否则 ep.name，最后 ep.id
                        const epDisplayName = getDisplayName(ep.id, ep.name);
                        return (
                            <div
                                key={ep.id}
                                className={`m-cell ${st}`}
                                onClick={() => {
                                    setActiveEp(ep);
                                    setActiveDev(devices.find(d => d.id === ep.device_id));
                                }}
                                title={`${epDisplayName} (${t('dashboard.ep_click_hint')})`}
                            >
                            </div>
                        );
                    })}
                    {list.length === 0 && (
                        <div style={{
                            gridColumn: '1/-1', textAlign: 'center',
                            padding: '40px', color: 'var(--text-dim)',
                            fontSize: '10px', letterSpacing: '2px',
                        }}>
                            {t('dashboard.no_endpoints')}
                        </div>
                    )}
                </div>
            </div>

            {/* 图例 */}
            <div className="matrix-legend">
                {[
                    { key: 'online', label: t('dashboard.legend_online'), cls: 'online' },
                    { key: 'ready', label: t('dashboard.legend_ready'), cls: 'ready' },
                    { key: 'offline', label: t('dashboard.legend_offline'), cls: 'offline' },
                    { key: 'warning', label: t('dashboard.legend_warning'), cls: 'warning' },
                ].map(({ key, label, cls }) => (
                    <div key={key} className="legend-item">
                        <div className={`legend-dot ${cls}`} />
                        <span>{label}</span>
                        <span className="legend-count">{counts[key]}</span>
                    </div>
                ))}
                <div style={{ marginLeft: 'auto', fontSize: '9px', color: 'var(--text-dim)' }}>
                    {total} {t('dashboard.ep_total_hint')} · {t('dashboard.ep_click_hint')}
                </div>
            </div>

            {activeEp && (
                <EndpointDetail
                    ep={activeEp}
                    dev={activeDev}
                    onClose={() => setActiveEp(null)}
                />
            )}
        </div>
    );
};

export default MatrixView;
