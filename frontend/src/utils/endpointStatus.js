const KEYBOARD_MOUSE_VALUES = {
    none: 'dashboard.status_none',
    keyboard: 'dashboard.status_kb',
    mouse: 'dashboard.status_mouse',
    keyboardMouse: 'dashboard.status_kb_mouse',
};

const USB_HID_VALUES = {
    notConnected: 'dashboard.status_not_connected',
    connected: 'dashboard.status_connected',
    initialized: 'dashboard.status_active',
};

const VIDEO_VALUES = {
    none: 'dashboard.video_none',
    vga: null,
    dvisl: null,
    dvidl: null,
    dmdp: null,
    dp: null,
    hdmi: null,
};

const hasKeyboard = (value) => value === 'keyboard' || value === 'keyboardMouse';
const hasMouse = (value) => value === 'mouse' || value === 'keyboardMouse';
const hasKnownValue = (value) => value !== undefined && value !== null && value !== '';

export function getEndpointDeviceState(ep) {
    if (ep?.device_reachability === 'offline') return 'offline';
    const st = ep?.last_status || {};
    if (ep?.module_type === 'con') {
        return st.con_device_status || 'offline';
    }
    return st.ep_device_status || 'offline';
}

export function getConKeyboardMouseState(status = {}) {
    const ps2 = status.con_console_ps2;
    const usb = status.con_console_usb;
    const hasAnyField = hasKnownValue(ps2) || hasKnownValue(usb);

    if (!hasAnyField) {
        return {
            state: 'unknown',
            labelKey: 'dashboard.status_unknown',
            hasKeyboard: false,
            hasMouse: false,
        };
    }

    const keyboard = hasKeyboard(ps2) || hasKeyboard(usb);
    const mouse = hasMouse(ps2) || hasMouse(usb);

    if (keyboard && mouse) {
        return {
            state: 'ok',
            labelKey: 'dashboard.status_complete',
            hasKeyboard: true,
            hasMouse: true,
        };
    }

    if (keyboard || mouse) {
        return {
            state: 'partial',
            labelKey: 'dashboard.status_partial',
            hasKeyboard: keyboard,
            hasMouse: mouse,
        };
    }

    return {
        state: 'disconnected',
        labelKey: 'dashboard.status_disconnected',
        hasKeyboard: false,
        hasMouse: false,
    };
}

export function getEndpointStatus(ep) {
    if (ep?.device_reachability === 'offline') return 'offline';
    const st = ep?.last_status || {};

    if (ep?.module_type === 'con') {
        const devSt = st.con_device_status;
        if (!devSt || devSt === 'offline') return 'offline';
        if (st.con_display_conn === 'notConnected') return 'warning';
        if (st.con_freeze === 'true') return 'warning';

        const km = getConKeyboardMouseState(st);
        if (km.state !== 'ok') return 'warning';

        return devSt;
    }

    const devSt = st.ep_device_status;
    if (!devSt || devSt === 'offline') return 'offline';
    if (st.ep_target_video_cable === 'notConnected') return 'warning';
    if (st.ep_target_usb_hid === 'notConnected') return 'warning';
    if (st.ep_target_power === 'off') return 'warning';
    return devSt;
}

export function getEndpointSortIndex(ep) {
    const value = Number(ep?.index);
    return Number.isFinite(value) ? value : 0;
}

export function formatEndpointPosition(ep, t, { short = false } = {}) {
    const value = ep?.index ?? '—';
    return short ? `#${value}` : `${t('dashboard.detail_interface')} #${value}`;
}

export function formatKeyboardMouseValue(value, t) {
    if (!hasKnownValue(value)) return t('dashboard.status_unknown');
    const key = KEYBOARD_MOUSE_VALUES[value];
    return key ? t(key) : String(value);
}

export function formatKeyboardMouseState(state, t) {
    return t(state?.labelKey || 'dashboard.status_unknown');
}

export function formatUsbHidValue(value, t) {
    if (!hasKnownValue(value)) return t('dashboard.status_unknown');
    const key = USB_HID_VALUES[value];
    return key ? t(key) : String(value);
}

export function formatVideoValue(value, t) {
    if (!hasKnownValue(value)) return '—';
    const key = VIDEO_VALUES[value];
    return key ? t(key) : String(value).toUpperCase();
}

export function getDevicePortSummary(device) {
    const ports = device?.last_metrics?.ports || {};
    const values = Object.values(ports);
    const total = values.length;
    const up = values.filter(p => p?.port_status === 'up' || p?.port_status === 3).length;
    const down = values.filter(p => p?.port_status === 'down' || p?.port_status === 2).length;
    return { total, up, down };
}
