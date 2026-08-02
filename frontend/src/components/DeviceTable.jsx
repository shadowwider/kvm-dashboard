import { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Eye, Search } from 'lucide-react';
import { useTranslation } from '../i18n';
import { useStore } from '../store/mainStore';
import {
    filterAndSortDevices,
    getPeripheralFieldKind,
    hidBoundaryState,
    keyboardMouseState,
} from '../utils/multiProfile';
import DeviceDetail from './DeviceDetail';
import './DeviceInventory.css';

const DEVICE_TYPE_TABS = [
    { id: 'all', labelKey: 'devices.type_tabs.all', fallback: 'All' },
    { id: 'matrix', labelKey: 'profiles.roles.matrix', fallback: 'Matrix' },
    { id: 'cpu', labelKey: 'devices.type_tabs.cpu', fallback: 'CPU' },
    { id: 'con', labelKey: 'devices.type_tabs.con', fallback: 'CON' },
    { id: 'dwc', labelKey: 'devices.type_tabs.dwc', fallback: 'DWC' },
    { id: 'mux', labelKey: 'devices.type_tabs.mux', fallback: 'MUX' },
];

function formatDate(value, locale) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString(locale);
}

function normalizedTypeText(device) {
    return [
        device?.profile_id,
        device?.profile?.id,
        device?.device_role,
        device?.profile?.role,
        device?.model,
        device?.model_name,
    ].filter(Boolean).join(' ').toLocaleLowerCase();
}

function deviceType(device) {
    const role = String(device?.device_role || device?.profile?.role || '')
        .trim()
        .toLocaleLowerCase();
    const source = normalizedTypeText(device);

    if (role === 'matrix' || /(?:^|[_\s-])(matrix|ccdc|ccdm|controlcenter)(?:$|[_\s-])/.test(source)) {
        return 'matrix';
    }
    // DWC must precede the generic channel-device / MUX rule.
    if (role.includes('dwc') || /(?:^|[_\s-])dwc(?:$|[_\s-])/.test(source)) return 'dwc';
    if (role.includes('mux') || role === 'channel_device' || /(?:^|[_\s-])mux(?:$|[_\s-])/.test(source)) return 'mux';
    if (role.includes('cpu') || /(?:^|[_\s-])cpu(?:$|[_\s-])/.test(source)) return 'cpu';
    if (role.includes('con') || role === 'console' || /(?:^|[_\s-])con(?:$|[_\s-])/.test(source)) return 'con';
    return null;
}

function isDisplayableField(field) {
    return field
        && field.supported !== false
        && field.present !== false
        && field.value !== null
        && field.value !== undefined
        && field.value !== '';
}

function metricFields(device, detail) {
    const detailFields = (detail?.sections || []).flatMap((section) => section.fields || []);
    if (detailFields.length > 0) return detailFields.filter(isDisplayableField);

    const rawMetrics = device?.last_metrics?.summary || device?.last_metrics || {};
    if (!rawMetrics || typeof rawMetrics !== 'object' || Array.isArray(rawMetrics)) return [];
    return Object.entries(rawMetrics)
        .filter(([, value]) => value !== null && value !== undefined && typeof value !== 'object')
        .map(([key, value]) => ({
            key,
            label_key: `fields.${key}`,
            label: key,
            value,
            unit: null,
            status: 'ok',
            supported: true,
            present: true,
        }));
}

function fieldPriority(field) {
    const key = `${field.key || ''} ${field.semantic || ''}`.toLocaleLowerCase();
    if (/(temperature|fan|thermal)/.test(key)) return 10;
    if (/(network|ether|sfp|link|connection)/.test(key)) return 20;
    if (/(keyboard|mouse|usb|hid|ps2)/.test(key)) return 30;
    if (/(video|display|signal|freeze)/.test(key)) return 40;
    return 90;
}

function extensionColumns(devices, details) {
    const byKey = new Map();
    devices.forEach((device) => {
        metricFields(device, details[device.id]).forEach((field) => {
            if (!byKey.has(field.key)) byKey.set(field.key, field);
        });
    });

    return [...byKey.values()]
        .sort((left, right) => (
            fieldPriority(left) - fieldPriority(right)
            || String(left.key).localeCompare(String(right.key))
        ))
        .slice(0, 4);
}

function displayFieldValue(field, t) {
    if (!field) return '—';
    const peripheralKind = getPeripheralFieldKind(field);
    if (peripheralKind === 'keyboard_mouse') {
        const state = keyboardMouseState(field.value);
        if (!state.known) return t('status.unknown');
        return `${t('detail.keyboard')}: ${state.keyboard ? t('status.connected') : t('status.disconnected')} · ${t('detail.mouse')}: ${state.mouse ? t('status.connected') : t('status.disconnected')}`;
    }
    if (peripheralKind === 'hid') {
        const state = hidBoundaryState(field.value);
        return t(`status.${state.state}`, String(field.value));
    }
    if (typeof field.value === 'boolean') return field.value ? 'true' : 'false';
    if (typeof field.value === 'object') return JSON.stringify(field.value);
    return `${field.value}${field.unit ? ` ${field.unit}` : ''}`;
}

function typeTabLabel(tab, t, locale) {
    const fallback = tab.id === 'all'
        ? (locale === 'zh-CN' ? '全部' : 'All')
        : tab.fallback;
    return t(tab.labelKey, fallback);
}

function SortButton({ column, label, setSort, sort }) {
    const active = sort.key === column;
    const nextDirection = active && sort.direction === 'asc' ? 'desc' : 'asc';
    return (
        <button
            type="button"
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
    const [type, setType] = useState('all');
    const [sort, setSort] = useState({ key: 'name', direction: 'asc' });
    const [detailDeviceId, setDetailDeviceId] = useState(null);

    const namedDevices = useMemo(() => devices.map((device) => ({
        ...device,
        name: aliases[device.id] || device.name,
    })), [aliases, devices]);

    const typeScopeDevices = useMemo(() => filterAndSortDevices(namedDevices, {
        profile,
        selectedDeviceId: filterDeviceId,
    }), [filterDeviceId, namedDevices, profile]);

    const filteredDevices = useMemo(() => filterAndSortDevices(namedDevices, {
        query,
        profile,
        status,
        selectedDeviceId: filterDeviceId,
    }, sort), [filterDeviceId, namedDevices, profile, query, sort, status]);

    const availableTabs = useMemo(() => DEVICE_TYPE_TABS.filter((tab) => (
        tab.id === 'all' || typeScopeDevices.some((device) => deviceType(device) === tab.id)
    )), [typeScopeDevices]);

    const activeType = availableTabs.some((tab) => tab.id === type) ? type : 'all';

    const tabCounts = useMemo(() => Object.fromEntries(DEVICE_TYPE_TABS.map((tab) => [
        tab.id,
        tab.id === 'all'
            ? filteredDevices.length
            : filteredDevices.filter((device) => deviceType(device) === tab.id).length,
    ])), [filteredDevices]);

    const displayDevices = useMemo(() => (
        activeType === 'all'
            ? filteredDevices
            : filteredDevices.filter((device) => deviceType(device) === activeType)
    ), [activeType, filteredDevices]);

    const visibleExtensions = useMemo(() => (
        extensionColumns(displayDevices, deviceDetails)
    ), [deviceDetails, displayDevices]);

    const availableProfiles = profiles.length > 0
        ? profiles
        : Array.from(new Map(namedDevices.map((device) => [
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
        <div className="device-table-view device-inventory">
            <div className="device-type-tabs" role="tablist" aria-label={t('devices.type_tabs.label', locale === 'zh-CN' ? '设备类型' : 'Device type')}>
                {availableTabs.map((tab) => (
                    <button
                        key={tab.id}
                        type="button"
                        role="tab"
                        aria-selected={activeType === tab.id}
                        className={`device-type-tab ${activeType === tab.id ? 'active' : ''}`}
                        onClick={() => setType(tab.id)}
                    >
                        <span>{typeTabLabel(tab, t, locale)}</span>
                        <b>{tabCounts[tab.id] || 0}</b>
                    </button>
                ))}
            </div>

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
                            <th><SortButton column="host" label={t('devices.host')} sort={sort} setSort={setSort} /></th>
                            <th>{t('devices.reachability')}</th>
                            <th>{t('devices.freshness')}</th>
                            <th>{t('devices.health')}</th>
                            <th>{t('devices.entities')}</th>
                            <th>{t('devices.alerts')}</th>
                            <th>{t('devices.last_check')}</th>
                            {visibleExtensions.map((field) => (
                                <th key={field.key} className="device-extension-heading">
                                    {t(field.label_key, field.label || field.key)}
                                </th>
                            ))}
                            <th><span className="sr-only">{t('devices.actions')}</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayDevices.map((device) => {
                            const fieldsByKey = new Map(
                                metricFields(device, deviceDetails[device.id]).map((field) => [field.key, field])
                            );
                            return (
                                <tr
                                    key={device.id}
                                    className="device-table-row"
                                    onClick={() => openDetail(device)}
                                    onKeyDown={(event) => {
                                        if (event.key === 'Enter' || event.key === ' ') {
                                            event.preventDefault();
                                            openDetail(device);
                                        }
                                    }}
                                    tabIndex={0}
                                >
                                    <td>
                                        <button
                                            type="button"
                                            className="device-name-button"
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                openDetail(device);
                                            }}
                                        >
                                            <strong>{device.name}</strong>
                                            <span>{device.model || device.id}</span>
                                        </button>
                                    </td>
                                    <td>
                                        <div className="device-profile-cell">
                                            <span>{t(device.profile_label_key || `profiles.${device.profile_id}`, device.profile_id)}</span>
                                            <small>{t(`profiles.roles.${device.device_role}`, device.device_role || '—')}</small>
                                        </div>
                                    </td>
                                    <td className="mono">{device.host}:{device.port}</td>
                                    <td><span className={`status-badge ${device.online_status}`}>{t(`status.${device.online_status}`)}</span></td>
                                    <td><span className={`status-badge ${device.freshness_status}`}>{t(`status.${device.freshness_status}`)}</span></td>
                                    <td><span className={`status-badge ${device.health_status}`}>{t(`status.${device.health_status}`)}</span></td>
                                    <td>{device.entity_count ?? '—'}</td>
                                    <td>{device.active_alert_count ?? 0}</td>
                                    <td>{formatDate(device.last_health_check, locale)}</td>
                                    {visibleExtensions.map((field) => {
                                        const value = fieldsByKey.get(field.key);
                                        return (
                                            <td key={field.key} className="device-extension-value" title={value ? displayFieldValue(value, t) : '—'}>
                                                {displayFieldValue(value, t)}
                                            </td>
                                        );
                                    })}
                                    <td>
                                        <button
                                            type="button"
                                            className="icon-button"
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                openDetail(device);
                                            }}
                                            title={t('devices.view_details')}
                                            aria-label={t('devices.view_details')}
                                        >
                                            <Eye size={15} />
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
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
