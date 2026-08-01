import { useCallback, useEffect, useMemo, useRef } from 'react';
import useWebSocketLib from 'react-use-websocket';
import { useAuthStore } from '../store/authStore';
import { useStore } from '../store/mainStore';
import { extractRealtimeAlerts } from '../utils/alertSync';

const useWebSocket = useWebSocketLib.default || useWebSocketLib;

export default function useSystemWebSocket() {
    const token = useAuthStore((state) => state.token);
    const beginAlertHistorySync = useStore((state) => state.beginAlertHistorySync);
    const completeAlertHistorySync = useStore((state) => state.completeAlertHistorySync);
    const fetchAlertHistory = useStore((state) => state.fetchAlertHistory);
    const fetchDevices = useStore((state) => state.fetchDevices);
    const fetchAll = useStore((state) => state.fetchAll);
    const prependNewAlerts = useStore((state) => state.prependNewAlerts);
    const updateDeviceState = useStore((state) => state.updateDeviceState);
    const updateDiscoveryJobState = useStore((state) => state.updateDiscoveryJobState);
    const updateEndpointState = useStore((state) => state.updateEndpointState);
    const updateEntityState = useStore((state) => state.updateEntityState);
    const updatePortState = useStore((state) => state.updatePortState);
    const connectionEpochRef = useRef(0);
    const alertSyncRef = useRef({ ready: false, buffered: [], syncId: null });

    const wsUrl = useMemo(() => {
        if (!token) return null;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/api/v1/ws/monitor?token=${encodeURIComponent(token)}`;
    }, [token]);

    const handleOpen = useCallback(() => {
        const epoch = connectionEpochRef.current + 1;
        connectionEpochRef.current = epoch;
        const syncId = beginAlertHistorySync();
        alertSyncRef.current = { ready: false, buffered: [], syncId };

        fetchDevices();
        fetchAlertHistory()
            .then((historyAlerts) => {
                if (connectionEpochRef.current !== epoch) return;
                const liveAlerts = alertSyncRef.current.buffered.splice(0);
                completeAlertHistorySync(syncId, historyAlerts, liveAlerts);
                alertSyncRef.current.ready = true;
                alertSyncRef.current.syncId = null;
            })
            .catch((error) => {
                if (connectionEpochRef.current !== epoch) return;
                console.error('Failed to synchronize alert history', error);
                const liveAlerts = alertSyncRef.current.buffered.splice(0);
                completeAlertHistorySync(syncId, [], liveAlerts, { historyLoaded: false });
                alertSyncRef.current.ready = true;
                alertSyncRef.current.syncId = null;
            });
    }, [
        beginAlertHistorySync,
        completeAlertHistorySync,
        fetchAlertHistory,
        fetchDevices,
    ]);

    const handleClose = useCallback(() => {
        const current = alertSyncRef.current;
        if (!current.ready && current.syncId !== null) {
            completeAlertHistorySync(
                current.syncId,
                [],
                current.buffered,
                { historyLoaded: false }
            );
        }
        connectionEpochRef.current += 1;
        alertSyncRef.current = { ready: false, buffered: [], syncId: null };
    }, [completeAlertHistorySync]);

    const handleMessage = useCallback((event) => {
        let message;
        try {
            message = JSON.parse(event.data);
        } catch {
            return;
        }
        const alerts = extractRealtimeAlerts(message);
        if (alerts === null) return;
        if (!alertSyncRef.current.ready) {
            alertSyncRef.current.buffered.push(...alerts);
            return;
        }
        prependNewAlerts(alerts);
    }, [prependNewAlerts]);

    const { lastJsonMessage, readyState } = useWebSocket(wsUrl, {
        shouldReconnect: () => Boolean(token),
        reconnectAttempts: 20,
        reconnectInterval: 3000,
        onOpen: handleOpen,
        onClose: handleClose,
        onMessage: handleMessage,
    });

    useEffect(() => () => {
        handleClose();
    }, [handleClose]);

    useEffect(() => {
        if (!lastJsonMessage) return;
        const type = lastJsonMessage.type;

        if (type === 'device_update') {
            updateDeviceState(lastJsonMessage);
            return;
        }
        if (type === 'entity_update') {
            updateEntityState(lastJsonMessage);
            return;
        }
        if (extractRealtimeAlerts(lastJsonMessage) !== null) {
            return;
        }
        if (type === 'discovery_job_update') {
            updateDiscoveryJobState(lastJsonMessage);
            return;
        }

        if (type === 'endpoint_update') {
            updateEndpointState(lastJsonMessage);
        } else if (type === 'port_update') {
            updatePortState(lastJsonMessage);
        } else if (type === 'simulation_topology_update' || type === 'metric_update') {
            fetchAll();
        }
    }, [
        fetchAll,
        lastJsonMessage,
        updateDeviceState,
        updateDiscoveryJobState,
        updateEndpointState,
        updateEntityState,
        updatePortState,
    ]);

    return { readyState };
}
