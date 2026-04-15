import { create } from 'zustand';
import api from '../utils/api';

export const useStore = create((set, get) => ({
    // 数据集
    stats: null,
    devices: [],
    endpoints: [],   // 合并所有已拉取设备的终端，key by id
    alerts: [],
    topology: null,
    aliases: {},      // { target_id -> alias_name } 别名映射
    oidConfigs: [],   // OID 配置列表（含 display_enabled 等）

    // UI 状态
    selectedDeviceId: null,
    viewMode: 'grid', // 'grid' | 'topology'

    // 加载状态
    loading: false,
    error: null,

    // ── 别名相关 ──────────────────────────────────────
    // 获取显示名：有别名用别名，否则用原始 name，最后用 id
    getDisplayName: (id, fallbackName) => {
        const { aliases } = get();
        return aliases[id] || fallbackName || id;
    },

    fetchAliases: async () => {
        try {
            const res = await api.get('/aliases');
            const map = {};
            (res.data || []).forEach(a => { map[a.target_id] = a.alias; });
            set({ aliases: map });
        } catch (err) {
            console.error('Failed to fetch aliases', err);
        }
    },

    // ── OID 配置 ──────────────────────────────────────
    fetchOidConfigs: async () => {
        try {
            const res = await api.get('/oids');
            set({ oidConfigs: res.data || [] });
        } catch (err) {
            console.error('Failed to fetch OID configs', err);
        }
    },

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

    // Action：获取指定设备的终端数据 —— 合并到全局 endpoints 数组（不覆盖其他设备）
    fetchEndpoints: async (deviceId) => {
        if (!deviceId) return;
        try {
            const res = await api.get(`/endpoints?device_id=${deviceId}`);
            const newEps = res.data || [];
            set((state) => {
                // 保留其他设备的终端，更新/追加当前设备的终端
                const otherEps = state.endpoints.filter(ep => ep.device_id !== deviceId);
                return { endpoints: [...otherEps, ...newEps] };
            });
        } catch (err) {
            console.error('Failed to fetch endpoints', err);
        }
    },

    // Action：拉取全部设备的终端（矩阵全部模式用）
    fetchAllEndpoints: async () => {
        const { devices } = get();
        if (!devices.length) return;
        try {
            const results = await Promise.allSettled(
                devices.map(d => api.get(`/endpoints?device_id=${d.id}`).then(r => r.data || []))
            );
            const all = results.flatMap(r => r.status === 'fulfilled' ? r.value : []);
            set({ endpoints: all });
        } catch (err) {
            console.error('Failed to fetch all endpoints', err);
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

    // Action: 拉取拓扑连线结构
    fetchTopology: async (deviceId) => {
        if (!deviceId) return;
        try {
            const res = await api.get(`/topology/${deviceId}`);
            set({ topology: res.data });
        } catch (err) {
            console.error('Failed to fetch topology', err);
        }
    },

    // 综合批量拉取大屏数据
    fetchAll: async () => {
        const { fetchStats, fetchDevices, fetchAlerts, fetchAllEndpoints, fetchAliases, fetchOidConfigs } = get();
        await Promise.all([
            fetchStats(),
            fetchDevices(),
            fetchAlerts(),
            fetchAliases(),
            fetchOidConfigs(),
        ]);
        // devices 拉完后立刻拉所有终端
        await fetchAllEndpoints();
    },

    // Websocket Action: 处理单点刷新
    updateDeviceState: (deviceUpdate) => {
        set((state) => {
            const updatedDevices = state.devices.map(d =>
                d.id === deviceUpdate.device_id
                    ? { ...d, last_status: deviceUpdate.online_status || 'online', updated_at: deviceUpdate.timestamp }
                    : d
            );
            return { devices: updatedDevices };
        });
    },

    // Websocket Action: 收到新的告警
    prependNewAlerts: (newAlerts) => {
        set((state) => ({
            alerts: [...newAlerts, ...state.alerts].slice(0, 50)
        }));
    },
}));
