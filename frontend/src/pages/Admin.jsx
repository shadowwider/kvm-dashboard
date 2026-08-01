import { useCallback, useState } from 'react';
import { Languages, LogOut, Moon, Sun } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AlertsTab from '../components/admin/AlertsTab';
import AliasesTab from '../components/admin/AliasesTab';
import AuditLogsTab from '../components/admin/AuditLogsTab';
import DevicesTab from '../components/admin/DevicesTab';
import DiscoveryTab from '../components/admin/DiscoveryTab';
import EndpointsTab from '../components/admin/EndpointsTab';
import OIDsTab from '../components/admin/OIDsTab';
import UsersTab from '../components/admin/UsersTab';
import SoundControl from '../components/SoundControl';
import useAlertSound from '../hooks/useAlertSound';
import useSystemWebSocket from '../hooks/useSystemWebSocket';
import { useTranslation, useTranslationStore } from '../i18n';
import { useAuthStore } from '../store/authStore';
import './Admin.css';

const TABS = ['devices', 'endpoints', 'aliases', 'oids', 'alerts', 'discovery', 'audit', 'users'];

export default function Admin() {
    const navigate = useNavigate();
    const { t } = useTranslation();
    const { locale, setLocale } = useTranslationStore();
    const user = useAuthStore((state) => state.user);
    const logout = useAuthStore((state) => state.logout);
    const [activeTab, setActiveTab] = useState('devices');
    const [theme, setTheme] = useState('dark');
    const [toast, setToast] = useState(null);
    useSystemWebSocket();
    useAlertSound();

    const showToast = useCallback((message, type = 'success') => {
        setToast({ message, type });
        window.setTimeout(() => setToast(null), 3000);
    }, []);

    const tabProps = { t, showToast };
    const tabContent = {
        devices: <DevicesTab {...tabProps} />,
        endpoints: <EndpointsTab {...tabProps} />,
        aliases: <AliasesTab {...tabProps} />,
        oids: <OIDsTab {...tabProps} />,
        alerts: <AlertsTab {...tabProps} />,
        discovery: <DiscoveryTab {...tabProps} />,
        audit: <AuditLogsTab {...tabProps} />,
        users: <UsersTab {...tabProps} />,
    };

    return (
        <div className={`admin-page ${theme}`}>
            <div className="admin-topbar">
                <div className="admin-topbar-left">
                    <button className="admin-back-btn" onClick={() => navigate('/dashboard')}>
                        {t('admin.back')}
                    </button>
                    <span className="admin-title">{t('admin.title')}</span>
                </div>
                <div className="admin-topbar-right">
                    <SoundControl />
                    <button
                        className="admin-icon-btn"
                        onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
                        title={t('common.switch_language')}
                    >
                        <Languages size={14} />
                        {locale === 'zh-CN' ? t('admin.lang.en') : t('admin.lang.zh')}
                    </button>
                    <button
                        className="admin-icon-btn"
                        onClick={() => setTheme((value) => value === 'dark' ? 'light' : 'dark')}
                        title={t('common.switch_theme')}
                    >
                        {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
                        {theme === 'dark' ? t('admin.theme.light') : t('admin.theme.dark')}
                    </button>
                    <div className="admin-user-badge">
                        <span>{user?.username}</span>
                        <span className="user-role">[{user?.role}]</span>
                    </div>
                    <button
                        className="admin-btn danger"
                        onClick={() => {
                            logout();
                            navigate('/login');
                        }}
                    >
                        <LogOut size={14} /> {t('common.logout')}
                    </button>
                </div>
            </div>

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

            <div className="admin-content">{tabContent[activeTab]}</div>

            {toast && <div className={`admin-toast ${toast.type}`}>{toast.message}</div>}
        </div>
    );
}
