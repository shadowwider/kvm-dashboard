import assert from 'node:assert/strict';
import test from 'node:test';

import {
    extractRealtimeAlerts,
    reconcileAlertHistory,
} from '../src/utils/alertSync.js';

test('extracts persisted alerts from all realtime alert envelopes', () => {
    assert.equal(extractRealtimeAlerts({
        type: 'alert_created',
        data: { alert: { id: 21, severity: 'critical' } },
    })[0].id, 21);

    assert.deepEqual(
        extractRealtimeAlerts({
            type: 'new_alerts',
            data: { alerts: [{ alert_id: 22, severity: 'warning' }] },
        }).map((alert) => alert.id),
        [22]
    );

    const trap = extractRealtimeAlerts({
        type: 'trap_received',
        data: {
            alert: { id: 23, severity: 'critical' },
            trap: { level: 2, notification_oid: '1.3.6.1.4.1.32828.2.1.0.4' },
        },
    })[0];
    assert.equal(trap.id, 23);
    assert.equal(trap.alert_type, 'metric');
    assert.equal(trap.event_type, 'trap_received');
    assert.equal(trap.trap_level, 2);
});

test('history seed excludes buffered live ids while preserving their sound events', () => {
    const reconciled = reconcileAlertHistory({
        existingAlerts: [{ id: 10 }],
        historyAlerts: [{ id: 10 }, { id: 11 }, { id: 12 }],
        liveAlerts: [{ id: 12, severity: 'critical' }, { id: 13, severity: 'warning' }],
    });

    assert.deepEqual(reconciled.seedAlerts.map((alert) => alert.id), [10, 11]);
    assert.deepEqual(reconciled.soundAlerts.map((alert) => alert.id), [12, 13]);
    assert.deepEqual(reconciled.alerts.map((alert) => alert.id), [12, 13, 10, 11]);
});

test('reconnect does not replay existing ids and keeps buffered alerts if history fails', () => {
    const reconciled = reconcileAlertHistory({
        existingAlerts: [{ id: 30 }, { id: 29 }],
        historyAlerts: [],
        historyLoaded: false,
        liveAlerts: [{ id: 30 }, { id: 31 }],
    });

    assert.deepEqual(reconciled.soundAlerts.map((alert) => alert.id), [31]);
    assert.deepEqual(reconciled.alerts.map((alert) => alert.id), [30, 31, 29]);
});
