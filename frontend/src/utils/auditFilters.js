export function buildAuditLogQuery(filters, page, pageSize = 50) {
    return Object.fromEntries(Object.entries({
        ...filters,
        page,
        page_size: pageSize,
    }).filter(([, value]) => value !== ''));
}
