import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 8000,
  headers: { 'Content-Type': 'application/json' },
});

const unwrap = response => response.data;

export async function listTopologies() {
  try {
    return unwrap(await api.get('/topologies'));
  } catch {
    const scenarios = unwrap(await api.get('/scenarios'));
    return scenarios.map(item => ({
      ...item,
      name: item.name || item.title,
      title: item.title || item.name,
      read_only: true,
      preset: true,
      source: 'legacy-scenario',
    }));
  }
}

export async function loadTopology(id) {
  try {
    return unwrap(await api.get(`/topologies/${encodeURIComponent(id)}`));
  } catch (error) {
    if (error.response && error.response.status !== 404) throw error;
    return unwrap(await api.post(`/scenarios/${encodeURIComponent(id)}/load`));
  }
}

export async function saveTopology(topology, { forceCreate = false } = {}) {
  const shouldCreate = forceCreate || !topology.id;
  const method = shouldCreate ? 'post' : 'put';
  const path = shouldCreate ? '/topologies' : `/topologies/${encodeURIComponent(topology.id)}`;
  return unwrap(await api[method](path, topology));
}

export async function startTopology(id) {
  try {
    return unwrap(await api.post(`/topologies/${encodeURIComponent(id)}/start`));
  } catch (error) {
    if (error.response && error.response.status !== 404) throw error;
    return unwrap(await api.post(`/scenarios/${encodeURIComponent(id)}/load`));
  }
}

export async function stopTopology(id) {
  return unwrap(await api.post(`/topologies/${encodeURIComponent(id)}/stop`));
}

export async function getRuntimeState() {
  return unwrap(await api.get('/state'));
}

export async function getProfiles() {
  try {
    return unwrap(await api.get('/profiles'));
  } catch {
    return null;
  }
}

export async function patchDeviceState(deviceId, patches, options = {}) {
  const patchList = Array.isArray(patches)
    ? patches
    : Object.entries(patches || {}).map(([path, value]) => ({ path, value }));
  try {
    return unwrap(await api.patch(`/runtime/devices/${encodeURIComponent(deviceId)}/state`, {
      patches: patchList,
      emit_trap: Boolean(options.emitTrap),
    }));
  } catch (error) {
    if (error.response && ![404, 405].includes(error.response.status)) throw error;
    const endpointPatch = patchList.find(item => item.path.startsWith('endpoints['));
    if (!endpointPatch) throw new Error('Simulator backend does not expose generic runtime state PATCH yet.');
    const [, endpointId, field] = endpointPatch.path.match(/^endpoints\[([^\]]+)\]\.(.+)$/) || [];
    if (!endpointId || field !== 'status') throw new Error('Legacy API only supports endpoint status patches.');
    return unwrap(await api.patch(`/devices/${encodeURIComponent(deviceId)}/endpoints/${encodeURIComponent(endpointId)}`, { status: endpointPatch.value }));
  }
}

export async function deviceAction(deviceId, action) {
  try {
    return unwrap(await api.post(`/runtime/devices/${encodeURIComponent(deviceId)}/actions`, { action }));
  } catch (error) {
    if (error.response && ![404, 405].includes(error.response.status)) throw error;
    if (action === 'disconnect' || action === 'restore') {
      return unwrap(await api.post(`/devices/${encodeURIComponent(deviceId)}/reachability`, null, {
        params: { paused: action === 'disconnect' },
      }));
    }
    throw new Error('Device power actions require the new simulator runtime API.');
  }
}

export async function sendTrap(payload) {
  return unwrap(await api.post('/traps', payload));
}

export function openSimulatorSocket({ onMessage, onOpen, onClose, onError }) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws`);
  socket.addEventListener('open', event => onOpen?.(event));
  socket.addEventListener('close', event => onClose?.(event));
  socket.addEventListener('error', event => onError?.(event));
  socket.addEventListener('message', event => {
    try {
      onMessage?.(JSON.parse(event.data));
    } catch {
      onMessage?.({ type: 'raw', payload: event.data });
    }
  });
  return socket;
}
