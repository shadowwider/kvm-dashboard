export const ALERT_SEVERITIES = ['info', 'warning', 'critical', 'trap', 'offline'];

export function normalizeAlertSeverity(alert = {}) {
    if (
        alert.alert_type === 'trap'
        || alert.type === 'trap_received'
        || alert.event_type === 'trap_received'
        || alert.trap_oid
        || alert.trap_level !== null && alert.trap_level !== undefined
    ) return 'trap';
    if (alert.alert_type === 'offline' || alert.kind === 'offline') return 'offline';
    const severity = String(alert.severity || 'info').toLowerCase();
    return ALERT_SEVERITIES.includes(severity) ? severity : 'info';
}

export function createAlertSoundGate({ now = () => Date.now(), minIntervalMs = 900 } = {}) {
    const seenIds = new Set();
    let lastPlayedAt = Number.NEGATIVE_INFINITY;

    return {
        seed(alerts = []) {
            alerts.forEach((alert) => {
                const persistedId = alert?.id ?? alert?.alert_id;
                if (persistedId !== null && persistedId !== undefined) {
                    seenIds.add(String(persistedId));
                }
            });
        },
        evaluate(alert, preferences = {}) {
            const persistedId = alert?.id ?? alert?.alert_id;
            if (persistedId === null || persistedId === undefined) {
                return { play: false, reason: 'missing_id' };
            }

            const id = String(persistedId);
            if (seenIds.has(id)) return { play: false, reason: 'duplicate' };
            seenIds.add(id);

            const severity = normalizeAlertSeverity(alert);
            if (preferences.muted) return { play: false, reason: 'muted', severity };
            if (preferences.severities?.[severity] === false) {
                return { play: false, reason: 'severity_disabled', severity };
            }

            const current = now();
            if (current - lastPlayedAt < minIntervalMs) {
                return { play: false, reason: 'throttled', severity };
            }

            lastPlayedAt = current;
            return { play: true, reason: 'accepted', severity };
        },
        hasSeen(id) {
            return seenIds.has(String(id));
        },
    };
}

export function getToneSpec(severity) {
    const specs = {
        info: { frequency: 660, duration: 0.11, gain: 0.055 },
        warning: { frequency: 760, duration: 0.16, gain: 0.07 },
        critical: { frequency: 930, duration: 0.22, gain: 0.09 },
        trap: { frequency: 820, duration: 0.18, gain: 0.08 },
        offline: { frequency: 480, duration: 0.24, gain: 0.085 },
    };
    return specs[severity] || specs.info;
}

export async function playToneWithContext(context, severity = 'info') {
    if (!context) throw new Error('audio_unsupported');
    if (context.state === 'suspended') await context.resume();

    const { duration, frequency, gain } = getToneSpec(severity);
    const oscillator = context.createOscillator();
    const volume = context.createGain();
    const start = context.currentTime;

    oscillator.type = severity === 'critical' || severity === 'offline' ? 'square' : 'sine';
    oscillator.frequency.setValueAtTime(frequency, start);
    volume.gain.setValueAtTime(0.0001, start);
    volume.gain.exponentialRampToValueAtTime(gain, start + 0.015);
    volume.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    oscillator.connect(volume);
    volume.connect(context.destination);
    oscillator.start(start);
    oscillator.stop(start + duration + 0.02);
}

export const liveAlertSoundGate = createAlertSoundGate();
