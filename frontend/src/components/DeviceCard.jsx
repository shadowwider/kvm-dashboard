import React, { useEffect, useState } from 'react';
import api from '../utils/api';
import { useStore } from '../store/mainStore';
import { useTranslation } from '../i18n';

/**
 * DeviceCard — 左侧 KVM 设备卡片
 * 集成：别名、OID display_enabled、i18n
 */
const DeviceCard = ({ device, isActive, onClick }) => {
    const status = device.last_status || 'offline';
    const [metrics, setMetrics] = useState(null);
    const getDisplayName = useStore(s => s.getDisplayName);
    const oidConfigs = useStore(s => s.oidConfigs);
    const { t } = useTranslation();

    const isDisplayEnabled = (oidName) => {
        const cfg = oidConfigs.find(o => o.name === oidName);
        return cfg ? cfg.display_enabled : true;
    };

    useEffect(() => {
        const fields = ['temperature', 'main_power', 'redundant_power', 'net_if0', 'net_if1',
            'fan1', 'fan2', 'fan3', 'fan4', 'fan5', 'fan6'];
        Promise.allSettled(
            fields.map(f =>
                api.get(`/metrics/history?oid_name=${f}&device_id=${device.id}&hours=1`)
                    .then(r => ({ name: f, data: r.data || [] }))
            )
        ).then(results => {
            const m = {};
            results.forEach(r => {
                if (r.status === 'fulfilled' && r.value.data.length > 0) {
                    const last = r.value.data[r.value.data.length - 1];
                    m[r.value.name] = last.value_num ?? last.value_str ?? null;
                }
            });
            setMetrics(m);
        });
    }, [device.id]);

    const temp = metrics?.temperature ?? null;
    const tempClass = temp === null ? '' : temp > 55 ? 'hot' : temp > 45 ? 'warm' : 'cool';
    const tempText = temp !== null ? `${parseFloat(temp).toFixed(1)}°C` : 'N/A';
    const psu1 = metrics?.main_power === 1 || metrics?.main_power === 'on';
    const psu2 = metrics?.redundant_power === 1 || metrics?.redundant_power === 'on';
    const net0 = metrics?.net_if0 === 1 || metrics?.net_if0 === 'up';
    const net1 = metrics?.net_if1 === 1 || metrics?.net_if1 === 'up';
    const fans = [
        metrics?.fan1, metrics?.fan2, metrics?.fan3,
        metrics?.fan4, metrics?.fan5, metrics?.fan6,
    ].map(v => (v === undefined || v === null) ? null : Number(v));
    const hasMetrics = metrics !== null;
    const displayName = getDisplayName(device.id, device.name);

    return (
        <div
            className={`device-card ${status} ${isActive ? 'active' : ''}`}
            onClick={onClick}
        >
            <div className="dc-name">{displayName}</div>
            <div className="dc-ip">{device.host}</div>

            <div className="dc-metrics">
                {isDisplayEnabled('temperature') && (
                    <div>
                        <div className="dc-metric-label">{t('dashboard.dc_temp')}</div>
                        <div className={`dc-metric-val ${tempClass}`}>
                            {hasMetrics ? tempText : '—'}
                        </div>
                    </div>
                )}
                {(isDisplayEnabled('main_power') || isDisplayEnabled('redundant_power')) && (
                    <div>
                        <div className="dc-metric-label">{t('dashboard.dc_power')}</div>
                        <div className="dc-metric-val">
                            {hasMetrics ? (
                                <>
                                    <span style={{ color: psu1 ? 'var(--green)' : 'var(--red)' }}>{psu1 ? '✓' : '✗'}</span>
                                    {' '}
                                    <span style={{ color: psu2 ? 'var(--green)' : 'var(--red)' }}>{psu2 ? '✓' : '✗'}</span>
                                </>
                            ) : '—'}
                        </div>
                    </div>
                )}
                {(isDisplayEnabled('net_if0') || isDisplayEnabled('net_if1')) && (
                    <div>
                        <div className="dc-metric-label">{t('dashboard.dc_net')}</div>
                        <div className="dc-metric-val">
                            {hasMetrics ? (
                                <>
                                    <span style={{ color: net0 ? 'var(--green)' : 'var(--red)' }}>●</span>
                                    {' '}
                                    <span style={{ color: net1 ? 'var(--green)' : 'var(--red)' }}>●</span>
                                </>
                            ) : '—'}
                        </div>
                    </div>
                )}
                <div>
                    <div className="dc-metric-label">{t('dashboard.dc_endpoints')}</div>
                    <div className="dc-metric-val">{device.endpoint_count ?? '—'}</div>
                </div>
            </div>

            {hasMetrics && fans.some(f => f !== null) && isDisplayEnabled('fan1') && (
                <div className="dc-fans">
                    {fans.map((f, i) =>
                        f !== null ? (
                            <div
                                key={i}
                                className={`fan-dot ${f === 0 ? 'dead' : ''}`}
                                title={f === 0 ? `${t('dashboard.dc_fan_fault')} ${i + 1}` : `Fan${i + 1}: ${f} RPM`}
                            />
                        ) : null
                    )}
                </div>
            )}
        </div>
    );
};

export default DeviceCard;
