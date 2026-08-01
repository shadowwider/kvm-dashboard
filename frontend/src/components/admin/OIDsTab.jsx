import React, { useState, useEffect, useCallback } from 'react';
import api from '../../utils/api';

function OIDsTab({ t, showToast }) {
    const [oids, setOids] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState(''); // '' | 'device' | 'endpoint'

    // Fetch (only show loading spinner on first load)
    const fetchOids = useCallback(async (showSpinner = true) => {
        try {
            if (showSpinner) setLoading(true);
            const params = filter ? `?category=${filter}` : '';
            const res = await api.get(`/oids${params}`);
            setOids(res.data || []);
        } catch {
            showToast(t('admin.common.error'), 'error');
        } finally {
            setLoading(false);
        }
    }, [showToast, t, filter]);

    useEffect(() => { fetchOids(true); }, [fetchOids]);

    // Optimistic toggle: update UI immediately, then PATCH in background
    const handleToggle = async (oid, field) => {
        // Optimistic update: flip the value in local state immediately
        setOids(prev => prev.map(o =>
            o.id === oid.id ? { ...o, [field]: !o[field] } : o
        ));

        try {
            await api.patch(`/oids/${oid.id}`, { [field]: !oid[field] });
            // Don't refetch — the optimistic state is already correct
        } catch (err) {
            // Revert on error
            setOids(prev => prev.map(o =>
                o.id === oid.id ? { ...o, [field]: oid[field] } : o
            ));
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    if (loading) return <div className="admin-empty">{t('admin.common.loading')}</div>;

    return (
        <>
            <div className="admin-toolbar">
                <div className="admin-toolbar-left">
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                        {t('admin.tabs.oids')} ({oids.length})
                    </span>
                    <select
                        className="admin-select"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                    >
                        <option value="">{t('admin.alerts.all')}</option>
                        <option value="device">{t('admin.oids.device')}</option>
                        <option value="endpoint">{t('admin.oids.endpoint')}</option>
                    </select>
                </div>
            </div>

            <div className="admin-table-wrap oid-table-wrap">
                <table className="admin-table oid-table">
                    <thead>
                        <tr>
                            <th>{t('admin.oids.name')}</th>
                            <th>{t('admin.oids.display_name')}</th>
                            <th>{t('admin.oids.category')}</th>
                            <th style={{ textAlign: 'center' }}>{t('admin.oids.poll_enabled')}</th>
                            <th style={{ textAlign: 'center' }}>{t('admin.oids.archive_enabled')}</th>
                            <th style={{ textAlign: 'center' }}>{t('admin.oids.alert_enabled')}</th>
                            <th style={{ textAlign: 'center' }}>{t('admin.oids.display_enabled')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {oids.map((o) => (
                            <tr key={o.id}>
                                <td style={{ fontWeight: 600 }}>{o.name}</td>
                                <td>{o.display_name}</td>
                                <td>
                                    <span className={`status-badge ${o.category === 'device' ? 'info' : 'active'}`}>
                                        {o.category === 'device' ? t('admin.oids.device') : t('admin.oids.endpoint')}
                                    </span>
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                    <label className="toggle-switch">
                                        <input
                                            type="checkbox"
                                            checked={o.poll_enabled}
                                            onChange={() => handleToggle(o, 'poll_enabled')}
                                        />
                                        <span className="toggle-slider"></span>
                                    </label>
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                    <label className="toggle-switch">
                                        <input
                                            type="checkbox"
                                            checked={o.archive_enabled}
                                            onChange={() => handleToggle(o, 'archive_enabled')}
                                        />
                                        <span className="toggle-slider"></span>
                                    </label>
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                    <label className="toggle-switch">
                                        <input
                                            type="checkbox"
                                            checked={o.alert_enabled}
                                            onChange={() => handleToggle(o, 'alert_enabled')}
                                        />
                                        <span className="toggle-slider"></span>
                                    </label>
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                    <label className="toggle-switch">
                                        <input
                                            type="checkbox"
                                            checked={o.display_enabled}
                                            onChange={() => handleToggle(o, 'display_enabled')}
                                        />
                                        <span className="toggle-slider"></span>
                                    </label>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </>
    );
}

export default OIDsTab;
