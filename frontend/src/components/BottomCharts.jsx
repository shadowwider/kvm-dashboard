import { useEffect, useMemo, useState } from 'react';
import api from '../utils/api';
import { useTranslation } from '../i18n';
import { useStore } from '../store/mainStore';
import { getEndpointDeviceState } from '../utils/endpointStatus';
import { unwrapList } from '../utils/multiProfile';

const SERIES_COLORS = ['#00d4ff', '#00ff88', '#ffb300', '#ff3355', '#a78bfa'];

function NoData({ children }) {
    return <div className="chart-no-data">{children}</div>;
}

function TemperatureChart({ devices, selectedDeviceId }) {
    const { t } = useTranslation();
    const getDisplayName = useStore((state) => state.getDisplayName);
    const [series, setSeries] = useState([]);
    const targets = useMemo(() => (
        selectedDeviceId
            ? devices.filter((device) => device.id === selectedDeviceId)
            : devices
    ), [devices, selectedDeviceId]);

    useEffect(() => {
        let active = true;
        Promise.all(targets.map(async (device, index) => {
            try {
                const response = await api.get('/metrics/history', {
                    params: {
                        oid_name: 'temperature',
                        device_id: device.id,
                        hours: 24,
                    },
                });
                const data = unwrapList(response.data)
                    .map((point) => ({
                        ...point,
                        value_num: Number(point.value_num ?? point.value),
                    }))
                    .filter((point) => Number.isFinite(point.value_num));
                return {
                    id: device.id,
                    label: getDisplayName(device.id, device.name),
                    data,
                    color: SERIES_COLORS[index % SERIES_COLORS.length],
                };
            } catch {
                return {
                    id: device.id,
                    label: getDisplayName(device.id, device.name),
                    data: [],
                    color: SERIES_COLORS[index % SERIES_COLORS.length],
                };
            }
        })).then((result) => {
            if (active) setSeries(result);
        });
        return () => {
            active = false;
        };
    }, [getDisplayName, targets]);

    const populated = series.filter((item) => item.data.length > 0);
    const values = populated.flatMap((item) => item.data.map((point) => point.value_num));
    const minimum = values.length > 0 ? Math.min(...values) : 0;
    const maximum = values.length > 0 ? Math.max(...values) : 1;
    const padding = Math.max((maximum - minimum) * 0.15, 2);
    const minValue = minimum - padding;
    const maxValue = maximum + padding;
    const width = 300;
    const height = 72;
    const yFor = (value) => height - ((value - minValue) / (maxValue - minValue || 1)) * height;
    const lineFor = (data) => data.map((point, index) => {
        const x = data.length === 1 ? width / 2 : (index / (data.length - 1)) * width;
        return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${yFor(point.value_num).toFixed(1)}`;
    }).join(' ');

    return (
        <div className="chart-panel">
            <div className="chart-title">{t('dashboard.temp_title')}<span>°C</span></div>
            {populated.length === 0 ? (
                <NoData>{t('charts.no_history')}</NoData>
            ) : (
                <>
                    <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
                        {[18, 36, 54].map((y) => (
                            <line
                                key={y}
                                x1="0"
                                y1={y}
                                x2={width}
                                y2={y}
                                stroke="rgba(0,212,255,.05)"
                                strokeWidth="1"
                            />
                        ))}
                        {populated.map((item) => (
                            <path
                                key={item.id}
                                d={lineFor(item.data)}
                                fill="none"
                                stroke={item.color}
                                strokeWidth="1.5"
                            />
                        ))}
                    </svg>
                    <div className="chart-legend">
                        {populated.map((item) => (
                            <span key={item.id}>
                                <i style={{ background: item.color }} />
                                {item.label}
                            </span>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}

function collectFanFields(detail) {
    if (!detail?.sections) return [];
    const fields = detail.sections.flatMap((section) => [
        ...section.fields.map((field, index) => ({
            ...field,
            renderKey: `${section.key}:field:${field.key}:${index}`,
        })),
        ...section.entities.flatMap((entity) => entity.fields.map((field, index) => ({
            ...field,
            renderKey: `${section.key}:${entity.entity_key}:${field.key}:${index}`,
        }))),
    ]);
    return fields.filter((field) => {
        const key = field.key.toLowerCase();
        return key.includes('fan') && (key.includes('speed') || key.includes('rpm') || /^fan\d+$/.test(key));
    });
}

function FanStatus({ devices, selectedDeviceId }) {
    const { t } = useTranslation();
    const targetDevice = selectedDeviceId
        ? devices.find((device) => device.id === selectedDeviceId)
        : devices.find((device) => device.online_status === 'online') || devices[0];
    const detail = useStore((state) => (
        targetDevice ? state.deviceDetails[targetDevice.id] : null
    ));
    const detailLoading = useStore((state) => (
        targetDevice ? state.detailLoading[targetDevice.id] : false
    ));
    const fetchDeviceDetail = useStore((state) => state.fetchDeviceDetail);

    useEffect(() => {
        if (targetDevice) fetchDeviceDetail(targetDevice.id);
    }, [fetchDeviceDetail, targetDevice]);

    const fans = collectFanFields(detail);

    return (
        <div className="chart-panel">
            <div className="chart-title">{t('dashboard.fan_title')}<span>RPM</span></div>
            {detailLoading ? (
                <NoData>{t('common.loading')}</NoData>
            ) : fans.length === 0 ? (
                <NoData>{t('dashboard.fan_no_data')}</NoData>
            ) : (
                <div className="fan-status-list">
                    {fans.map((fan) => (
                        <div key={fan.renderKey} className={`fan-status-item ${fan.status}`}>
                            <span>{t(fan.label_key, fan.label || fan.key)}</span>
                            <strong>
                                {fan.supported === false
                                    ? t('status.unsupported')
                                    : fan.present === false
                                        ? t('status.absent')
                                        : `${fan.value ?? '—'}${fan.unit ? ` ${fan.unit}` : ''}`}
                            </strong>
                            <small>{t(`status.${fan.status}`, fan.status)}</small>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function AvailabilitySnapshot({ devices, endpoints }) {
    const { t } = useTranslation();
    const matrixEndpointCount = endpoints.length;
    const onlineEndpoints = endpoints.filter((endpoint) => (
        ['online', 'ready'].includes(getEndpointDeviceState(endpoint))
    )).length;
    const sourceTotal = matrixEndpointCount > 0 ? matrixEndpointCount : devices.length;
    const sourceOnline = matrixEndpointCount > 0
        ? onlineEndpoints
        : devices.filter((device) => device.online_status === 'online').length;
    const rate = sourceTotal > 0 ? (sourceOnline / sourceTotal) * 100 : null;

    return (
        <div className="chart-panel">
            <div className="chart-title">{t('charts.availability_title')}<span>%</span></div>
            <div className="availability-snapshot">
                <strong>{rate === null ? '—' : `${rate.toFixed(1)}%`}</strong>
                <div className="availability-track">
                    <span style={{ width: `${rate ?? 0}%` }} />
                </div>
                <div className="availability-meta">
                    <span>{t('charts.online_now')}: {sourceOnline}</span>
                    <span>{t('charts.total_now')}: {sourceTotal}</span>
                </div>
                <small>{t('charts.snapshot_only')}</small>
            </div>
        </div>
    );
}

export default function BottomCharts({ devices, selectedDeviceId, endpoints = [] }) {
    return (
        <>
            <TemperatureChart devices={devices} selectedDeviceId={selectedDeviceId} />
            <FanStatus devices={devices} selectedDeviceId={selectedDeviceId} />
            <AvailabilitySnapshot devices={devices} endpoints={endpoints} />
        </>
    );
}
