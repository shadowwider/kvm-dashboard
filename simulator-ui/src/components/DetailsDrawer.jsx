import { X } from 'lucide-react';
import { metadataToGroups, readPathValue } from '../profileFields.js';

function FieldInput({ field, value, onChange }) {
  const disabled = field.mutable === false;
  if (field.type === 'boolean' || field.kind === 'boolean') {
    return <input type="checkbox" checked={Boolean(value)} disabled={disabled} onChange={event => onChange(event.target.checked)} />;
  }
  const options = field.options || field.enum || field.values;
  if (options) {
    const entries = Array.isArray(options) ? options.map(item => [item.value ?? item, item.label ?? String(item.value ?? item)]) : Object.entries(options);
    return <select value={value ?? ''} disabled={disabled} onChange={event => onChange(event.target.value)}>{entries.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>;
  }
  const type = field.type === 'integer' || field.type === 'number' || field.kind === 'number' ? 'number' : 'text';
  return <input type={type} value={value ?? ''} disabled={disabled} onChange={event => onChange(type === 'number' ? Number(event.target.value) : event.target.value)} />;
}

export default function DetailsDrawer({ device, runtimeDevice, metadata, onClose, onPatch }) {
  const merged = runtimeDevice || device;
  if (!merged) {
    return <aside className="details-drawer empty">Select a node to inspect profile metadata and runtime fields.</aside>;
  }
  const profileMeta = metadata?.profiles?.[merged.profile] || metadata?.[merged.profile];
  const groups = metadataToGroups(profileMeta);
  const canPatch = typeof onPatch === 'function';

  return (
    <aside className="details-drawer">
      <button className="close" onClick={onClose}><X size={16} /></button>
      <div className="drawer-title">
        <span>{merged.name || merged.label || merged.id}</span>
        <small>{merged.profile || merged.type}</small>
      </div>
      <div className="device-summary">
        <span>{merged.host || '127.0.0.1'}:{merged.snmp_port || merged.port || 161}</span>
        <span>evidence: {merged.evidence || 'simulation-declared'}</span>
      </div>
      {!runtimeDevice && <p className="hint">Editing local topology defaults. Click Start to launch this node as a runtime device.</p>}
      <div className="field-groups">
        {groups.map(group => (
          <section key={group.group}>
            <h3>{group.group}</h3>
            {group.fields.map(field => {
              const path = field.path || field.name;
              const value = readPathValue(merged, path) ?? field.default ?? '';
              return (
                <label className="field-row" key={path}>
                  <span>{field.label || field.name || path}{field.unit ? ` (${field.unit})` : ''}</span>
                  <FieldInput field={field} value={value} onChange={nextValue => canPatch && onPatch(merged.id, { [path]: nextValue })} />
                </label>
              );
            })}
          </section>
        ))}
      </div>
    </aside>
  );
}
