import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useTranslation, useTranslationStore } from '../i18n';
import DevicesTab from '../components/admin/DevicesTab';
import AliasesTab from '../components/admin/AliasesTab';
import OIDsTab from '../components/admin/OIDsTab';
import AlertsTab from '../components/admin/AlertsTab';
import UsersTab from '../components/admin/UsersTab';
import './Admin.css';

const TABS = ['devices', 'aliases', 'oids', 'alerts', 'users'];

function Admin() {
    const navigate = useNavigate();
    const { t } = useTranslation();
    const { locale, setLocale } = useTranslationStore();
    const user = useAuthStore((s) => s.user);
    const logout = useAuthStore((s) => s.logout);

    const [activeTab, setActiveTab] = useState('devices');
    const [theme, setTheme] = useState('dark');
    const [toast, setToast] = useState(null);

    // Toast helper
    const showToast = useCallback((message, type = 'success') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    }, []);

    // Theme toggle
    const toggleTheme = () => {
        setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
    };

    // Language toggle
    const toggleLang = () => {
        setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN');
    };

    // Render active tab content
    const renderTab = () => {
        switch (activeTab) {
            case 'devices':
                return <DevicesTab t={t} showToast={showToast} />;
            case 'aliases':
                return <AliasesTab t={t} showToast={showToast} />;
            case 'oids':
                return <OIDsTab t={t} showToast={showToast} />;
            case 'alerts':
                return <AlertsTab t={t} showToast={showToast} />;
            case 'users':
                return <UsersTab t={t} showToast={showToast} />;
            default:
                return null;
        }
    };

    return (
        <div className={`admin-page ${theme}`}>
            {/* ── Top Bar ────────────────────────── */}
            <div className="admin-topbar">
                <div className="admin-topbar-left">
                    <button className="admin-back-btn" onClick={() => navigate('/dashboard')}>
                        ← {t('admin.back')}
                    </button>
                    <span className="admin-title">{t('admin.title')}</span>
                </div>
                <div className="admin-topbar-right">
                    {/* Language Toggle */}
                    <button className="admin-icon-btn" onClick={toggleLang} title="切换语言">
                        <span className="icon">🌐</span>
                        {locale === 'zh-CN' ? t('admin.lang.en') : t('admin.lang.zh')}
                    </button>
                    {/* Theme Toggle */}
                    <button className="admin-icon-btn" onClick={toggleTheme} title="切换主题">
                        <span className="icon">{theme === 'dark' ? '☀️' : '🌙'}</span>
                        {theme === 'dark' ? t('admin.theme.light') : t('admin.theme.dark')}
                    </button>
                    {/* User Badge */}
                    <div className="admin-user-badge">
                        <span>{user?.username}</span>
                        <span className="user-role">[{user?.role}]</span>
                    </div>
                    <button className="admin-btn danger" onClick={() => { logout(); navigate('/login'); }}>
                        Logout
                    </button>
                </div>
            </div>

            {/* ── Tab Bar ────────────────────────── */}
            <div className="admin-tabs">
                {TABS.map((tab) => (
                    <button
                        key={tab}
                        className={`admin-tab ${activeTab === tab ? 'active' : ''}`}
                        onClick={() => setActiveTab(tab)}
                    >
                        {t(`admin.tabs.${tab}`)}
                    </button>
                ))}
            </div>

            {/* ── Content ────────────────────────── */}
            <div className="admin-content">
                {renderTab()}
            </div>

            {/* ── Toast ──────────────────────────── */}
            {toast && (
                <div className={`admin-toast ${toast.type}`}>
                    {toast.message}
                </div>
            )}
        </div>
    );
}

export default Admin;
