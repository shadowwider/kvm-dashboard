import { useMemo, useState } from 'react';
import { X } from 'lucide-react';
import { groupRegistryFields, readPathValue, registryFields } from '../profileFields.js';

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

const endpointTableByProfile = {
  ccdc_legacy_unverified: { cpu: 'cpu_modules', con: 'con_modules' },
  ccdm_matrix: { cpu: 'target_module_table', con: 'user_module_table' },
};

const quickFieldLabels = {
  ep_console_ps2: '控制台 PS/2 键鼠', ep_console_usb: '控制台 USB 键鼠', ep_target_ps2: '目标 PS/2 键鼠', ep_target_usb_hid: '目标 USB HID', ep_target_video_cable: '目标视频线缆', ep_target_video_signal: '目标视频信号', ep_net_if0: '网络接口',
  con_console_ps2: '控制台 PS/2 键鼠', con_console_usb: '控制台 USB 键鼠', con_display_conn: '显示器连接', con_freeze: '冻结画面', con_net_if0: '网络接口',
  console_ps2_connection: '控制台 PS/2 键鼠', console_usbconnection: '控制台 USB 键鼠', target_ps2_connection: '目标 PS/2 键鼠', target_usb_hid: '目标 USB HID', target_video_cable: '目标视频线缆', target_video_signal: '目标视频信号', network_interface0: '网络接口', display_connection: '显示器连接', freeze: '冻结画面',
};

function EndpointDrawer({ endpoint, device, metadata, onClose, onPatch, onPatchDevice, pending }) {
  const update = (field, value) => onPatch({ [field]: value });
  const status = Number(endpoint.status ?? 1);
  const table = endpointTableByProfile[device?.profile]?.[endpoint.module_type];
  const rowPrefix = table ? `tables.${table}[${endpoint.row}].` : null;
  const quickFields = rowPrefix
    ? registryFields(device, metadata).filter(field => rowPrefix && field.path.startsWith(rowPrefix) && quickFieldLabels[field.path.slice(rowPrefix.length)])
    : [];
  return <aside className="drawer" aria-label="endpoint-details">
    <div className="drawer-head"><div><h2>{endpoint.display_name || endpoint.id}</h2><p>{endpoint.module_type?.toUpperCase() || 'Endpoint'} · 挂载于 {device?.name || device?.id || 'unknown device'}</p></div><button className="icon" onClick={onClose} aria-label="关闭详情"><X size={16} /></button></div>
    <p className="hint">这是模块级状态，不会把整台矩阵下线。网络断开/恢复属于设备 Agent 级操作，请先选择矩阵节点后使用顶部按钮。</p>
    <section className="field-group"><h3>模块状态</h3>
      <label className="field-row"><span><strong>在线状态</strong><small>写入 endpoint status；状态变更会产生对应事件/Trap。</small></span><select aria-label="endpoint-status" value={status} disabled={pending} onChange={event => update('status', Number(event.target.value))}><option value={0}>离线</option><option value={1}>在线</option><option value={2}>就绪</option></select></label>
      <label className="field-row"><span><strong>视频连接</strong><small>模拟该模块的视频链路是否存在。</small></span><input aria-label="endpoint-video-connected" type="checkbox" checked={Boolean(endpoint.video_connected)} disabled={pending} onChange={event => update('video_connected', event.target.checked)} /></label>
      <label className="field-row"><span><strong>显示器连接</strong><small>模拟显示设备接入状态。</small></span><input aria-label="endpoint-display-connected" type="checkbox" checked={Boolean(endpoint.display_connected)} disabled={pending} onChange={event => update('display_connected', event.target.checked)} /></label>
      <label className="field-row"><span><strong>冻结画面</strong><small>模拟视频画面冻结，不等同于网络中断。</small></span><input aria-label="endpoint-frozen" type="checkbox" checked={Boolean(endpoint.frozen)} disabled={pending} onChange={event => update('frozen', event.target.checked)} /></label>
    </section>
    {quickFields.length > 0 && <section className="field-group"><h3>模块链路与外设（SNMP 状态）</h3>{quickFields.map(field => <label className="field-row" key={field.path}><span><strong>{quickFieldLabels[field.path.slice(rowPrefix.length)]}</strong><small title={field.path}>{field.path} · runtime {field.mutable ? 'writable' : 'read-only'}</small></span><FieldInput field={field} value={readPathValue(device, field.path)} onChange={value => onPatchDevice([{ path: field.path, value }])} /></label>)}</section>}
    <section className="field-group"><h3>边界说明</h3><p className="hint">这里只显示服务器实际返回、且和当前 CPU/CON 行对应的 SNMP 状态字段。网络断开/恢复属于设备 Agent 级操作，请先选择矩阵节点后使用顶部按钮；未出现在此处的字段尚未由当前 Profile fixture 实例化。</p></section>
  </aside>;
}

export default function DetailsDrawer({ device, endpoint, endpointDevice, metadata, onClose, onPatch, onPatchEndpoint, pending, fieldErrors = {} }) {
  const [query, setQuery] = useState('');
  const groups = useMemo(() => groupRegistryFields(device, metadata, query), [device, metadata, query]);
  if (endpoint) return <EndpointDrawer endpoint={endpoint} device={endpointDevice} metadata={metadata} onClose={onClose} onPatch={onPatchEndpoint} onPatchDevice={patches => onPatch(endpointDevice.id || endpointDevice.identity?.device_id, patches)} pending={pending} />;
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
