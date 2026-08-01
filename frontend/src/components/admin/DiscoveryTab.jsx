import { useCallback, useEffect, useMemo, useState } from 'react';
import { Play, RefreshCw, Save } from 'lucide-react';
import {
    getApiError,
    getDiscoveryConfig,
    getDiscoveryJobs,
    runDiscoveryScan,
    updateDiscoveryConfig,
} from '../../services/multiProfileApi';
import { useStore } from '../../store/mainStore';

const emptyConfig = {
    cidr: '',
    snmp_port: 161,
    timeout_seconds: 0.5,
    retries: 0,
    concurrency: 64,
    enabled: true,
    scan_on_startup: false,
    credential_configured: false,
    community: '',
};

function progressFor(job) {
    if (!job?.total_hosts) return 0;
    return Math.min((Number(job.scanned_hosts || 0) / Number(job.total_hosts)) * 100, 100);
}

export default function DiscoveryTab({ showToast, t }) {
    const liveJobs = useStore((state) => state.discoveryJobs);
    const [config, setConfig] = useState(emptyConfig);
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [scanning, setScanning] = useState(false);

    const load = useCallback(async () => {
        try {
            const [nextConfig, jobPage] = await Promise.all([
                getDiscoveryConfig(),
                getDiscoveryJobs({ page: 1, page_size: 50 }),
            ]);
            setConfig({ ...emptyConfig, ...nextConfig, community: '' });
            setJobs(jobPage.items);
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        } finally {
            setLoading(false);
        }
    }, [showToast, t]);

    useEffect(() => {
        load();
    }, [load]);

    useEffect(() => {
        const hasRunningJob = jobs.some((job) => ['queued', 'running'].includes(job.status));
        if (!hasRunningJob) return undefined;
        const timer = window.setInterval(async () => {
            try {
                const result = await getDiscoveryJobs({ page: 1, page_size: 50 });
                setJobs(result.items);
            } catch {
                // The WebSocket path remains active; a later interval can recover.
            }
        }, 2000);
        return () => window.clearInterval(timer);
    }, [jobs]);

    const mergedJobs = useMemo(() => {
        const byId = new Map(jobs.map((job) => [String(job.id), job]));
        Object.values(liveJobs).forEach((job) => byId.set(String(job.id), job));
        return [...byId.values()].sort((left, right) => Number(right.id) - Number(left.id));
    }, [jobs, liveJobs]);

    const setField = (key, value) => {
        setConfig((current) => ({ ...current, [key]: value }));
    };

    const save = async () => {
        const payload = {
            cidr: config.cidr.trim(),
            snmp_port: Number(config.snmp_port),
            timeout_seconds: Number(config.timeout_seconds),
            retries: Number(config.retries),
            concurrency: Number(config.concurrency),
            enabled: Boolean(config.enabled),
            scan_on_startup: Boolean(config.scan_on_startup),
        };
        if (config.community.trim()) payload.community = config.community;

        setSaving(true);
        try {
            const saved = await updateDiscoveryConfig(payload);
            setConfig((current) => ({ ...current, ...saved, community: '' }));
            showToast(t('admin.discovery.saved'));
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        } finally {
            setSaving(false);
        }
    };

    const scan = async () => {
        setScanning(true);
        try {
            await runDiscoveryScan();
            showToast(t('admin.discovery.scan_started'));
            const result = await getDiscoveryJobs({ page: 1, page_size: 50 });
            setJobs(result.items);
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        } finally {
            setScanning(false);
        }
    };

    if (loading) return <div className="admin-empty">{t('admin.common.loading')}</div>;

    return (
        <div className="admin-split">
            <section className="admin-section">
                <div className="admin-section-header">
                    <div>
                        <h2>{t('admin.discovery.config_title')}</h2>
                        <p>{t('admin.discovery.config_hint')}</p>
                    </div>
                    <span className={`status-badge ${config.credential_configured ? 'online' : 'warning'}`}>
                        {config.credential_configured
                            ? t('admin.discovery.credential_configured')
                            : t('admin.discovery.credential_missing')}
                    </span>
                </div>

                <div className="admin-form-grid">
                    <label>
                        <span>{t('admin.discovery.cidr')}</span>
                        <input
                            value={config.cidr}
                            onChange={(event) => setField('cidr', event.target.value)}
                            placeholder={t('admin.discovery.cidr_placeholder')}
                        />
                    </label>
                    <label>
                        <span>{t('admin.discovery.community')}</span>
                        <input
                            type="password"
                            value={config.community}
                            onChange={(event) => setField('community', event.target.value)}
                            placeholder={t('admin.discovery.community_placeholder')}
                            autoComplete="new-password"
                        />
                    </label>
                    <label>
                        <span>{t('admin.discovery.snmp_port')}</span>
                        <input
                            type="number"
                            value={config.snmp_port}
                            onChange={(event) => setField('snmp_port', event.target.value)}
                        />
                    </label>
                    <label>
                        <span>{t('admin.discovery.timeout')}</span>
                        <input
                            type="number"
                            min="0.1"
                            step="0.1"
                            value={config.timeout_seconds}
                            onChange={(event) => setField('timeout_seconds', event.target.value)}
                        />
                    </label>
                    <label>
                        <span>{t('admin.discovery.retries')}</span>
                        <input
                            type="number"
                            min="0"
                            value={config.retries}
                            onChange={(event) => setField('retries', event.target.value)}
                        />
                    </label>
                    <label>
                        <span>{t('admin.discovery.concurrency')}</span>
                        <input
                            type="number"
                            min="1"
                            max="256"
                            value={config.concurrency}
                            onChange={(event) => setField('concurrency', event.target.value)}
                        />
                    </label>
                </div>

                <div className="admin-check-row">
                    <label>
                        <input
                            type="checkbox"
                            checked={config.enabled}
                            onChange={(event) => setField('enabled', event.target.checked)}
                        />
                        <span>{t('admin.discovery.enabled')}</span>
                    </label>
                    <label>
                        <input
                            type="checkbox"
                            checked={config.scan_on_startup}
                            onChange={(event) => setField('scan_on_startup', event.target.checked)}
                        />
                        <span>{t('admin.discovery.scan_on_startup')}</span>
                    </label>
                </div>

                <div className="admin-section-actions">
                    <button className="admin-btn" onClick={load}>
                        <RefreshCw size={14} /> {t('admin.common.refresh')}
                    </button>
                    <button className="admin-btn primary" onClick={save} disabled={saving}>
                        <Save size={14} /> {saving ? t('admin.common.saving') : t('admin.common.save')}
                    </button>
                    <button className="admin-btn success" onClick={scan} disabled={scanning || !config.enabled}>
                        <Play size={14} /> {scanning ? t('admin.discovery.starting') : t('admin.discovery.scan_now')}
                    </button>
                </div>
            </section>

            <section className="admin-section">
                <div className="admin-section-header">
                    <div>
                        <h2>{t('admin.discovery.jobs_title')}</h2>
                        <p>{t('admin.discovery.jobs_hint')}</p>
                    </div>
                </div>
                <div className="admin-table-wrap">
                    <table className="admin-table discovery-table">
                        <thead>
                            <tr>
                                <th>{t('admin.discovery.job_id')}</th>
                                <th>{t('admin.discovery.job_status')}</th>
                                <th>{t('admin.discovery.progress')}</th>
                                <th>{t('admin.discovery.responded')}</th>
                                <th>{t('admin.discovery.recognized')}</th>
                                <th>{t('admin.discovery.imported')}</th>
                                <th>{t('admin.discovery.updated')}</th>
                                <th>{t('admin.discovery.unsupported')}</th>
                                <th>{t('admin.discovery.errors')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {mergedJobs.map((job) => (
                                <tr key={job.id}>
                                    <td>#{job.id}</td>
                                    <td><span className={`status-badge ${job.status}`}>{t(`job_status.${job.status}`)}</span></td>
                                    <td>
                                        <div className="discovery-progress">
                                            <span style={{ width: `${progressFor(job)}%` }} />
                                        </div>
                                        <small>{job.scanned_hosts ?? 0}/{job.total_hosts ?? 0}</small>
                                    </td>
                                    <td>{job.responded_hosts ?? 0}</td>
                                    <td>{job.recognized_hosts ?? 0}</td>
                                    <td>{job.imported_devices ?? 0}</td>
                                    <td>{job.updated_devices ?? 0}</td>
                                    <td>{job.unsupported_devices ?? 0}</td>
                                    <td title={job.last_error || ''}>{job.error_count ?? 0}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {mergedJobs.length === 0 && (
                        <div className="admin-empty">{t('admin.discovery.no_jobs')}</div>
                    )}
                </div>
            </section>
        </div>
    );
}
