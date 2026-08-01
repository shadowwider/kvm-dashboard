import { useCallback, useEffect, useRef, useState } from 'react';
import { addEdge, Background, Controls, MiniMap, ReactFlow, useEdgesState, useNodesState } from '@xyflow/react';
import SimulatorNode from './components/SimulatorNode.jsx';
import TopologySidebar from './components/TopologySidebar.jsx';
import RuntimeToolbar from './components/RuntimeToolbar.jsx';
import DetailsDrawer from './components/DetailsDrawer.jsx';
import TrapPanel from './components/TrapPanel.jsx';
import EventTimeline from './components/EventTimeline.jsx';
import { apiError, deviceAction, getProfiles, getRuntimeState, getStatus, listTopologies, loadTopology, openSimulatorSocket, patchDeviceState, patchEndpointState, saveTopology, sendTrap, startTopology, stopTopology } from './api/client.js';
import { normalizeRuntimeSnapshot, profilePalette } from './profileFields.js';

const nodeTypes = { simulator: SimulatorNode };
const MAX_BATCH = 100;
const event = (type, payload = {}) => ({ id: `${Date.now()}-${crypto.randomUUID?.() || Math.random()}`, time: Date.now(), type, ...payload });

function toFlow(snapshot) {
  const { devices, edges, pausedDevices } = normalizeRuntimeSnapshot(snapshot);
  const deviceNodes = devices.map((device, index) => ({
    id: device.id || device.identity?.device_id,
    type: 'simulator', position: device.position || { x: 120 + (index % 3) * 285, y: 90 + Math.floor(index / 3) * 210 },
    data: { ...device, node_kind: 'device', paused: pausedDevices.includes(device.id || device.identity?.device_id) },
  })).filter(node => node.id);
  const endpointNodes = devices.flatMap((device, deviceIndex) => (device.endpoints || []).map((endpoint, endpointIndex) => ({
    id: endpoint.id, type: 'simulator', position: { x: (device.position?.x ?? 120 + (deviceIndex % 3) * 285) + 245, y: (device.position?.y ?? 90 + Math.floor(deviceIndex / 3) * 210) + endpointIndex * 74 },
    data: { ...endpoint, node_kind: 'endpoint', name: endpoint.display_name || endpoint.id, parent_device_id: device.id, profile: device.profile, paused: pausedDevices.includes(device.id) },
  })));
  const known = new Set([...deviceNodes, ...endpointNodes].map(node => node.id));
  const routes = edges.length ? edges : devices.flatMap(device => device.routes || []);
  return {
    nodes: [...deviceNodes, ...endpointNodes],
    edges: routes.map((edge, index) => ({
      id: edge.id || `edge-${index}`, source: edge.source || edge.source_device_id || edge.source_endpoint_id,
      target: edge.target || edge.target_device_id || edge.target_endpoint_id,
      sourceHandle: edge.source_port ? `port:${edge.source_port}` : undefined,
      targetHandle: edge.target_port ? `port:${edge.target_port}` : undefined,
      label: edge.kind === 'port-link' ? 'physical edge' : edge.label || 'simulation route',
      className: edge.kind === 'port-link' ? 'physical-edge' : 'simulation-edge',
      style: edge.kind === 'port-link' ? undefined : { strokeDasharray: '7 5' },
      data: { kind: edge.kind || 'route', metadata: edge.metadata || {}, evidence: edge.evidence || 'simulation-declared' },
    })).filter(edge => known.has(edge.source) && known.has(edge.target) && edge.source !== edge.target),
  };
}

function topologyPayload(activeTopologyId, nodes, edges, forceNew, revision) {
  const id = forceNew || !activeTopologyId ? `topology-${Date.now()}` : activeTopologyId;
  return {
    id, title: forceNew || !activeTopologyId ? `Simulator topology ${new Date().toLocaleString()}` : id, revision: forceNew ? 1 : (revision || 1),
    devices: nodes.filter(node => node.data.node_kind !== 'endpoint').map((node, index) => ({
      id: node.id, name: node.data.name || node.id, profile: node.data.profile,
      host: node.data.host || null, snmp_port: node.data.snmp_port || 11161 + index,
      ports: Array.isArray(node.data.ports) ? node.data.ports : [], endpoints: node.data.endpoints || [], routes: node.data.routes || [],
      profile_state: node.data.profile_state || {}, position: node.position,
    })),
    // Never drop endpoint-to-endpoint routes. Server decides semantic validity.
    edges: edges.map(edge => ({ id: edge.id, source: edge.source, target: edge.target, kind: edge.data?.kind || 'route', source_port: edge.data?.source_port, target_port: edge.data?.target_port, label: typeof edge.label === 'string' ? edge.label : undefined, metadata: edge.data?.metadata || {} })),
  };
}

export default function App() {
  const [topologies, setTopologies] = useState([]); const [status, setStatus] = useState(null);
  const [runtime, setRuntime] = useState(null); const [metadata, setMetadata] = useState(null);
  const [activeTopologyId, setActiveTopologyId] = useState(''); const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [events, setEvents] = useState([]); const [trapHistory, setTrapHistory] = useState([]); const [wsState, setWsState] = useState('connecting');
  const [loading, setLoading] = useState(false); const [fieldErrors, setFieldErrors] = useState({}); const [pending, setPending] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState([]); const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const revisionRef = useRef(0); const retryRef = useRef(null);
  const push = useCallback(item => setEvents(current => [event(item.type || 'event', item), ...current].slice(0, 100)), []);
  const applySnapshot = useCallback((snapshot, source = 'snapshot') => {
    if (!snapshot) return;
    const next = normalizeRuntimeSnapshot(snapshot); revisionRef.current = Math.max(revisionRef.current, Number(next.revision || 0));
    setRuntime(snapshot); setActiveTopologyId(current => next.activeTopologyId || current);
    const flow = toFlow(snapshot); setNodes(flow.nodes); setEdges(flow.edges);
    push({ type: source, message: `revision ${next.revision ?? 0}` });
  }, [push, setEdges, setNodes]);
  const refreshRuntime = useCallback(async (source = 'REST refresh') => applySnapshot(await getRuntimeState(), source), [applySnapshot]);
  const refreshStatus = useCallback(async () => setStatus(await getStatus()), []);
  const refreshTopologies = useCallback(async () => { const data = await listTopologies(); setTopologies(Array.isArray(data) ? data : data.items || data.topologies || []); }, []);
  const refreshMetadata = useCallback(async () => { const data = await getProfiles(); if (data) setMetadata(data); }, []);
  const refreshAll = useCallback(async () => Promise.all([refreshRuntime(), refreshStatus(), refreshTopologies(), refreshMetadata()]), [refreshMetadata, refreshRuntime, refreshStatus, refreshTopologies]);

  useEffect(() => { const timer = setTimeout(() => { refreshAll().catch(error => push({ type: 'initial-load-failed', message: apiError(error).message })); }, 0); return () => clearTimeout(timer); }, [push, refreshAll]);
  useEffect(() => {
    let disposed = false; let socket;
    const connect = () => {
      if (disposed) return; setWsState('connecting'); socket = openSimulatorSocket({
        onOpen: () => setWsState('online'), onError: () => setWsState('error'),
        onClose: () => { if (disposed) return; setWsState('reconnecting'); retryRef.current = setTimeout(connect, 1000); },
        onMessage: message => {
          const incoming = Number(message.revision ?? message.state?.revision ?? message.snapshot?.revision ?? 0);
          if (incoming && incoming > revisionRef.current + 1) { push({ type: 'ws-gap', message: `revision gap ${revisionRef.current} → ${incoming}; refetching` }); refreshRuntime('WS gap refetch').catch(error => push({ type: 'refresh-failed', message: apiError(error).message })); return; }
          if (incoming && incoming < revisionRef.current) return;
          if (message.state || message.snapshot) applySnapshot(message.state || message.snapshot, message.type || 'WS snapshot');
          else if (message.type === 'topology_stopped') {
            setRuntime(null); setNodes([]); setEdges([]); setSelectedNodeId(null);
            refreshStatus().catch(error => push({ type: 'refresh-failed', message: apiError(error).message }));
            refreshTopologies().catch(error => push({ type: 'refresh-failed', message: apiError(error).message }));
          } else if (message.requires_refetch) refreshAll().catch(error => push({ type: 'refresh-failed', message: apiError(error).message }));
          push({ type: message.type || 'ws-event', message: message.message, payload: message });
        },
      });
    }; connect(); return () => { disposed = true; clearTimeout(retryRef.current); socket?.close(); };
  }, [applySnapshot, push, refreshAll, refreshRuntime, refreshStatus, refreshTopologies, setEdges, setNodes]);

  const normalized = normalizeRuntimeSnapshot(runtime); const runtimeDevices = normalized.devices;
  const activeTopology = topologies.find(item => item.id === activeTopologyId); const activeIsPreset = Boolean(activeTopology?.read_only || activeTopology?.readonly || activeTopology?.preset);
  const selectedDevice = runtimeDevices.find(item => (item.id || item.identity?.device_id) === selectedNodeId) || null;
  const selectedEndpointDevice = runtimeDevices.find(device => (device.endpoints || []).some(endpoint => endpoint.id === selectedNodeId)) || null;
  const selectedEndpoint = selectedEndpointDevice?.endpoints?.find(endpoint => endpoint.id === selectedNodeId) || null;
  const running = Boolean(status?.runtime?.running); const palette = profilePalette(metadata);

  const save = async forceNew => { const saved = await saveTopology(topologyPayload(activeTopologyId, nodes, edges, forceNew, activeTopology?.revision), { forceCreate: forceNew || activeIsPreset }); setActiveTopologyId(saved.id); await refreshTopologies(); push({ type: 'topology-saved', message: saved.id }); };
  const guard = async (name, action) => { setLoading(true); try { await action(); } catch (error) { const failure = apiError(error); push({ type: `${name}-failed`, message: failure.message, payload: failure }); } finally { setLoading(false); } };
  const onLoad = id => guard('topology-load', async () => { applySnapshot(await loadTopology(id), 'topology loaded'); setActiveTopologyId(id); });
  const onStart = () => guard('topology-start', async () => { const id = activeTopologyId || topologies[0]?.id; if (!id) throw new Error('没有可启动的拓扑，请先从服务器加载或保存。'); applySnapshot(await startTopology(id), 'topology started'); await refreshStatus(); });
  const onStop = () => guard('topology-stop', async () => { await stopTopology(activeTopologyId); await refreshAll(); push({ type: 'topology-stopped', message: activeTopologyId }); });
  const onPatch = async (deviceId, patches) => {
    if (patches.length > MAX_BATCH) { setFieldErrors({ _batch: '单次最多 100 项。' }); return; }
    setPending(true); setFieldErrors({});
    try { const result = await patchDeviceState(deviceId, patches, { expectedRevision: revisionRef.current }); applySnapshot(result.snapshot || result.state || result, 'patch committed'); push({ type: result.idempotent ? 'patch-idempotent' : 'patch-committed', message: `${deviceId}: ${(result.changed_paths || []).join(', ')}`, payload: result }); }
    catch (error) { const failure = apiError(error); const details = failure.details?.fields || failure.details?.paths || {}; setFieldErrors(details); push({ type: failure.status === 409 ? 'patch-conflict' : 'patch-failed', message: failure.message, payload: failure }); if (failure.status === 409) refreshRuntime('conflict refresh').catch(() => {}); }
    finally { setPending(false); }
  };
  const onPatchEndpoint = async patch => {
    if (!selectedEndpoint || !selectedEndpointDevice) return;
    setPending(true); setFieldErrors({});
    try { const result = await patchEndpointState(selectedEndpointDevice.id || selectedEndpointDevice.identity?.device_id, selectedEndpoint.id, patch); applySnapshot(result.snapshot || result.state || result, 'endpoint patch committed'); push({ type: 'endpoint-patch-committed', message: `${selectedEndpoint.id}: ${Object.keys(patch).join(', ')}`, payload: result }); }
    catch (error) { const failure = apiError(error); push({ type: 'endpoint-patch-failed', message: failure.message, payload: failure }); }
    finally { setPending(false); }
  };
  const onAction = action => guard(`device-${action}`, async () => { if (!selectedDevice) throw new Error('请选择运行设备。'); applySnapshot(await deviceAction(selectedDevice.id || selectedDevice.identity?.device_id, action), `device ${action}`); await refreshStatus(); });
  const onTrap = payload => guard('trap', async () => { const result = await sendTrap(payload); setTrapHistory(current => [{ id: `${Date.now()}`, ...payload, result }, ...current].slice(0, 20)); push({ type: 'trap-sent', message: payload.message, payload: result }); });
  const onAdd = profile => setNodes(current => current.concat({ id: `${profile.id}-${current.length + 1}`, type: 'simulator', position: { x: 120 + current.length * 36, y: 80 + current.length * 36 }, data: { id: `${profile.id}-${current.length + 1}`, name: profile.label, profile: profile.id, node_kind: 'device', ports: [] } }));
  const onConnect = connection => {
    if (connection.source === connection.target) { push({ type: 'invalid-connection', message: '不允许自环；保存时仍由服务器执行最终校验。' }); return; }
    const source = nodes.find(node => node.id === connection.source); const target = nodes.find(node => node.id === connection.target);
    const sourcePort = Number(String(connection.sourceHandle || '').replace('port:', ''));
    const targetPort = Number(String(connection.targetHandle || '').replace('port:', ''));
    const physical = source?.data.node_kind === 'device' && target?.data.node_kind === 'device' && Number.isInteger(sourcePort) && sourcePort > 0 && Number.isInteger(targetPort) && targetPort > 0;
    const route = source?.data.node_kind === 'endpoint' && target?.data.node_kind === 'endpoint';
    if (!physical && !route) { push({ type: 'invalid-connection', message: '物理连线必须连接设备实际端口；模拟路由必须连接 endpoint。' }); return; }
    setEdges(current => addEdge({ ...connection, label: physical ? `port ${sourcePort} ↔ ${targetPort}` : 'simulation route', className: physical ? 'physical-edge' : 'simulation-edge', style: physical ? undefined : { strokeDasharray: '7 5' }, data: physical ? { kind: 'port-link', source_port: sourcePort, target_port: targetPort } : { kind: 'route', metadata: { evidence: 'simulation-declared' } } }, current));
  };

  return <div className="app-shell">
    <RuntimeToolbar status={status} running={running} wsState={wsState} revision={normalized.revision} selectedDevice={selectedDevice} loading={loading} onStart={onStart} onStop={onStop} onRefresh={() => guard('refresh', refreshAll)} onAction={onAction} />
    <main className="main-grid"><TopologySidebar topologies={topologies} activeTopologyId={activeTopologyId} onLoad={onLoad} onSave={() => guard('topology-save', () => save(false))} onSaveAs={() => guard('topology-save-as', () => save(true))} onAddDevice={onAdd} palette={palette} loading={loading} isPreset={activeIsPreset} />
      <section className="canvas-card"><div className="canvas-legend"><span className="physical">实物链路</span><span className="simulation">模拟路由（非 SNMP OID）</span></div><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onNodeClick={(_, node) => setSelectedNodeId(node.id)} fitView><Background color="#35506b" gap={18} /><MiniMap pannable zoomable /><Controls /></ReactFlow></section>
      <DetailsDrawer device={selectedDevice} endpoint={selectedEndpoint} endpointDevice={selectedEndpointDevice} metadata={metadata} onClose={() => setSelectedNodeId(null)} onPatch={onPatch} onPatchEndpoint={onPatchEndpoint} pending={pending} fieldErrors={fieldErrors} /></main>
    <div className="bottom-grid"><TrapPanel devices={runtimeDevices} selectedDeviceId={selectedDevice?.id || selectedDevice?.identity?.device_id} onSend={onTrap} history={trapHistory} /><EventTimeline events={events} /></div>
  </div>;
}
