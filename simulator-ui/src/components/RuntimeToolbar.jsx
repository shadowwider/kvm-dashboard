import { PauseCircle, PlayCircle, Power, RefreshCcw, WifiOff } from 'lucide-react';

export default function RuntimeToolbar({ status, running, wsState, revision, selectedDevice, loading, onStart, onStop, onRefresh, onAction }) {
  const agents = status?.agents;
  const bridge = status?.bridge;
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
        <span>Agent {agents ? `${agents.running}/${agents.expected}` : '—'}</span>
        <span className={bridge?.enabled && bridge?.last_reconcile?.ok === false ? 'degraded' : ''}>Bridge {bridge?.enabled ? (bridge?.last_reconcile?.ok === false ? 'degraded' : 'enabled') : 'disabled'}</span>
      </div>
      <div className="toolbar-actions">
        <button className="primary" onClick={onStart} disabled={loading || running}><PlayCircle size={16} /> Start</button>
        <button onClick={onStop} disabled={loading || !running}><PauseCircle size={16} /> Stop</button>
        <button onClick={onRefresh} disabled={loading}><RefreshCcw size={16} /> Refresh</button>
        <button onClick={() => onAction('disconnect')} disabled={loading || !selectedDevice}><WifiOff size={16} /> Disconnect</button>
        <button onClick={() => onAction('power_off')} disabled={loading || !selectedDevice}><Power size={16} /> Power off</button>
        <button onClick={() => onAction('restore')} disabled={loading || !selectedDevice}>Restore</button>
      </div>
    </header>
  );
}
