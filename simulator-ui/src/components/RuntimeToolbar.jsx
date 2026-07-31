import { PauseCircle, PlayCircle, Power, RefreshCcw, WifiOff } from 'lucide-react';

export default function RuntimeToolbar({ running, wsState, revision, selectedDevice, onStart, onStop, onRefresh, onAction }) {
  return (
    <header className="runtime-toolbar">
      <div>
        <div className="eyebrow">KVM SNMP Simulator</div>
        <h1>Visual topology and runtime control</h1>
      </div>
      <div className="toolbar-status">
        <span className={`dot ${running ? 'online' : ''}`} />
        <span>{running ? 'Running' : 'Editing'}</span>
        <span className={`ws ${wsState}`}>WS {wsState}</span>
        <span>rev {revision ?? 0}</span>
      </div>
      <div className="toolbar-actions">
        <button className="primary" onClick={onStart}><PlayCircle size={16} /> Start</button>
        <button onClick={onStop}><PauseCircle size={16} /> Stop</button>
        <button onClick={onRefresh}><RefreshCcw size={16} /> Refresh</button>
        <button onClick={() => onAction('disconnect')} disabled={!selectedDevice}><WifiOff size={16} /> Disconnect</button>
        <button onClick={() => onAction('power_off')} disabled={!selectedDevice}><Power size={16} /> Power off</button>
        <button onClick={() => onAction('restore')} disabled={!selectedDevice}>Restore</button>
      </div>
    </header>
  );
}
