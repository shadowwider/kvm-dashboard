import { useCallback, useEffect, useState } from 'react';
import { Download, Filter, RefreshCw } from 'lucide-react';
import {
    exportAuditLogs,
    getApiError,
    getAuditLogs,
} from '../../services/multiProfileApi';
import { buildAuditLogQuery } from '../../utils/auditFilters';

const initialFilters = {
    actor_id: '',
    action: '',
    target_type: '',
    target_id: '',
    result: '',
    date_from: '',
    date_to: '',
};

export default function AuditLogsTab({ showToast, t }) {
    const [filters, setFilters] = useState(initialFilters);
    const [appliedFilters, setAppliedFilters] = useState(initialFilters);
    const [page, setPage] = useState(1);
    const [result, setResult] = useState({ items: [], total: 0, page: 1, page_size: 50 });
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            setResult(await getAuditLogs(buildAuditLogQuery(appliedFilters, page)));
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        } finally {
            setLoading(false);
        }
    }, [appliedFilters, page, showToast, t]);

    useEffect(() => {
        load();
    }, [load]);

    const apply = () => {
        setPage(1);
        setAppliedFilters(filters);
    };

    const exportCsv = async () => {
        try {
            const blob = await exportAuditLogs(buildAuditLogQuery(appliedFilters, page));
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`;
            link.click();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            showToast(getApiError(error).message || t('admin.common.error'), 'error');
        }
    };

    const totalPages = Math.max(Math.ceil(result.total / result.page_size), 1);

    return (
        <>
            <div className="admin-toolbar audit-toolbar">
                <div className="admin-toolbar-left">
                    <input
                        className="admin-search"
                        value={filters.actor_id}
                        onChange={(event) => setFilters({ ...filters, actor_id: event.target.value })}
                        placeholder={t('admin.audit.actor_id')}
                    />
                    <input
                        className="admin-search"
                        value={filters.action}
                        onChange={(event) => setFilters({ ...filters, action: event.target.value })}
                        placeholder={t('admin.audit.action')}
                    />
                    <input
                        className="admin-search"
                        value={filters.target_type}
                        onChange={(event) => setFilters({ ...filters, target_type: event.target.value })}
                        placeholder={t('admin.audit.target_type')}
                    />
                    <input
                        className="admin-search"
                        value={filters.target_id}
                        onChange={(event) => setFilters({ ...filters, target_id: event.target.value })}
                        placeholder={t('admin.audit.target_id')}
                    />
                    <select
                        className="admin-select"
                        value={filters.result}
                        onChange={(event) => setFilters({ ...filters, result: event.target.value })}
                    >
                        <option value="">{t('admin.audit.all_results')}</option>
                        <option value="success">{t('audit_result.success')}</option>
                        <option value="failure">{t('audit_result.failure')}</option>
                    </select>
                    <input
                        className="admin-search"
                        type="datetime-local"
                        value={filters.date_from}
                        onChange={(event) => setFilters({ ...filters, date_from: event.target.value })}
                        aria-label={t('admin.audit.date_from')}
                    />
                    <input
                        className="admin-search"
                        type="datetime-local"
                        value={filters.date_to}
                        onChange={(event) => setFilters({ ...filters, date_to: event.target.value })}
                        aria-label={t('admin.audit.date_to')}
                    />
                </div>
                <div className="admin-toolbar-right">
                    <button className="admin-btn" onClick={apply}>
                        <Filter size={14} /> {t('admin.audit.apply_filters')}
                    </button>
                    <button className="admin-btn" onClick={load}>
                        <RefreshCw size={14} /> {t('admin.common.refresh')}
                    </button>
                    <button className="admin-btn primary" onClick={exportCsv}>
                        <Download size={14} /> {t('admin.audit.export')}
                    </button>
                </div>
            </div>

            <div className="admin-table-wrap audit-table-wrap">
                <table className="admin-table">
                    <thead>
                        <tr>
                            <th>{t('admin.audit.time')}</th>
                            <th>{t('admin.audit.actor')}</th>
                            <th>{t('admin.audit.action')}</th>
                            <th>{t('admin.audit.target')}</th>
                            <th>{t('admin.audit.result')}</th>
                            <th>{t('admin.audit.ip_address')}</th>
                            <th>{t('admin.audit.change_summary')}</th>
                            <th>{t('admin.audit.request_id')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {result.items.map((item) => (
                            <tr key={item.id}>
                                <td>{item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</td>
                                <td>{item.actor?.username || item.actor?.id || '—'}</td>
                                <td>{t(`audit_action.${item.action}`, item.action)}</td>
                                <td>{item.target ? `${item.target.type}:${item.target.id}` : '—'}</td>
                                <td><span className={`status-badge ${item.result}`}>{t(`audit_result.${item.result}`, item.result)}</span></td>
                                <td>{item.ip_address || '—'}</td>
                                <td><code>{item.change_summary ? JSON.stringify(item.change_summary) : '—'}</code></td>
                                <td>{item.request_id || '—'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {!loading && result.items.length === 0 && (
                    <div className="admin-empty">{t('admin.common.no_data')}</div>
                )}
                {loading && <div className="admin-empty">{t('admin.common.loading')}</div>}
            </div>

            <div className="admin-pagination">
                <button className="admin-btn" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
                    {t('admin.common.previous')}
                </button>
                <span>
                    {t('admin.common.page_of', '{{page}} / {{total}}')
                        .replace('{{page}}', page)
                        .replace('{{total}}', totalPages)}
                </span>
                <button className="admin-btn" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>
                    {t('admin.common.next')}
                </button>
            </div>
        </>
    );
}
