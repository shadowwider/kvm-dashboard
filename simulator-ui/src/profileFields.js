/**
 * UI-only adapters.  This file intentionally contains no OID, field, enum,
 * range, or writable-path fallback.  Those facts belong to L4 metadata.
 */

export function normalizeRuntimeSnapshot(snapshot) {
  const source = snapshot?.state || snapshot?.snapshot || snapshot || {};
  const scenario = source.scenario || source.topology || source;
  const instances = source.runtime_instances?.devices || [];
  const instancesByDeviceId = new Map(instances.map(instance => [instance.device_id, instance]));
  const devices = (scenario?.devices || source.devices || []).map(device => {
    const deviceId = device.id || device.identity?.device_id;
    const instance = instancesByDeviceId.get(deviceId);
    // The scenario carries values/availability; L4 keeps instance-only path
    // metadata separately so it never expands non-existent fixture rows.
    return instance ? { ...device, path_registry: instance.path_registry } : device;
  });
  return {
    scenario,
    devices,
    edges: scenario?.edges || source.edges || [],
    revision: source.revision ?? snapshot?.revision ?? 0,
    pausedDevices: source.paused_devices || [],
    activeTopologyId: source.active_topology_id || snapshot?.active_topology_id || null,
  };
}

export function registryFields(device, metadata) {
  const registry = device?.path_registry
    || metadata?.devices?.[device?.id]?.path_registry
    || metadata?.runtime_instances?.[device?.id]?.path_registry;
  const paths = registry?.paths || [];
  return paths.map(spec => ({
    ...spec,
    label: spec.path,
    mutable: spec.runtime_writable === true,
    group: spec.kind === 'scalar' ? 'scalars' : spec.kind === 'column' ? `tables.${spec.table_id}` : spec.kind,
  }));
}

export function groupRegistryFields(device, metadata, query = '') {
  const needle = query.trim().toLowerCase();
  const fields = registryFields(device, metadata).filter(field =>
    !needle || field.path.toLowerCase().includes(needle) || field.syntax?.toLowerCase().includes(needle),
  );
  const groups = new Map();
  for (const field of fields) {
    if (!groups.has(field.group)) groups.set(field.group, []);
    groups.get(field.group).push(field);
  }
  return [...groups.entries()].map(([group, groupedFields]) => ({ group, fields: groupedFields }));
}

export function readPathValue(device, path) {
  if (!device || !path) return undefined;
  const values = device.profile_state || device;
  if (path.startsWith('scalars.')) return values.scalars?.[path.slice('scalars.'.length)];
  const table = path.match(/^tables\.([^[]+)\[([^\]]+)\]\.(.+)$/);
  if (table) {
    const [, tableId, rowKey, fieldId] = table;
    const row = values.tables?.[tableId]?.[rowKey];
    return fieldId.startsWith('indexes.')
      ? row?.indexes?.[Number(fieldId.slice('indexes.'.length))]
      : row?.values?.[fieldId] ?? row?.[fieldId];
  }
  if (path === 'runtime.availability') return device.runtime?.availability || device.availability;
  if (path.startsWith('identity.')) return device.identity?.[path.slice('identity.'.length)];
  return undefined;
}

export function profilePalette(metadata) {
  const profiles = metadata?.profiles || {};
  return Object.entries(profiles).map(([id, profile]) => ({
    id,
    label: profile.display_name || id,
    category: profile.category || 'device',
  }));
}
