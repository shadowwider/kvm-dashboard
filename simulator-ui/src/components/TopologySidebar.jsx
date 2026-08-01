import { Database, Plus, Save } from 'lucide-react';

export default function TopologySidebar({ topologies, activeTopologyId, onLoad, onSave, onSaveAs, onAddDevice, palette, loading, isPreset }) {
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
          {palette.map(device => (
            <button key={device.id} className="palette-card" onClick={() => onAddDevice(device)}>
              <strong>{device.label}</strong>
              <span>{device.category}</span>
            </button>
          ))}
          {!palette.length && <div className="empty">等待服务器 metadata 提供可建模的 Profile。</div>}
        </div>
        <p className="hint">设备类型来自服务器 metadata。端口和物理连线语义由 L4 topology 契约冻结后接入，当前新增连线均标识为 simulation route。</p>
      </section>
    </aside>
  );
}
