import React, { useState, useEffect, useCallback } from 'react';
import api from '../../utils/api';

function AlertsTab({ t, showToast }) {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [devices, setDevices] = useState([]);
    const [filterDevice, setFilterDevice] = useState('');
    const [filterSeverity, setFilterSeverity] = useState('');
    const [filterResolved, setFilterResolved] = useState('false'); // 'false' = pending only

    // Fetch devices for filter dropdown
    useEffect(() => {
        api.get('/devices').then(r => setDevices(r.data || [])).catch(() => { });
    }, []);

    // Fetch alerts
    const fetchAlerts = useCallback(async () => {
        try {
            setLoading(true);
            const params = new URLSearchParams();
            if (filterDevice) params.set('device_id', filterDevice);
            if (filterSeverity) params.set('severity', filterSeverity);
            if (filterResolved !== '') params.set('is_resolved', filterResolved);
            params.set('limit', '200');
            const res = await api.get(`/alerts?${params.toString()}`);
            setAlerts(res.data || []);
        } catch (err) {
            showToast(t('admin.common.error'), 'error');
        } finally {
            setLoading(false);
        }
    }, [showToast, t, filterDevice, filterSeverity, filterResolved]);

    useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

    // Resolve single alert
    const resolveAlert = async (id) => {
        try {
            await api.patch(`/alerts/${id}/resolve`);
            showToast(t('admin.common.success'));
            fetchAlerts();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Resolve all — 二次点击确认（避免 window.confirm 被拦截）
    const [confirmingAll, setConfirmingAll] = useState(false);
    const resolveAll = async () => {
        if (!confirmingAll) {
            setConfirmingAll(true);
            setTimeout(() => setConfirmingAll(false), 3000); // 3秒内不点击则取消确认态
            return;
        }
        setConfirmingAll(false);
        try {
            const params = filterDevice ? `?device_id=${filterDevice}` : '';
            await api.post(`/alerts/resolve-all${params}`);
            showToast(t('admin.common.success'));
            fetchAlerts();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };


    // Export CSV
    const exportCSV = () => {
        const params = new URLSearchParams();
        if (filterDevice) params.set('device_id', filterDevice);
        if (filterSeverity) params.set('severity', filterSeverity);
        // Open in new tab to trigger download
        const token = document.cookie || '';
        const url = `/api/v1/alerts/export?${params.toString()}`;
        // Use fetch with auth header for download
        api.get(`/alerts/export?${params.toString()}`, { responseType: 'blob' })
            .then(res => {
                const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = `alerts_${new Date().toISOString().slice(0, 10)}.csv`;
                link.click();
                URL.revokeObjectURL(link.href);
            })
            .catch(() => showToast(t('admin.common.error'), 'error'));
    };

    // Format time
    const fmtTime = (iso) => {
        if (!iso) return '—';
        const d = new Date(iso);
        return d.toLocaleString('zh-CN', { hour12: false });
    };

    // Severity badge
    const severityBadge = (sev) => {
        const clsMap = { info: 'info', warning: 'warning', critical: 'critical' };
        const labelMap = {
            info: t('admin.alerts.info'),
            warning: t('admin.alerts.warning'),
            critical: t('admin.alerts.critical'),
        };
        return <span className={`status-badge ${clsMap[sev] || 'info'}`}>{labelMap[sev] || sev}</span>;
    };

    if (loading) return <div className="admin-empty">{t('admin.common.loading')}</div>;

    return (
        <>
            <div className="admin-toolbar">
                <div className="admin-toolbar-left">
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                        {t('admin.tabs.alerts')} ({alerts.length})
                    </span>
                    <select className="admin-select" value={filterDevice} onChange={(e) => setFilterDevice(e.target.value)}>
                        <option value="">{t('admin.alerts.filter_device')}</option>
                        {devices.map(d => <option key={d.id} value={d.id}>{d.name} ({d.id})</option>)}
                    </select>
                    <select className="admin-select" value={filterSeverity} onChange={(e) => setFilterSeverity(e.target.value)}>
                        <option value="">{t('admin.alerts.filter_severity')}</option>
                        <option value="info">{t('admin.alerts.info')}</option>
                        <option value="warning">{t('admin.alerts.warning')}</option>
                        <option value="critical">{t('admin.alerts.critical')}</option>
                    </select>
                    <select className="admin-select" value={filterResolved} onChange={(e) => setFilterResolved(e.target.value)}>
                        <option value="">{t('admin.alerts.all')}</option>
                        <option value="false">{t('admin.alerts.pending')}</option>
                        <option value="true">{t('admin.alerts.resolved')}</option>
                    </select>
                </div>
                <div className="admin-toolbar-right">
                    <button className={`admin-btn ${confirmingAll ? 'danger' : 'warning'}`} onClick={resolveAll}>
                        {confirmingAll ? '⚠ ' + t('admin.common.confirm') + '?' : '✓ ' + t('admin.alerts.resolve_all')}
                    </button>
                    <button className="admin-btn" onClick={exportCSV}>
                        ↓ {t('admin.alerts.export_csv')}
                    </button>
                </div>
            </div>

            {alerts.length === 0 ? (
                <div className="admin-empty">
                    <div className="empty-icon">🔔</div>
                    {t('admin.common.no_data')}
                </div>
            ) : (
                <div className="admin-table-wrap">
                    <table className="admin-table">
                        <thead>
                            <tr>
                                <th>{t('admin.alerts.time')}</th>
                                <th>{t('admin.alerts.device')}</th>
                                <th>{t('admin.alerts.endpoint')}</th>
                                <th>{t('admin.alerts.oid')}</th>
                                <th>{t('admin.alerts.severity')}</th>
                                <th>{t('admin.alerts.message')}</th>
                                <th>{t('admin.alerts.status')}</th>
                                <th>{t('admin.alerts.actions')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {alerts.map((a) => (
                                <tr key={a.id}>
                                    <td style={{ whiteSpace: 'nowrap', fontSize: 11 }}>{fmtTime(a.created_at)}</td>
                                    <td>{a.device_id}</td>
                                    <td>{a.endpoint_id || '—'}</td>
                                    <td>{a.oid_name || '—'}</td>
                                    <td>{severityBadge(a.severity)}</td>
                                    <td style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {a.message}
                                    </td>
                                    <td>
                                        <span className={`status-badge ${a.is_resolved ? 'resolved' : 'pending'}`}>
                                            {a.is_resolved ? t('admin.alerts.resolved') : t('admin.alerts.pending')}
                                        </span>
                                    </td>
                                    <td>
                                        {!a.is_resolved && (
                                            <button className="action-btn success" onClick={() => resolveAlert(a.id)}>
                                                {t('admin.alerts.resolve')}
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </>
    );
}

export default AlertsTab;
