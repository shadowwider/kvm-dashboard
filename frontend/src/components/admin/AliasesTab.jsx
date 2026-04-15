import React, { useState, useEffect, useCallback, useRef } from 'react';
import api from '../../utils/api';

function AliasesTab({ t, showToast }) {
    const [aliases, setAliases] = useState([]);
    const [devices, setDevices] = useState([]);
    const [endpoints, setEndpoints] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editingId, setEditingId] = useState(null);
    const [editValue, setEditValue] = useState('');
    const [showAddModal, setShowAddModal] = useState(false);
    const [addForm, setAddForm] = useState({ target_type: 'device', target_id: '', alias: '', note: '' });
    const inputRef = useRef(null);

    // Fetch aliases + devices + endpoints for the add-modal dropdown
    const fetchAliases = useCallback(async () => {
        try {
            setLoading(true);
            const [aliasRes, devRes] = await Promise.all([
                api.get('/aliases'),
                api.get('/devices'),
            ]);
            setAliases(aliasRes.data || []);
            setDevices(devRes.data || []);

            // fetch all endpoints for all devices
            const devIds = (devRes.data || []).map(d => d.id);
            const epPromises = devIds.map(id => api.get(`/endpoints?device_id=${id}`).catch(() => ({ data: [] })));
            const epResults = await Promise.all(epPromises);
            const allEps = epResults.flatMap(r => r.data || []);
            setEndpoints(allEps);
        } catch (err) {
            showToast(t('admin.common.error'), 'error');
        } finally {
            setLoading(false);
        }
    }, [showToast, t]);

    useEffect(() => { fetchAliases(); }, [fetchAliases]);

    // Get dropdown options based on target_type
    const getTargetOptions = () => {
        if (addForm.target_type === 'device') {
            return devices.map(d => ({ id: d.id, label: `${d.id} — ${d.name}` }));
        }
        return endpoints.map(ep => ({
            id: ep.id,
            label: `[${(ep.module_type || 'cpu').toUpperCase()}] ${ep.id} — ${ep.name || '未命名'}`,
        }));
    };

    // Add alias
    const handleAdd = async () => {
        if (!addForm.target_id || !addForm.alias.trim()) return;
        try {
            await api.put(`/aliases/${addForm.target_id}`, {
                alias: addForm.alias.trim(),
                target_type: addForm.target_type,
                note: addForm.note || null,
            });
            showToast(t('admin.aliases.save_success'));
            setShowAddModal(false);
            setAddForm({ target_type: 'device', target_id: '', alias: '', note: '' });
            fetchAliases();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Inline edit
    const startEdit = (alias) => {
        setEditingId(alias.target_id);
        setEditValue(alias.alias);
        setTimeout(() => inputRef.current?.focus(), 50);
    };

    const saveEdit = async (targetId, targetType) => {
        if (!editValue.trim()) {
            setEditingId(null);
            return;
        }
        try {
            await api.put(`/aliases/${targetId}`, {
                alias: editValue.trim(),
                target_type: targetType,
            });
            showToast(t('admin.aliases.save_success'));
            setEditingId(null);
            fetchAliases();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Delete
    const handleDelete = async (targetId) => {
        try {
            await api.delete(`/aliases/${targetId}`);
            showToast(t('admin.common.success'));
            fetchAliases();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    if (loading) return <div className="admin-empty">{t('admin.common.loading')}</div>;

    return (
        <>
            <div className="admin-toolbar">
                <div className="admin-toolbar-left">
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                        {t('admin.tabs.aliases')} ({aliases.length})
                    </span>
                </div>
                <div className="admin-toolbar-right">
                    <button className="admin-btn primary" onClick={() => setShowAddModal(true)}>
                        + {t('admin.aliases.add') || '添加别名'}
                    </button>
                </div>
            </div>

            {aliases.length === 0 ? (
                <div className="admin-empty">
                    <div className="empty-icon">📝</div>
                    {t('admin.aliases.no_aliases')}
                    <div style={{ marginTop: 12 }}>
                        <button className="admin-btn primary" onClick={() => setShowAddModal(true)}>
                            + {t('admin.aliases.add') || '添加别名'}
                        </button>
                    </div>
                </div>
            ) : (
                <div className="admin-table-wrap">
                    <table className="admin-table">
                        <thead>
                            <tr>
                                <th>{t('admin.aliases.target_id')}</th>
                                <th>{t('admin.aliases.target_type')}</th>
                                <th>{t('admin.aliases.alias')}</th>
                                <th>{t('admin.aliases.note')}</th>
                                <th>{t('admin.aliases.actions')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {aliases.map((a) => (
                                <tr key={a.target_id}>
                                    <td style={{ fontWeight: 600 }}>{a.target_id}</td>
                                    <td>
                                        <span className={`status-badge ${a.target_type === 'device' ? 'info' : 'active'}`}>
                                            {a.target_type === 'device'
                                                ? t('admin.aliases.type_device')
                                                : t('admin.aliases.type_endpoint')}
                                        </span>
                                    </td>
                                    <td>
                                        {editingId === a.target_id ? (
                                            <input
                                                ref={inputRef}
                                                className="inline-edit-input"
                                                value={editValue}
                                                onChange={(e) => setEditValue(e.target.value)}
                                                onBlur={() => saveEdit(a.target_id, a.target_type)}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter') saveEdit(a.target_id, a.target_type);
                                                    if (e.key === 'Escape') setEditingId(null);
                                                }}
                                            />
                                        ) : (
                                            <div className="inline-edit" onClick={() => startEdit(a)}>
                                                {a.alias || <span style={{ opacity: 0.4 }}>{t('admin.aliases.click_to_edit')}</span>}
                                                <span style={{ opacity: 0.3, fontSize: 10 }}>✎</span>
                                            </div>
                                        )}
                                    </td>
                                    <td style={{ color: 'var(--admin-text-dim)' }}>{a.note || '—'}</td>
                                    <td>
                                        <div className="action-btns">
                                            <button className="action-btn danger" onClick={() => handleDelete(a.target_id)}>
                                                {t('admin.aliases.delete')}
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Add Alias Modal */}
            {showAddModal && (
                <div className="admin-modal-overlay" onClick={() => setShowAddModal(false)}>
                    <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
                        <h3>{t('admin.aliases.add') || '添加别名'}</h3>

                        <div className="form-group">
                            <label>{t('admin.aliases.target_type')}</label>
                            <select
                                value={addForm.target_type}
                                onChange={(e) => setAddForm({ ...addForm, target_type: e.target.value, target_id: '' })}
                            >
                                <option value="device">{t('admin.aliases.type_device')}</option>
                                <option value="endpoint">{t('admin.aliases.type_endpoint')}</option>
                            </select>
                        </div>

                        <div className="form-group">
                            <label>{t('admin.aliases.target_id')}</label>
                            <select
                                value={addForm.target_id}
                                onChange={(e) => setAddForm({ ...addForm, target_id: e.target.value })}
                            >
                                <option value="">
                                    — {addForm.target_type === 'device' ? t('admin.aliases.select_device') || '选择设备' : t('admin.aliases.select_endpoint') || '选择终端'} —
                                </option>
                                {getTargetOptions().map(opt => (
                                    <option key={opt.id} value={opt.id}>{opt.label}</option>
                                ))}
                            </select>
                        </div>

                        <div className="form-group">
                            <label>{t('admin.aliases.alias')}</label>
                            <input
                                value={addForm.alias}
                                onChange={(e) => setAddForm({ ...addForm, alias: e.target.value })}
                                placeholder={t('admin.aliases.alias_placeholder') || '自定义显示名称'}
                            />
                        </div>

                        <div className="form-group">
                            <label>{t('admin.aliases.note')}</label>
                            <input
                                value={addForm.note}
                                onChange={(e) => setAddForm({ ...addForm, note: e.target.value })}
                                placeholder={t('admin.aliases.note_placeholder') || '备注（可选）'}
                            />
                        </div>

                        <div className="form-actions">
                            <button className="admin-btn" onClick={() => setShowAddModal(false)}>
                                {t('admin.common.cancel')}
                            </button>
                            <button className="admin-btn primary" onClick={handleAdd} disabled={!addForm.target_id || !addForm.alias.trim()}>
                                {t('admin.common.save')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

export default AliasesTab;
