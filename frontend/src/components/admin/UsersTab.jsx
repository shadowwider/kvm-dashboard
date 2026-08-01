import React, { useState, useEffect, useCallback } from 'react';
import api from '../../utils/api';

function UsersTab({ t, showToast }) {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAddModal, setShowAddModal] = useState(false);
    const [showPwdModal, setShowPwdModal] = useState(null); // user object or null
    const [showRoleModal, setShowRoleModal] = useState(null); // user object or null
    const [addForm, setAddForm] = useState({ username: '', password: '', role: 'viewer' });
    const [newPassword, setNewPassword] = useState('');
    const [newRole, setNewRole] = useState('viewer');

    // Fetch
    const fetchUsers = useCallback(async () => {
        try {
            setLoading(true);
            const res = await api.get('/auth/users');
            setUsers(res.data || []);
        } catch {
            showToast(t('admin.common.error'), 'error');
        } finally {
            setLoading(false);
        }
    }, [showToast, t]);

    useEffect(() => { fetchUsers(); }, [fetchUsers]);

    // Add User
    const handleAdd = async () => {
        if (!addForm.username || !addForm.password) return;
        try {
            await api.post('/auth/users', addForm);
            showToast(t('admin.common.success'));
            setShowAddModal(false);
            setAddForm({ username: '', password: '', role: 'viewer' });
            fetchUsers();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Toggle active
    const handleToggle = async (user) => {
        try {
            await api.patch(`/auth/users/${user.id}/toggle`);
            showToast(t('admin.common.success'));
            fetchUsers();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Reset password
    const handleResetPassword = async () => {
        if (!newPassword || newPassword.length < 6) {
            showToast(t('admin.users.password_placeholder'), 'error');
            return;
        }
        try {
            await api.patch(`/auth/users/${showPwdModal.id}/reset-password`, {
                new_password: newPassword,
            });
            showToast(t('admin.common.success'));
            setShowPwdModal(null);
            setNewPassword('');
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Change role
    const handleChangeRole = async () => {
        try {
            await api.patch(`/auth/users/${showRoleModal.id}/role`, {
                role: newRole,
            });
            showToast(t('admin.common.success'));
            setShowRoleModal(null);
            fetchUsers();
        } catch (err) {
            showToast(err.response?.data?.detail || t('admin.common.error'), 'error');
        }
    };

    // Format time
    const fmtTime = (iso) => {
        if (!iso) return '—';
        return new Date(iso).toLocaleString('zh-CN', { hour12: false });
    };

    if (loading) return <div className="admin-empty">{t('admin.common.loading')}</div>;

    return (
        <>
            <div className="admin-toolbar">
                <div className="admin-toolbar-left">
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                        {t('admin.tabs.users')} ({users.length})
                    </span>
                </div>
                <div className="admin-toolbar-right">
                    <button className="admin-btn primary" onClick={() => setShowAddModal(true)}>
                        + {t('admin.users.add')}
                    </button>
                </div>
            </div>

            <div className="admin-table-wrap">
                <table className="admin-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>{t('admin.users.username')}</th>
                            <th>{t('admin.users.role')}</th>
                            <th>{t('admin.users.status')}</th>
                            <th>{t('admin.users.created_at')}</th>
                            <th>{t('admin.users.actions')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map((u) => (
                            <tr key={u.id}>
                                <td>{u.id}</td>
                                <td style={{ fontWeight: 600 }}>{u.username}</td>
                                <td>
                                    <span className={`status-badge ${u.role === 'admin' ? 'info' : 'active'}`}>
                                        {u.role === 'admin' ? t('admin.users.role_admin') : t('admin.users.role_viewer')}
                                    </span>
                                </td>
                                <td>
                                    <span className={`status-badge ${u.is_active ? 'active' : 'inactive'}`}>
                                        <span className={`status-dot ${u.is_active ? 'online' : 'offline'}`}></span>
                                        {u.is_active ? t('admin.users.active') : t('admin.users.inactive')}
                                    </span>
                                </td>
                                <td style={{ fontSize: 11 }}>{fmtTime(u.created_at)}</td>
                                <td>
                                    <div className="action-btns">
                                        <button className="action-btn" onClick={() => handleToggle(u)}>
                                            {t('admin.users.toggle')}
                                        </button>
                                        <button
                                            className="action-btn"
                                            onClick={() => {
                                                setShowPwdModal(u);
                                                setNewPassword('');
                                            }}
                                        >
                                            {t('admin.users.reset_password')}
                                        </button>
                                        <button
                                            className="action-btn"
                                            onClick={() => {
                                                setShowRoleModal(u);
                                                setNewRole(u.role === 'admin' ? 'viewer' : 'admin');
                                            }}
                                        >
                                            {t('admin.users.change_role')}
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Add User Modal */}
            {showAddModal && (
                <div className="admin-modal-overlay" onClick={() => setShowAddModal(false)}>
                    <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
                        <h3>{t('admin.users.add')}</h3>
                        <div className="form-group">
                            <label>{t('admin.users.username')}</label>
                            <input
                                value={addForm.username}
                                onChange={(e) => setAddForm({ ...addForm, username: e.target.value })}
                                placeholder="username"
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.users.password')}</label>
                            <input
                                type="password"
                                value={addForm.password}
                                onChange={(e) => setAddForm({ ...addForm, password: e.target.value })}
                                placeholder={t('admin.users.password_placeholder')}
                            />
                        </div>
                        <div className="form-group">
                            <label>{t('admin.users.role')}</label>
                            <select
                                value={addForm.role}
                                onChange={(e) => setAddForm({ ...addForm, role: e.target.value })}
                            >
                                <option value="viewer">{t('admin.users.role_viewer')}</option>
                                <option value="admin">{t('admin.users.role_admin')}</option>
                            </select>
                        </div>
                        <div className="form-actions">
                            <button className="admin-btn" onClick={() => setShowAddModal(false)}>
                                {t('admin.common.cancel')}
                            </button>
                            <button className="admin-btn primary" onClick={handleAdd}>
                                {t('admin.common.save')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Reset Password Modal */}
            {showPwdModal && (
                <div className="admin-modal-overlay" onClick={() => setShowPwdModal(null)}>
                    <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
                        <h3>{t('admin.users.reset_password')} — {showPwdModal.username}</h3>
                        <div className="form-group">
                            <label>{t('admin.users.new_password')}</label>
                            <input
                                type="password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                placeholder={t('admin.users.password_placeholder')}
                            />
                        </div>
                        <div className="form-actions">
                            <button className="admin-btn" onClick={() => setShowPwdModal(null)}>
                                {t('admin.common.cancel')}
                            </button>
                            <button className="admin-btn primary" onClick={handleResetPassword}>
                                {t('admin.common.confirm')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Change Role Modal */}
            {showRoleModal && (
                <div className="admin-modal-overlay" onClick={() => setShowRoleModal(null)}>
                    <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
                        <h3>{t('admin.users.change_role')} — {showRoleModal.username}</h3>
                        <div className="form-group">
                            <label>{t('admin.users.role')}</label>
                            <select value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                                <option value="viewer">{t('admin.users.role_viewer')}</option>
                                <option value="admin">{t('admin.users.role_admin')}</option>
                            </select>
                        </div>
                        <div className="form-actions">
                            <button className="admin-btn" onClick={() => setShowRoleModal(null)}>
                                {t('admin.common.cancel')}
                            </button>
                            <button className="admin-btn primary" onClick={handleChangeRole}>
                                {t('admin.common.confirm')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

export default UsersTab;
