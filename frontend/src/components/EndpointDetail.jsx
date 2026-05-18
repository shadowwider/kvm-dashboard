import React, { useEffect, useState } from 'react';
import api from '../utils/api';
import { useStore } from '../store/mainStore';
import { useTranslation } from '../i18n';
import {
    formatEndpointPosition,
    formatKeyboardMouseState,
    formatKeyboardMouseValue,
    formatUsbHidValue,
    formatVideoValue,
    getConKeyboardMouseState,
    getEndpointStatus,
} from '../utils/endpointStatus';

const EndpointDetail = ({ ep, dev, onClose }) => {
    const [histData, setHistData] = useState([]);
    const getDisplayName = useStore(s => s.getDisplayName);
    const { t } = useTranslation();
    const endpointId = ep?.id;
    const endpointDeviceId = ep?.device_id;
    const endpointModuleType = ep?.module_type;

    useEffect(() => {
        if (!endpointId) return;
        const oidName = endpointModuleType === 'con' ? 'con_temperature' : 'ep_temperature';
        api.get(`/metrics/history?oid_name=${oidName}&endpoint_id=${endpointId}&device_id=${endpointDeviceId}&hours=12`)
            .then(r => setHistData(r.data || []))
            .catch(() => setHistData([]));
    }, [endpointId, endpointDeviceId, endpointModuleType]);

    if (!ep) return null;

    const st = getEndpointStatus(ep);
    const isCon = ep.module_type === 'con';
    const stRaw = ep.last_status || {};
    const temp = parseFloat(isCon ? stRaw.con_temperature : stRaw.ep_temperature);
    const sfpTx = isCon ? stRaw.con_sfp_tx_power : stRaw.ep_sfp_tx_power;
    const sfpRx = isCon ? stRaw.con_sfp_rx_power : stRaw.ep_sfp_rx_power;
    const kmState = isCon ? getConKeyboardMouseState(stRaw) : null;

    const video = isCon
        ? (stRaw.con_display_conn === 'connected' ? t('dashboard.status_connected') : t('dashboard.status_not_connected'))
        : formatVideoValue(stRaw.ep_target_video_signal, t);
    const access = isCon
        ? (stRaw.con_freeze === 'true' ? t('dashboard.status_frozen') : '—')
        : (stRaw.ep_target_access || '—');

    const STATUS_TEXT = {
        online: t('dashboard.legend_online'),
        ready: t('dashboard.legend_ready'),
        offline: t('dashboard.legend_offline'),
        warning: t('dashboard.legend_warning'),
    };

    const epName = getDisplayName(ep.id, ep.name);
    const devName = dev ? getDisplayName(dev.id, dev.name) : ep.device_id;

    const PW = 164;
    const PH = 58;
    let miniPath = '';
    let miniArea = '';
    if (histData.length > 1) {
        const vals = histData.map(d => d.value_num ?? 0);
        const mn = Math.min(...vals) - 2;
        const mx = Math.max(...vals) + 2;
        const ty = value => PH - ((value - mn) / (mx - mn || 1)) * PH;
        const tx = (i, n) => (i / (n - 1)) * PW;
        const line = vals.map((value, i) => `${i === 0 ? 'M' : 'L'}${tx(i, vals.length).toFixed(1)},${ty(value).toFixed(1)}`).join(' ');
        miniPath = line;
        miniArea = `${line} L${PW},${PH} L0,${PH} Z`;
    }

    return (
        <div className="topo-detail-panel" style={{ zIndex: 10001 }}>
            <button className="td-close" onClick={onClose}>× {t('dashboard.detail_close')}</button>
            <div className="td-title">{epName}</div>
            <div className={`td-badge ${st}`}>{STATUS_TEXT[st] || st}</div>
            <div className="td-div" />
            <div className="td-row">
                <span className="td-k">{t('dashboard.detail_device')}</span>
                <span className="td-v">{devName}</span>
            </div>
            <div className="td-row">
                <span className="td-k">{t('dashboard.detail_interface')}</span>
                <span className="td-v">{formatEndpointPosition(ep, t, { short: true })}</span>
            </div>
            <div className="td-row">
                <span className="td-k">{t('dashboard.detail_video')}</span>
                <span className="td-v">{video}</span>
            </div>

            {!isCon && (
                <>
                    <div className="td-row">
                        <span className="td-k">{t('dashboard.detail_video_cable')}</span>
                        <span className="td-v">
                            {stRaw.ep_target_video_cable === 'connected'
                                ? t('dashboard.status_connected')
                                : stRaw.ep_target_video_cable === 'notConnected'
                                    ? t('dashboard.status_not_connected')
                                    : '—'}
                        </span>
                    </div>
                    <div className="td-row">
                        <span className="td-k">{t('dashboard.detail_usb_hid')}</span>
                        <span className="td-v">{formatUsbHidValue(stRaw.ep_target_usb_hid, t)}</span>
                    </div>
                    <div className="td-row">
                        <span className="td-k">{t('dashboard.detail_network')}</span>
                        <span className="td-v">
                            {stRaw.ep_net_if0 === 'up'
                                ? t('dashboard.status_up')
                                : stRaw.ep_net_if0
                                    ? t('dashboard.status_down')
                                    : '—'}
                        </span>
                    </div>
                </>
            )}

            {isCon && (
                <>
                    {stRaw.con_display_type && (
                        <div className="td-row">
                            <span className="td-k">{t('dashboard.detail_display')}</span>
                            <span className="td-v">{stRaw.con_display_type}</span>
                        </div>
                    )}
                    {/* 只显示综合键鼠状态，不再单独显示 PS/2 和 USB */}
                    <div className="td-row">
                        <span className="td-k">{t('dashboard.detail_keyboard_mouse')}</span>
                        <span className={`td-v km-${kmState.state}`}>{formatKeyboardMouseState(kmState, t)}</span>
                    </div>
                </>
            )}

            <div className="td-row">
                <span className="td-k">{t('dashboard.detail_temp')}</span>
                <span className="td-v">{Number.isNaN(temp) ? 'N/A' : `${temp.toFixed(1)}°C`}</span>
            </div>
            <div className="td-row">
                <span className="td-k">{t('dashboard.detail_access')}</span>
                <span className="td-v">{access}</span>
            </div>
            {sfpTx && (
                <div className="td-row">
                    <span className="td-k">SFP TX</span>
                    <span className="td-v">{sfpTx} uW</span>
                </div>
            )}
            {sfpRx && (
                <div className="td-row">
                    <span className="td-k">SFP RX</span>
                    <span className="td-v">{sfpRx} uW</span>
                </div>
            )}

            <div className="td-div" />
            {histData.length > 1 && (
                <>
                    <div style={{ fontSize: '8px', color: 'var(--text-dim)', letterSpacing: '1px', marginBottom: '2px' }}>
                        {t('dashboard.detail_trend')}
                    </div>
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
