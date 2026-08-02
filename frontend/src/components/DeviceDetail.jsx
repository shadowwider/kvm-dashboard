import { RefreshCw, X } from 'lucide-react';
import { useTranslation } from '../i18n';
import {
    getPeripheralFieldKind,
    hidBoundaryState,
    keyboardMouseState,
} from '../utils/multiProfile';

function formatDate(value, locale) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString(locale);
}

function displayValue(value) {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
}

function StatusBadge({ status, t }) {
    const normalized = status || 'unknown';
    return (
        <span className={`detail-status ${normalized}`}>
            {t(`status.${normalized}`, normalized)}
        </span>
    );
}

function FieldValue({ field, t }) {
    const peripheralKind = getPeripheralFieldKind(field);

    if (peripheralKind === 'keyboard_mouse') {
        const state = keyboardMouseState(field.value);
        if (!state.known) {
            return <span className="detail-field-value">{t('status.unknown')}</span>;
        }
        return (
            <div className="boundary-state">
                <span className={state.keyboard ? 'connected' : 'disconnected'}>
                    {t('detail.keyboard')}: {state.keyboard ? t('status.connected') : t('status.disconnected')}
                </span>
                <span className={state.mouse ? 'connected' : 'disconnected'}>
                    {t('detail.mouse')}: {state.mouse ? t('status.connected') : t('status.disconnected')}
                </span>
            </div>
        );
    }

    if (peripheralKind === 'hid') {
        const state = hidBoundaryState(field.value);
        return (
            <div className="boundary-state">
                <span className={state.connected ? 'connected' : 'disconnected'}>
                    {displayValue(field.value)}
                </span>
                <span className="boundary-note">{t('detail.hid_not_differentiated')}</span>
            </div>
        );
    }

    if (peripheralKind === 'keyboard' || peripheralKind === 'mouse') {
        const connected = field.value === true
            || field.value === 'connected'
            || field.value === 'initialized';
        return (
            <span className={`detail-field-value ${connected ? 'connected' : 'disconnected'}`}>
                {connected ? t('status.connected') : t('status.disconnected')}
            </span>
        );
    }

    return (
        <span className="detail-field-value">
            {displayValue(field.value)}
            {field.unit ? ` ${field.unit}` : ''}
        </span>
    );
}

function FieldRow({ field, locale, t }) {
    const label = t(field.label_key, field.label || field.key);
    const rawDiffers = field.raw !== null
        && field.raw !== undefined
        && String(field.raw) !== String(field.value);

    return (
        <div className="detail-field-row">
            <div className="detail-field-name">{label}</div>
            <div className="detail-field-main">
                <FieldValue field={field} t={t} />
                <StatusBadge status={field.status} t={t} />
            </div>
            <div className="detail-field-meta">
                {rawDiffers && <span>{t('detail.raw')}: {displayValue(field.raw)}</span>}
                <span>{t('detail.updated_at')}: {formatDate(field.updated_at, locale)}</span>
            </div>
        </div>
    );
}

function EntityBlock({ entity, locale, t }) {
    const fields = Array.isArray(entity.fields) ? entity.fields : [];
    return (
        <div className="detail-entity">
            <div className="detail-entity-header">
                <div>
                    <strong>{t(entity.label_key, entity.label || entity.entity_type)}</strong>
                    <span className="detail-entity-key">{entity.entity_key}</span>
                </div>
                <StatusBadge status={entity.status} t={t} />
            </div>
            {entity.index_key && (
                <div className="detail-indexes">
                    {(Array.isArray(entity.index_key)
                        ? entity.index_key
                        : Object.entries(entity.index_key).map(([name, value]) => ({ name, value }))
                    ).map((item) => (
                        <span key={`${item.name}:${item.value}`}>{item.name}: {displayValue(item.value)}</span>
                    ))}
                </div>
            )}
            <div className="detail-fields">
                {fields.map((field, index) => (
                    <FieldRow
                        key={`${entity.entity_key}:${field.key}:${index}`}
                        field={field}
                        locale={locale}
                        t={t}
                    />
                ))}
            </div>
        </div>
    );
}

export default function DeviceDetail({
    detail,
    error,
    loading,
    onClose,
    onRefresh,
}) {
    const { t, locale } = useTranslation();
    const sections = Array.isArray(detail?.sections) ? detail.sections : [];
    const device = detail?.device;

    return (
        <div className="device-detail-panel">
            <div className="device-detail-header">
                <div>
                    <span className="device-detail-eyebrow">
                        {device?.profile_label_key
                            ? t(device.profile_label_key)
                            : t('detail.device')}
                    </span>
                    <h2>{device?.name || t('detail.device')}</h2>
                    {device && (
                        <span>{device.host}:{device.port}</span>
                    )}
                </div>
                <div className="device-detail-actions">
                    <button
                        className="icon-button"
                        onClick={onRefresh}
                        title={t('common.refresh')}
                        aria-label={t('common.refresh')}
                    >
                        <RefreshCw size={15} />
                    </button>
                    <button
                        className="icon-button"
                        onClick={onClose}
                        title={t('common.close')}
                        aria-label={t('common.close')}
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            <div className="device-detail-body">
                {device && (
                    <div className="detail-device-overview">
                        <StatusBadge status={device.online_status} t={t} />
                        <StatusBadge status={device.freshness_status} t={t} />
                        <StatusBadge status={device.health_status} t={t} />
                    </div>
                )}
                {loading && <div className="detail-empty">{t('common.loading')}</div>}
                {error && <div className="detail-error">{t('detail.load_failed')}: {error}</div>}
                {!loading && !error && sections.length === 0 && (
                    <div className="detail-empty">{t('detail.no_sections')}</div>
                )}

                {sections.map((section) => (
                    <section key={section.key} className="detail-section">
                        <div className="detail-section-header">
                            <h3>{t(section.label_key, section.label || section.key)}</h3>
                            <StatusBadge status={section.status} t={t} />
                        </div>
                        <div className="detail-fields">
                            {(section.fields || []).map((field, index) => (
                                <FieldRow
                                    key={`${section.key}:${field.key}:${index}`}
                                    field={field}
                                    locale={locale}
                                    t={t}
                                />
                            ))}
                        </div>
                        {(section.entities || []).length > 0 && (
                            <div className="detail-entities">
                                {(section.entities || []).map((entity) => (
                                    <EntityBlock
                                        key={entity.entity_key}
                                        entity={entity}
                                        locale={locale}
                                        t={t}
                                    />
                                ))}
                            </div>
                        )}
                    </section>
                ))}
            </div>
        </div>
    );
}
