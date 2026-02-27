import { useEffect } from 'react';
import useWebSocketLib from 'react-use-websocket';

const useWebSocket = useWebSocketLib.default || useWebSocketLib;
import { useStore } from '../store/mainStore';

const useSystemWebSocket = () => {
    const { updateDeviceState, prependNewAlerts, fetchAll } = useStore();

    // Get current host automatically from browser location
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // When using vite proxy, window.location.host includes the 3000 port, targeting the proxy.
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/monitor`;

    const { lastJsonMessage, readyState } = useWebSocket(wsUrl, {
        shouldReconnect: (closeEvent) => true,
        reconnectAttempts: 10,
        reconnectInterval: 3000,
    });

    useEffect(() => {
        if (!lastJsonMessage) return;

        const { type } = lastJsonMessage;

        if (type === 'device_update') {
            updateDeviceState(lastJsonMessage);
        } else if (type === 'new_alerts' || type === 'trap_received') {
            const now = new Date().toISOString();
            const rawAlerts = lastJsonMessage.alerts || [{
                id: Date.now(),
                severity: lastJsonMessage.severity || 'warning',
                message: lastJsonMessage.message || 'TRAP 告警',
                device_id: lastJsonMessage.device_id || lastJsonMessage.source_ip || '未知设备',
                created_at: lastJsonMessage.timestamp || now,
            }];
            // 确保每条告警都有 created_at
            const alerts = rawAlerts.map(a => ({
                ...a,
                created_at: a.created_at || now,
            }));
            prependNewAlerts(alerts);
        } else if (type === 'metric_update') {
            // Optionally dispatch to update stats block
            fetchAll();
        }
    }, [lastJsonMessage]);

    return { readyState };
};

export default useSystemWebSocket;
