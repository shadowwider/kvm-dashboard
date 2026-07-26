from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .bridge import DashboardBridge
from .models import EndpointStatePatch, RouteStatePatch, TrapRequest
from .scenarios import built_in_scenarios
from .snmp_agent import SnmpAgent, send_formal_trap
from .state import ScenarioState

TRAP_HOST = os.environ.get("TRAP_TARGET_HOST", "127.0.0.1")
TRAP_PORT = int(os.environ.get("SNMP_TRAP_PORT", "10162"))
COMMUNITY = os.environ.get("SNMP_COMMUNITY", "public")
SIMULATOR_HOST = os.environ.get("SIMULATOR_HOST", "127.0.0.1")
SIMULATOR_PORT = int(os.environ.get("SIM_WEB_PORT", "8888"))

state: ScenarioState | None = None
agents: dict[str, SnmpAgent] = {}
bridge = DashboardBridge()


def current_state() -> ScenarioState:
    if state is None:
        raise HTTPException(409, "No simulator scenario is loaded")
    return state


def start_scenario(scenario_id: str) -> ScenarioState:
    global state
    stop_scenario()
    definition = built_in_scenarios().get(scenario_id)
    if not definition:
        raise HTTPException(404, f"Unknown scenario: {scenario_id}")
    state = ScenarioState(definition)
    for device in definition.devices:
        agent = SnmpAgent(state, device.id, COMMUNITY)
        agent.start()
        agents[device.id] = agent
    bridge.reconcile(state)
    return state


def stop_scenario() -> None:
    for agent in agents.values():
        agent.stop()
    agents.clear()


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_scenario(os.environ.get("SIM_SCENARIO", "ccdc-regression"))
    yield
    stop_scenario()


app = FastAPI(title="KVM Simulator", version="2.0", lifespan=lifespan)


@app.get("/api/v1/scenarios")
def list_scenarios():
    return [
        {"id": item.id, "title": item.title, "devices": len(item.devices)}
        for item in built_in_scenarios().values()
    ]


@app.post("/api/v1/scenarios/{scenario_id}/load")
def load_scenario(scenario_id: str):
    runtime = start_scenario(scenario_id)
    return runtime.snapshot()


@app.get("/api/v1/state")
def get_state():
    return current_state().snapshot()


@app.post("/api/v1/devices/{device_id}/reachability")
def set_reachability(device_id: str, paused: bool):
    runtime = current_state()
    result = runtime.pause_device(device_id, paused)
    return {"revision": result.revision, "device_id": result.device_id, "paused": paused}


@app.patch("/api/v1/devices/{device_id}/endpoints/{endpoint_id}")
def update_endpoint(device_id: str, endpoint_id: str, patch: EndpointStatePatch):
    runtime = current_state()
    try:
        result = runtime.patch_endpoint(device_id, endpoint_id, patch)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown endpoint: {exc.args[0]}") from exc
    if result.trap:
        send_formal_trap(result.trap.level, result.trap.message, TRAP_HOST, TRAP_PORT, COMMUNITY)
    reconcile = bridge.reconcile(runtime)
    return {
        "revision": result.revision,
        "device_id": result.device_id,
        "trap_sent": result.trap is not None,
        "bridge": {"reconcile": reconcile},
    }


@app.patch("/api/v1/devices/{device_id}/routes/{route_id}")
def update_route(device_id: str, route_id: str, patch: RouteStatePatch):
    runtime = current_state()
    try:
        result = runtime.patch_route(device_id, route_id, patch)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown route: {exc.args[0]}") from exc
    return {"revision": result.revision, "device_id": result.device_id}


@app.post("/api/v1/traps")
def send_trap(request: TrapRequest):
    send_formal_trap(request.level, request.message, TRAP_HOST, TRAP_PORT, COMMUNITY)
    return {"sent": True, "notification_oid": "1.3.6.1.4.1.32828.2.1.0.4"}


@app.post("/api/v1/reset")
def reset_scenario():
    runtime = current_state()
    runtime.reset()
    return runtime.snapshot()


@app.get("/", response_class=HTMLResponse)
def control_page():
    return """<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>KVM Simulator</title>
<style>body{font-family:system-ui;background:#101821;color:#dfe8f3;margin:32px;max-width:1100px}button,select{padding:8px;margin:3px;background:#213449;color:#dfe8f3;border:1px solid #4c718f;border-radius:4px}pre{background:#071018;padding:16px;overflow:auto;border-radius:6px}.offline{color:#ff7272}.active{color:#63d6a2}</style></head><body>
<h1>KVM SNMP Simulator</h1><p>所有路由均为 <b>simulation-declared</b> 测试数据，不代表实机发现的连接。</p>
<label>场景 <select id='scenario'></select></label><button onclick='loadScenario()'>加载场景</button><button onclick='resetScenario()'>重置</button><button onclick='refresh()'>刷新</button><div id='content'></div>
<script>
async function api(path, options={}){const r=await fetch(path,{headers:{'Content-Type':'application/json'},...options});if(!r.ok)throw new Error(await r.text());return r.json()}
async function boot(){let scenarios=await api('/api/v1/scenarios');document.querySelector('#scenario').innerHTML=scenarios.map(s=>`<option value="${s.id}">${s.title}</option>`).join('');refresh()}
async function loadScenario(){await api('/api/v1/scenarios/'+scenario.value+'/load',{method:'POST'});refresh()}
async function resetScenario(){await api('/api/v1/reset',{method:'POST'});refresh()}
async function endpoint(device,endpoint,status){await api(`/api/v1/devices/${device}/endpoints/${endpoint}`,{method:'PATCH',body:JSON.stringify({status})});refresh()}
async function route(device,id,state){await api(`/api/v1/devices/${device}/routes/${id}`,{method:'PATCH',body:JSON.stringify({state})});refresh()}
async function reachability(device,paused){await api(`/api/v1/devices/${device}/reachability?paused=${paused}`,{method:'POST'});refresh()}
async function refresh(){try{const x=await api('/api/v1/state');let h=`<p>Revision ${x.revision}</p>`;for(const d of x.scenario.devices){const paused=x.paused_devices.includes(d.id);h+=`<section><h2>${d.name} <small>${d.profile} / UDP ${d.snmp_port}</small></h2><button onclick="reachability('${d.id}',${!paused})">${paused?'恢复 SNMP':'暂停 SNMP（模拟断网）'}</button><h3>端点</h3>`;for(const e of d.endpoints){h+=`<div>${e.id} <b class="${e.status===0?'offline':'active'}">${['offline','online','ready'][e.status]}</b> <button onclick="endpoint('${d.id}','${e.id}',0)">离线 + Trap</button><button onclick="endpoint('${d.id}','${e.id}',1)">在线 + Trap</button></div>`}h+='<h3>模拟路由</h3>';for(const r of d.routes){h+=`<div>${r.source_endpoint_id} → ${r.target_endpoint_id}: <b>${r.state}</b> <button onclick="route('${d.id}','${r.id}','active')">连接</button><button onclick="route('${d.id}','${r.id}','disconnected')">断开</button></div>`}h+='</section>'}content.innerHTML=h+'<h3>完整状态</h3><pre>'+JSON.stringify(x,null,2)+'</pre>'}catch(e){content.innerHTML='<pre class="offline">'+e+'</pre>'}}
boot();setInterval(refresh,2000)
</script></body></html>"""
