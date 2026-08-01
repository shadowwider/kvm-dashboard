import { Handle, Position } from '@xyflow/react';
import { Cpu, Network, Router, Server } from 'lucide-react';

const iconByCategory = {
  matrix: Server,
  endpoint: Cpu,
  switch: Router,
  module: Network,
};

function countPorts(ports, fallback) {
  if (Array.isArray(ports)) return ports.length;
  if (Number.isFinite(Number(ports))) return Number(ports);
  return fallback || 0;
}

export default function SimulatorNode({ data, selected }) {
  const Icon = iconByCategory[data.category] || Server;
  const status = data.paused || data.status === 0 ? 'offline' : data.status === 1 || data.status === 2 ? 'online' : data.status || 'online';
  const portCount = countPorts(data.ports, data.port_count || data.endpoints?.length);

  const physicalPorts = data.node_kind === 'device' && Array.isArray(data.ports) ? data.ports : [];
  const portOffset = index => `${34 + index * 18}%`;

  return (
    <div className={`sim-node ${selected ? 'selected' : ''} ${status}`}>
      {data.node_kind === 'endpoint' && <Handle id="route-target" type="target" position={Position.Left} />}
      {physicalPorts.map((port, index) => <Handle key={`target-${port.index}`} id={`port:${port.index}`} type="target" position={Position.Left} style={{ top: portOffset(index) }} title={`physical port ${port.index}`} />)}
      <div className="node-header">
        <Icon size={18} />
        <span>{data.name || data.label}</span>
      </div>
      <div className="node-profile">{data.profile || data.identity?.profile_id || data.type}</div>
      <div className="node-meta">
        <span>{data.host || '127.0.0.1'}:{data.snmp_port || data.port || 161}</span>
        <span>{portCount} ports</span>
      </div>
      <div className="node-badges">
        <span className={`badge ${status}`}>{status}</span>
        {data.route_provenance && <span className="badge muted">{data.route_provenance}</span>}
      </div>
      {data.node_kind === 'endpoint' && <Handle id="route-source" type="source" position={Position.Right} />}
      {physicalPorts.map((port, index) => <Handle key={`source-${port.index}`} id={`port:${port.index}`} type="source" position={Position.Right} style={{ top: portOffset(index) }} title={`physical port ${port.index}`} />)}
    </div>
  );
}
