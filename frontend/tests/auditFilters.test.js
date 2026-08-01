import assert from 'node:assert/strict';
import test from 'node:test';

import { buildAuditLogQuery } from '../src/utils/auditFilters.js';

test('audit query includes target_id and omits empty filters', () => {
    assert.deepEqual(buildAuditLogQuery({
        actor_id: '',
        action: 'device.update',
        target_type: 'device',
        target_id: 'fixture-ccdm_matrix',
        result: '',
    }, 2), {
        action: 'device.update',
        target_type: 'device',
        target_id: 'fixture-ccdm_matrix',
        page: 2,
        page_size: 50,
    });
});
