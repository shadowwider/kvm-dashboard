import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 8000,
  headers: { 'Content-Type': 'application/json' },
});

const unwrap = response => response.data;

export function apiError(error) {
  const body = error?.response?.data;
  return {
    status: error?.response?.status || 0,
    code: body?.code || body?.detail?.code || 'request_failed',
    message: body?.message || body?.detail?.message || (typeof body?.detail === 'string' ? body.detail : error?.message || 'Request failed'),
    details: body?.details || body?.detail?.details || {},
    revision: body?.revision ?? body?.current_revision,
    retryable: Boolean(body?.retryable),
  };
}

export async function listTopologies() {
  return unwrap(await api.get('/topologies'));
}

export async function loadTopology(id) {
  return unwrap(await api.get(`/topologies/${encodeURIComponent(id)}`));
}

export async function saveTopology(topology, { forceCreate = false } = {}) {
  const shouldCreate = forceCreate || !topology.id;
  const method = shouldCreate ? 'post' : 'put';
  const path = shouldCreate ? '/topologies' : `/topologies/${encodeURIComponent(topology.id)}`;
  return unwrap(await api[method](path, topology));
}

export async function startTopology(id) {
  return unwrap(await api.post(`/topologies/${encodeURIComponent(id)}/start`));
}

export async function stopTopology(id) {
  return unwrap(await api.post(`/topologies/${encodeURIComponent(id)}/stop`));
}

export async function getRuntimeState() {
  return unwrap(await api.get('/state'));
}

export async function getStatus() {
  return unwrap(await api.get('/status'));
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
  return unwrap(await api.patch(`/runtime/devices/${encodeURIComponent(deviceId)}/state`, {
    patches: patchList,
    emit_trap: Boolean(options.emitTrap),
    ...(options.expectedRevision === undefined ? {} : { expected_revision: options.expectedRevision }),
  }));
}

export async function deviceAction(deviceId, action) {
  return unwrap(await api.post(`/runtime/devices/${encodeURIComponent(deviceId)}/actions`, { action }));
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
