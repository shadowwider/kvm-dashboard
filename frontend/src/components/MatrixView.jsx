import React, { useEffect, useMemo, useState } from 'react';
import { useStore } from '../store/mainStore';
import { useTranslation } from '../i18n';
import EndpointDetail from './EndpointDetail';
import {
    formatEndpointPosition,
    getDevicePortSummary,
    getEndpointSortIndex,
    getEndpointStatus,
} from '../utils/endpointStatus';
import { isMatrixProfile } from '../utils/multiProfile';

const MatrixView = ({ filterDeviceId }) => {
    const { endpoints, devices, fetchEndpoints } = useStore();
    const getDisplayName = useStore(state => state.getDisplayName);
    const { t } = useTranslation();
    const [activeEp, setActiveEp] = useState(null);
    const [activeDev, setActiveDev] = useState(null);

    const visibleDevices = useMemo(() => (
        filterDeviceId === 'all'
            ? devices.filter(isMatrixProfile)
            : devices.filter(dev => dev.id === filterDeviceId && isMatrixProfile(dev))
    ), [devices, filterDeviceId]);

    useEffect(() => {
        visibleDevices.forEach(dev => fetchEndpoints(dev.id));
    }, [visibleDevices, fetchEndpoints]);

    const list = useMemo(() => {
        const deviceIds = new Set(visibleDevices.map(dev => dev.id));
        return endpoints
            .filter(ep => deviceIds.has(ep.device_id))
            .slice()
            .sort((a, b) => {
                if (a.device_id !== b.device_id) return a.device_id.localeCompare(b.device_id);
                if ((a.module_type || 'cpu') !== (b.module_type || 'cpu')) {
                    return (a.module_type || 'cpu') === 'cpu' ? -1 : 1;
                }
                return getEndpointSortIndex(a) - getEndpointSortIndex(b);
            });
    }, [endpoints, visibleDevices]);

    const counts = { online: 0, ready: 0, offline: 0, warning: 0 };
    list.forEach(ep => {
        const st = getEndpointStatus(ep);
        if (counts[st] !== undefined) counts[st] += 1;
    });

    const openEndpoint = (ep, dev) => {
        setActiveEp(ep);
        setActiveDev(dev);
    };

    const renderEndpointCard = (ep, dev) => {
        const st = getEndpointStatus(ep);
        const epName = getDisplayName(ep.id, ep.name);
        const type = ep.module_type === 'con' ? 'CON' : 'CPU';

        return (
            <button
                key={ep.id}
                className={`m-cell tier-card ${st}`}
                onClick={() => openEndpoint(ep, dev)}
                title={`${getDisplayName(dev.id, dev.name)} ${formatEndpointPosition(ep, t)}`}
            >
                <span className="m-cell-port">{formatEndpointPosition(ep, t, { short: true })}</span>
                <span className="m-cell-name">{epName}</span>
                <span className="m-cell-type">{type}</span>
            </button>
        );
    };

    const renderStack = (dev) => {
        const devEndpoints = list.filter(ep => ep.device_id === dev.id);
        const cpus = devEndpoints.filter(ep => ep.module_type !== 'con');
        const cons = devEndpoints.filter(ep => ep.module_type === 'con');
        const portSummary = getDevicePortSummary(dev);
        const devName = getDisplayName(dev.id, dev.name);

        return (
            <section key={dev.id} className="matrix-device-stack">
                <div className="tiered-layer top">
                    {cpus.length > 0
                        ? cpus.map(ep => renderEndpointCard(ep, dev))
                        : <div className="tiered-empty">{t('dashboard.empty_cpu')}</div>}
                </div>

                <div className="tier-connector top" />

                <div className="tiered-layer middle">
                    <button
                        className={`m-switch-node ${dev.last_status || 'offline'}`}
                        onClick={() => setActiveDev(dev)}
                        title={`${devName} ${dev.host || ''}`}
                    >
                        <span className="ms-icon">SW</span>
                        <span className="ms-name">{devName}</span>
                        <span className="ms-meta">{dev.host || dev.id}</span>
                        <span className="ms-stats">
                            CPU {cpus.length} · CON {cons.length}
                            {portSummary.total > 0
                                ? ` · ${t('dashboard.switch_ports')} ${portSummary.up}/${portSummary.total}`
                                : ''}
                        </span>
                    </button>
                </div>

                <div className="tier-connector bottom" />

                <div className="tiered-layer bottom">
                    {cons.length > 0
                        ? cons.map(ep => renderEndpointCard(ep, dev))
                        : <div className="tiered-empty">{t('dashboard.empty_con')}</div>}
                </div>
            </section>
        );
    };

    return (
        <div className="matrix-view">
            <div className="matrix-content tiered-content">
                {visibleDevices.length > 0 && (
                    <div className="matrix-tiered-container">
                        {visibleDevices.map(renderStack)}
                    </div>
                )}

                {list.length === 0 && (
                    <div className="empty-state">
                        {t('dashboard.no_endpoints')}
                    </div>
                )}
            </div>

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

                <div className="matrix-hint">
                    {list.length} {t('dashboard.ep_total_hint')} · {t('dashboard.ep_click_hint')}
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
