import api from '../utils/api';
import {
    fixtureAuditLogs,
    fixtureDeviceDetails,
    fixtureDevices,
    fixtureDiscoveryConfig,
    fixtureDiscoveryJobs,
    fixtureProfiles,
} from '../fixtures/multiProfileFixtures';
import {
    normalizeDeviceDetail,
    normalizeDeviceSummaries,
    normalizePagedResult,
    sanitizeSensitiveData,
    unwrapList,
} from '../utils/multiProfile';

export const useMultiProfileFixtures = import.meta.env.VITE_USE_MULTI_PROFILE_FIXTURES === 'true';

const fixturePage = (items, page = 1, pageSize = 100) => ({
    items,
    total: items.length,
    page,
    page_size: pageSize,
});

export function getApiError(error) {
    const detail = error?.response?.data?.detail;
    if (detail && typeof detail === 'object') {
        return {
            code: detail.code || 'internal_error',
            message: detail.message || error.message,
            fields: detail.fields || {},
            retryable: Boolean(detail.retryable),
        };
    }
    return {
        code: 'internal_error',
        message: typeof detail === 'string' ? detail : error?.message,
        fields: {},
        retryable: false,
    };
}

export async function getDeviceSummaries(params = {}) {
    if (useMultiProfileFixtures) {
        return fixturePage(normalizeDeviceSummaries(fixtureDevices));
    }
    const response = await api.get('/devices', { params });
    const page = normalizePagedResult(response.data, params.page_size || 100);
    return {
        ...page,
        items: normalizeDeviceSummaries(response.data),
    };
}

function legacyDetail(device) {
    const metrics = device?.last_metrics || {};
    const fields = Object.entries(metrics)
        .filter(([, value]) => value === null || typeof value !== 'object')
        .map(([key, value]) => ({
            key,
            label_key: `fields.${key}`,
            raw: value,
            value,
            unit: null,
            status: value === null ? 'unknown' : 'ok',
            supported: true,
            present: value !== null,
            stale: false,
            updated_at: device.updated_at || null,
        }));
    return normalizeDeviceDetail({
        device,
        sections: [{
            key: 'health',
            label_key: 'detail.sections.health',
            order: 20,
            status: device.health_status || 'unknown',
            fields,
            entities: [],
        }],
    }, null, device);
}

export async function getDeviceDetail(device) {
    const deviceId = typeof device === 'object' ? device.id : device;
    if (useMultiProfileFixtures) {
        const detail = fixtureDeviceDetails[deviceId];
        if (!detail) throw new Error(`Missing fixture detail for ${deviceId}`);
        return normalizeDeviceDetail(detail, null, detail.device);
    }

    try {
        const response = await api.get(`/devices/${encodeURIComponent(deviceId)}/details`);
        return normalizeDeviceDetail(response.data, null, typeof device === 'object' ? device : {});
    } catch (error) {
        if (![404, 405].includes(error?.response?.status)) throw error;
        return legacyDetail(typeof device === 'object' ? device : { id: deviceId });
    }
}

export async function getDeviceEntities(deviceId, params = {}) {
    if (useMultiProfileFixtures) {
        const detail = fixtureDeviceDetails[deviceId];
        const items = detail?.sections?.flatMap((section) => (
            section.entities.map((item) => ({
                ...item,
                table_id: section.key,
                profile_id: detail.device.profile.id,
            }))
        )) || [];
        return fixturePage(items, params.page || 1, params.page_size || 100);
    }
    const response = await api.get(`/devices/${encodeURIComponent(deviceId)}/entities`, { params });
    return normalizePagedResult(response.data, params.page_size || 100);
}

export async function getProfiles() {
    if (useMultiProfileFixtures) return fixturePage(fixtureProfiles);
    const response = await api.get('/profiles');
    return {
        ...normalizePagedResult(response.data, 100),
        items: unwrapList(response.data).map(sanitizeSensitiveData),
    };
}

export async function getDiscoveryConfig() {
    if (useMultiProfileFixtures) return { ...fixtureDiscoveryConfig };
    const response = await api.get('/discovery/config');
    return sanitizeSensitiveData(response.data);
}

export async function updateDiscoveryConfig(config) {
    if (useMultiProfileFixtures) {
        return sanitizeSensitiveData({ ...fixtureDiscoveryConfig, ...config, updated_at: new Date().toISOString() });
    }
    const response = await api.put('/discovery/config', config);
    return sanitizeSensitiveData(response.data);
}

export async function runDiscoveryScan() {
    if (useMultiProfileFixtures) return { job_id: 43, status: 'queued' };
    const response = await api.post('/discovery/scan');
    return response.data;
}

export async function getDiscoveryJobs(params = {}) {
    if (useMultiProfileFixtures) return fixturePage(fixtureDiscoveryJobs, params.page || 1, params.page_size || 50);
    const response = await api.get('/discovery/jobs', { params });
    return normalizePagedResult(response.data, params.page_size || 50);
}

export async function getDiscoveryJob(jobId) {
    if (useMultiProfileFixtures) {
        return fixtureDiscoveryJobs.find((job) => String(job.id) === String(jobId)) || null;
    }
    const response = await api.get(`/discovery/jobs/${encodeURIComponent(jobId)}`);
    return response.data;
}

export async function getAuditLogs(params = {}) {
    if (useMultiProfileFixtures) return fixturePage(fixtureAuditLogs, params.page || 1, params.page_size || 50);
    const response = await api.get('/audit-logs', { params });
    return normalizePagedResult(response.data, params.page_size || 50);
}

export async function exportAuditLogs(params = {}) {
    if (useMultiProfileFixtures) {
        const header = 'id,actor,action,target_type,target_id,result,created_at';
        const rows = fixtureAuditLogs.map((item) => [
            item.id,
            item.actor.username,
            item.action,
            item.target.type,
            item.target.id,
            item.result,
            item.created_at,
        ].join(','));
        return new Blob([[header, ...rows].join('\n')], { type: 'text/csv;charset=utf-8' });
    }
    const response = await api.get('/audit-logs/export', { params, responseType: 'blob' });
    return response.data;
}
