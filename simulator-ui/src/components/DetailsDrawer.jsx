import { useMemo, useState } from 'react';
import { X } from 'lucide-react';
import { groupRegistryFields, readPathValue } from '../profileFields.js';

function FieldInput({ field, value, onChange }) {
  const disabled = !field.mutable;
  if (field.syntax === 'TruthValue') {
    return <input aria-label={field.path} type="checkbox" checked={Boolean(value)} disabled={disabled} onChange={event => onChange(event.target.checked)} />;
  }
  if (field.enum_values?.length) {
    return <select aria-label={field.path} value={value ?? ''} disabled={disabled} onChange={event => onChange(Number(event.target.value))}>
      {field.enum_values.map(option => <option key={option} value={option}>{option}</option>)}
    </select>;
  }
  const numeric = field.minimum !== null || field.maximum !== null || /^(Integer|Unsigned|Gauge|Counter|TimeTicks)/.test(field.syntax || '');
  return <input
    aria-label={field.path}
    type={numeric ? 'number' : 'text'} value={value ?? ''} disabled={disabled}
    min={field.minimum ?? undefined} max={field.maximum ?? undefined}
    maxLength={field.max_utf8_bytes ?? undefined}
    onChange={event => onChange(numeric ? Number(event.target.value) : event.target.value)}
  />;
}

export default function DetailsDrawer({ device, metadata, onClose, onPatch, pending, fieldErrors = {} }) {
  const [query, setQuery] = useState('');
  const groups = useMemo(() => groupRegistryFields(device, metadata, query), [device, metadata, query]);
  if (!device) return <aside className="drawer empty-drawer">选择运行中的设备后，显示服务器报告的实际 path registry。</aside>;
  const availability = readPathValue(device, 'runtime.availability');
  return <aside className="drawer" aria-label="runtime-details">
    <div className="drawer-head"><div><h2>{device.identity?.device_id || device.id}</h2><p>{device.identity?.profile_id || device.profile} · {availability || 'unknown'}</p></div><button className="icon" onClick={onClose} aria-label="关闭详情"><X size={16} /></button></div>
    <p className="hint">仅显示服务器返回的实际实例。runtime writable 与 vendor SNMP writable 分开标识。</p>
    <input className="field-search" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索 canonical path / syntax" aria-label="搜索字段" />
    {!groups.length && <div className="empty">当前响应没有 path registry；L4 metadata fixture 尚未提供可编辑实例。</div>}
    <div className="field-groups">{groups.map(group => <section className="field-group" key={group.group}><h3>{group.group}</h3>{group.fields.map(field => {
      const value = readPathValue(device, field.path);
      return <label className="field-row" key={field.path}><span><strong title={field.path}>{field.path}</strong><small>{field.syntax || 'unknown syntax'} · runtime {field.mutable ? 'writable' : 'read-only'} · SNMP {field.vendor_snmp_writable ? 'writable' : 'read-only'}</small></span><span><FieldInput field={field} value={value} onChange={nextValue => onPatch(device.identity?.device_id || device.id, [{ path: field.path, value: nextValue }])} />{fieldErrors[field.path] && <small className="field-error">{fieldErrors[field.path]}</small>}</span></label>;
    })}</section>)}</div>
    {pending && <div className="pending">正在等待服务器提交结果…</div>}
  </aside>;
}
