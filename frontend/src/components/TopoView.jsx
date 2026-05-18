import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useStore } from '../store/mainStore';
import { useTranslation } from '../i18n';
import EndpointDetail from './EndpointDetail';
import {
    formatEndpointPosition,
    formatVideoValue,
    getDevicePortSummary,
    getEndpointSortIndex,
    getEndpointStatus,
} from '../utils/endpointStatus';

const SCALE_MIN = 0.3;
const SCALE_MAX = 3.0;

function isVideoLost(ep) {
    const st = ep.last_status || {};
    if (ep.module_type === 'con') return st.con_display_conn !== 'connected';
    return st.ep_target_video_cable === 'notConnected' || st.ep_target_video_cable === 'disconnected';
}

const TopoView = ({ filterDeviceId, devices }) => {
    const { endpoints, fetchEndpoints, getDisplayName } = useStore();
    const { t } = useTranslation();
    const canvasRef = useRef(null);
    const viewportRef = useRef(null);
    const dragRef = useRef(null);
    const [activeEp, setActiveEp] = useState(null);
    const [activeDev, setActiveDev] = useState(null);
    const [transform, setTransform] = useState({ scale: 1, tx: 0, ty: 0 });
    const transRef = useRef(transform);

    useEffect(() => {
        transRef.current = transform;
    }, [transform]);

    const visibleDevices = useMemo(() => (
        filterDeviceId === 'all'
            ? devices
            : devices.filter(dev => dev.id === filterDeviceId)
    ), [devices, filterDeviceId]);

    useEffect(() => {
        visibleDevices.forEach(dev => fetchEndpoints(dev.id));
    }, [visibleDevices, fetchEndpoints]);

    const applyTransform = useCallback((next) => {
        if (!viewportRef.current) return;
        viewportRef.current.style.transform = `translate(${next.tx}px,${next.ty}px) scale(${next.scale})`;
    }, []);

    const onWheel = useCallback((e) => {
        e.preventDefault();
        const delta = e.deltaY < 0 ? 1.1 : 0.91;
        setTransform(prev => {
            const ns = Math.min(SCALE_MAX, Math.max(SCALE_MIN, prev.scale * delta));
            const rect = canvasRef.current.getBoundingClientRect();
            const mx = e.clientX - rect.left - prev.tx;
            const my = e.clientY - rect.top - prev.ty;
            const ratio = ns / prev.scale;
            const next = { scale: ns, tx: prev.tx - mx * (ratio - 1), ty: prev.ty - my * (ratio - 1) };
            applyTransform(next);
            return next;
        });
    }, [applyTransform]);

    const onMouseDown = useCallback((e) => {
        const target = e.target;
        if (e.button !== 0 || (target instanceof Element && target.closest('button'))) return;
        dragRef.current = {
            startX: e.clientX,
            startY: e.clientY,
            startTx: transRef.current.tx,
            startTy: transRef.current.ty,
        };
        canvasRef.current?.classList.add('dragging');
    }, []);

    const onMouseMove = useCallback((e) => {
        if (!dragRef.current) return;
        const dx = e.clientX - dragRef.current.startX;
        const dy = e.clientY - dragRef.current.startY;
        const next = {
            ...transRef.current,
            tx: dragRef.current.startTx + dx,
            ty: dragRef.current.startTy + dy,
        };
        transRef.current = next;
        applyTransform(next);
    }, [applyTransform]);

    const onMouseUp = useCallback(() => {
        if (!dragRef.current) return;
        dragRef.current = null;
        canvasRef.current?.classList.remove('dragging');
        setTransform({ ...transRef.current });
    }, []);

    useEffect(() => {
        const el = canvasRef.current;
        if (!el) return undefined;
        el.addEventListener('wheel', onWheel, { passive: false });
        el.addEventListener('mousedown', onMouseDown);
        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
        return () => {
            el.removeEventListener('wheel', onWheel);
            el.removeEventListener('mousedown', onMouseDown);
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
        };
    }, [onWheel, onMouseDown, onMouseMove, onMouseUp]);

    const resetZoom = useCallback(() => {
        const next = { scale: 1, tx: 0, ty: 0 };
        setTransform(next);
        applyTransform(next);
    }, [applyTransform]);

    const changeScale = useCallback((factor) => {
        setTransform(prev => {
            const next = {
                ...prev,
                scale: Math.min(SCALE_MAX, Math.max(SCALE_MIN, prev.scale * factor)),
            };
            applyTransform(next);
            return next;
        });
    }, [applyTransform]);

    const visibleEndpointList = useMemo(() => {
        const ids = new Set(visibleDevices.map(dev => dev.id));
        return endpoints
            .filter(ep => ids.has(ep.device_id))
            .slice()
            .sort((a, b) => getEndpointSortIndex(a) - getEndpointSortIndex(b));
    }, [endpoints, visibleDevices]);

    const openEndpoint = (ep, dev) => {
        setActiveEp(ep);
        setActiveDev(dev);
    };

    const renderEndpointNode = (ep, dev) => {
        const st = getEndpointStatus(ep);
        const raw = ep.last_status || {};
        const epName = getDisplayName(ep.id, ep.name);
        const isCon = ep.module_type === 'con';
        const signal = isCon
            ? (raw.con_display_conn === 'connected' ? t('dashboard.status_connected') : t('dashboard.status_not_connected'))
            : formatVideoValue(raw.ep_target_video_signal, t);

        return (
            <button
                key={ep.id}
                className={`topo-tier-node endpoint ${st}`}
                onClick={(e) => {
                    e.stopPropagation();
                    openEndpoint(ep, dev);
                }}
                title={`${getDisplayName(dev.id, dev.name)} ${formatEndpointPosition(ep, t)}`}
            >
                <span className="topo-node-head">
                    <span className="topo-node-kind">{isCon ? 'CON' : 'CPU'}</span>
                    <span className="topo-node-port">{formatEndpointPosition(ep, t, { short: true })}</span>
                </span>
                <span className="topo-node-name">{epName}</span>
                <span className="topo-node-signal">{isVideoLost(ep) ? t('dashboard.topo_video_disc') : signal}</span>
            </button>
        );
    };

    const renderLinks = (items, side) => (
        <div className={`topo-link-row ${side}`}>
            {items.length > 0
                ? items.map(ep => <span key={ep.id} className={`topo-link-segment ${getEndpointStatus(ep)}`} />)
                : <span className="topo-link-segment muted" />}
        </div>
    );

    const renderDeviceTopology = (dev) => {
        const devEndpoints = visibleEndpointList.filter(ep => ep.device_id === dev.id);
        const cpus = devEndpoints.filter(ep => ep.module_type !== 'con');
        const cons = devEndpoints.filter(ep => ep.module_type === 'con');
        const portSummary = getDevicePortSummary(dev);
        const devName = getDisplayName(dev.id, dev.name);

        return (
            <section key={dev.id} className="topo-device-stack">
                <div className="topo-tier-row top">
                    {cpus.length ? cpus.map(ep => renderEndpointNode(ep, dev)) : <div className="topo-empty">{t('dashboard.empty_cpu')}</div>}
                </div>
                {renderLinks(cpus, 'top')}
                <div className="topo-tier-row middle">
                    <div className={`topo-tier-node switch ${dev.last_status || 'offline'}`}>
                        <span className="topo-node-kind">KVM</span>
                        <span className="topo-switch-name">{devName}</span>
                        <span className="topo-switch-host">{dev.host || dev.id}</span>
                        <span className="topo-switch-stats">
                            CPU {cpus.length} · CON {cons.length}
                            {portSummary.total > 0
                                ? ` · ${t('dashboard.switch_ports')} ${portSummary.up}/${portSummary.total}`
                                : ''}
                        </span>
                    </div>
                </div>
                {renderLinks(cons, 'bottom')}
                <div className="topo-tier-row bottom">
                    {cons.length ? cons.map(ep => renderEndpointNode(ep, dev)) : <div className="topo-empty">{t('dashboard.empty_con')}</div>}
                </div>
            </section>
        );
    };

    const activeEpVisible = activeEp && visibleEndpointList.some(ep => ep.id === activeEp.id);

    return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div
                ref={canvasRef}
                className="topo-canvas"
                style={{ flex: 1, position: 'relative', overflow: 'hidden' }}
            >
                <div ref={viewportRef} className="topo-tiered-board">
                    {visibleDevices.map(renderDeviceTopology)}
                    {visibleDevices.length === 0 && <div className="empty-state">{t('dashboard.no_endpoints')}</div>}
                </div>

                <div className="topo-zoom-bar">
                    <button className="topo-zoom-btn" onClick={() => changeScale(0.8)} title="−">−</button>
                    <div className="topo-zoom-val">{Math.round(transform.scale * 100)}%</div>
                    <button className="topo-zoom-btn" onClick={() => changeScale(1.25)} title="+">+</button>
                    <button className="topo-zoom-reset" onClick={resetZoom}>{t('dashboard.topo_reset')}</button>
                </div>

                {activeEpVisible && (
                    <EndpointDetail
                        ep={activeEp}
                        dev={activeDev}
                        onClose={() => setActiveEp(null)}
                    />
                )}
            </div>
            <div className="topo-legend">
                <div className="tl-item"><div className="tl-line conn" /><span>{t('dashboard.topo_video_conn')}</span></div>
                <div className="tl-item"><div className="tl-line disc" /><span>{t('dashboard.topo_video_disc')}</span></div>
                <div className="tl-item" style={{ marginLeft: '6px' }}>
                    <div className="tl-dot" style={{ background: 'var(--green)', boxShadow: '0 0 4px var(--green)' }} />
                    <span>{t('dashboard.legend_online')}</span>
                </div>
                <div className="tl-item"><div className="tl-dot" style={{ background: 'var(--cyan)' }} /><span>{t('dashboard.legend_ready')}</span></div>
                <div className="tl-item"><div className="tl-dot" style={{ background: 'var(--red)' }} /><span>{t('dashboard.legend_offline')}</span></div>
                <div className="tl-item"><div className="tl-dot" style={{ background: 'var(--amber)' }} /><span>{t('dashboard.legend_warning')}</span></div>
                <span style={{ marginLeft: 'auto', fontSize: '9px', color: 'var(--text-dim)' }}>
                    {t('dashboard.topo_zoom_hint')}
                </span>
            </div>
        </div>
    );
};

export default TopoView;
