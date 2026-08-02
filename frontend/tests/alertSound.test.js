import assert from 'node:assert/strict';
import test from 'node:test';

import {
    createAlertSoundGate,
    normalizeAlertSeverity,
    playToneWithContext,
} from '../src/utils/alertSound.js';

const allEnabled = {
    muted: false,
    severities: {
        info: true,
        warning: true,
        critical: true,
        trap: true,
        offline: true,
    },
};

test('historical alerts seed persisted id and alert_id values across reconnects', () => {
    const gate = createAlertSoundGate({ now: () => 10000, minIntervalMs: 0 });
    gate.seed([{ id: 10 }, { alert_id: '11' }]);

    assert.equal(gate.evaluate({ alert_id: 10, severity: 'critical' }, allEnabled).reason, 'duplicate');
    assert.equal(gate.evaluate({ id: 11, severity: 'warning' }, allEnabled).reason, 'duplicate');
});

test('live sound requires a persisted alert id and deduplicates repeated payloads', () => {
    const gate = createAlertSoundGate({ now: () => 10000, minIntervalMs: 0 });

    assert.equal(gate.evaluate({ severity: 'critical' }, allEnabled).reason, 'missing_id');
    assert.equal(gate.evaluate({ alert_id: 12, severity: 'critical' }, allEnabled).play, true);
    assert.equal(gate.evaluate({ id: 12, severity: 'critical' }, allEnabled).reason, 'duplicate');
});

test('mute and severity preferences consume ids without replaying them later', () => {
    const gate = createAlertSoundGate({ now: () => 10000, minIntervalMs: 0 });

    assert.equal(gate.evaluate(
        { alert_id: 13, severity: 'warning' },
        { ...allEnabled, muted: true }
    ).reason, 'muted');
    assert.equal(gate.evaluate({ alert_id: 13, severity: 'warning' }, allEnabled).reason, 'duplicate');

    assert.equal(gate.evaluate(
        { alert_id: 14, severity: 'info' },
        { ...allEnabled, severities: { ...allEnabled.severities, info: false } }
    ).reason, 'severity_disabled');
    assert.equal(gate.evaluate({ alert_id: 14, severity: 'info' }, allEnabled).reason, 'duplicate');
});

test('throttle limits bursts while preserving persisted-id deduplication', () => {
    let now = 1000;
    const gate = createAlertSoundGate({ now: () => now, minIntervalMs: 900 });

    assert.equal(gate.evaluate({ alert_id: 15, severity: 'critical' }, allEnabled).play, true);
    now = 1200;
    assert.equal(gate.evaluate({ alert_id: 16, severity: 'warning' }, allEnabled).reason, 'throttled');
    now = 2000;
    assert.equal(gate.evaluate({ alert_id: 17, severity: 'offline' }, allEnabled).play, true);
    assert.equal(gate.evaluate({ alert_id: 16, severity: 'warning' }, allEnabled).reason, 'duplicate');
});

test('trap and offline payloads map to their dedicated sound severities', () => {
    assert.equal(normalizeAlertSeverity({ alert_type: 'trap', severity: 'critical' }), 'trap');
    assert.equal(normalizeAlertSeverity({ kind: 'offline', severity: 'critical' }), 'offline');
});

test('preview tone starts Web Audio after a user gesture has made its context ready', async () => {
    const calls = [];
    const oscillator = {
        frequency: { setValueAtTime: (...args) => calls.push(['frequency', ...args]) },
        connect: (target) => calls.push(['oscillator.connect', target]),
        start: (at) => calls.push(['oscillator.start', at]),
        stop: (at) => calls.push(['oscillator.stop', at]),
    };
    const volume = {
        gain: {
            setValueAtTime: (...args) => calls.push(['gain.set', ...args]),
            exponentialRampToValueAtTime: (...args) => calls.push(['gain.ramp', ...args]),
        },
        connect: (target) => calls.push(['gain.connect', target]),
    };
    const destination = { name: 'speaker' };
    const context = {
        state: 'running',
        currentTime: 4,
        destination,
        createOscillator: () => oscillator,
        createGain: () => volume,
    };

    await playToneWithContext(context, 'warning');

    assert.deepEqual(calls, [
        ['frequency', 760, 4],
        ['gain.set', 0.0001, 4],
        ['gain.ramp', 0.07, 4.015],
        ['gain.ramp', 0.0001, 4.16],
        ['oscillator.connect', volume],
        ['gain.connect', destination],
        ['oscillator.start', 4],
        ['oscillator.stop', 4.18],
    ]);
});

test('preview reports an error when Web Audio is unsupported or browser resume is blocked', async () => {
    await assert.rejects(
        playToneWithContext(null, 'warning'),
        /audio_unsupported/
    );

    const blocked = {
        state: 'suspended',
        resume: async () => { throw new Error('NotAllowedError'); },
    };
    await assert.rejects(playToneWithContext(blocked, 'warning'), /NotAllowedError/);
});
