import React, { useEffect, useState } from 'react';
import api from '../utils/api';

// ─── 温度趋势折线图（SVG）────────────────────────────────
const TempChart = ({ devices, selectedDeviceId }) => {
    const [series, setSeries] = useState([]);

    useEffect(() => {
        const targets = selectedDeviceId
            ? devices.filter(d => d.id === selectedDeviceId)
            : devices;

        const fetchAll = targets.map(dev =>
            api.get(`/metrics/history?oid_name=temperature&device_id=${dev.id}&hours=24`)
                .then(r => ({ label: dev.name || dev.id, data: r.data || [] }))
                .catch(() => ({ label: dev.name || dev.id, data: [] }))
        );

        Promise.all(fetchAll).then(results => {
            const colors = ['#00d4ff', '#00ff88', '#ffb300', '#ff3355'];
            setSeries(results.map((r, i) => ({ ...r, color: colors[i % colors.length] })));
        });
    }, [selectedDeviceId, devices.length]);

    const W = 300, H = 72, minT = 28, maxT = 65;
    const ty = t => H - ((t - minT) / (maxT - minT)) * H;
    const mkLine = data => {
        if (!data || data.length < 2) return '';
        const n = data.length;
        return data.map((d, i) => {
            const x = (i / (n - 1)) * W;
            const y = ty(d.value_num ?? 0);
            return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(' ');
    };
    const mkArea = data => {
        const line = mkLine(data);
        return line ? `${line} L${W},${H} L0,${H} Z` : '';
    };

    return (
        <div className="chart-panel">
            <div className="chart-title">温度趋势<span>°C</span></div>
            <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
                <defs>
                    {series.map((s, i) => (
                        <linearGradient key={i} id={`tg${i}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={s.color} stopOpacity=".35" />
                            <stop offset="100%" stopColor={s.color} stopOpacity="0" />
                        </linearGradient>
                    ))}
                </defs>
                {[18, 36, 54].map(y => (
                    <line key={y} x1="0" y1={y} x2={W} y2={y} stroke="rgba(0,212,255,.05)" strokeWidth="1" />
                ))}
                <line x1="0" y1={ty(55)} x2={W} y2={ty(55)} stroke="rgba(255,51,85,.25)" strokeWidth="1" strokeDasharray="4,3" />
                <text x={W - 4} y={ty(55) - 2} fill="rgba(255,51,85,.6)" fontSize="6" textAnchor="end" fontFamily="JetBrains Mono">55°C</text>
                {series.map((s, i) => (
                    <React.Fragment key={i}>
                        <path d={mkArea(s.data)} fill={`url(#tg${i})`} />
                        <path d={mkLine(s.data)} fill="none" stroke={s.color}
                            strokeWidth={i === 0 ? '1.5' : '1'}
                            strokeDasharray={i === 0 ? 'none' : '3,2'}
                            opacity={i === 0 ? '1' : '.7'} />
                    </React.Fragment>
                ))}
            </svg>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                {series.map((s, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '8px', color: 'var(--text-dim)' }}>
                        <div style={{ width: '14px', height: i === 0 ? '1.5px' : '1px', background: s.color }} />
                        {s.label}
                    </div>
                ))}
            </div>
        </div>
    );
};

// ─── 风扇仪表盘（SVG 圆弧）──────────────────────────────
const FanGauges = ({ devices, selectedDeviceId }) => {
    const targetDev = selectedDeviceId
        ? devices.find(d => d.id === selectedDeviceId)
        : devices.find(d => d.last_status === 'online' || d.last_status === 'warning') || devices[0];

    const [fans, setFans] = useState(Array(6).fill(null));

    useEffect(() => {
        if (!targetDev) return;
        const fanNames = ['fan1', 'fan2', 'fan3', 'fan4', 'fan5', 'fan6'];
        Promise.allSettled(
            fanNames.map(f =>
                api.get(`/metrics/history?oid_name=${f}&device_id=${targetDev.id}&hours=1`)
                    .then(r => {
                        const d = r.data || [];
                        return d.length > 0 ? (d[d.length - 1].value_num ?? null) : null;
                    }).catch(() => null)
            )
        ).then(results => {
            setFans(results.map(r => r.status === 'fulfilled' ? r.value : null));
        });
    }, [targetDev?.id]);

    const toRad = d => d * Math.PI / 180;
    const arc = (cx, cy, r, start, end) => {
        const sx = cx + r * Math.cos(toRad(start));
        const sy = cy + r * Math.sin(toRad(start));
        const ex = cx + r * Math.cos(toRad(end));
        const ey = cy + r * Math.sin(toRad(end));
        const large = end - start > 180 ? 1 : 0;
        return `M${sx.toFixed(2)},${sy.toFixed(2)} A${r},${r} 0 ${large},1 ${ex.toFixed(2)},${ey.toFixed(2)}`;
    };

    return (
        <div className="chart-panel">
            <div className="chart-title">风扇转速<span>RPM</span></div>
            <div className="gauge-row">
                {fans.map((rpm, i) => {
                    if (rpm === null) return (
                        <div key={i} className="gauge-item">
                            <svg width="38" height="22" viewBox="0 0 38 22">
                                <path d={arc(19, 17, 15, -210, 30)} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" strokeLinecap="round" />
                            </svg>
                            <div className="gauge-val">—</div>
                            <div className="gauge-lbl">F{i + 1}</div>
                        </div>
                    );
                    const pct = rpm === 0 ? 0 : Math.min((rpm / 4500) * 100, 100);
                    const color = rpm === 0 ? '#ff3355' : pct > 80 ? '#ffb300' : '#00d4ff';
                    const ea = -210 + (pct / 100) * 240;
                    return (
                        <div key={i} className="gauge-item">
                            <svg width="38" height="22" viewBox="0 0 38 22">
                                <path d={arc(19, 17, 15, -210, 30)} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" strokeLinecap="round" />
                                <path d={arc(19, 17, 15, -210, ea <= -210 ? -209.5 : ea)} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
                                    style={{ filter: `drop-shadow(0 0 3px ${color})` }} />
                            </svg>
                            <div className="gauge-val">{rpm === 0 ? '--' : rpm}</div>
                            <div className="gauge-lbl">F{i + 1}</div>
                        </div>
                    );
                })}
                {fans.every(f => f === null) && (
                    <div style={{ color: 'var(--text-dim)', fontSize: '9px', margin: 'auto', letterSpacing: '1px' }}>
                        暂无风扇数据
                    </div>
                )}
            </div>
        </div>
    );
};

// ─── 24H 在线率 ──────────────────────────────────────────
const OnlineRate = ({ devices, endpoints }) => {
    const [bars, setBars] = useState([]);

    useEffect(() => {
        api.get('/metrics/history?oid_name=ep_device_status&hours=24')
            .then(r => {
                const data = r.data || [];
                if (data.length > 0) {
                    setBars(data.slice(-24).map(d => Number(d.value_num ?? 98)));
                } else {
                    setBars(Array(24).fill(98));
                }
            })
            .catch(() => setBars(Array(24).fill(98)));
    }, []);

    // 用前端 endpoints 计算当前在线率（与健康率口径一致）
    let currentRate = '—';
    if (endpoints && endpoints.length > 0) {
        const onl = endpoints.filter(ep => {
            const devSt = (ep.last_status || {}).ep_device_status;
            return devSt === 'online' || devSt === 'ready';
        }).length;
        currentRate = `${((onl / endpoints.length) * 100).toFixed(1)}%`;
    } else if (devices.length > 0) {
        const onl = devices.filter(d => d.last_status === 'online').length;
        currentRate = `${((onl / devices.length) * 100).toFixed(0)}%`;
    }

    const validBars = bars.filter(v => !isNaN(v) && v !== null);
    const maxVal = validBars.length > 0 ? Math.max(...validBars) : 100;
    const minVal = 90;
    const range = maxVal > minVal ? maxVal - minVal : 1; // 防除零

    return (
        <div className="chart-panel">
            <div className="chart-title">24H 在线率<span>%</span></div>
            <div style={{ display: 'flex', flex: 1, flexDirection: 'column', gap: '4px' }}>
                <div style={{
                    fontFamily: "'Orbitron', monospace",
                    fontSize: '18px', fontWeight: '700',
                    color: 'var(--green)', textShadow: '0 0 10px var(--green)',
                }}>
                    {currentRate}
                </div>
                <div className="rate-bars">
                    {(validBars.length > 0 ? validBars : Array(24).fill(98)).map((v, i) => {
                        const safeV = isNaN(v) ? 98 : v;
                        const h = Math.max(((safeV - minVal) / range) * 100, 2);
                        const isLast = i === (validBars.length > 0 ? validBars : Array(24)).length - 1;
                        return (
                            <div
                                key={i}
                                className={`rate-bar${isLast ? ' last' : ''}`}
                                style={{ height: `${h}%` }}
                            />
                        );
                    })}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '8px', color: 'var(--text-dim)' }}>
                    <span>00:00</span>
                    <span>06:00</span>
                    <span>12:00</span>
                    <span>18:00</span>
                    <span>现在</span>
                </div>
            </div>
        </div>
    );
};

// ─── 主组件（输出三个面板） ──────────────────────────────
const BottomCharts = ({ devices, selectedDeviceId, endpoints }) => (
    <>
        <TempChart devices={devices} selectedDeviceId={selectedDeviceId} />
        <FanGauges devices={devices} selectedDeviceId={selectedDeviceId} />
        <OnlineRate devices={devices} endpoints={endpoints || []} />
    </>
);

export default BottomCharts;
