import { useCallback, useEffect, useMemo, useState } from 'react';
import { addEdge, Background, Controls, MiniMap, ReactFlow, useEdgesState, useNodesState } from '@xyflow/react';
import SimulatorNode from './components/SimulatorNode.jsx';
import TopologySidebar from './components/TopologySidebar.jsx';
import RuntimeToolbar from './components/RuntimeToolbar.jsx';
import DetailsDrawer from './components/DetailsDrawer.jsx';
import TrapPanel from './components/TrapPanel.jsx';
import EventTimeline from './components/EventTimeline.jsx';
import { deviceAction, getProfiles, getRuntimeState, listTopologies, loadTopology, openSimulatorSocket, patchDeviceState, saveTopology, sendTrap, startTopology, stopTopology } from './api/client.js';
import { normalizeRuntimeSnapshot } from './profileFields.js';

const nodeTypes = { simulator: SimulatorNode };

function makeEvent(type, payload = {}) {
  return { id: `${Date.now()}-${Math.random()}`, time: Date.now(), type, ...payload };
}

function toFlow(snapshot) {
  const { devices, edges, pausedDevices } = normalizeRuntimeSnapshot(snapshot);
  const deviceNodes = devices.map((device, index) => ({
    id: device.id,
    type: 'simulator',
    position: device.position || device.canvas_position || { x: 140 + (index % 3) * 270, y: 80 + Math.floor(index / 3) * 190 },
    data: { ...device, node_kind: 'device', paused: pausedDevices.includes(device.id) },
  }));
  const endpointNodes = devices.flatMap((device, deviceIndex) => (device.endpoints || []).map((endpoint, endpointIndex) => ({
    id: endpoint.id,
    type: 'simulator',
    position: {
      x: (device.position?.x ?? 140 + (deviceIndex % 3) * 270) + (endpoint.module_type === 'cpu' ? -85 : 250),
      y: (device.position?.y ?? 80 + Math.floor(deviceIndex / 3) * 190) + endpointIndex * 80,
    },
    data: { ...endpoint, name: endpoint.display_name || endpoint.id, profile: endpoint.module_type === 'cpu' ? 'visionxs_cpu' : 'visionxs_con', category: 'endpoint', node_kind: 'endpoint', parent_device_id: device.id, host: device.host, snmp_port: device.snmp_port, paused: pausedDevices.includes(device.id) },
  })));
  const nodeIds = new Set([...deviceNodes, ...endpointNodes].map(node => node.id));
  const flowEdges = (edges.length ? edges : devices.flatMap(device => device.routes || [])).map((edge, index) => ({
    id: edge.id || `edge-${index}`,
    source: edge.source || edge.source_device_id || edge.source_endpoint_id || devices[0]?.id,
    target: edge.target || edge.target_device_id || edge.target_endpoint_id || devices[1]?.id,
    label: edge.label || edge.state || edge.route_provenance || 'simulation-declared',
    animated: edge.state === 'active',
    style: edge.route_provenance === 'simulation-declared' ? { strokeDasharray: '7 5' } : undefined,
  })).filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target) && edge.source !== edge.target);
  return { nodes: [...deviceNodes, ...endpointNodes], edges: flowEdges };
}

function normalizePorts(ports) {
  if (Array.isArray(ports)) {
    return ports.map((port, index) => typeof port === 'object'
      ? { index: Number(port.index ?? index + 1), status: port.status || 'up' }
      : { index: Number(port), status: 'up' });
  }
  const count = Number(ports || 0);
  return Number.isFinite(count) && count > 0
    ? Array.from({ length: count }, (_, index) => ({ index: index + 1, status: 'up' }))
    : [];
}

function buildTopologyPayload(activeTopologyId, nodes, edges, { forceNew = false } = {}) {
  const id = forceNew || !activeTopologyId ? `topology-${Date.now()}` : activeTopologyId;
  return {
    id,
    title: forceNew || !activeTopologyId ? `Simulator topology ${new Date().toLocaleString()}` : activeTopologyId,
    devices: nodes.filter(node => node.data.node_kind !== 'endpoint').map((node, index) => ({
      id: node.id,
      name: node.data.name || node.data.label || node.id,
      profile: node.data.profile || node.data.type,
      host: node.data.host || null,
      snmp_port: node.data.snmp_port || node.data.port || 11161 + index,
      ports: normalizePorts(node.data.ports),
      endpoints: Array.isArray(node.data.endpoints) ? node.data.endpoints : [],
      routes: Array.isArray(node.data.routes) ? node.data.routes : [],
      profile_state: node.data.profile_state || {},
      position: node.position,
    })),
    edges: edges.filter(edge => {
      const source = nodes.find(node => node.id === edge.source);
      const target = nodes.find(node => node.id === edge.target);
      return source?.data.node_kind !== 'endpoint' || target?.data.node_kind !== 'endpoint';
    }).map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      kind: edge.data?.kind || 'route',
      label: typeof edge.label === 'string' ? edge.label : undefined,
      metadata: edge.data?.metadata || {},
    })),
  };
}

export default function App() {
  const [topologies, setTopologies] = useState([]);
  const [activeTopologyId, setActiveTopologyId] = useState('');
  const [runtime, setRuntime] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [events, setEvents] = useState([]);
  const [trapHistory, setTrapHistory] = useState([]);
  const [wsState, setWsState] = useState('offline');
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const activeTopology = useMemo(() => topologies.find(item => item.id === activeTopologyId), [activeTopologyId, topologies]);
  const activeIsPreset = Boolean(activeTopology?.read_only || activeTopology?.readonly || activeTopology?.preset || activeTopology?.source === 'preset');
  const pushEvent = useCallback(event => setEvents(current => [makeEvent(event.type || 'event', event), ...current].slice(0, 80)), []);

  const refreshTopologies = useCallback(async () => {
    const data = await listTopologies();
    setTopologies(Array.isArray(data) ? data : data.items || data.topologies || []);
  }, []);

  const refreshProfiles = useCallback(async () => {
    const profiles = await getProfiles();
    if (profiles) setMetadata(profiles);
  }, []);

  const refreshRuntime = useCallback(async () => {
    const snapshot = await getRuntimeState();
    setRuntime(snapshot);
    setMetadata(current => snapshot.profile_metadata || snapshot.metadata || snapshot.profiles || current);
    const flow = toFlow(snapshot);
    if (flow.nodes.length) {
      setNodes(flow.nodes);
      setEdges(flow.edges);
    }
    pushEvent({ type: 'snapshot', message: `Loaded runtime revision ${snapshot.revision ?? 0}` });
  }, [pushEvent, setEdges, setNodes]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      refreshTopologies().catch(error => pushEvent({ type: 'api-error', message: error.message }));
      refreshProfiles().catch(error => pushEvent({ type: 'profiles-error', message: error.message }));
      refreshRuntime().catch(error => pushEvent({ type: 'api-placeholder', message: error.message }));
    });
    return () => {
      cancelled = true;
    };
  }, [refreshRuntime, refreshTopologies, refreshProfiles, pushEvent]);

  useEffect(() => {
    const socket = openSimulatorSocket({
      onOpen: () => setWsState('online'),
      onClose: () => setWsState('offline'),
      onError: () => setWsState('error'),
      onMessage: message => {
        pushEvent({ type: message.type || 'ws', message: message.message, payload: message });
        if (message.snapshot || message.state) {
          const snapshot = message.snapshot || message.state;
          setRuntime(snapshot);
          const flow = toFlow(snapshot);
          if (flow.nodes.length) {
            setNodes(flow.nodes);
            setEdges(flow.edges);
          }
        }
      },
    });
    return () => socket.close();
  }, [pushEvent, setEdges, setNodes]);

  const selectedNode = useMemo(() => nodes.find(node => node.id === selectedNodeId), [nodes, selectedNodeId]);
  const runtimeDevices = normalizeRuntimeSnapshot(runtime).devices;
  const selectedRuntimeDevice = runtimeDevices.find(device => device.id === selectedNodeId);
  const selectedActionDeviceId = selectedRuntimeDevice?.id || null;

  const handleLoad = async id => {
    setLoading(true);
    try {
      const loaded = await loadTopology(id);
      setActiveTopologyId(id);
      const snapshot = loaded?.scenario || loaded?.topology ? loaded : { topology: loaded };
      setRuntime(snapshot);
      const flow = toFlow(snapshot);
      setNodes(flow.nodes);
      setEdges(flow.edges);
      pushEvent({ type: 'topology-loaded', message: id });
    } catch (error) {
      pushEvent({ type: 'topology-load-failed', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  const doSave = async ({ forceNew = false } = {}) => {
    const payload = buildTopologyPayload(activeTopologyId, nodes, edges, { forceNew });
    const saved = await saveTopology(payload, { forceCreate: forceNew || !activeTopologyId || activeIsPreset });
    setActiveTopologyId(saved.id || payload.id);
    await refreshTopologies();
    pushEvent({ type: 'topology-saved', message: saved.id || payload.id });
    return saved;
  };

  const handleSave = async () => {
    if (activeIsPreset) return pushEvent({ type: 'save-blocked', message: 'Preset topology is read-only. Use Save as new topology.' });
    setLoading(true);
    try {
      await doSave();
    } catch (error) {
      pushEvent({ type: 'save-failed', message: error.response?.data?.detail || error.message });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAs = async () => {
    setLoading(true);
    try {
      await doSave({ forceNew: true });
    } catch (error) {
      pushEvent({ type: 'save-as-failed', message: error.response?.data?.detail || error.message });
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async () => {
    setLoading(true);
    try {
      let id = activeTopologyId;
      if ((!id || activeIsPreset) && nodes.length && !activeIsPreset) {
        const saved = await doSave();
        id = saved.id;
      }
      id = id || topologies[0]?.id;
      if (!id) return pushEvent({ type: 'start-skipped', message: 'Save or load a topology first.' });
      const snapshot = await startTopology(id);
      setRunning(true);
      setRuntime(snapshot);
      const flow = toFlow(snapshot);
      if (flow.nodes.length) {
        setNodes(flow.nodes);
        setEdges(flow.edges);
      }
      pushEvent({ type: 'topology-started', message: id });
    } catch (error) {
      pushEvent({ type: 'topology-start-failed', message: error.response?.data?.detail || error.message });
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    const id = activeTopologyId || topologies[0]?.id || 'current';
    try {
      await stopTopology(id);
      setRunning(false);
      pushEvent({ type: 'topology-stopped', message: id });
    } catch (error) {
      pushEvent({ type: 'topology-stop-failed', message: error.response?.data?.detail || error.message });
    }
  };

  const handleAddDevice = device => {
    const id = `${device.type}-${nodes.length + 1}`.replaceAll('_', '-');
    setNodes(current => current.concat({
      id,
      type: 'simulator',
      position: { x: 180 + (current.length % 4) * 80, y: 110 + current.length * 35 },
      data: { id, name: device.label, label: device.label, profile: device.type, type: device.type, category: device.category, ports: device.ports, host: '127.0.0.1', snmp_port: 11161 + current.length },
    }));
  };

  const applyLocalPatch = (deviceId, patches) => {
    const setNested = (target, path, value) => {
      const parts = path.replace(/\[(.*?)\]/g, '.$1').split('.').filter(Boolean);
      const root = parts[0];
      let current = (root === 'scalars' || root === 'tables')
        ? (target.profile_state ||= {})
        : target;
      for (const part of parts.slice(0, -1)) {
        current = (current[part] ||= {});
      }
      current[parts.at(-1)] = value;
    };
    setNodes(current => current.map(node => {
      if (node.id !== deviceId) return node;
      const data = structuredClone(node.data);
      for (const [path, value] of Object.entries(patches)) setNested(data, path, value);
      return { ...node, data };
    }));
  };

  const handlePatch = async (deviceId, patches) => {
    const isRuntimeDevice = runtimeDevices.some(device => device.id === deviceId);
    if (!isRuntimeDevice) {
      applyLocalPatch(deviceId, patches);
      pushEvent({ type: 'local-field-edited', message: `${deviceId}: ${Object.keys(patches).join(', ')}` });
      return;
    }
    try {
      const result = await patchDeviceState(deviceId, patches);
      pushEvent({ type: 'state-patched', message: `${deviceId}: ${Object.keys(patches).join(', ')}`, payload: result });
      await refreshRuntime();
    } catch (error) {
      pushEvent({ type: 'patch-failed', message: error.response?.data?.detail || error.message });
    }
  };

  const handleAction = async action => {
    if (!selectedActionDeviceId) return pushEvent({ type: 'action-skipped', message: 'Select a simulator device, not an endpoint/module node.' });
    try {
      const result = await deviceAction(selectedActionDeviceId, action);
      pushEvent({ type: `device-${action}`, message: selectedActionDeviceId, payload: result });
      await refreshRuntime();
    } catch (error) {
      pushEvent({ type: 'action-failed', message: error.response?.data?.detail || error.message });
    }
  };

  const handleTrap = async payload => {
    try {
      const result = await sendTrap(payload);
      const entry = { id: `${Date.now()}`, ...payload, result };
      setTrapHistory(current => [entry, ...current].slice(0, 20));
      pushEvent({ type: 'trap-sent', message: payload.message, payload: result });
    } catch (error) {
      pushEvent({ type: 'trap-failed', message: error.response?.data?.detail || error.message });
    }
  };

  return (
    <div className="app-shell">
      <RuntimeToolbar running={running} wsState={wsState} revision={runtime?.revision} selectedDevice={selectedActionDeviceId} onStart={handleStart} onStop={handleStop} onRefresh={refreshRuntime} onAction={handleAction} />
      <main className="main-grid">
        <TopologySidebar topologies={topologies} activeTopologyId={activeTopologyId} onLoad={handleLoad} onSave={handleSave} onSaveAs={handleSaveAs} onAddDevice={handleAddDevice} loading={loading} isPreset={activeIsPreset} />
        <section className="canvas-card">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={connection => setEdges(current => addEdge({ ...connection, label: 'simulation-declared', animated: true, data: { kind: 'route', metadata: { evidence: 'simulation-declared' } } }, current))}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            fitView
          >
            <Background color="#35506b" gap={18} />
            <MiniMap pannable zoomable />
            <Controls />
          </ReactFlow>
        </section>
        <DetailsDrawer device={selectedNode?.data} runtimeDevice={selectedRuntimeDevice} metadata={metadata} onClose={() => setSelectedNodeId(null)} onPatch={handlePatch} />
      </main>
      <div className="bottom-grid">
        <TrapPanel devices={nodes.map(node => node.data)} selectedDeviceId={selectedNodeId} onSend={handleTrap} history={trapHistory} />
        <EventTimeline events={events} />
      </div>
    </div>
  );
}
