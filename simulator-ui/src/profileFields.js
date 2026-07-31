export const PROFILE_LABELS = {
  ccdc_legacy: 'CCDC Matrix',
  ccdc_legacy_unverified: 'CCDC Matrix',
  ccdm_matrix: 'CCDM Matrix',
  visionxs_cpu: 'VisionXS CPU',
  visionxs_con: 'VisionXS CON',
  dp12_mux_atc: 'DP1.2 MUX ATC',
  dp12_mux_atc_readonly: 'DP1.2 MUX ATC',
};

export const DEVICE_PALETTE = [
  { type: 'ccdc_legacy', label: 'CCDC 矩阵', ports: 20, category: 'matrix' },
  { type: 'ccdm_matrix', label: 'CCDM 矩阵', ports: 32, category: 'matrix' },
  { type: 'visionxs_cpu', label: 'VisionXS CPU', ports: 1, category: 'endpoint' },
  { type: 'visionxs_con', label: 'VisionXS CON', ports: 1, category: 'endpoint' },
  { type: 'dp12_mux_atc', label: 'DP12 MUX', ports: 4, category: 'switch' },
];

export const FALLBACK_PROFILE_FIELDS = [
  {
    group: '设备状态',
    fields: [
      { path: 'scalars.status', label: '设备状态', type: 'enum', mutable: true, options: { online: '在线', offline: '离线', warning: '告警' } },
      { path: 'scalars.temperature1', label: '温度 1', type: 'number', mutable: true, unit: '℃' },
      { path: 'scalars.main_power', label: '主电源', type: 'boolean', mutable: true },
      { path: 'scalars.backup_power', label: '备电源', type: 'boolean', mutable: true },
    ],
  },
  {
    group: '网络 / 链路',
    fields: [
      { path: 'ports[1].status', label: '端口 1 状态', type: 'enum', mutable: true, options: { up: 'up', down: 'down', 1: 'up', 0: 'down' } },
      { path: 'ports[1].sfpRxPower', label: '端口 1 SFP Rx', type: 'number', mutable: true, unit: 'dBm' },
      { path: 'ports[1].sfpTxPower', label: '端口 1 SFP Tx', type: 'number', mutable: true, unit: 'dBm' },
    ],
  },
];

export function metadataToGroups(metadata, device) {
  const raw = metadata?.profiles?.[device?.profile] || metadata?.[device?.profile] || device?.profile_metadata || device?.metadata;
  if (!raw) return FALLBACK_PROFILE_FIELDS;
  const groups = raw.groups || raw.ui_groups || raw.field_groups;
  if (Array.isArray(groups)) return groups;
  const fields = raw.fields || raw.mutable_fields || [];
  const byGroup = new Map();
  for (const field of fields) {
    const group = field.group || field.ui_group || 'Profile fields';
    if (!byGroup.has(group)) byGroup.set(group, []);
    byGroup.get(group).push({ ...field, mutable: field.mutable !== false });
  }
  return [...byGroup.entries()].map(([group, groupedFields]) => ({ group, fields: groupedFields }));
}

export function readPathValue(source, path) {
  if (!source || !path) return undefined;
  const parts = path.replace(/\[(.*?)\]/g, '.$1').split('.').filter(Boolean);
  const root = parts[0];
  const base = (root === 'scalars' || root === 'tables') && source.profile_state ? source.profile_state : source;
  return parts.reduce((value, part) => (value && value[part] !== undefined ? value[part] : undefined), base);
}

export function normalizeRuntimeSnapshot(snapshot) {
  const scenario = snapshot?.scenario || snapshot?.topology || snapshot || {};
  const devices = scenario.devices || snapshot?.devices || [];
  const edges = scenario.edges || snapshot?.edges || [];
  return { scenario, devices, edges, revision: snapshot?.revision ?? 0, pausedDevices: snapshot?.paused_devices || [] };
}
