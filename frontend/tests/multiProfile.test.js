import assert from 'node:assert/strict';
import test from 'node:test';

import {
    fixtureDeviceDetails,
    fixtureDevices,
    fixtureProfiles,
} from '../src/fixtures/multiProfileFixtures.js';
import {
    getPeripheralFieldKind,
    hidBoundaryState,
    keyboardMouseState,
    normalizeDeviceDetail,
    normalizeDeviceSummary,
    sanitizeSensitiveData,
} from '../src/utils/multiProfile.js';

const expectedProfiles = [
    'ccdc_legacy',
    'ccdm_matrix',
    'dp12_mux_atc',
    'visionxs_con',
    'visionxs_cpu',
];

test('normalizes the frozen nested DeviceSummary DTO without object coercion', () => {
    const raw = {
        id: 'sim-ccdm-01',
        name: 'SIM / CCDM',
        host: '192.168.1.20',
        profile: {
            id: 'ccdm_matrix',
            version: '2.3.1',
            role: 'matrix',
            label_key: 'profiles.ccdm_matrix',
        },
        reachability: {
            status: 'online',
            last_check: '2026-08-01T08:00:00Z',
            latency_ms: 12,
        },
        health: {
            status: 'warning',
            warning_count: 1,
            critical_count: 0,
        },
        data_freshness: {
            status: 'fresh',
            last_full_poll: '2026-08-01T07:59:45Z',
            age_seconds: 15,
        },
    };

    const normalized = normalizeDeviceSummary(raw);

    assert.equal(normalized.profile_id, 'ccdm_matrix');
    assert.equal(normalized.profile_version, '2.3.1');
    assert.equal(normalized.device_role, 'matrix');
    assert.equal(normalized.online_status, 'online');
    assert.equal(normalized.health_status, 'warning');
    assert.equal(normalized.freshness_status, 'fresh');
    assert.equal(normalized.last_health_check, '2026-08-01T08:00:00Z');
    assert.equal(normalized.last_full_poll, '2026-08-01T07:59:45Z');
    assert.equal(normalized.profile.id, 'ccdm_matrix');
    assert.notEqual(String(normalized.profile_id), '[object Object]');
});

test('five fixtures cover every frozen Profile and produce ordered details', () => {
    assert.deepEqual(fixtureProfiles.map((profile) => profile.id), expectedProfiles);
    assert.deepEqual(fixtureDevices.map((device) => device.profile.id), expectedProfiles);

    for (const device of fixtureDevices) {
        const detail = normalizeDeviceDetail(fixtureDeviceDetails[device.id], null, device);
        assert.equal(detail.device.profile_id, device.profile.id);
        assert.ok(detail.sections.length >= 4);
        assert.deepEqual(
            detail.sections.map((section) => section.order),
            detail.sections.map((section) => section.order).slice().sort((left, right) => left - right)
        );
        assert.ok(detail.sections.some((section) => section.key === 'usb_hid'));
    }

    const ccdmFields = normalizeDeviceDetail(
        fixtureDeviceDetails['fixture-ccdm_matrix'],
        null,
        fixtureDevices[1]
    ).sections.find((section) => section.key === 'usb_hid').fields;
    assert.ok(ccdmFields.some((field) => field.key === 'console_ps2_connection'));
    assert.ok(ccdmFields.some((field) => field.key === 'console_usbconnection'));
    assert.ok(ccdmFields.some((field) => field.key === 'target_usb_hid'));
});

test('fan fixtures preserve positive, zero, unsupported, absent, and stale states', () => {
    const fanStates = fixtureDevices.map((device) => {
        const detail = normalizeDeviceDetail(fixtureDeviceDetails[device.id], null, device);
        return detail.sections
            .find((section) => section.key === 'environment')
            .fields.find((field) => field.key === 'fan_speed');
    });

    assert.equal(fanStates[0].value, 3200);
    assert.equal(fanStates[1].value, 0);
    assert.equal(fanStates[1].status, 'critical');
    assert.equal(fanStates[2].status, 'unsupported');
    assert.equal(fanStates[2].supported, false);
    assert.equal(fanStates[3].status, 'absent');
    assert.equal(fanStates[3].present, false);
    assert.equal(fanStates[4].status, 'stale');
    assert.equal(fanStates[4].stale, true);
});

test('keyboard/mouse enum remains distinct from undifferentiated HID state', () => {
    assert.deepEqual(keyboardMouseState('none'), {
        keyboard: false,
        mouse: false,
        known: true,
        source: null,
        raw: 'none',
    });
    assert.equal(keyboardMouseState('keyboard').keyboard, true);
    assert.equal(keyboardMouseState('keyboard').mouse, false);
    assert.equal(keyboardMouseState('mouse').keyboard, false);
    assert.equal(keyboardMouseState('mouse').mouse, true);
    assert.deepEqual(
        {
            keyboard: keyboardMouseState('keyboardMouse').keyboard,
            mouse: keyboardMouseState('keyboardMouse').mouse,
        },
        { keyboard: true, mouse: true }
    );

    const hid = hidBoundaryState('initialized');
    assert.equal(hid.connected, true);
    assert.equal(hid.initialized, true);
    assert.equal(hid.deviceTypeDifferentiated, false);
    assert.equal(keyboardMouseState('unexpected').known, false);
});

test('backend KeyboardMouseStatus objects and peripheral transports remain explicit', () => {
    const normalized = keyboardMouseState({
        keyboard: true,
        mouse: false,
        source: 'console_ps2_connection',
    });
    assert.equal(normalized.keyboard, true);
    assert.equal(normalized.mouse, false);
    assert.equal(normalized.known, true);
    assert.equal(normalized.source, 'console_ps2_connection');

    assert.equal(getPeripheralFieldKind({
        key: 'console_ps2_connection',
        value: normalized.raw,
    }), 'keyboard_mouse');
    assert.equal(getPeripheralFieldKind({
        key: 'console_usbconnection',
        value: { keyboard: false, mouse: true },
    }), 'keyboard_mouse');
    assert.equal(getPeripheralFieldKind({
        key: 'target_usb_hid',
        value: 'initialized',
    }), 'hid');
    assert.equal(getPeripheralFieldKind({
        key: 'cpu_channel_target_ps2',
        value: 'connected',
    }), null);
});

test('sensitive credentials are recursively removed from compatibility payloads', () => {
    assert.deepEqual(sanitizeSensitiveData({
        community: 'public',
        nested: {
            password: 'secret',
            safe: 'visible',
        },
        rows: [{ token: 'jwt', id: 1 }],
    }), {
        nested: { safe: 'visible' },
        rows: [{ id: 1 }],
    });
});
