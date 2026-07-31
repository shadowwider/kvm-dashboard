import { Database, Plus, Save } from 'lucide-react';
import { DEVICE_PALETTE } from '../profileFields.js';

export default function TopologySidebar({ topologies, activeTopologyId, onLoad, onSave, onSaveAs, onAddDevice, loading, isPreset }) {
  return (
    <aside className="sidebar">
      <section className="panel">
        <div className="panel-title"><Database size={16} /> Topology Library</div>
        <div className="topology-list">
          {topologies.map(item => (
            <button
              key={item.id}
              className={item.id === activeTopologyId ? 'topology-item active' : 'topology-item'}
              onClick={() => onLoad(item.id)}
              disabled={loading}
            >
              <span>{item.title || item.name || item.id}</span>
              {item.read_only || item.readonly || item.preset ? <small>preset</small> : <small>user</small>}
            </button>
          ))}
          {!topologies.length && <div className="empty">No topology API yet. Start by dragging devices.</div>}
        </div>
        <button className="primary full" onClick={onSave} disabled={loading || isPreset}>
          <Save size={15} /> Save topology
        </button>
        <button className="secondary full" onClick={onSaveAs} disabled={loading}>
          <Save size={15} /> Save as new topology
        </button>
      </section>

      <section className="panel">
        <div className="panel-title"><Plus size={16} /> Device Palette</div>
        <div className="palette">
          {DEVICE_PALETTE.map(device => (
            <button key={device.type} className="palette-card" onClick={() => onAddDevice(device)}>
              <strong>{device.label}</strong>
              <span>{device.category} / {device.ports} ports</span>
            </button>
          ))}
        </div>
        <p className="hint">Click to add nodes. Use the React Flow handles to draw endpoint, port, or simulation-declared route links.</p>
      </section>
    </aside>
  );
}
