import { Send } from 'lucide-react';
import { useMemo, useState } from 'react';

export default function TrapPanel({ devices, selectedDeviceId, onSend, history }) {
  const [targets, setTargets] = useState([]);
  const [level, setLevel] = useState(3);
  const [message, setMessage] = useState('Runtime test notification');
  const [layout, setLayout] = useState('formal');

  const effectiveTargets = useMemo(() => targets.length ? targets : (selectedDeviceId ? [selectedDeviceId] : []), [selectedDeviceId, targets]);

  return (
    <aside className="trap-panel">
      <div className="panel-title"><Send size={16} /> Trap Console</div>
      <label>
        Target devices
        <select multiple value={targets} onChange={event => setTargets([...event.target.selectedOptions].map(option => option.value))}>
          {devices.map(device => <option key={device.id} value={device.id}>{device.name || device.id}</option>)}
        </select>
      </label>
      <label>Message<textarea value={message} onChange={event => setMessage(event.target.value)} rows={3} maxLength={1024} /></label>
      <div className="trap-grid">
        <label>
          Level
          <input type="number" value={level} onChange={event => setLevel(Number(event.target.value))} />
        </label>
        <label>Layout<select value={layout} onChange={event => setLayout(event.target.value)}><option value="formal">formal .32828.2.1.0.*</option><option value="legacy">legacy .32828.5.*</option></select></label>
      </div>
      <p className="hint">level 原样发送；平台不将其宣称为厂家严重度枚举。目标只能是当前 runtime 设备。</p>
      <button className="primary full" onClick={() => onSend({ device_ids: effectiveTargets, level: Number(level), message, layout })} disabled={!effectiveTargets.length || !message.trim()}>Send Trap</button>
      <div className="history">
        <h3>Trap history</h3>
        {history.slice(0, 5).map(item => <div className="history-item" key={item.id}>{item.message}<small>{item.level} · {(item.device_ids || []).join(', ')}</small></div>)}
      </div>
    </aside>
  );
}
