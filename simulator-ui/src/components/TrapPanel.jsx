import { Send } from 'lucide-react';
import { useMemo, useState } from 'react';

const PRESETS = [
  "entered critical state: 'Offline'",
  'SFP Rx power changed',
  'Display connection state changed',
  'Power supply failed',
  'Temperature threshold exceeded',
];

const LEVELS = [
  { value: 5, label: 'info' },
  { value: 3, label: 'warning' },
  { value: 2, label: 'critical' },
];

export default function TrapPanel({ devices, selectedDeviceId, onSend, history }) {
  const [targets, setTargets] = useState([]);
  const [level, setLevel] = useState(3);
  const [message, setMessage] = useState(PRESETS[0]);
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
      <label>
        Preset / message
        <select value={message} onChange={event => setMessage(event.target.value)}>
          {PRESETS.map(preset => <option key={preset} value={preset}>{preset}</option>)}
        </select>
      </label>
      <textarea value={message} onChange={event => setMessage(event.target.value)} rows={3} />
      <div className="trap-grid">
        <label>
          Level
          <select value={level} onChange={event => setLevel(Number(event.target.value))}>
            {LEVELS.map(item => <option key={item.value} value={item.value}>{item.label} ({item.value})</option>)}
          </select>
        </label>
        <label>Layout<select value={layout} onChange={event => setLayout(event.target.value)}><option value="formal">formal .32828.2.1.0.*</option><option value="legacy">legacy .32828.5.*</option></select></label>
      </div>
      <button className="primary full" onClick={() => onSend({ device_ids: effectiveTargets, level: Number(level), message, layout })} disabled={!effectiveTargets.length}>Send Trap</button>
      <div className="history">
        <h3>Trap history</h3>
        {history.slice(0, 5).map(item => <div className="history-item" key={item.id}>{item.message}<small>{item.level} · {(item.device_ids || []).join(', ')}</small></div>)}
      </div>
    </aside>
  );
}
