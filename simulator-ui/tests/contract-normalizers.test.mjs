import assert from 'node:assert/strict';
import test from 'node:test';
import fixture from './fixtures/api-v1-draft.json' with { type: 'json' };
import { groupRegistryFields, normalizeRuntimeSnapshot, readPathValue } from '../src/profileFields.js';

test('L4 Draft state fixture keeps server topology and revision authoritative', () => {
  const snapshot = normalizeRuntimeSnapshot(fixture.state);
  assert.equal(snapshot.revision, 7);
  assert.equal(snapshot.activeTopologyId, 'all-profiles');
  assert.equal(snapshot.devices[0].id, 'device-1');
});

test('actual L3 registry drives scalar and composite-index field rendering', () => {
  const device = fixture.state.scenario.devices[0];
  const groups = groupRegistryFields(device, {});
  assert.deepEqual(groups.map(group => group.group), ['scalars', 'tables.fan_table']);
  assert.equal(readPathValue(device, 'scalars.switch_temperature'), 42);
  assert.equal(readPathValue(device, 'tables.fan_table[1,2].fan_speed'), 3400);
  assert.equal(groups.flatMap(group => group.fields).some(field => field.path.startsWith('ports[')), false);
});
