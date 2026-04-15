import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useStore } from '../store/mainStore';
import { useTranslation } from '../i18n';
import api from '../utils/api';
import EndpointDetail from './EndpointDetail';

const VIDEO_LABEL = {
    none: 'No Signal', vga: 'VGA', dvisl: 'DVI-SL', dvidl: 'DVI-DL',
    dmdp: 'MDP', dp: 'DP', hdmi: 'HDMI',
};
const STATUS_COLOR = { online: '#00ff88', ready: '#00d4ff', offline: '#ff3355', warning: '#ffb300' };

function mkSVG(tag, attrs = {}) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    return el;
}

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

function ensureGlowDefs(svgEl) {
    if (svgEl.querySelector('#glow-topo')) return;
    const defs = mkSVG('defs');
    const filt = mkSVG('filter', { id: 'glow-topo', x: '-50%', y: '-50%', width: '200%', height: '200%' });
    const feG = mkSVG('feGaussianBlur', { stdDeviation: '2.5', result: 'b' });
    const feM = mkSVG('feMerge');
    [mkSVG('feMergeNode', { in: 'b' }), mkSVG('feMergeNode', { in: 'SourceGraphic' })]
        .forEach(e => feM.appendChild(e));
    filt.appendChild(feG); filt.appendChild(feM);
    defs.appendChild(filt);
    svgEl.appendChild(defs);
}

// ─── 全局总览（所有设备 + Root 节点）─────────────────
function renderAllDevices(container, svgEl, nodesWrap, devices, endpoints, onDeviceClick, getAlias, labels) {
    svgEl.innerHTML = '';
    nodesWrap.innerHTML = '';
    ensureGlowDefs(svgEl);

    const W = container.clientWidth || 700;
    const H = container.clientHeight || 360;
    const rootX = W / 2;
    const rootY = 64;

    const cols = Math.min(5, Math.max(1, devices.length));
    const rows = Math.ceil(devices.length / cols);
    const devAreaTop = rootY + 88;
    const devAreaH = H - devAreaTop - 10;
    const cw = W / cols;
    const ch = devAreaH / Math.max(rows, 1);

    const devPositions = devices.map((dev, i) => ({
        cx: cw * (i % cols) + cw / 2,
        cy: devAreaTop + ch * Math.floor(i / cols) + ch / 2,
    }));

    const rootBottom = rootY + 22;
    devPositions.forEach(({ cx, cy }) => {
        const endY = cy - 48;
        const midY = (rootBottom + endY) / 2;
        const d = `M${rootX.toFixed(1)},${rootBottom.toFixed(1)} C${rootX.toFixed(1)},${midY.toFixed(1)} ${cx.toFixed(1)},${midY.toFixed(1)} ${cx.toFixed(1)},${endY.toFixed(1)}`;
        const path = mkSVG('path', {
            d, fill: 'none', stroke: 'rgba(0,212,255,0.4)',
            'stroke-width': '1.5', 'stroke-dasharray': '6,3', filter: 'url(#glow-topo)',
        });
        svgEl.appendChild(path);
    });

    // Root 节点
    const rootNode = document.createElement('div');
    rootNode.className = 'topo-node';
    rootNode.style.cssText = `position:absolute;transform:translate(-50%,-50%);left:${rootX}px;top:${rootY}px;z-index:20;`;
    rootNode.innerHTML = `
      <div style="
        width:120px;height:42px;border-radius:4px;
        background:var(--bg-card);border:2px solid var(--cyan);
        display:flex;align-items:center;justify-content:center;gap:8px;
        box-shadow:0 0 24px rgba(0,212,255,.2),0 0 50px rgba(0,212,255,.05);
        position:relative;
      ">
        <div style="position:absolute;inset:-4px;border:1px solid rgba(0,212,255,.12);border-radius:7px;animation:tcpulse 2.5s ease-in-out infinite;pointer-events:none;"></div>
        <div style="font-size:16px">🌐</div>
        <div>
          <div style="font-family:'Orbitron',monospace;font-size:8px;letter-spacing:2px;color:var(--cyan);">${labels.network}</div>
          <div style="font-size:7px;color:var(--text-dim);letter-spacing:1px;">CTRL-OPS</div>
        </div>
      </div>`;
    nodesWrap.appendChild(rootNode);

    // 各设备卡片
    devices.forEach((dev, i) => {
        const { cx, cy } = devPositions[i];
        const st = dev.last_status || 'offline';
        const bc = STATUS_COLOR[st] || STATUS_COLOR.offline;
        const glow = st === 'online' ? 'rgba(0,255,136,.18)' : st === 'warning' ? 'rgba(255,179,0,.18)' : 'rgba(255,51,85,.18)';
        const epList = endpoints.filter(e => e.device_id === dev.id);
        const onl = epList.filter(e => ['online', 'ready'].includes(getEpStatus(e))).length;
        const devName = getAlias(dev.id, dev.name);

        const node = document.createElement('div');
        node.className = 'topo-node';
        node.style.cssText = `position:absolute;transform:translate(-50%,-50%);left:${cx}px;top:${cy}px;cursor:pointer;`;
        node.innerHTML = `
          <div style="
            width:108px;height:86px;border-radius:4px;
            background:var(--bg-card);border:2px solid ${bc};
            box-shadow:0 0 16px ${glow};
            display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;
            transition:all .2s;
          ">
            <div style="font-size:18px">🖥️</div>
            <div style="font-family:'Rajdhani',sans-serif;font-size:9px;font-weight:700;color:var(--text-bright);text-align:center;line-height:1.2;padding:0 4px;">${devName}</div>
            <div style="font-size:7px;color:var(--text-dim);">${dev.host || ''}</div>
            <div style="font-size:8px;color:var(--text-dim);">
              ${labels.epCount} <span style="color:var(--green)">${onl}</span>/<span style="color:var(--text-main)">${epList.length || '?'}</span>
            </div>
            <div style="width:6px;height:6px;border-radius:50%;background:${bc};box-shadow:0 0 5px ${bc};"></div>
          </div>`;
        const inner = node.querySelector('div');
        inner.addEventListener('click', () => onDeviceClick(dev));
        node.addEventListener('mouseover', () => { inner.style.filter = 'brightness(1.2)'; node.style.transform = 'translate(-50%,-50%) scale(1.06)'; });
        node.addEventListener('mouseout', () => { inner.style.filter = ''; node.style.transform = 'translate(-50%,-50%)'; });
        nodesWrap.appendChild(node);
    });
}

// ─── 单设备拓扑（粒子流光）───────────────────────────
function renderSingleDevice(container, svgEl, nodesWrap, dev, eps, onEpClick, getAlias, labels) {
    svgEl.innerHTML = '';
    nodesWrap.innerHTML = '';
    ensureGlowDefs(svgEl);

    const W = container.clientWidth || 700;
    const H = container.clientHeight || 360;
    const cx = W / 2;
    const cy = H / 2;
    const n = eps.length;
    const R = Math.min(W, H) * 0.36;

    const edges = [];
    eps.forEach((ep, i) => {
        const angle = (i / Math.max(n, 1)) * 2 * Math.PI - Math.PI / 2;
        const ex = cx + R * Math.cos(angle);
        const ey = cy + R * Math.sin(angle);
        const st = getEpStatus(ep);
        const connected = st !== 'offline';
        const color = STATUS_COLOR[st] || STATUS_COLOR.offline;

        const mx = (cx + ex) / 2, my = (cy + ey) / 2;
        const dx = ex - cx, dy = ey - cy;
        const bx = mx - dy * 0.14, by = my + dx * 0.14;
        const d = `M${cx.toFixed(1)},${cy.toFixed(1)} Q${bx.toFixed(1)},${by.toFixed(1)} ${ex.toFixed(1)},${ey.toFixed(1)}`;

        const path = mkSVG('path', {
            d, fill: 'none', stroke: color,
            'stroke-width': connected ? '1.6' : '1',
            'stroke-dasharray': connected ? 'none' : '5,4',
            opacity: connected ? '0.55' : '0.25',
            filter: 'url(#glow-topo)',
        });
        svgEl.appendChild(path);

        const rstSt = ep.last_status || {};
        const videoLost = ep.module_type === 'con'
            ? rstSt.con_display_conn !== 'connected'
            : (rstSt.ep_target_video_cable === 'notConnected' || rstSt.ep_target_video_cable === 'disconnected');
        if (videoLost) {
            const txt = mkSVG('text', {
                x: bx.toFixed(1), y: by.toFixed(1),
                fill: '#ff3355', 'font-size': '7', 'font-family': 'JetBrains Mono',
                'text-anchor': 'middle', opacity: '0.9', filter: 'url(#glow-topo)',
            });
            txt.textContent = 'VIDEO LOST';
            svgEl.appendChild(txt);
        }

        if (connected) edges.push({ path, progress: Math.random(), speed: 0.003 + Math.random() * 0.003, color });
    });

    // 粒子动画循环
    let animId = null;
    let running = true;
    function anim() {
        svgEl.querySelectorAll('.tp').forEach(p => p.remove());
        edges.forEach(e => {
            e.progress = (e.progress + e.speed) % 1;
            try {
                const len = e.path.getTotalLength();
                const pt = e.path.getPointAtLength(e.progress * len);
                const c = mkSVG('circle', {
                    cx: pt.x.toFixed(2), cy: pt.y.toFixed(2),
                    r: '2.5', fill: e.color, opacity: '0.9', filter: 'url(#glow-topo)',
                });
                c.classList.add('tp');
                svgEl.appendChild(c);
            } catch (_) { }
        });
        if (running) animId = requestAnimationFrame(anim);
    }
    if (edges.length) anim();

    if (!document.getElementById('topo-keyframes')) {
        const s = document.createElement('style');
        s.id = 'topo-keyframes';
        s.textContent = `@keyframes tcpulse{0%,100%{opacity:.2;transform:scale(1)}50%{opacity:.7;transform:scale(1.03)}}@keyframes deadp{0%,100%{opacity:.4}50%{opacity:.9}}`;
        document.head.appendChild(s);
    }

    // 中心 KVM 节点 — 用别名
    const devName = getAlias(dev.id, dev.name);
    const cnode = document.createElement('div');
    cnode.className = 'topo-node';
    cnode.style.cssText = `position:absolute;transform:translate(-50%,-50%);left:${cx}px;top:${cy}px;z-index:10;`;
    cnode.innerHTML = `
      <div style="
        width:84px;height:78px;border-radius:4px;border:2px solid var(--cyan);
        background:var(--bg-card);
        display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;
        box-shadow:0 0 20px rgba(0,212,255,.2),0 0 40px rgba(0,212,255,.05);position:relative;
      ">
        <div style="position:absolute;inset:-5px;border:1px solid rgba(0,212,255,.15);border-radius:7px;animation:tcpulse 2.5s ease-in-out infinite;pointer-events:none;"></div>
        <div style="font-size:20px">🖥️</div>
        <div style="font-family:'Rajdhani',sans-serif;font-size:9px;font-weight:700;color:var(--cyan);letter-spacing:1px;text-align:center;line-height:1.2;padding:0 4px;">${devName}</div>
        <div style="font-size:7px;color:var(--text-dim);text-align:center;">${dev.host || ''}</div>
      </div>`;
    nodesWrap.appendChild(cnode);

    // 终端节点 — 用别名
    eps.forEach((ep, i) => {
        const angle = (i / Math.max(n, 1)) * 2 * Math.PI - Math.PI / 2;
        const ex = cx + R * Math.cos(angle);
        const ey = cy + R * Math.sin(angle);
        const st = getEpStatus(ep);
        const stRaw = ep.last_status || {};
        const video = ep.module_type === 'con'
            ? (stRaw.con_display_conn === 'connected' ? 'DISP-ON' : 'NO DISP')
            : (VIDEO_LABEL[stRaw.ep_target_video_signal] || '—');
        const bColor = STATUS_COLOR[st] || STATUS_COLOR.offline;
        const epName = getAlias(ep.id, ep.name);
        // 取末段作为短名
        const shortName = epName.length > 10 ? epName.split('_').pop() : epName;

        const node = document.createElement('div');
        node.className = 'topo-node';
        node.style.cssText = `position:absolute;transform:translate(-50%,-50%);left:${ex}px;top:${ey}px;`;
        node.innerHTML = `
          <div style="
            width:60px;height:54px;border-radius:3px;border:1px solid ${bColor};
            background:var(--bg-card);
            display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;
            cursor:pointer;transition:all .2s;
            ${st === 'offline' ? 'animation:deadp 2s ease-in-out infinite' : ''};
          ">
            <div style="width:7px;height:7px;border-radius:50%;background:${bColor};box-shadow:0 0 5px ${bColor};"></div>
            <div style="font-family:'Rajdhani',sans-serif;font-size:9px;font-weight:600;color:var(--text-bright);text-align:center;line-height:1;padding:0 2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:54px;">${shortName}</div>
            <div style="font-size:7px;color:var(--text-dim);text-align:center;max-width:52px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${epName}</div>
            <div style="font-size:7px;letter-spacing:1px;color:${bColor}">${video}</div>
          </div>`;
        node.querySelector('div').addEventListener('click', e => { e.stopPropagation(); onEpClick(ep, dev); });
        nodesWrap.appendChild(node);
    });

    return () => { running = false; if (animId) cancelAnimationFrame(animId); };
}



// ─── 主组件────────────────────────────────────────────
const SCALE_MIN = 0.3, SCALE_MAX = 3.0;

const TopoView = ({ filterDeviceId, devices }) => {
    const { endpoints, fetchTopology, getDisplayName } = useStore();
    const { t } = useTranslation();
    const canvasRef = useRef(null);
    const svgRef = useRef(null);
    const nodesWrapRef = useRef(null);
    const cleanupRef = useRef(null);

    const [activeEp, setActiveEp] = useState(null);
    const [activeDev, setActiveDev] = useState(null);

    const [transform, setTransform] = useState({ scale: 1, tx: 0, ty: 0 });
    const dragRef = useRef(null);
    const transRef = useRef(transform);
    transRef.current = transform;

    const applyTransform = useCallback((t) => {
        if (!nodesWrapRef.current || !svgRef.current) return;
        const css = `translate(${t.tx}px,${t.ty}px) scale(${t.scale})`;
        nodesWrapRef.current.style.transform = css;
        svgRef.current.style.transform = css;
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
            const nt = { scale: ns, tx: prev.tx - mx * (ratio - 1), ty: prev.ty - my * (ratio - 1) };
            applyTransform(nt);
            return nt;
        });
    }, [applyTransform]);

    const onMouseDown = useCallback((e) => {
        if (e.button !== 0) return;
        dragRef.current = { startX: e.clientX, startY: e.clientY, startTx: transRef.current.tx, startTy: transRef.current.ty };
        canvasRef.current?.classList.add('dragging');
    }, []);

    const onMouseMove = useCallback((e) => {
        if (!dragRef.current) return;
        const dx = e.clientX - dragRef.current.startX;
        const dy = e.clientY - dragRef.current.startY;
        const nt = { ...transRef.current, tx: dragRef.current.startTx + dx, ty: dragRef.current.startTy + dy };
        transRef.current = nt;
        applyTransform(nt);
    }, [applyTransform]);

    const onMouseUp = useCallback(() => {
        if (!dragRef.current) return;
        dragRef.current = null;
        canvasRef.current?.classList.remove('dragging');
        setTransform({ ...transRef.current });
    }, []);

    useEffect(() => {
        const el = canvasRef.current;
        if (!el) return;
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
        const t = { scale: 1, tx: 0, ty: 0 };
        setTransform(t);
        applyTransform(t);
    }, [applyTransform]);

    const changeScale = useCallback((factor) => {
        setTransform(prev => {
            const ns = Math.min(SCALE_MAX, Math.max(SCALE_MIN, prev.scale * factor));
            const nt = { ...prev, scale: ns };
            applyTransform(nt);
            return nt;
        });
    }, [applyTransform]);

    const handleEpClick = useCallback((ep, dev) => { setActiveEp(ep); setActiveDev(dev); }, []);
    const handleDeviceClick = useCallback((dev) => { fetchTopology(dev.id); }, []);

    // 传给 render 函数的 i18n 标签
    const labels = {
        network: t('dashboard.topo_network'),
        epCount: t('dashboard.topo_ep_count'),
    };

    useEffect(() => {
        if (!canvasRef.current || !svgRef.current || !nodesWrapRef.current) return;
        if (cleanupRef.current) { cleanupRef.current(); cleanupRef.current = null; }
        setActiveEp(null);
        const t0 = { scale: 1, tx: 0, ty: 0 };
        setTransform(t0);
        applyTransform(t0);

        const container = canvasRef.current;
        const svgEl = svgRef.current;
        const nodesWrap = nodesWrapRef.current;

        if (filterDeviceId === 'all') {
            renderAllDevices(container, svgEl, nodesWrap, devices, endpoints, handleDeviceClick, getDisplayName, labels);
        } else {
            const dev = devices.find(d => d.id === filterDeviceId);
            if (!dev) return;
            const eps = endpoints.filter(e => e.device_id === filterDeviceId);
            const cleanup = renderSingleDevice(container, svgEl, nodesWrap, dev, eps, handleEpClick, getDisplayName, labels);
            cleanupRef.current = cleanup;
        }

        return () => { if (cleanupRef.current) cleanupRef.current(); };
    }, [filterDeviceId, devices, endpoints]);

    return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div
                ref={canvasRef}
                className="topo-canvas"
                style={{ flex: 1, position: 'relative', overflow: 'hidden' }}
            >
                <svg
                    ref={svgRef}
                    style={{
                        position: 'absolute', inset: 0,
                        width: '100%', height: '100%',
                        transformOrigin: '0 0',
                    }}
                />
                <div
                    ref={nodesWrapRef}
                    style={{
                        position: 'absolute', inset: 0,
                        transformOrigin: '0 0',
                    }}
                />

                <div className="topo-zoom-bar">
                    <button className="topo-zoom-btn" onClick={() => changeScale(0.8)} title="−">−</button>
                    <div className="topo-zoom-val">{Math.round(transform.scale * 100)}%</div>
                    <button className="topo-zoom-btn" onClick={() => changeScale(1.25)} title="+">+</button>
                    <button className="topo-zoom-reset" onClick={resetZoom}>{t('dashboard.topo_reset')}</button>
                </div>

                {activeEp && (
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
