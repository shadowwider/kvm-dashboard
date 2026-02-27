import React, { useEffect, useState } from 'react';
import api from '../utils/api';

const VIDEO_LABEL = {
    none: '无信号', vga: 'VGA', dvisl: 'DVI-SL', dvidl: 'DVI-DL',
    dmdp: 'MDP', dp: 'DP', hdmi: 'HDMI',
};
const STATUS_TEXT = { online: '在线', ready: '就绪', offline: '离线', warning: '告警' };

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

const EndpointDetail = ({ ep, dev, onClose }) => {
    const [histData, setHistData] = useState([]);

    useEffect(() => {
        if (!ep) return;
        api.get(`/metrics/history?oid_name=ep_temperature&endpoint_id=${ep.id}&hours=12`)
            .then(r => setHistData(r.data || []))
            .catch(() => setHistData([]));
    }, [ep?.id]);

    if (!ep) return null;
    const st = getEpStatus(ep);
    const stRaw = ep.last_status || {};
    const temp = parseFloat(stRaw.ep_temperature);
    const video = VIDEO_LABEL[stRaw.ep_target_video_signal] || stRaw.ep_target_video_signal || '—';
    const access = stRaw.ep_target_access || '—';
    const sfpTx = stRaw.ep_sfp_tx_power;
    const sfpRx = stRaw.ep_sfp_rx_power;

    const PW = 164, PH = 58;
    let miniPath = '', miniArea = '';
    if (histData.length > 1) {
        const vals = histData.map(d => d.value_num ?? 0);
        const mn = Math.min(...vals) - 2, mx = Math.max(...vals) + 2;
        const ty = t => PH - ((t - mn) / (mx - mn)) * PH;
        const tx = (i, n) => (i / (n - 1)) * PW;
        const ld = vals.map((t, i) => `${i === 0 ? 'M' : 'L'}${tx(i, vals.length).toFixed(1)},${ty(t).toFixed(1)}`).join(' ');
        miniPath = ld;
        miniArea = ld + ` L${PW},${PH} L0,${PH} Z`;
    }

    return (
        <div className="topo-detail-panel" style={{ zIndex: 10001 }}>
            <button className="td-close" onClick={onClose}>✕ 关闭</button>
            <div className="td-title">{ep.name || ep.id}</div>
            <div className={`td-badge ${st}`}>{STATUS_TEXT[st] || st}</div>
            <div className="td-div" />
            <div className="td-row"><span className="td-k">所属设备</span><span className="td-v">{dev?.name || dev?.id}</span></div>
            <div className="td-row"><span className="td-k">端口号</span><span className="td-v">#{ep.index || '—'}</span></div>
            <div className="td-row"><span className="td-k">视频信号</span><span className="td-v">{video}</span></div>
            <div className="td-row"><span className="td-k">当前温度</span><span className="td-v">{isNaN(temp) ? 'N/A' : `${temp.toFixed(1)}°C`}</span></div>
            <div className="td-row"><span className="td-k">访问状态</span><span className="td-v">{access}</span></div>
            {sfpTx && <div className="td-row"><span className="td-k">SFP 发送</span><span className="td-v">{sfpTx} uW</span></div>}
            {sfpRx && <div className="td-row"><span className="td-k">SFP 接收</span><span className="td-v">{sfpRx} uW</span></div>}
            <div className="td-div" />
            {histData.length > 1 && (
                <>
                    <div style={{ fontSize: '8px', color: 'var(--text-dim)', letterSpacing: '1px', marginBottom: '2px' }}>温度趋势（近12次轮询）</div>
                    <div className="td-chart-wrap">
                        <svg style={{ width: '100%', height: '58px' }} viewBox="0 0 164 58" preserveAspectRatio="none">
                            {miniArea && <path d={miniArea} fill="rgba(0,212,255,0.1)" />}
                            {miniPath && <path d={miniPath} fill="none" stroke="var(--cyan)" strokeWidth="1.5" />}
                        </svg>
                    </div>
                </>
            )}
        </div>
    );
};

export default EndpointDetail;
