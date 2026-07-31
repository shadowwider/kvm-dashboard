import { Handle, Position } from '@xyflow/react';
import { Cpu, Network, Router, Server } from 'lucide-react';
import { PROFILE_LABELS } from '../profileFields.js';

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
  const status = data.paused ? 'offline' : data.status || 'online';
  const portCount = countPorts(data.ports, data.port_count || data.endpoints?.length);

  return (
    <div className={`sim-node ${selected ? 'selected' : ''} ${status}`}>
      <Handle type="target" position={Position.Left} />
      <div className="node-header">
        <Icon size={18} />
        <span>{data.name || data.label}</span>
      </div>
      <div className="node-profile">{PROFILE_LABELS[data.profile] || data.profile || data.type}</div>
      <div className="node-meta">
        <span>{data.host || '127.0.0.1'}:{data.snmp_port || data.port || 161}</span>
        <span>{portCount} ports</span>
      </div>
      <div className="node-badges">
        <span className={`badge ${status}`}>{status}</span>
        {data.route_provenance && <span className="badge muted">{data.route_provenance}</span>}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
