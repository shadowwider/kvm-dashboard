import React, { useEffect, useState } from 'react';
import { useStore } from '../store/mainStore';
import EndpointDetail from './EndpointDetail';

const VIDEO_MAP = {
    none: '无信号', vga: 'VGA', dvisl: 'DVI-SL', dvidl: 'DVI-DL',
    dmdp: 'MDP', dp: 'DP', hdmi: 'HDMI',
};

const STATUS_TEXT = { online: '在线', ready: '就绪', offline: '离线', warning: '告警' };

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
    const { endpoints, devices, fetchEndpoints } = useStore();
    const [activeEp, setActiveEp] = useState(null);
    const [activeDev, setActiveDev] = useState(null);

    // 全部 = 拉取所有设备的终端
    useEffect(() => {
        if (filterDeviceId === 'all') {
            // 拉全部设备的终端
            devices.forEach(d => fetchEndpoints(d.id));
        } else if (filterDeviceId) {
            fetchEndpoints(filterDeviceId);
        }
    }, [filterDeviceId, devices.length]);

    // 过滤 endpoints
    const list = filterDeviceId === 'all'
        ? endpoints
        : endpoints.filter(ep => ep.device_id === filterDeviceId);

    // 每次 list 变化重新计数
    const counts = { online: 0, ready: 0, offline: 0, warning: 0 };
    list.forEach(ep => {
        const st = getEpStatus(ep);
        if (counts[st] !== undefined) counts[st]++;
    });

    // 根据终端总数自适应列数（每列最多 32 个，最小 16）
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
                        const stRaw = ep.last_status || {};
                        const temp = stRaw.ep_temperature
                            ? `${parseFloat(stRaw.ep_temperature).toFixed(1)}°C`
                            : 'N/A';
                        const video = VIDEO_MAP[stRaw.ep_target_video_signal] || stRaw.ep_target_video_signal || '—';
                        const dev = devices.find(d => d.id === ep.device_id);
                        return (
                            <div
                                key={ep.id}
                                className={`m-cell ${st}`}
                                onClick={() => { setActiveEp(ep); setActiveDev(dev); }}
                                title={`${ep.name || ep.id} (点击查看详情)`}
                            >
                                {/* 移除 hover tooltip，改为点击弹出 EndpointDetail 以防被滚动截取和遮挡 */}
                            </div>
                        );
                    })}
                    {list.length === 0 && (
                        <div style={{
                            gridColumn: '1/-1', textAlign: 'center',
                            padding: '40px', color: 'var(--text-dim)',
                            fontSize: '10px', letterSpacing: '2px',
                        }}>
                            暂无终端数据
                        </div>
                    )}
                </div>
            </div>

            {/* 图例 — 全部数量 */}
            <div className="matrix-legend">
                {[
                    { key: 'online', label: '在线', cls: 'online' },
                    { key: 'ready', label: '就绪', cls: 'ready' },
                    { key: 'offline', label: '离线', cls: 'offline' },
                    { key: 'warning', label: '告警', cls: 'warning' },
                ].map(({ key, label, cls }) => (
                    <div key={key} className="legend-item">
                        <div className={`legend-dot ${cls}`} />
                        <span>{label}</span>
                        <span className="legend-count">{counts[key]}</span>
                    </div>
                ))}
                <div style={{ marginLeft: 'auto', fontSize: '9px', color: 'var(--text-dim)' }}>
                    共 {total} 个终端 · 点击节点查看详情
                </div>
            </div>

            {/* 终端详情面板：复用到矩阵视图，避免原先悬浮框产生的容器遮挡 */}
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
