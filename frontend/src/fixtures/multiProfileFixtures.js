const now = '2026-08-01T08:00:00Z';

const profileDefinitions = [
    {
        id: 'ccdc_legacy',
        version: '1.0.0',
        evidence_version: 'fixture=1;profile=ccdc',
        product: 'ControlCenter-Compact',
        role: 'matrix',
        system_oid: '1.3.6.1.4.1.32828.3.257.16',
        label_key: 'profiles.ccdc_legacy',
        section_keys: ['identity', 'health', 'power', 'environment', 'network', 'cards_ports'],
    },
    {
        id: 'ccdm_matrix',
        version: '1.0.0',
        evidence_version: 'fixture=1;profile=ccdm',
        product: 'ControlCenter-Digital',
        role: 'matrix',
        system_oid: '1.3.6.1.4.1.32828.3.257.10',
        label_key: 'profiles.ccdm_matrix',
        section_keys: ['identity', 'health', 'power', 'environment', 'network', 'cards_ports'],
    },
    {
        id: 'dp12_mux_atc',
        version: '1.0.0',
        evidence_version: 'fixture=1;profile=dp12',
        product: 'DP1.2-MUX3-ATC',
        role: 'channel_device',
        system_oid: '1.3.6.1.4.1.32828.3.1792.17',
        label_key: 'profiles.dp12_mux_atc',
        section_keys: ['identity', 'power', 'environment', 'video', 'usb_hid', 'errors'],
    },
    {
        id: 'visionxs_con',
        version: '1.0.0',
        evidence_version: 'fixture=1;profile=visionxs-con',
        product: 'VisionXS CON',
        role: 'independent_con',
        system_oid: '1.3.6.1.4.1.32828.3.769.768',
        label_key: 'profiles.visionxs_con',
        section_keys: ['identity', 'power', 'environment', 'network', 'video', 'usb_hid', 'links', 'errors'],
    },
    {
        id: 'visionxs_cpu',
        version: '1.0.0',
        evidence_version: 'fixture=1;profile=visionxs-cpu',
        product: 'VisionXS CPU',
        role: 'independent_cpu',
        system_oid: '1.3.6.1.4.1.32828.3.768.768',
        label_key: 'profiles.visionxs_cpu',
        section_keys: ['identity', 'power', 'environment', 'network', 'video', 'usb_hid', 'links', 'errors'],
    },
];

function device(profile, index, overrides = {}) {
    return {
        id: `fixture-${profile.id}`,
        name: `Fixture / ${profile.product}`,
        host: `192.168.1.${20 + index}`,
        port: 161,
        location: 'Fixture Lab',
        description: null,
        profile: {
            id: profile.id,
            version: profile.version,
            evidence_version: profile.evidence_version,
            label_key: profile.label_key,
            role: profile.role,
        },
        system_oid: profile.system_oid,
        model_name: profile.product,
        serial_number: `FIX-${String(index + 1).padStart(4, '0')}`,
        credential_configured: true,
        is_active: true,
        reachability: { status: 'online', last_check: now, latency_ms: 8 + index },
        data_freshness: { status: 'fresh', last_full_poll: now, age_seconds: 0 },
        health: { status: 'ok', warning_count: 0, critical_count: 0 },
        endpoint_count: profile.role === 'matrix' ? 4 : 0,
        entity_count: 4 + index,
        active_alert_count: 0,
        created_at: now,
        updated_at: now,
        ...overrides,
    };
}

export const fixtureProfiles = profileDefinitions;

export const fixtureDevices = profileDefinitions.map((profile, index) => device(
    profile,
    index,
    profile.id === 'dp12_mux_atc'
        ? {
            health: { status: 'warning', warning_count: 1, critical_count: 0 },
            active_alert_count: 1,
        }
        : {}
));

function field(key, value, options = {}) {
    return {
        key,
        label_key: `fields.${key}`,
        raw: options.raw ?? value,
        value,
        unit: options.unit ?? null,
        status: options.status ?? 'ok',
        supported: options.supported ?? true,
        present: options.present ?? true,
        stale: options.stale ?? false,
        updated_at: now,
    };
}

function identitySection(summary) {
    return {
        key: 'identity',
        label_key: 'detail.sections.identity',
        order: 10,
        status: 'ok',
        fields: [
            field('model_name', summary.model_name),
            field('serial_number', summary.serial_number),
            field('system_oid', summary.system_oid),
        ],
        entities: [],
    };
}

function entity(entityKey, entityType, label, index, fields, options = {}) {
    return {
        entity_key: entityKey,
        entity_type: entityType,
        label,
        index_key: [{ name: `${entityType}_index`, value: index }],
        status: options.status ?? 'ok',
        present: options.present ?? true,
        stale: options.stale ?? false,
        updated_at: now,
        fields,
    };
}

const keyboardMouseValues = ['none', 'keyboard', 'mouse', 'keyboardMouse'];

function keyboardMouseValue(value, source) {
    return {
        keyboard: value === 'keyboard' || value === 'keyboardMouse',
        mouse: value === 'mouse' || value === 'keyboardMouse',
        source,
    };
}

function peripheralFields(summary, index) {
    const value = keyboardMouseValues[index % keyboardMouseValues.length];
    const keyboardMouse = (key) => field(key, keyboardMouseValue(value, key));

    if (summary.profile.id === 'visionxs_con') {
        return [keyboardMouse('console_usbconnection')];
    }
    if (summary.profile.id === 'visionxs_cpu') {
        return [field('target_usb_hid', 'initialized')];
    }
    if (summary.profile.id === 'dp12_mux_atc') {
        return [
            keyboardMouse('console_ps2_connection'),
            keyboardMouse('console_usbconnection'),
            field('cpu_channel_target_usb_hid', 'connected'),
        ];
    }
    return [
        keyboardMouse('console_ps2_connection'),
        keyboardMouse('console_usbconnection'),
        keyboardMouse('target_ps2_connection'),
        field('target_usb_hid', index % 2 === 0 ? 'initialized' : 'connected'),
    ];
}

export const fixtureDeviceDetails = Object.fromEntries(
    fixtureDevices.map((summary, index) => {
        const fanField = index === 0
            ? field('fan_speed', 3200, { raw: '3200 RPM', unit: 'RPM' })
            : index === 1
                ? field('fan_speed', 0, { raw: '0 RPM', unit: 'RPM', status: 'critical' })
                : index === 2
                    ? field('fan_speed', null, { supported: false, present: false, status: 'unsupported' })
                    : index === 3
                        ? field('fan_speed', null, { present: false, status: 'absent' })
                        : field('fan_speed', 2800, { unit: 'RPM', stale: true, status: 'stale' });
        const sections = [
            identitySection(summary),
            {
                key: 'environment',
                label_key: 'detail.sections.environment',
                order: 40,
                status: fanField.status,
                fields: [
                    field('temperature', 39 + index, { unit: '°C' }),
                    fanField,
                ],
                entities: [],
            },
            {
                key: 'usb_hid',
                label_key: 'detail.sections.usb_hid',
                order: 70,
                status: 'ok',
                fields: peripheralFields(summary, index),
                entities: [],
            },
            {
                key: summary.profile.role === 'matrix' ? 'cards_ports' : 'links',
                label_key: summary.profile.role === 'matrix'
                    ? 'detail.sections.cards_ports'
                    : 'detail.sections.links',
                order: 80,
                status: 'ok',
                fields: [],
                entities: [
                    entity(
                        `${summary.profile.role === 'matrix' ? 'port' : 'link'}_table:index=1`,
                        summary.profile.role === 'matrix' ? 'port' : 'link_channel',
                        summary.profile.role === 'matrix' ? 'Port 1' : 'Link 1',
                        1,
                        [
                            field('connection_status', 'connected'),
                            field('signal_status', index === 2 ? 'warning' : 'ok', {
                                status: index === 2 ? 'warning' : 'ok',
                            }),
                        ]
                    ),
                ],
            },
        ];

        return [summary.id, { device: summary, sections }];
    })
);

export const fixtureDiscoveryConfig = {
    cidr: '192.168.1.0/24',
    snmp_port: 161,
    timeout_seconds: 0.5,
    retries: 0,
    concurrency: 64,
    enabled: true,
    scan_on_startup: false,
    credential_configured: true,
    updated_at: now,
};

export const fixtureDiscoveryJobs = [
    {
        id: 42,
        status: 'completed',
        cidr: fixtureDiscoveryConfig.cidr,
        total_hosts: 254,
        scanned_hosts: 254,
        responded_hosts: 5,
        recognized_hosts: 5,
        imported_devices: 4,
        updated_devices: 1,
        unsupported_devices: 0,
        no_response_hosts: 249,
        error_count: 0,
        started_at: '2026-08-01T07:58:00Z',
        finished_at: now,
        last_error: null,
    },
];

export const fixtureAuditLogs = [
    {
        id: 1001,
        actor: { id: 1, username: 'admin', role: 'admin' },
        action: 'discovery.scan',
        target: { type: 'discovery_job', id: '42' },
        result: 'success',
        request_id: 'fixture-request-1001',
        ip_address: '127.0.0.1',
        user_agent: 'Fixture Browser',
        change_summary: { cidr: fixtureDiscoveryConfig.cidr, imported_devices: 4 },
        created_at: now,
    },
];
