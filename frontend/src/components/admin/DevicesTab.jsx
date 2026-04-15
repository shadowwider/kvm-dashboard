import React, { useState, useEffect, useCallback } from 'react';
import api from '../../utils/api';

function DevicesTab({ t, showToast }) {
    const [devices, setDevices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editDevice, setEditDevice] = useState(null); // null=新增, object=编辑
    const [form, setForm] = useState({
        id: '', name: '', host: '', port: 161,
        community: 'public', location: '', description: '', poll_interval: 60
    });

    // Fetch devices
    const fetchDevices = useCallback(async () => {
        try {
            setLoading(true);
            const res = await api.get('/devices');
            setDevices(res.data || []);
        } catch (err) {
            showToast(t('admin.common.error') + ': ' + (err.response?.data?.detail || err.message), 'error');
        } finally {
            setLoading(false);
        }
    }, [showToast, t]);

    useEffect(() => { fetchDevices(); }, [fetchDevices]);

    // Open modal
    const openAdd = () => {
        setEditDevice(null);
        setForm({ id: '', name: '', host: '', port: 161, community: 'public', location: '', description: '', poll_interval: 60 });
        setShowModal(true);
    };

    const openEdit = (device) => {
        setEditDevice(device);
        setForm({
            id: device.id,
            name: device.name,
            host: device.host,
            port: device.port,
            community: device.community,
            location: device.location || '',
            description: device.description || '',
            poll_interval: device.poll_interval,
        });
        setShowModal(true);
    };

    // Submit form
    const handleSubmit = async () => {
        if (!editDevice && !form.id.trim()) {
            showToast('设备 ID 不能为空', 'error');
            return;
        }
        if (!form.name.trim() || !form.host.trim()) {
            showToast('名称和 IP 不能为空', 'error');
            return;
        }
        try {
            if (editDevice) {
                const { id, ...body } = form;
                await api.patch(`/devices/${editDevice.id}`, body);
            } else {
                await api.post('/devices', form);
            }
            showToast(t('admin.common.success'));
            setShowModal(false);
            fetchDevices();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Delete
    const handleDelete = async (device) => {
        if (!window.confirm(`${t('admin.devices.confirm_delete')} "${device.name}" (${device.id})?`)) return;
        try {
            await api.delete(`/devices/${device.id}`);
            showToast(t('admin.common.success'));
            fetchDevices();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Toggle active
    const handleToggle = async (device) => {
        try {
            await api.patch(`/devices/${device.id}`, { is_active: !device.is_active });
            showToast(t('admin.common.success'));
            fetchDevices();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Manual poll
    const handlePoll = async (device) => {
        try {
            await api.post(`/devices/${device.id}/poll`);
            showToast(`${device.id} ${t('admin.devices.poll')}...`);
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    if (loading) return <div className="admin-empty">{t('admin.common.loading')}</div>;

    return (
        <>
            {/* Toolbar */}
            <div className="admin-toolbar">
                <div className="admin-toolbar-left">
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                        {t('admin.tabs.devices')} ({devices.length})
                    </span>
                </div>
                <div className="admin-toolbar-right">
                    <button className="admin-btn primary" onClick={openAdd}>
                        + {t('admin.devices.add')}
                    </button>
                </div>
            </div>

            {/* Table */}
            <div className="admin-table-wrap">
                <table className="admin-table">
                    <thead>
                        <tr>
                            <th>{t('admin.devices.id')}</th>
                            <th>{t('admin.devices.name')}</th>
                            <th>{t('admin.devices.host')}</th>
                            <th>{t('admin.devices.port')}</th>
                            <th>{t('admin.devices.community')}</th>
                            <th>{t('admin.devices.poll_interval')}</th>
                            <th>{t('admin.devices.status')}</th>
                            <th>{t('admin.devices.actions')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {devices.map((d) => (
                            <tr key={d.id}>
                                <td style={{ fontWeight: 600 }}>{d.id}</td>
                                <td>{d.name}</td>
                                <td>{d.host}</td>
                                <td>{d.port}</td>
                                <td>{d.community}</td>
                                <td>{d.poll_interval}s</td>
                                <td>
                                    <span className={`status-badge ${d.is_active ? (d.last_status || 'online') : 'inactive'}`}>
                                        <span className={`status-dot ${d.is_active ? (d.last_status || 'online') : 'offline'}`}></span>
                                        {d.is_active
                                            ? (d.last_status === 'offline' ? t('admin.devices.offline') : t('admin.devices.online'))
                                            : t('admin.devices.disabled')}
                                    </span>
                                </td>
                                <td>
                                    <div className="action-btns">
                                        <button className="action-btn" onClick={() => openEdit(d)}>
                                            {t('admin.devices.edit')}
                                        </button>
                                        <button className="action-btn" onClick={() => handleToggle(d)}>
                                            {d.is_active ? t('admin.devices.disabled') : t('admin.devices.enabled')}
                                        </button>
                                        <button className="action-btn success" onClick={() => handlePoll(d)}>
                                            {t('admin.devices.poll')}
                                        </button>
                                        <button className="action-btn danger" onClick={() => handleDelete(d)}>
                                            {t('admin.devices.delete')}
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Modal */}
            {showModal && (
                <div className="admin-modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
                        <h3>{editDevice ? t('admin.devices.edit') : t('admin.devices.add')}</h3>

                        <div className="form-group">
                            <label>{t('admin.devices.id')}</label>
                            <input
                                value={form.id}
                                onChange={(e) => setForm({ ...form, id: e.target.value })}
                                disabled={!!editDevice}
                                placeholder="CCDC-01"
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.name')}</label>
                            <input
                                value={form.name}
                                onChange={(e) => setForm({ ...form, name: e.target.value })}
                                placeholder="核心机房-KVM1"
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.host')}</label>
                            <input
                                value={form.host}
                                onChange={(e) => setForm({ ...form, host: e.target.value })}
                                placeholder="192.168.1.10"
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.port')}</label>
                            <input
                                type="number"
                                value={form.port}
                                onChange={(e) => setForm({ ...form, port: parseInt(e.target.value) || 161 })}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.community')}</label>
                            <input
                                value={form.community}
                                onChange={(e) => setForm({ ...form, community: e.target.value })}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.poll_interval')}</label>
                            <input
                                type="number"
                                value={form.poll_interval}
                                onChange={(e) => setForm({ ...form, poll_interval: parseInt(e.target.value) || 60 })}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.location')}</label>
                            <input
                                value={form.location}
                                onChange={(e) => setForm({ ...form, location: e.target.value })}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.description')}</label>
                            <input
                                value={form.description}
                                onChange={(e) => setForm({ ...form, description: e.target.value })}
                            />
                        </div>

                        <div className="form-actions">
                            <button className="admin-btn" onClick={() => setShowModal(false)}>
                                {t('admin.common.cancel')}
                            </button>
                            <button className="admin-btn primary" onClick={handleSubmit}>
                                {t('admin.common.save')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

export default DevicesTab;
