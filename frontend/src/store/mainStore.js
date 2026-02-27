import { create } from 'zustand';
import api from '../utils/api';

export const useStore = create((set, get) => ({
    // 数据集
    stats: null,
    devices: [],
    endpoints: [],
    alerts: [],
    topology: null,

    // UI 状态
    selectedDeviceId: null,
    viewMode: 'grid', // 'grid' | 'topology'

    // 加载状态
    loading: false,
    error: null,

    // Action：修改视图状态
    setSelectedDevice: (id) => set({ selectedDeviceId: id }),
    setViewMode: (mode) => set({ viewMode: mode }),

    // Action：拉取全局 KPI 和统计
    fetchStats: async () => {
        try {
            const res = await api.get('/stats/dashboard');
            set({ stats: res.data, error: null });
        } catch (err) {
            console.error('Failed to fetch stats', err);
        }
    },

    // Action：拉取左侧设备卡片
    fetchDevices: async () => {
        try {
            set({ loading: true });
            const res = await api.get('/devices');
            set({ devices: res.data, error: null });
        } catch (err) {
            set({ error: err.message });
            console.error('Failed to fetch devices', err);
        } finally {
            set({ loading: false });
        }
    },

    // Action：获取指定设备的终端数据 (主网格图)
    fetchEndpoints: async (deviceId) => {
        if (!deviceId) return;
        try {
            const res = await api.get(`/endpoints?device_id=${deviceId}`);
            set({ endpoints: res.data });
        } catch (err) {
            console.error('Failed to fetch endpoints', err);
        }
    },

    // Action：拉取右侧告警流
    fetchAlerts: async () => {
        try {
            const res = await api.get('/alerts?is_resolved=false&limit=50');
            set({ alerts: res.data });
        } catch (err) {
            console.error('Failed to fetch alerts', err);
        }
    },

    // Action: 拉取第二层详细的拓扑连线结构
    fetchTopology: async (deviceId) => {
        if (!deviceId) return;
        try {
            const res = await api.get(`/topology/${deviceId}`);
            set({ topology: res.data });
        } catch (err) {
            console.error('Failed to fetch topology', err);
        }
    },

    // 综合批量拉取大屏数据 (定时或最初始执行)
    fetchAll: async () => {
        const { fetchStats, fetchDevices, fetchAlerts, selectedDeviceId, fetchEndpoints } = get();
        await Promise.all([
            fetchStats(),
            fetchDevices(),
            fetchAlerts()
        ]);
        if (selectedDeviceId) {
            await fetchEndpoints(selectedDeviceId);
        }
    },

    // Websocket Action: 处理单点刷新
    updateDeviceState: (deviceUpdate) => {
        set((state) => {
            const updatedDevices = state.devices.map(d =>
                d.id === deviceUpdate.device_id ? { ...d, last_status: deviceUpdate.online_status || 'online', updated_at: deviceUpdate.timestamp } : d
            );
            return { devices: updatedDevices };
        });
    },

    // Websocket Action: 收到新的告警
    prependNewAlerts: (newAlerts) => {
        set((state) => {
            // Put it at beginning, limit array to 50
            return { alerts: [...newAlerts, ...state.alerts].slice(0, 50) };
        });
    }
}));
