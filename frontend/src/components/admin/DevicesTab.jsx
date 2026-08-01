import { useCallback, useEffect, useState } from 'react';
import { getApiError, getDeviceSummaries } from '../../services/multiProfileApi';
import api from '../../utils/api';

const emptyForm = {
    id: '',
    name: '',
    host: '',
    port: 161,
    community: '',
    location: '',
    description: '',
};

export default function DevicesTab({ t, showToast }) {
    const [devices, setDevices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editDevice, setEditDevice] = useState(null);
    const [form, setForm] = useState(emptyForm);

    const fetchDevices = useCallback(async () => {
        try {
            setLoading(true);
            const result = await getDeviceSummaries({ page: 1, page_size: 100 });
            setDevices(result.items);
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        } finally {
            setLoading(false);
        }
    }, [showToast, t]);

    useEffect(() => {
        fetchDevices();
    }, [fetchDevices]);

    const openAdd = () => {
        setEditDevice(null);
        setForm(emptyForm);
        setShowModal(true);
    };

    const openEdit = (device) => {
        setEditDevice(device);
        setForm({
            id: device.id,
            name: device.name,
            host: device.host,
            port: device.port,
            community: '',
            location: device.location || '',
            description: device.description || '',
        });
        setShowModal(true);
    };

    const handleSubmit = async () => {
        if (!editDevice && !form.id.trim()) {
            showToast(t('admin.devices.validation_id'), 'error');
            return;
        }
        if (!form.name.trim() || !form.host.trim()) {
            showToast(t('admin.devices.validation_name_host'), 'error');
            return;
        }
        if (!editDevice && !form.community.trim()) {
            showToast(t('admin.devices.validation_community'), 'error');
            return;
        }

        const body = {
            name: form.name.trim(),
            host: form.host.trim(),
            port: Number(form.port),
            location: form.location.trim() || null,
            description: form.description.trim() || null,
        };
        if (form.community.trim()) body.community = form.community;

        try {
            if (editDevice) {
                await api.patch(`/devices/${encodeURIComponent(editDevice.id)}`, body);
            } else {
                await api.post('/devices', { id: form.id.trim(), ...body });
            }
            showToast(t('admin.common.success'));
            setShowModal(false);
            fetchDevices();
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        }
    };

    const handleDelete = async (device) => {
        if (!window.confirm(`${t('admin.devices.confirm_delete')} "${device.name}"?`)) return;
        try {
            await api.delete(`/devices/${encodeURIComponent(device.id)}`);
            showToast(t('admin.common.success'));
            fetchDevices();
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        }
    };

    const handleToggle = async (device) => {
        try {
            await api.patch(`/devices/${encodeURIComponent(device.id)}`, { is_active: !device.is_active });
            showToast(t('admin.common.success'));
            fetchDevices();
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        }
    };

    const handlePoll = async (device) => {
        try {
            await api.post(`/devices/${encodeURIComponent(device.id)}/poll`);
            showToast(t('admin.devices.poll_started'));
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        }
    };

    if (loading) return <div className="admin-empty">{t('admin.common.loading')}</div>;

    return (
        <>
            <div className="admin-toolbar">
                <div className="admin-toolbar-left">
                    <strong>{t('admin.tabs.devices')} ({devices.length})</strong>
                </div>
                <div className="admin-toolbar-right">
                    <button className="admin-btn primary" onClick={openAdd}>
                        {t('admin.devices.add')}
                    </button>
                </div>
            </div>

            <div className="admin-table-wrap">
                <table className="admin-table">
                    <thead>
                        <tr>
                            <th>{t('admin.devices.id')}</th>
                            <th>{t('admin.devices.name')}</th>
                            <th>{t('admin.devices.profile')}</th>
                            <th>{t('admin.devices.host')}</th>
                            <th>{t('admin.devices.credential')}</th>
                            <th>{t('admin.devices.status')}</th>
                            <th>{t('admin.devices.actions')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {devices.map((device) => (
                            <tr key={device.id}>
                                <td><strong>{device.id}</strong></td>
                                <td>{device.name}</td>
                                <td>{t(device.profile_label_key || `profiles.${device.profile_id}`, device.profile_id)}</td>
                                <td>{device.host}:{device.port}</td>
                                <td>
                                    <span className={`status-badge ${device.credential_configured ? 'online' : 'warning'}`}>
                                        {device.credential_configured
                                            ? t('admin.devices.credential_configured')
                                            : t('admin.devices.credential_missing')}
                                    </span>
                                </td>
                                <td>
                                    <span className={`status-badge ${device.is_active ? device.online_status : 'inactive'}`}>
                                        {device.is_active
                                            ? t(`status.${device.online_status}`)
                                            : t('admin.devices.disabled')}
                                    </span>
                                </td>
                                <td>
                                    <div className="action-btns">
                                        <button className="action-btn" onClick={() => openEdit(device)}>
                                            {t('admin.devices.edit')}
                                        </button>
                                        <button className="action-btn" onClick={() => handleToggle(device)}>
                                            {device.is_active ? t('admin.devices.disable') : t('admin.devices.enable')}
                                        </button>
                                        <button className="action-btn success" onClick={() => handlePoll(device)}>
                                            {t('admin.devices.poll')}
                                        </button>
                                        <button className="action-btn danger" onClick={() => handleDelete(device)}>
                                            {t('admin.devices.delete')}
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {showModal && (
                <div className="admin-modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="admin-modal" onClick={(event) => event.stopPropagation()}>
                        <h3>{editDevice ? t('admin.devices.edit') : t('admin.devices.add')}</h3>
                        <div className="form-group">
                            <label>{t('admin.devices.id')}</label>
                            <input
                                value={form.id}
                                onChange={(event) => setForm({ ...form, id: event.target.value })}
                                disabled={Boolean(editDevice)}
                                placeholder={t('admin.devices.id_placeholder')}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.name')}</label>
                            <input
                                value={form.name}
                                onChange={(event) => setForm({ ...form, name: event.target.value })}
                                placeholder={t('admin.devices.name_placeholder')}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.host')}</label>
                            <input
                                value={form.host}
                                onChange={(event) => setForm({ ...form, host: event.target.value })}
                                placeholder={t('admin.devices.host_placeholder')}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.port')}</label>
                            <input
                                type="number"
                                value={form.port}
                                onChange={(event) => setForm({ ...form, port: event.target.value })}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.community')}</label>
                            <input
                                type="password"
                                value={form.community}
                                onChange={(event) => setForm({ ...form, community: event.target.value })}
                                placeholder={editDevice
                                    ? t('admin.devices.community_keep')
                                    : t('admin.devices.community_placeholder')}
                                autoComplete="new-password"
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.location')}</label>
                            <input
                                value={form.location}
                                onChange={(event) => setForm({ ...form, location: event.target.value })}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.devices.description')}</label>
                            <input
                                value={form.description}
                                onChange={(event) => setForm({ ...form, description: event.target.value })}
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
