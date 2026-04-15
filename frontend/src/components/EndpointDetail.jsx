import React, { useEffect, useState } from 'react';
import api from '../utils/api';
import { useStore } from '../store/mainStore';
import { useTranslation } from '../i18n';

const VIDEO_LABEL = {
    none: 'No Signal', vga: 'VGA', dvisl: 'DVI-SL', dvidl: 'DVI-DL',
    dmdp: 'MDP', dp: 'DP', hdmi: 'HDMI',
};

const USB_HID_LABEL = { notConnected: 'Not Connected', connected: 'Connected', initialized: 'Active' };

function getEpStatus(ep) {
    const st = ep.last_status || {};
    if (ep.module_type === 'con') {
        const devSt = st.con_device_status;
        if (!devSt || devSt === 'offline') return 'offline';
        if (st.con_display_conn === 'notConnected') return 'warning';
        if (!st.con_console_usb || st.con_console_usb === 'none') return 'warning';
        if (st.con_freeze === 'true') return 'warning';
        return devSt;
    }
    const devSt = st.ep_device_status;
    if (!devSt || devSt === 'offline') return 'offline';
    if (st.ep_target_video_cable === 'notConnected') return 'warning';
    if (st.ep_target_usb_hid === 'notConnected') return 'warning';
    if (st.ep_target_power === 'off') return 'warning';
    return devSt;
}

const EndpointDetail = ({ ep, dev, onClose }) => {
    const [histData, setHistData] = useState([]);
    const getDisplayName = useStore(s => s.getDisplayName);
    const { t } = useTranslation();

    useEffect(() => {
        if (!ep) return;
        const oidName = ep.module_type === 'con' ? 'con_temperature' : 'ep_temperature';
        api.get(`/metrics/history?oid_name=${oidName}&endpoint_id=${ep.id}&device_id=${ep.device_id}&hours=12`)
            .then(r => setHistData(r.data || []))
            .catch(() => setHistData([]));
    }, [ep?.id]);

    if (!ep) return null;
    const st = getEpStatus(ep);
    const isCon = ep.module_type === 'con';
    const stRaw = ep.last_status || {};
    const temp   = parseFloat(isCon ? stRaw.con_temperature   : stRaw.ep_temperature);
    const video  = isCon
        ? (stRaw.con_display_conn === 'connected' ? 'Connected' : 'Not Connected')
        : (VIDEO_LABEL[stRaw.ep_target_video_signal] || stRaw.ep_target_video_signal || '—');
    const access = isCon
        ? (stRaw.con_freeze === 'true' ? 'FROZEN ⚠' : '—')
        : (stRaw.ep_target_access || '—');
    const sfpTx  = isCon ? stRaw.con_sfp_tx_power : stRaw.ep_sfp_tx_power;
    const sfpRx  = isCon ? stRaw.con_sfp_rx_power : stRaw.ep_sfp_rx_power;

    const STATUS_TEXT = {
        online: t('dashboard.legend_online'),
        ready: t('dashboard.legend_ready'),
        offline: t('dashboard.legend_offline'),
        warning: t('dashboard.legend_warning'),
    };

    const epName = getDisplayName(ep.id, ep.name);
    const devName = dev ? getDisplayName(dev.id, dev.name) : '—';

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
            <button className="td-close" onClick={onClose}>✕ {t('dashboard.detail_close')}</button>
            <div className="td-title">{epName}</div>
            <div className={`td-badge ${st}`}>{STATUS_TEXT[st] || st}</div>
            <div className="td-div" />
            <div className="td-row"><span className="td-k">{t('dashboard.detail_device')}</span><span className="td-v">{devName}</span></div>
            <div className="td-row"><span className="td-k">{t('dashboard.detail_port')}</span><span className="td-v">#{ep.index || '—'}</span></div>
            <div className="td-row"><span className="td-k">{t('dashboard.detail_video')}</span><span className="td-v">{video}</span></div>
            {!isCon && (
                <div className="td-row">
                    <span className="td-k">Video Cable</span>
                    <span className="td-v">{stRaw.ep_target_video_cable === 'connected' ? 'Connected' : stRaw.ep_target_video_cable === 'notConnected' ? 'Not Connected' : '—'}</span>
                </div>
            )}
            {!isCon && stRaw.ep_target_usb_hid && (
                <div className="td-row">
                    <span className="td-k">USB HID</span>
                    <span className="td-v">{USB_HID_LABEL[stRaw.ep_target_usb_hid] || stRaw.ep_target_usb_hid}</span>
                </div>
            )}
            {!isCon && stRaw.ep_net_if0 && (
                <div className="td-row">
                    <span className="td-k">Network</span>
                    <span className="td-v">{stRaw.ep_net_if0 === 'up' ? 'Up' : 'Down'}</span>
                </div>
            )}
            {isCon && stRaw.con_display_type && (
                <div className="td-row"><span className="td-k">Display</span><span className="td-v">{stRaw.con_display_type}</span></div>
            )}
            {isCon && (() => {
                const KM_LABEL = { none: '—', keyboard: 'Keyboard', mouse: 'Mouse', keyboardMouse: 'KB + Mouse' };
                const ps2 = KM_LABEL[stRaw.con_console_ps2] || stRaw.con_console_ps2;
                const usb = KM_LABEL[stRaw.con_console_usb] || stRaw.con_console_usb;
                return (<>
                    {stRaw.con_console_ps2 && stRaw.con_console_ps2 !== 'none' && (
                        <div className="td-row"><span className="td-k">PS/2</span><span className="td-v">{ps2}</span></div>
                    )}
                    {stRaw.con_console_usb && stRaw.con_console_usb !== 'none' && (
                        <div className="td-row"><span className="td-k">USB KM</span><span className="td-v">{usb}</span></div>
                    )}
                </>);
            })()}
            <div className="td-row"><span className="td-k">{t('dashboard.detail_temp')}</span><span className="td-v">{isNaN(temp) ? 'N/A' : `${temp.toFixed(1)}°C`}</span></div>
            <div className="td-row"><span className="td-k">{t('dashboard.detail_access')}</span><span className="td-v">{access}</span></div>
            {sfpTx && <div className="td-row"><span className="td-k">SFP TX</span><span className="td-v">{sfpTx} uW</span></div>}
            {sfpRx && <div className="td-row"><span className="td-k">SFP RX</span><span className="td-v">{sfpRx} uW</span></div>}
            <div className="td-div" />
            {histData.length > 1 && (
                <>
                    <div style={{ fontSize: '8px', color: 'var(--text-dim)', letterSpacing: '1px', marginBottom: '2px' }}>{t('dashboard.detail_trend')}</div>
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
