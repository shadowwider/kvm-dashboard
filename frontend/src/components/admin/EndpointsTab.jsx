import React, { useState, useEffect, useCallback } from 'react';
import api from '../../utils/api';

const STATUS_LABEL = { online: '在线', ready: '就绪', offline: '离线' };
const STATUS_COLOR = { online: '#00ff88', ready: '#00d4ff', offline: '#ff3355' };

function getDeviceStatus(ep) {
    const st = ep.last_status || {};
    return (ep.module_type === 'con' ? st.con_device_status : st.ep_device_status) || 'offline';
}

function EndpointsTab({ showToast }) {
    const [devices, setDevices] = useState([]);
    const [endpoints, setEndpoints] = useState([]);
    const [filterDevice, setFilterDevice] = useState('all');
    const [filterStatus, setFilterStatus] = useState('all');
    const [filterType, setFilterType] = useState('all');
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(new Set());

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [devRes, epRes] = await Promise.all([
                api.get('/devices'),
                api.get('/endpoints'),
            ]);
            setDevices(devRes.data || []);
            setEndpoints(epRes.data || []);
        } catch (err) {
            showToast('加载失败: ' + (err.response?.data?.detail || err.message), 'error');
        } finally {
            setLoading(false);
        }
    }, [showToast]);

    useEffect(() => { fetchData(); }, [fetchData]);

    // ── 过滤 ─────────────────────────────────────────────────────
    const filtered = endpoints.filter(ep => {
        if (filterDevice !== 'all' && ep.device_id !== filterDevice) return false;
        if (filterType !== 'all' && ep.module_type !== filterType) return false;
        if (filterStatus !== 'all' && getDeviceStatus(ep) !== filterStatus) return false;
        return true;
    });

    const offlineCount = filtered.filter(ep => getDeviceStatus(ep) === 'offline').length;

    // ── 全选 ─────────────────────────────────────────────────────
    const allIds = filtered.map(ep => ep.id);
    const allChecked = allIds.length > 0 && allIds.every(id => selected.has(id));
    const toggleAll = () => {
        if (allChecked) {
            setSelected(prev => { const n = new Set(prev); allIds.forEach(id => n.delete(id)); return n; });
        } else {
            setSelected(prev => new Set([...prev, ...allIds]));
        }
    };
    const toggleOne = (id) => {
        setSelected(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
    };

    // ── 删除 ─────────────────────────────────────────────────────
    const deleteOne = async (ep) => {
        if (!window.confirm(`删除终端 "${ep.name || ep.id}" (${ep.module_type.toUpperCase()})？`)) return;
        try {
            await api.delete(`/endpoints/${ep.id}`);
            showToast('终端已删除');
            setSelected(prev => { const n = new Set(prev); n.delete(ep.id); return n; });
            fetchData();
        } catch (err) {
            showToast(err.response?.data?.detail || '删除失败', 'error');
        }
    };

    const deleteBatch = async () => {
        if (selected.size === 0) return;
        if (!window.confirm(`批量删除已选 ${selected.size} 个终端？此操作不可撤销。`)) return;
        let ok = 0, fail = 0;
        for (const id of selected) {
            try { await api.delete(`/endpoints/${id}`); ok++; }
            catch { fail++; }
        }
        showToast(`已删除 ${ok} 个${fail ? `，失败 ${fail} 个` : ''}`, fail ? 'error' : 'success');
        setSelected(new Set());
        fetchData();
    };

    const deleteOfflineFiltered = async () => {
        const offlineIds = filtered
            .filter(ep => getDeviceStatus(ep) === 'offline')
            .map(ep => ep.id);
        if (offlineIds.length === 0) { showToast('当前过滤结果中无离线终端', 'error'); return; }
        if (!window.confirm(`删除当前过滤结果中所有 ${offlineIds.length} 个离线终端？`)) return;
        let ok = 0, fail = 0;
        for (const id of offlineIds) {
            try { await api.delete(`/endpoints/${id}`); ok++; }
            catch { fail++; }
        }
        showToast(`已删除 ${ok} 个离线终端${fail ? `，失败 ${fail} 个` : ''}`, fail ? 'error' : 'success');
        setSelected(new Set());
        fetchData();
    };

    // ── 设备名映射 ────────────────────────────────────────────────
    const deviceMap = Object.fromEntries(devices.map(d => [d.id, d.name]));

    if (loading) return <div className="admin-empty">加载中…</div>;

    return (
        <>
            {/* Toolbar */}
            <div className="admin-toolbar">
                <div className="admin-toolbar-left" style={{ gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                        终端管理 ({filtered.length} / {endpoints.length})
                    </span>
                    {offlineCount > 0 && (
                        <span style={{ color: '#ff3355', fontSize: 12 }}>
                            离线 {offlineCount} 个
                        </span>
                    )}

                    {/* 过滤：交换机 */}
                    <select
                        className="admin-select"
                        value={filterDevice}
                        onChange={e => setFilterDevice(e.target.value)}
                    >
                        <option value="all">全部交换机</option>
                        {devices.map(d => (
                            <option key={d.id} value={d.id}>{d.name}</option>
                        ))}
                    </select>

                    {/* 过滤：类型 */}
                    <select
                        className="admin-select"
                        value={filterType}
                        onChange={e => setFilterType(e.target.value)}
                    >
                        <option value="all">CPU + CON</option>
                        <option value="cpu">仅 CPU</option>
                        <option value="con">仅 CON</option>
                    </select>

                    {/* 过滤：状态 */}
                    <select
                        className="admin-select"
                        value={filterStatus}
                        onChange={e => setFilterStatus(e.target.value)}
                    >
                        <option value="all">全部状态</option>
                        <option value="online">在线</option>
                        <option value="ready">就绪</option>
                        <option value="offline">离线</option>
                    </select>
                </div>

                <div className="admin-toolbar-right" style={{ gap: 8 }}>
                    {selected.size > 0 && (
                        <button className="admin-btn danger" onClick={deleteBatch}>
                            删除已选 ({selected.size})
                        </button>
                    )}
                    <button
                        className="admin-btn danger"
                        onClick={deleteOfflineFiltered}
                        disabled={offlineCount === 0}
                        title="删除当前过滤结果中所有离线终端"
                    >
                        清除离线 ({offlineCount})
                    </button>
                </div>
            </div>

            {/* Table */}
            <div className="admin-table-wrap">
                <table className="admin-table">
                    <thead>
                        <tr>
                            <th style={{ width: 36 }}>
                                <input type="checkbox" checked={allChecked} onChange={toggleAll} />
                            </th>
                            <th>类型</th>
                            <th>终端名称</th>
                            <th>所属交换机</th>
                            <th>Row#</th>
                            <th>状态</th>
                            <th>最近更新</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.length === 0 ? (
                            <tr>
                                <td colSpan={8} style={{ textAlign: 'center', color: '#3d5a7a', padding: '24px 0' }}>
                                    无匹配终端
                                </td>
                            </tr>
                        ) : filtered.map(ep => {
                            const status = getDeviceStatus(ep);
                            const isOffline = status === 'offline';
                            return (
                                <tr
                                    key={ep.id}
                                    style={{ opacity: isOffline ? 0.65 : 1 }}
                                >
                                    <td>
                                        <input
                                            type="checkbox"
                                            checked={selected.has(ep.id)}
                                            onChange={() => toggleOne(ep.id)}
                                        />
                                    </td>
                                    <td>
                                        <span style={{
                                            padding: '1px 7px',
                                            fontSize: 10,
                                            letterSpacing: 1,
                                            textTransform: 'uppercase',
                                            border: `1px solid ${ep.module_type === 'cpu' ? 'rgba(0,212,255,.4)' : 'rgba(0,255,136,.3)'}`,
                                            color: ep.module_type === 'cpu' ? '#00d4ff' : '#00ff88',
                                            background: ep.module_type === 'cpu' ? 'rgba(0,212,255,.08)' : 'rgba(0,255,136,.07)',
                                        }}>
                                            {ep.module_type}
                                        </span>
                                    </td>
                                    <td style={{ fontWeight: 600 }}>{ep.name || ep.id}</td>
                                    <td style={{ color: '#8ba8c8' }}>{deviceMap[ep.device_id] || ep.device_id}</td>
                                    <td style={{ color: '#3d5a7a' }}>#{ep.index}</td>
                                    <td>
                                        <span style={{
                                            display: 'inline-flex', alignItems: 'center', gap: 5,
                                        }}>
                                            <span style={{
                                                width: 7, height: 7, borderRadius: '50%',
                                                background: STATUS_COLOR[status] || '#3d5a7a',
                                                flexShrink: 0,
                                            }} />
                                            {STATUS_LABEL[status] || status}
                                        </span>
                                    </td>
                                    <td style={{ color: '#3d5a7a', fontSize: 11 }}>
                                        {ep.updated_at
                                            ? new Date(ep.updated_at).toLocaleString('zh-CN', { hour12: false })
                                            : '—'}
                                    </td>
                                    <td>
                                        <button
                                            className="action-btn danger"
                                            onClick={() => deleteOne(ep)}
                                        >
                                            删除
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </>
    );
}

export default EndpointsTab;
