import { normalizeAlert, normalizeAlerts } from './multiProfile.js';

const ALERT_EVENT_TYPES = new Set([
    'alert_created',
    'new_alerts',
    'trap_received',
]);

function decorateTrapAlert(alert, message) {
    const data = message?.data || {};
    const trap = data.trap || message?.trap || {};
    if (alert) {
        return {
            ...alert,
            event_type: 'trap_received',
            trap_level: alert.trap_level ?? trap.level ?? null,
            trap_oid: alert.trap_oid ?? trap.notification_oid ?? null,
        };
    }
    if (!message?.message) return null;
    return {
        id: null,
        device_id: message.device_id || message.source_ip || null,
        severity: message.severity || 'warning',
        alert_type: 'trap',
        event_type: 'trap_received',
        message: message.message,
        created_at: message.timestamp || null,
    };
}

export function extractRealtimeAlerts(message) {
    if (!message || !ALERT_EVENT_TYPES.has(message.type)) return null;
    const data = message.data || {};

    if (message.type === 'alert_created') {
        return data.alert ? [normalizeAlert({ ...data.alert, event_type: message.type })] : [];
    }
    if (message.type === 'new_alerts') {
        return normalizeAlerts(message.alerts || data.alerts || []);
    }

    const alert = decorateTrapAlert(data.alert || message.alert, message);
    return alert ? [normalizeAlert(alert)] : [];
}

function mergeAlerts(incoming, existing, limit = 50) {
    const seenIds = new Set();
    const merged = [];

    [...incoming, ...existing].forEach((alert) => {
        if (alert.id !== null && alert.id !== undefined) {
            const id = String(alert.id);
            if (seenIds.has(id)) return;
            seenIds.add(id);
        }
        merged.push(alert);
    });

    return merged.slice(0, limit);
}

export function reconcileAlertHistory({
    existingAlerts = [],
    historyAlerts = [],
    historyLoaded = true,
    liveAlerts = [],
    limit = 50,
} = {}) {
    const existing = normalizeAlerts(existingAlerts);
    const history = normalizeAlerts(historyAlerts);
    const live = normalizeAlerts(liveAlerts);
    const liveIds = new Set(
        live
            .filter((alert) => alert.id !== null && alert.id !== undefined)
            .map((alert) => String(alert.id))
    );
    const existingIds = new Set(
        existing
            .filter((alert) => alert.id !== null && alert.id !== undefined)
            .map((alert) => String(alert.id))
    );
    const soundIds = new Set();
    const soundAlerts = live.filter((alert) => {
        if (alert.id === null || alert.id === undefined) return false;
        const id = String(alert.id);
        if (existingIds.has(id) || soundIds.has(id)) return false;
        soundIds.add(id);
        return true;
    });

    return {
        alerts: mergeAlerts(live, historyLoaded ? history : existing, limit),
        seedAlerts: history.filter((alert) => (
            alert.id === null
            || alert.id === undefined
            || !liveIds.has(String(alert.id))
        )),
        soundAlerts,
    };
}
