import { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Eye, Search } from 'lucide-react';
import { useTranslation } from '../i18n';
import { useStore } from '../store/mainStore';
import { filterAndSortDevices } from '../utils/multiProfile';
import DeviceDetail from './DeviceDetail';

function formatDate(value, locale) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString(locale);
}

function SortButton({ column, label, setSort, sort }) {
    const active = sort.key === column;
    const nextDirection = active && sort.direction === 'asc' ? 'desc' : 'asc';
    return (
        <button
            className={`table-sort ${active ? 'active' : ''}`}
            onClick={() => setSort({ key: column, direction: nextDirection })}
        >
            {label}
            {active && (sort.direction === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}
        </button>
    );
}

export default function DeviceTable({ filterDeviceId = 'all' }) {
    const { t, locale } = useTranslation();
    const devices = useStore((state) => state.devices);
    const profiles = useStore((state) => state.profiles);
    const aliases = useStore((state) => state.aliases);
    const detailLoading = useStore((state) => state.detailLoading);
    const detailErrors = useStore((state) => state.detailErrors);
    const deviceDetails = useStore((state) => state.deviceDetails);
    const fetchDeviceDetail = useStore((state) => state.fetchDeviceDetail);
    const setSelectedDevice = useStore((state) => state.setSelectedDevice);
    const [query, setQuery] = useState('');
    const [profile, setProfile] = useState('all');
    const [status, setStatus] = useState('all');
    const [sort, setSort] = useState({ key: 'name', direction: 'asc' });
    const [detailDeviceId, setDetailDeviceId] = useState(null);

    const displayDevices = useMemo(() => filterAndSortDevices(
        devices.map((device) => ({ ...device, name: aliases[device.id] || device.name })),
        {
            query,
            profile,
            status,
            selectedDeviceId: filterDeviceId,
        },
        sort
    ), [aliases, devices, filterDeviceId, profile, query, sort, status]);

    const availableProfiles = profiles.length > 0
        ? profiles
        : Array.from(new Map(devices.map((device) => [
            device.profile_id,
            {
                id: device.profile_id,
                label_key: device.profile_label_key,
                role: device.device_role,
            },
        ])).values());

    const openDetail = (device) => {
        setSelectedDevice(device.id);
        setDetailDeviceId(device.id);
        fetchDeviceDetail(device.id);
    };

    const detail = detailDeviceId ? deviceDetails[detailDeviceId] : null;

    return (
        <div className="device-table-view">
            <div className="device-table-toolbar">
                <label className="device-search">
                    <Search size={14} />
                    <input
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder={t('devices.search_placeholder')}
                        aria-label={t('devices.search_placeholder')}
                    />
                </label>
                <select value={profile} onChange={(event) => setProfile(event.target.value)}>
                    <option value="all">{t('devices.all_profiles')}</option>
                    {availableProfiles.filter((item) => item.id).map((item) => (
                        <option key={item.id} value={item.id}>
                            {t(item.label_key || `profiles.${item.id}`, item.product || item.id)}
                        </option>
                    ))}
                </select>
                <select value={status} onChange={(event) => setStatus(event.target.value)}>
                    <option value="all">{t('devices.all_statuses')}</option>
                    {['online', 'offline', 'warning', 'critical', 'stale', 'unknown'].map((item) => (
                        <option key={item} value={item}>{t(`status.${item}`)}</option>
                    ))}
                </select>
                <span className="device-result-count">
                    {t('devices.result_count', '{{count}}').replace('{{count}}', displayDevices.length)}
                </span>
            </div>

            <div className="device-table-scroll">
                <table className="device-table">
                    <thead>
                        <tr>
                            <th><SortButton column="name" label={t('devices.name')} sort={sort} setSort={setSort} /></th>
                            <th>{t('devices.profile')}</th>
                            <th>{t('devices.role')}</th>
                            <th><SortButton column="host" label={t('devices.host')} sort={sort} setSort={setSort} /></th>
                            <th>{t('devices.reachability')}</th>
                            <th>{t('devices.freshness')}</th>
                            <th>{t('devices.health')}</th>
                            <th>{t('devices.entities')}</th>
                            <th>{t('devices.alerts')}</th>
                            <th>{t('devices.last_check')}</th>
                            <th>{t('devices.last_full_poll')}</th>
                            <th><span className="sr-only">{t('devices.actions')}</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayDevices.map((device) => (
                            <tr key={device.id} onDoubleClick={() => openDetail(device)}>
                                <td>
                                    <button className="device-name-button" onClick={() => openDetail(device)}>
                                        <strong>{device.name}</strong>
                                        <span>{device.model || device.id}</span>
                                    </button>
                                </td>
                                <td>{t(device.profile_label_key || `profiles.${device.profile_id}`, device.profile_id)}</td>
                                <td>{t(`profiles.roles.${device.device_role}`, device.device_role || '—')}</td>
                                <td className="mono">{device.host}:{device.port}</td>
                                <td><span className={`status-badge ${device.online_status}`}>{t(`status.${device.online_status}`)}</span></td>
                                <td><span className={`status-badge ${device.freshness_status}`}>{t(`status.${device.freshness_status}`)}</span></td>
                                <td><span className={`status-badge ${device.health_status}`}>{t(`status.${device.health_status}`)}</span></td>
                                <td>{device.entity_count ?? '—'}</td>
                                <td>{device.active_alert_count ?? 0}</td>
                                <td>{formatDate(device.last_health_check, locale)}</td>
                                <td>{formatDate(device.last_full_poll, locale)}</td>
                                <td>
                                    <button
                                        className="icon-button"
                                        onClick={() => openDetail(device)}
                                        title={t('devices.view_details')}
                                        aria-label={t('devices.view_details')}
                                    >
                                        <Eye size={15} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {displayDevices.length === 0 && (
                    <div className="detail-empty">{t('devices.no_results')}</div>
                )}
            </div>

            {detailDeviceId && (
                <DeviceDetail
                    detail={detail}
                    loading={Boolean(detailLoading[detailDeviceId])}
                    error={detailErrors[detailDeviceId]}
                    onClose={() => setDetailDeviceId(null)}
                    onRefresh={() => fetchDeviceDetail(detailDeviceId, { force: true })}
                />
            )}
        </div>
    );
}
