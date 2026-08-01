import { create } from 'zustand';
import api from '../utils/api';
import {
    getDeviceDetail,
    getDeviceSummaries,
    getProfiles,
} from '../services/multiProfileApi';
import { reconcileAlertHistory } from '../utils/alertSync';
import { liveAlertSoundGate } from '../utils/alertSound';
import {
    getStableEntityKey,
    isMatrixProfile,
    normalizeAlert,
    normalizeAlerts,
    normalizeDeviceSummary,
    normalizeEntity,
    unwrapList,
} from '../utils/multiProfile';

const MAX_ALERTS = 50;
const MAX_SOUND_EVENTS = 50;

function mergeAlertLists(incoming, existing) {
    const seenIds = new Set();
    const merged = [];

    [...incoming, ...existing].forEach((alert) => {
        if (alert.id !== null && alert.id !== undefined) {
            const key = String(alert.id);
            if (seenIds.has(key)) return;
            seenIds.add(key);
        }
        merged.push(alert);
    });

    return merged.slice(0, MAX_ALERTS);
}

export const useStore = create((set, get) => ({
    stats: null,
    devices: [],
    devicePage: { total: 0, page: 1, page_size: 100 },
    profiles: [],
    endpoints: [],
    alerts: [],
    aliases: {},
    oidConfigs: [],
    deviceDetails: {},
    detailLoading: {},
    detailErrors: {},
    discoveryJobs: {},
    soundEvents: [],
    alertHistorySyncId: 0,
    alertHistorySyncing: false,

    selectedDeviceId: null,
    viewMode: 'grid',

    loading: false,
    error: null,

    getDisplayName: (id, fallbackName) => {
        const { aliases } = get();
        return aliases[id] || fallbackName || id;
    },

    setSelectedDevice: (id) => set({ selectedDeviceId: id }),
    setViewMode: (mode) => set({ viewMode: mode }),

    fetchAliases: async () => {
        try {
            const response = await api.get('/aliases');
            const map = {};
            unwrapList(response.data).forEach((alias) => {
                map[alias.target_id] = alias.alias;
            });
            set({ aliases: map });
        } catch (error) {
            console.error('Failed to fetch aliases', error);
        }
    },

    fetchOidConfigs: async () => {
        try {
            const response = await api.get('/oids');
            set({ oidConfigs: unwrapList(response.data) });
        } catch (error) {
            console.error('Failed to fetch OID configs', error);
        }
    },

    fetchStats: async () => {
        try {
            const response = await api.get('/stats/dashboard');
            set({ stats: response.data, error: null });
        } catch (error) {
            console.error('Failed to fetch stats', error);
        }
    },

    fetchProfiles: async () => {
        try {
            const result = await getProfiles();
            set({ profiles: result.items });
        } catch (error) {
            console.error('Failed to fetch profiles', error);
        }
    },

    fetchDevices: async () => {
        try {
            set({ loading: true });
            const result = await getDeviceSummaries({ page: 1, page_size: 100 });
            set({
                devices: result.items,
                devicePage: {
                    total: result.total,
                    page: result.page,
                    page_size: result.page_size,
                },
                error: null,
            });
            return result.items;
        } catch (error) {
            set({ error: error.message });
            console.error('Failed to fetch devices', error);
            return [];
        } finally {
            set({ loading: false });
        }
    },

    fetchDeviceDetail: async (deviceId, { force = false } = {}) => {
        if (!deviceId) return null;
        const state = get();
        if (!force && state.deviceDetails[deviceId]) return state.deviceDetails[deviceId];
        if (state.detailLoading[deviceId]) return null;

        set((current) => ({
            detailLoading: { ...current.detailLoading, [deviceId]: true },
            detailErrors: { ...current.detailErrors, [deviceId]: null },
        }));
        try {
            const device = get().devices.find((item) => item.id === deviceId) || { id: deviceId };
            const detail = await getDeviceDetail(device);
            set((current) => ({
                deviceDetails: { ...current.deviceDetails, [deviceId]: detail },
            }));
            return detail;
        } catch (error) {
            set((current) => ({
                detailErrors: { ...current.detailErrors, [deviceId]: error.message },
            }));
            console.error('Failed to fetch device detail', error);
            return null;
        } finally {
            set((current) => ({
                detailLoading: { ...current.detailLoading, [deviceId]: false },
            }));
        }
    },

    fetchEndpoints: async (deviceId) => {
        if (!deviceId) return;
        const device = get().devices.find((item) => item.id === deviceId);
        if (device && !isMatrixProfile(device)) return;

        try {
            const response = await api.get('/endpoints', { params: { device_id: deviceId } });
            const newEndpoints = unwrapList(response.data);
            set((state) => ({
                endpoints: [
                    ...state.endpoints.filter((endpoint) => endpoint.device_id !== deviceId),
                    ...newEndpoints,
                ],
            }));
        } catch (error) {
            console.error('Failed to fetch endpoints', error);
        }
    },

    fetchAllEndpoints: async () => {
        const matrixDevices = get().devices.filter(isMatrixProfile);
        if (!matrixDevices.length) {
            set({ endpoints: [] });
            return;
        }

        const results = await Promise.allSettled(
            matrixDevices.map((device) => (
                api.get('/endpoints', { params: { device_id: device.id } })
                    .then((response) => unwrapList(response.data))
            ))
        );
        const endpoints = results.flatMap((result) => (
            result.status === 'fulfilled' ? result.value : []
        ));
        set({ endpoints });
    },

    fetchAlertHistory: async () => {
        const response = await api.get('/alerts', {
            params: { is_resolved: false, page: 1, page_size: MAX_ALERTS, limit: MAX_ALERTS },
        });
        return normalizeAlerts(response.data);
    },

    beginAlertHistorySync: () => {
        const syncId = get().alertHistorySyncId + 1;
        liveAlertSoundGate.seed(get().alerts);
        set({
            alertHistorySyncId: syncId,
            alertHistorySyncing: true,
        });
        return syncId;
    },

    completeAlertHistorySync: (
        syncId,
        historyAlerts,
        liveAlerts,
        { historyLoaded = true } = {}
    ) => {
        const state = get();
        if (state.alertHistorySyncId !== syncId) return false;

        const reconciled = reconcileAlertHistory({
            existingAlerts: state.alerts,
            historyAlerts,
            historyLoaded,
            liveAlerts,
            limit: MAX_ALERTS,
        });
        liveAlertSoundGate.seed(reconciled.seedAlerts);
        set((current) => {
            if (current.alertHistorySyncId !== syncId) return {};
            return {
                alerts: reconciled.alerts,
                soundEvents: [
                    ...current.soundEvents,
                    ...reconciled.soundAlerts,
                ].slice(-MAX_SOUND_EVENTS),
                alertHistorySyncing: false,
            };
        });
        return true;
    },

    fetchAlerts: async () => {
        try {
            const alerts = await get().fetchAlertHistory();
            if (get().alertHistorySyncing) return alerts;
            liveAlertSoundGate.seed(alerts);
            set({ alerts });
            return alerts;
        } catch (error) {
            console.error('Failed to fetch alerts', error);
            return [];
        }
    },

    fetchAll: async () => {
        const {
            fetchAliases,
            fetchDevices,
            fetchOidConfigs,
            fetchProfiles,
            fetchStats,
            fetchAllEndpoints,
        } = get();
        await Promise.all([
            fetchStats(),
            fetchDevices(),
            fetchAliases(),
            fetchOidConfigs(),
            fetchProfiles(),
        ]);
        await fetchAllEndpoints();
    },

    updateDeviceState: (payload) => {
        const contractDevice = payload?.data?.device || payload?.device;
        if (contractDevice) {
            const normalized = normalizeDeviceSummary(contractDevice);
            set((state) => {
                const exists = state.devices.some((device) => device.id === normalized.id);
                return {
                    devices: exists
                        ? state.devices.map((device) => (
                            device.id === normalized.id ? { ...device, ...normalized } : device
                        ))
                        : [normalized, ...state.devices],
                };
            });
            return;
        }

        const deviceId = payload?.device_id || payload?.data?.device_id;
        if (!deviceId) return;
        set((state) => ({
            devices: state.devices.map((device) => (
                device.id === deviceId
                    ? normalizeDeviceSummary({
                        ...device,
                        last_status: payload.online_status || payload.status || payload.reachability || device.last_status,
                        last_metrics: payload.last_metrics || device.last_metrics,
                        endpoint_count: payload.endpoint_count ?? device.endpoint_count,
                        updated_at: payload.timestamp || device.updated_at,
                    })
                    : device
            )),
        }));
    },

    updateEntityState: (payload) => {
        const source = payload?.data || payload || {};
        const deviceId = source.device_id;
        if (!deviceId || !source.entity) return;
        const entity = normalizeEntity(source.entity);
        const entityKey = getStableEntityKey(entity);

        set((state) => {
            const detail = state.deviceDetails[deviceId];
            if (!detail) return {};
            let replaced = false;
            const sections = detail.sections.map((section) => ({
                ...section,
                entities: section.entities.map((current) => {
                    if (getStableEntityKey(current) !== entityKey) return current;
                    replaced = true;
                    return entity;
                }),
            }));
            if (!replaced) {
                const sectionKey = entity.table_id || 'entities';
                const section = sections.find((item) => item.key === sectionKey);
                if (section) {
                    section.entities = [...section.entities, entity];
                } else {
                    sections.push({
                        key: sectionKey,
                        label_key: null,
                        label: sectionKey,
                        order: 999,
                        status: entity.status,
                        fields: [],
                        entities: [entity],
                    });
                }
            }
            return {
                deviceDetails: {
                    ...state.deviceDetails,
                    [deviceId]: { ...detail, sections },
                },
            };
        });
    },

    updateDiscoveryJobState: (payload) => {
        const job = payload?.data?.job || payload?.job;
        if (!job?.id) return;
        set((state) => ({
            discoveryJobs: { ...state.discoveryJobs, [job.id]: job },
        }));
    },

    updateEndpointState: (endpointUpdate) => {
        set((state) => ({
            endpoints: state.endpoints.map((endpoint) => (
                endpoint.id === endpointUpdate.endpoint_id
                    ? {
                        ...endpoint,
                        last_status: { ...endpoint.last_status, ...endpointUpdate.last_status },
                        updated_at: endpointUpdate.timestamp,
                    }
                    : endpoint
            )),
        }));
    },

    updatePortState: (portUpdate) => {
        set((state) => ({
            devices: state.devices.map((device) => {
                if (device.id !== portUpdate.device_id) return device;
                const metrics = device.last_metrics || {};
                return {
                    ...device,
                    last_metrics: {
                        ...metrics,
                        ports: {
                            ...(metrics.ports || {}),
                            [portUpdate.port_index]: {
                                ...((metrics.ports || {})[portUpdate.port_index] || {}),
                                port_status: portUpdate.status,
                                mapping_verified: portUpdate.mapping_verified,
                            },
                        },
                    },
                };
            }),
        }));
    },

    prependNewAlerts: (rawAlerts, { allowSound = true } = {}) => {
        const incoming = (Array.isArray(rawAlerts) ? rawAlerts : [rawAlerts])
            .filter(Boolean)
            .map(normalizeAlert);
        set((state) => {
            const existingIds = new Set(
                state.alerts
                    .filter((alert) => alert.id !== null && alert.id !== undefined)
                    .map((alert) => String(alert.id))
            );
            const soundEvents = allowSound
                ? incoming.filter((alert) => (
                    alert.id !== null
                    && alert.id !== undefined
                    && !existingIds.has(String(alert.id))
                ))
                : [];
            return {
                alerts: mergeAlertLists(incoming, state.alerts),
                soundEvents: [...state.soundEvents, ...soundEvents].slice(-MAX_SOUND_EVENTS),
            };
        });
    },
}));
