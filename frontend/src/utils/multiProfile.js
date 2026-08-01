export const PROFILE_META = {
    ccdc_legacy: {
        labelKey: 'profiles.ccdc_legacy',
        roleKey: 'profiles.roles.matrix',
        role: 'matrix',
        matrixCompatible: true,
    },
    ccdm_matrix: {
        labelKey: 'profiles.ccdm_matrix',
        roleKey: 'profiles.roles.matrix',
        role: 'matrix',
        matrixCompatible: true,
    },
    dp12_mux_atc: {
        labelKey: 'profiles.dp12_mux_atc',
        roleKey: 'profiles.roles.channel_device',
        role: 'channel_device',
        matrixCompatible: false,
    },
    visionxs_con: {
        labelKey: 'profiles.visionxs_con',
        roleKey: 'profiles.roles.console',
        role: 'independent_con',
        matrixCompatible: false,
    },
    visionxs_cpu: {
        labelKey: 'profiles.visionxs_cpu',
        roleKey: 'profiles.roles.cpu',
        role: 'independent_cpu',
        matrixCompatible: false,
    },
};

const SENSITIVE_KEYS = new Set([
    'community',
    'password',
    'token',
    'access_token',
    'refresh_token',
    'secret',
    'snmpv3_secret',
    'auth_password',
    'privacy_password',
]);

const normalizeStatus = (value, fallback = 'unknown') => {
    if (value === true) return 'online';
    if (value === false) return 'offline';
    if (value === null || value === undefined || value === '') return fallback;
    return String(value);
};

export function unwrapList(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.items)) return payload.items;
    if (Array.isArray(payload?.results)) return payload.results;
    if (Array.isArray(payload?.data)) return payload.data;
    return [];
}

export function sanitizeSensitiveData(value) {
    if (Array.isArray(value)) return value.map(sanitizeSensitiveData);
    if (!value || typeof value !== 'object') return value;

    return Object.fromEntries(
        Object.entries(value)
            .filter(([key]) => !SENSITIVE_KEYS.has(key.toLowerCase()))
            .map(([key, child]) => [key, sanitizeSensitiveData(child)])
    );
}

export function getProfileMeta(profileId) {
    return PROFILE_META[profileId] || {
        labelKey: null,
        roleKey: 'profiles.roles.unknown',
        matrixCompatible: false,
    };
}

export function isMatrixProfile(device) {
    const profileId = device?.profile_id || device?.profile?.id;
    if (!profileId) return true;
    return Boolean(PROFILE_META[profileId]?.matrixCompatible);
}

export function normalizeDeviceSummary(rawDevice = {}) {
    const device = sanitizeSensitiveData(rawDevice);
    const profileDto = device.profile && typeof device.profile === 'object'
        ? device.profile
        : {};
    const reachabilityDto = device.reachability && typeof device.reachability === 'object'
        ? device.reachability
        : {};
    const healthDto = device.health && typeof device.health === 'object'
        ? device.health
        : {};
    const freshnessDto = device.data_freshness && typeof device.data_freshness === 'object'
        ? device.data_freshness
        : {};
    const profileId = profileDto.id || device.profile_id || (
        typeof device.profile === 'string' ? device.profile : null
    ) || (
        device.system_oid === '1.3.6.1.4.1.32828.3.257.10'
            ? 'ccdm_matrix'
            : device.system_oid === '1.3.6.1.4.1.32828.3.1792.17'
                ? 'dp12_mux_atc'
                : device.system_oid === '1.3.6.1.4.1.32828.3.769.768'
                    ? 'visionxs_con'
                    : device.system_oid === '1.3.6.1.4.1.32828.3.768.768'
                        ? 'visionxs_cpu'
                        : 'ccdc_legacy'
    );
    const profileMeta = getProfileMeta(profileId);
    const onlineStatus = normalizeStatus(
        reachabilityDto.status
        ?? device.online_status
        ?? (typeof device.reachability === 'string' ? device.reachability : null)
        ?? device.last_status
        ?? device.status,
        'offline'
    );
    const healthStatus = normalizeStatus(
        healthDto.status
        ?? device.health_status
        ?? (typeof device.health === 'string' ? device.health : null)
        ?? device.overall_status,
        onlineStatus === 'offline' ? 'offline' : 'ok'
    );
    const activeAlerts = Number(
        device.unacknowledged_alert_count
        ?? device.active_alert_count
        ?? device.active_alerts
        ?? 0
    );

    return {
        ...device,
        id: device.id || device.device_id || device.host,
        name: device.name || device.display_name || device.device_id || device.host,
        host: device.host || device.ip_address || device.ip || '',
        port: Number(device.port ?? device.snmp_port ?? 161),
        profile: {
            ...profileDto,
            id: profileId,
            version: profileDto.version || device.profile_version || null,
            evidence_version: profileDto.evidence_version || device.evidence_version || null,
            label_key: profileDto.label_key || profileMeta.labelKey,
            role: profileDto.role || device.device_role || device.role || profileMeta.role,
        },
        profile_id: profileId,
        profile_version: profileDto.version || device.profile_version || null,
        evidence_version: profileDto.evidence_version || device.evidence_version || null,
        profile_label_key: profileDto.label_key || profileMeta.labelKey,
        model: device.model_name || device.model || device.device_type || device.product_name || profileId,
        model_name: device.model_name || device.model || null,
        serial_number: device.serial_number || null,
        device_role: profileDto.role || device.device_role || device.role || profileMeta.role,
        reachability: {
            ...reachabilityDto,
            status: onlineStatus,
            last_check: reachabilityDto.last_check
                || device.last_health_check
                || device.last_seen_at
                || device.updated_at
                || null,
            latency_ms: reachabilityDto.latency_ms ?? device.latency_ms ?? null,
        },
        online_status: onlineStatus,
        last_status: onlineStatus,
        health: {
            ...healthDto,
            status: healthStatus,
            warning_count: Number(healthDto.warning_count ?? device.warning_count ?? 0),
            critical_count: Number(healthDto.critical_count ?? device.critical_count ?? 0),
        },
        health_status: healthStatus,
        unacknowledged_alert_count: Number.isFinite(activeAlerts) ? activeAlerts : 0,
        active_alert_count: Number.isFinite(activeAlerts) ? activeAlerts : 0,
        data_freshness: {
            ...freshnessDto,
            status: normalizeStatus(
                freshnessDto.status
                ?? device.freshness_status
                ?? (typeof device.data_freshness === 'string' ? device.data_freshness : null)
                ?? device.freshness,
                device.is_stale ? 'stale' : 'unknown'
            ),
            last_full_poll: freshnessDto.last_full_poll
                || device.last_full_poll
                || device.last_full_poll_at
                || device.last_poll
                || null,
            age_seconds: freshnessDto.age_seconds ?? device.age_seconds ?? null,
        },
        freshness_status: normalizeStatus(
            freshnessDto.status
            ?? device.freshness_status
            ?? (typeof device.data_freshness === 'string' ? device.data_freshness : null)
            ?? device.freshness,
            device.is_stale ? 'stale' : 'unknown'
        ),
        last_health_check: reachabilityDto.last_check
            || device.last_health_check
            || device.last_seen_at
            || device.updated_at
            || null,
        last_full_poll: freshnessDto.last_full_poll
            || device.last_full_poll
            || device.last_full_poll_at
            || device.last_poll
            || null,
        credential_configured: Boolean(
            device.credential_configured
            ?? device.community_configured
            ?? rawDevice.community
        ),
    };
}

export function normalizeDeviceSummaries(payload) {
    return unwrapList(payload)
        .map(normalizeDeviceSummary)
        .filter((device) => Boolean(device.id));
}

export function stableStringify(value) {
    if (Array.isArray(value)) {
        return `[${value.map(stableStringify).join(',')}]`;
    }
    if (value && typeof value === 'object') {
        return `{${Object.keys(value).sort().map((key) => (
            `${JSON.stringify(key)}:${stableStringify(value[key])}`
        )).join(',')}}`;
    }
    return JSON.stringify(value);
}

export function getStableEntityKey(entity = {}) {
    if (entity.entity_key) return String(entity.entity_key);
    const tableId = entity.table_id || entity.entity_type || 'entity';
    return `${tableId}:${stableStringify(entity.index_key || entity.indexes || {})}`;
}

export function normalizeField(rawField, fallbackKey = 'field') {
    const field = rawField && typeof rawField === 'object' && !Array.isArray(rawField)
        ? rawField
        : { value: rawField, raw: rawField };
    const key = String(field.key || field.field_key || field.id || field.name || fallbackKey);
    const raw = field.raw ?? field.raw_value ?? field.value ?? null;
    const value = field.value ?? field.normalized ?? field.normalized_value ?? raw;
    const supported = field.supported ?? field.is_supported ?? true;
    const present = field.present ?? field.is_present ?? true;
    const stale = field.stale ?? field.is_stale ?? field.status === 'stale';
    const status = !supported
        ? 'unsupported'
        : !present
            ? 'absent'
            : stale
                ? 'stale'
                : normalizeStatus(field.status, value === null ? 'unknown' : 'ok');

    return {
        ...field,
        key,
        label: field.label || field.display_name || key,
        label_key: field.label_key || null,
        semantic: field.semantic || field.kind || null,
        raw,
        value,
        unit: field.unit || null,
        status,
        supported: Boolean(supported),
        present: Boolean(present),
        stale: Boolean(stale),
        updated_at: field.updated_at || field.last_seen_at || null,
    };
}

function fieldsFromMaps(entity) {
    const rawValues = entity.raw_values || {};
    const normalizedValues = entity.normalized_values || {};
    const fieldStates = entity.field_states || {};
    const keys = new Set([
        ...Object.keys(rawValues),
        ...Object.keys(normalizedValues),
        ...Object.keys(fieldStates),
    ]);

    return [...keys].map((key) => normalizeField({
        key,
        raw: rawValues[key],
        value: normalizedValues[key] ?? rawValues[key],
        ...(fieldStates[key] || {}),
    }, key));
}

export function normalizeEntity(rawEntity = {}) {
    const fieldInput = rawEntity.fields || rawEntity.values;
    const fields = Array.isArray(fieldInput)
        ? fieldInput.map((field, index) => normalizeField(field, `field-${index}`))
        : fieldInput && typeof fieldInput === 'object'
            ? Object.entries(fieldInput).map(([key, field]) => normalizeField(field, key))
            : fieldsFromMaps(rawEntity);

    return {
        ...sanitizeSensitiveData(rawEntity),
        entity_key: getStableEntityKey(rawEntity),
        table_id: rawEntity.table_id || rawEntity.entity_type || 'entity',
        entity_type: rawEntity.entity_type || rawEntity.table_id || 'entity',
        label: rawEntity.label || rawEntity.display_name || rawEntity.entity_key || rawEntity.entity_type,
        label_key: rawEntity.label_key || null,
        index_key: rawEntity.index_key || rawEntity.indexes || {},
        present: Boolean(rawEntity.present ?? rawEntity.is_present ?? true),
        stale: Boolean(rawEntity.stale ?? rawEntity.is_stale ?? false),
        status: normalizeStatus(
            rawEntity.status,
            rawEntity.is_stale ? 'stale' : rawEntity.is_present === false ? 'absent' : 'ok'
        ),
        updated_at: rawEntity.updated_at || rawEntity.last_seen_at || null,
        fields,
    };
}

export function normalizeSection(rawSection = {}, index = 0) {
    const fieldInput = rawSection.fields || rawSection.values || [];
    const entityInput = rawSection.entities || rawSection.rows || [];
    const fields = Array.isArray(fieldInput)
        ? fieldInput.map((field, fieldIndex) => normalizeField(field, `field-${fieldIndex}`))
        : Object.entries(fieldInput).map(([key, field]) => normalizeField(field, key));

    return {
        ...sanitizeSensitiveData(rawSection),
        key: String(rawSection.key || rawSection.section_id || rawSection.id || `section-${index}`),
        label: rawSection.label || rawSection.title || rawSection.name || `section-${index}`,
        label_key: rawSection.label_key || null,
        order: Number(rawSection.order ?? index),
        status: normalizeStatus(rawSection.status, 'unknown'),
        fields,
        entities: unwrapList(entityInput).map(normalizeEntity),
    };
}

function groupLooseEntities(rawEntities) {
    const groups = new Map();
    unwrapList(rawEntities).forEach((entity) => {
        const sectionKey = entity.section_id || entity.section_key || entity.category || 'entities';
        if (!groups.has(sectionKey)) {
            groups.set(sectionKey, {
                key: sectionKey,
                label: sectionKey,
                label_key: entity.section_label_key || null,
                fields: [],
                entities: [],
            });
        }
        groups.get(sectionKey).entities.push(normalizeEntity(entity));
    });
    return [...groups.values()];
}

export function normalizeDeviceDetail(payload, entityPayload, fallbackDevice = {}) {
    const source = payload?.data || payload || {};
    const device = normalizeDeviceSummary(source.device || fallbackDevice);
    const rawSections = Array.isArray(source.sections)
        ? source.sections
        : source.sections && typeof source.sections === 'object'
            ? Object.entries(source.sections).map(([key, section]) => ({ key, ...section }))
            : [];
    const sections = rawSections
        .map(normalizeSection)
        .sort((left, right) => left.order - right.order);
    const looseSections = groupLooseEntities(entityPayload);

    looseSections.forEach((looseSection) => {
        const existing = sections.find((section) => section.key === looseSection.key);
        if (existing) {
            const existingKeys = new Set(existing.entities.map((entity) => entity.entity_key));
            existing.entities.push(
                ...looseSection.entities.filter((entity) => !existingKeys.has(entity.entity_key))
            );
        } else {
            sections.push(looseSection);
        }
    });

    return {
        ...sanitizeSensitiveData(source),
        device,
        profile_id: source.profile_id || device.profile_id,
        profile_version: source.profile_version || device.profile_version,
        sections: sections.sort((left, right) => left.order - right.order),
    };
}

export function normalizeAlert(rawAlert = {}) {
    const alert = sanitizeSensitiveData(rawAlert);
    const persistedId = alert.id ?? alert.alert_id ?? null;
    return {
        ...alert,
        id: persistedId,
        alert_id: persistedId,
        device_id: alert.device_id ?? null,
        endpoint_id: alert.endpoint_id ?? null,
        entity_key: alert.entity_key ?? null,
        alert_type: alert.alert_type || alert.type || 'metric',
        severity: normalizeStatus(alert.severity, 'info').toLowerCase(),
        is_resolved: Boolean(alert.is_resolved),
        created_at: alert.created_at || alert.timestamp || null,
    };
}

export function normalizeAlerts(payload) {
    return unwrapList(payload).map(normalizeAlert);
}

export function keyboardMouseState(value) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
        const hasKeyboard = Object.prototype.hasOwnProperty.call(value, 'keyboard');
        const hasMouse = Object.prototype.hasOwnProperty.call(value, 'mouse');
        return {
            keyboard: Boolean(value.keyboard),
            mouse: Boolean(value.mouse),
            known: hasKeyboard || hasMouse,
            source: value.source || null,
            raw: value,
        };
    }

    const normalized = String(value ?? 'none');
    return {
        keyboard: normalized === 'keyboard' || normalized === 'keyboardMouse',
        mouse: normalized === 'mouse' || normalized === 'keyboardMouse',
        known: ['none', 'keyboard', 'mouse', 'keyboardMouse'].includes(normalized),
        source: null,
        raw: value,
    };
}

export function hidBoundaryState(value) {
    const normalized = String(value ?? 'unknown');
    return {
        state: normalized,
        connected: normalized === 'connected' || normalized === 'initialized',
        initialized: normalized === 'initialized',
        deviceTypeDifferentiated: false,
    };
}

function normalizedPeripheralKey(field = {}) {
    return String(field.key || field.field_key || field.name || '')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_');
}

export function getPeripheralFieldKind(field = {}) {
    const key = normalizedPeripheralKey(field);
    const semantic = String(field.semantic || field.kind || '').toLowerCase();
    const value = field.value ?? field.normalized ?? field.normalized_value;

    if (
        semantic === 'keyboard_mouse'
        || (
            value
            && typeof value === 'object'
            && !Array.isArray(value)
            && (
                Object.prototype.hasOwnProperty.call(value, 'keyboard')
                || Object.prototype.hasOwnProperty.call(value, 'mouse')
            )
        )
        || [
            'keyboard_mouse',
            'keyboard_mouse_status',
            'keyboard_mouse_connection',
            'console_ps2_connection',
            'console_usbconnection',
            'console_usb_connection',
            'ep_console_ps2',
            'ep_console_usb',
            'ep_target_ps2',
            'con_console_ps2',
            'con_console_usb',
            'target_ps2_connection',
        ].includes(key)
    ) {
        return 'keyboard_mouse';
    }

    if (
        semantic === 'hid'
        || key === 'usb_hid_status'
        || key === 'target_usb_hid'
        || key === 'ep_target_usb_hid'
        || key === 'cpu_channel_target_usb_hid'
        || key.endsWith('_usb_hid')
    ) {
        return 'hid';
    }

    if (semantic === 'keyboard' || key === 'keyboard' || key.endsWith('_keyboard')) {
        return 'keyboard';
    }
    if (semantic === 'mouse' || key === 'mouse' || key.endsWith('_mouse')) {
        return 'mouse';
    }
    return null;
}

function comparable(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'number') return value;
    const timestamp = Date.parse(value);
    if (!Number.isNaN(timestamp) && String(value).includes('-')) return timestamp;
    return String(value).toLocaleLowerCase();
}

export function filterAndSortDevices(devices, filters = {}, sort = {}) {
    const query = String(filters.query || '').trim().toLocaleLowerCase();
    const status = filters.status || 'all';
    const profile = filters.profile || 'all';
    const selectedDeviceId = filters.selectedDeviceId || 'all';
    const key = sort.key || 'name';
    const direction = sort.direction === 'desc' ? -1 : 1;

    return devices
        .filter((device) => {
            if (selectedDeviceId !== 'all' && device.id !== selectedDeviceId) return false;
            if (status !== 'all' && device.online_status !== status && device.health_status !== status) return false;
            if (profile !== 'all' && device.profile_id !== profile) return false;
            if (!query) return true;
            return [
                device.name,
                device.id,
                device.host,
                device.model,
                device.profile_id,
            ].some((value) => String(value || '').toLocaleLowerCase().includes(query));
        })
        .slice()
        .sort((left, right) => {
            const leftValue = comparable(left[key]);
            const rightValue = comparable(right[key]);
            if (leftValue < rightValue) return -1 * direction;
            if (leftValue > rightValue) return 1 * direction;
            return String(left.id).localeCompare(String(right.id));
        });
}

export function normalizePagedResult(payload, fallbackPageSize = 50) {
    const items = unwrapList(payload);
    return {
        items,
        total: Number(payload?.total ?? payload?.count ?? items.length),
        page: Number(payload?.page ?? 1),
        page_size: Number(payload?.page_size ?? payload?.limit ?? fallbackPageSize),
    };
}
