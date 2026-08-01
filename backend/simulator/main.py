from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .bridge import DashboardBridge
from .models import (
    EndpointStatePatch,
    RouteStatePatch,
    RuntimeDeviceActionRequest,
    RuntimeStatePatch,
    TopologyDefinition,
    TrapRequest,
)
from .profiles import profile_metadata
from .runtime_paths import RuntimeTransitionError
from .scenarios import built_in_scenarios
from .profiles import FORMAL_TRAP, LEGACY_TRAP
from .snmp_agent import SnmpAgent, send_formal_trap
from .state import ScenarioState, TransitionResult
from .topology_store import TopologyStore, topology_to_scenario

logger = logging.getLogger(__name__)

TRAP_HOST = os.environ.get("TRAP_TARGET_HOST", "127.0.0.1")
TRAP_PORT = int(os.environ.get("SNMP_TRAP_PORT", "10162"))
COMMUNITY = os.environ.get("SNMP_COMMUNITY", "public")
SIMULATOR_HOST = os.environ.get("SIMULATOR_HOST", "127.0.0.1")
SIMULATOR_PORT = int(os.environ.get("SIM_WEB_PORT", "8888"))
UI_DIST = Path(__file__).resolve().parents[2] / "simulator-ui" / "dist"

state: ScenarioState | None = None
active_topology_id: str | None = None
agents: dict[str, SnmpAgent] = {}
bridge = DashboardBridge()
store = TopologyStore()
_ws_clients: set[WebSocket] = set()
_event_loop: asyncio.AbstractEventLoop | None = None


def current_state() -> ScenarioState:
    if state is None:
        raise HTTPException(409, "No simulator topology is running")
    return state


def _current_bindings() -> set[tuple[str, int]]:
    if state is None:
        return set()
    return {(device.get("host", "127.0.0.1"), device["snmp_port"]) for device in state.snapshot()["scenario"].get("devices", [])}


def _preflight_bindings(definition) -> None:
    import socket

    occupied_by_current = _current_bindings()
    probes = []
    try:
        for device in definition.devices:
            binding = (device.host or "127.0.0.1", device.snmp_port)
            if binding in occupied_by_current:
                continue
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind(binding)
            except OSError as exc:
                probe.close()
                raise OSError(f"UDP binding {binding[0]}:{binding[1]} is unavailable: {exc}") from exc
            probes.append(probe)
    finally:
        for probe in probes:
            probe.close()


def _definition_bindings(definition) -> set[tuple[str, int]]:
    return {
        (device.host or "127.0.0.1", device.snmp_port)
        for device in definition.devices
    }


def _start_agents(runtime: ScenarioState, definition) -> dict[str, SnmpAgent]:
    """Start a complete candidate set, cleaning partial candidates on failure."""
    started: dict[str, SnmpAgent] = {}
    try:
        for device in definition.devices:
            agent = SnmpAgent(runtime, device.id, COMMUNITY)
            agent.start()
            started[device.id] = agent
        return started
    except Exception:
        for agent in started.values():
            agent.stop()
        raise


def _stop_agents(items: dict[str, SnmpAgent]) -> None:
    failed = [device_id for device_id, agent in items.items() if not agent.stop()]
    if failed:
        raise RuntimeError(
            "Failed to stop SNMP Agent thread(s): " + ", ".join(sorted(failed))
        )


def _start_definition(definition, topology_id: str | None = None) -> ScenarioState:
    global state, active_topology_id
    try:
        _preflight_bindings(definition)
    except OSError as exc:
        raise RuntimeError(f"Failed to reserve SNMP bindings for {topology_id or definition.id}: {exc}") from exc
    previous_state = state
    previous_topology_id = active_topology_id
    previous_agents = dict(agents)
    runtime = ScenarioState(definition)
    candidate_bindings = _definition_bindings(definition)
    overlapping = bool(candidate_bindings & _current_bindings())

    # Different UDP bindings can be prepared while the old topology remains
    # live.  Matching bindings require a short handover; a failed candidate is
    # compensated by re-starting the old runtime before returning an error.
    if not overlapping:
        started = _start_agents(runtime, definition)
        try:
            _stop_agents(previous_agents)
        except Exception as handover_error:
            _stop_agents(started)
            restored: dict[str, SnmpAgent] = {}
            if previous_state is not None:
                try:
                    restored = _start_agents(
                        previous_state, previous_state.definition
                    )
                except Exception as restore_error:
                    agents.clear()
                    agents.update(restored)
                    raise RuntimeError(
                        "Previous SNMP topology failed to stop and could not be restored"
                    ) from restore_error
            agents.clear()
            agents.update(restored)
            state = previous_state
            active_topology_id = previous_topology_id
            raise RuntimeError(
                "Candidate topology was not committed because the previous topology failed to stop"
            ) from handover_error
    else:
        _stop_agents(previous_agents)
        try:
            started = _start_agents(runtime, definition)
        except Exception as candidate_error:
            restored: dict[str, SnmpAgent] = {}
            if previous_state is not None:
                try:
                    restored = _start_agents(
                        previous_state, previous_state.definition
                    )
                except Exception as restore_error:
                    agents.clear()
                    agents.update(restored)
                    raise RuntimeError(
                        "Candidate SNMP topology failed and old topology could not be restored"
                    ) from restore_error
            agents.clear()
            agents.update(restored)
            state = previous_state
            active_topology_id = previous_topology_id
            raise RuntimeError(
                f"Failed to start candidate topology {topology_id or definition.id}; old topology restored"
            ) from candidate_error
    state = runtime
    agents.clear()
    agents.update(started)
    active_topology_id = topology_id or definition.id
    bridge_result = bridge.reconcile(runtime)
    if bridge_result.get("enabled") and not bridge_result.get("ok"):
        logger.error(
            "simulator_bridge_reconcile_failed topology_id=%s detail=%s",
            active_topology_id,
            bridge_result.get("detail", "unknown error"),
        )
    elif not bridge_result.get("enabled"):
        logger.warning(
            "simulator_bridge_disabled topology_id=%s detail=%s",
            active_topology_id,
            bridge_result.get("detail", "bridge disabled"),
        )
    return runtime


def start_scenario(scenario_id: str) -> ScenarioState:
    definition = built_in_scenarios().get(scenario_id)
    if not definition:
        raise HTTPException(404, f"Unknown scenario: {scenario_id}")
    return _start_definition(definition, scenario_id)


def start_topology(topology_id: str) -> ScenarioState:
    topology = store.get(topology_id)
    definition = topology_to_scenario(topology)
    return _start_definition(definition, topology_id)


def stop_runtime(clear_state: bool = True) -> None:
    global state, active_topology_id
    _stop_agents(agents)
    agents.clear()
    active_topology_id = None
    if clear_state:
        state = None


async def _broadcast(message: dict) -> None:
    stale = []
    for ws in list(_ws_clients):
        try:
            await ws.send_json(message)
        except Exception:
            stale.append(ws)
    for ws in stale:
        _ws_clients.discard(ws)


def _schedule_broadcast(message: dict) -> None:
    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast(message), _event_loop)
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_broadcast(message))


def _device_host(device_id: str | None) -> str | None:
    if not device_id or state is None:
        return None
    try:
        return state.device(device_id).get("host")
    except KeyError:
        return None


def _send_result_trap(result: TransitionResult) -> bool:
    if not result.trap:
        return False
    send_formal_trap(
        result.trap.level,
        result.trap.message,
        TRAP_HOST,
        TRAP_PORT,
        COMMUNITY,
        source_host=_device_host(result.device_id),
        layout=result.trap.layout,
    )
    return True


def _after_change(result: TransitionResult, event_type: str) -> dict:
    trap_sent = _send_result_trap(result)
    runtime = current_state()
    reconcile = (
        {"skipped": "idempotent"}
        if result.idempotent
        else bridge.reconcile(runtime)
    )
    snapshot = runtime.snapshot()
    snapshot["active_topology_id"] = active_topology_id
    snapshot["runtime_instances"] = runtime.runtime_instances_metadata()
    payload = {
        "type": event_type,
        "schema_version": snapshot["schema_version"],
        "revision": result.revision,
        "device_id": result.device_id,
        "event": result.event,
        "event_id": result.event["event_id"] if result.event else None,
        "changed_paths": list(result.changed_paths),
        "committed_values": [
            {"path": path, "value": value}
            for path, value in result.committed_values
        ],
        "idempotent": result.idempotent,
        "lifecycle_intent": result.lifecycle_intent,
        "trap_sent": trap_sent,
        "state": snapshot,
        "snapshot": snapshot,
    }
    if not result.idempotent:
        _schedule_broadcast(payload)
    return {
        "revision": result.revision,
        "device_id": result.device_id,
        "event": result.event,
        "changed_paths": list(result.changed_paths),
        "committed_values": [
            {"path": path, "value": value}
            for path, value in result.committed_values
        ],
        "idempotent": result.idempotent,
        "lifecycle_intent": result.lifecycle_intent,
        "trap_sent": trap_sent,
        "bridge": {"reconcile": reconcile},
        "state": snapshot,
        "snapshot": snapshot,
    }


def _apply_agent_lifecycle(
    runtime: ScenarioState, result: TransitionResult
) -> None:
    """Apply the explicit lifecycle intent emitted by the L3 facade."""

    if result.idempotent or result.device_id is None:
        return
    device_id = result.device_id
    if result.lifecycle_intent == "ensure_agent_running" and device_id not in agents:
        agent = SnmpAgent(runtime, device_id, COMMUNITY)
        agent.start()
        agents[device_id] = agent
    elif result.lifecycle_intent == "stop_agent" and device_id in agents:
        agents.pop(device_id).stop()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _event_loop
    _event_loop = asyncio.get_running_loop()
    start_topology(os.environ.get("SIM_TOPOLOGY", os.environ.get("SIM_SCENARIO", "ccdc-regression")))
    yield
    stop_runtime()
    _event_loop = None


app = FastAPI(title="KVM Simulator", version="3.0", lifespan=lifespan)
if UI_DIST.exists():
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="simulator-ui-assets")


@app.get("/api/v1/profiles")
def get_profiles():
    return profile_metadata()


@app.get("/api/v1/status")
def get_status():
    """Small redacted status payload used by the L0 smoke verifier."""
    snapshot = state.snapshot() if state is not None else None
    scenario = snapshot.get("scenario", {}) if snapshot else {}
    devices = scenario.get("devices", []) if isinstance(scenario, dict) else []
    expected_agents = len(devices)
    agent_details = [
        agent.status()
        for _, agent in sorted(agents.items())
    ]
    healthy_agents = sum(
        1
        for item in agent_details
        if item["thread_alive"] and item["ready"] and not item["error_type"]
    )
    bridge_status = bridge.status()
    bridge_failed = (
        bridge_status["enabled"]
        and isinstance(bridge_status["last_reconcile"], dict)
        and bridge_status["last_reconcile"].get("ok") is not True
    )
    runtime_degraded = state is None or healthy_agents != expected_agents
    return {
        "status": "degraded" if runtime_degraded or bridge_failed else "ok",
        "runtime": {
            "running": state is not None,
            "topology_id": active_topology_id,
            "revision": snapshot.get("revision") if snapshot else None,
            "device_count": expected_agents,
        },
        "agents": {
            "expected": expected_agents,
            "running": healthy_agents,
            "device_ids": sorted(agents),
            "bindings": agent_details,
        },
        "bridge": bridge_status,
        "dashboard": {
            "url": bridge_status["dashboard_url"],
            "last_reconcile_ok": (
                bridge_status["last_reconcile"].get("ok")
                if isinstance(bridge_status["last_reconcile"], dict)
                else None
            ),
        },
        "trap": {
            "target_host": TRAP_HOST,
            "target_port": TRAP_PORT,
            "receiver_verification": "dashboard-health-required",
        },
        "configuration": {
            "simulator_host": SIMULATOR_HOST,
            "web_port": SIMULATOR_PORT,
            "address_mode": os.environ.get("SIM_ADDRESS_MODE", "port"),
            "topology": os.environ.get(
                "SIM_TOPOLOGY",
                os.environ.get("SIM_SCENARIO", "ccdc-regression"),
            ),
            "bridge_token": "configured" if bridge.token else "not-configured",
            "community": "configured" if "SNMP_COMMUNITY" in os.environ else "default",
            "ui_mode": "built" if (UI_DIST / "index.html").is_file() else "fallback",
        },
    }


@app.post("/api/v1/bridge/reconcile")
def retry_bridge_reconcile():
    """Explicitly re-check the current Dashboard run for L0 diagnostics."""
    runtime = current_state()
    result = bridge.reconcile(runtime)
    status = bridge.status()
    if not result.get("enabled"):
        raise HTTPException(409, status)
    if result.get("ok") is not True:
        raise HTTPException(503, status)
    return status


@app.get("/api/v1/topologies")
def list_topologies():
    return [item.model_dump(mode="json") for item in store.list()]


@app.post("/api/v1/topologies", status_code=201)
def create_topology(topology: TopologyDefinition):
    created = store.create(topology)
    _schedule_broadcast({"type": "topology_created", "topology_id": created.id})
    return created


@app.get("/api/v1/topologies/{topology_id}")
def get_topology(topology_id: str):
    return store.get(topology_id)


@app.put("/api/v1/topologies/{topology_id}")
def update_topology(topology_id: str, topology: TopologyDefinition):
    updated = store.update(topology_id, topology)
    _schedule_broadcast({"type": "topology_updated", "topology_id": updated.id})
    return updated


@app.delete("/api/v1/topologies/{topology_id}", status_code=204)
def delete_topology(topology_id: str):
    if topology_id == active_topology_id:
        raise HTTPException(409, "Cannot delete the active topology; stop it first")
    store.delete(topology_id)
    _schedule_broadcast({"type": "topology_deleted", "topology_id": topology_id})
    return None


@app.post("/api/v1/topologies/{topology_id}/start")
def api_start_topology(topology_id: str):
    runtime = start_topology(topology_id)
    snapshot = runtime.snapshot()
    _schedule_broadcast({"type": "topology_started", "topology_id": topology_id, "revision": snapshot["revision"]})
    return snapshot


@app.post("/api/v1/topologies/{topology_id}/stop")
def api_stop_topology(topology_id: str):
    if active_topology_id and active_topology_id != topology_id:
        raise HTTPException(409, f"Running topology is {active_topology_id}")
    stop_runtime()
    _schedule_broadcast({"type": "topology_stopped", "topology_id": topology_id})
    return {"stopped": True, "topology_id": topology_id}


@app.patch("/api/v1/runtime/devices/{device_id}/state")
def patch_runtime_device_state(device_id: str, patch: RuntimeStatePatch):
    runtime = current_state()
    if (
        patch.expected_revision is not None
        and patch.expected_revision != runtime.revision
    ):
        raise HTTPException(
            409,
            {
                "code": "revision_conflict",
                "message": "Runtime revision has changed; refetch state before retrying",
                "current_revision": runtime.revision,
                "retryable": True,
            },
        )
    try:
        result = runtime.patch_device_state(device_id, patch)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown runtime path target: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _after_change(result, "runtime_state_patch")


@app.post("/api/v1/runtime/devices/{device_id}/actions")
def runtime_device_action(device_id: str, request: RuntimeDeviceActionRequest):
    runtime = current_state()
    try:
        result = runtime.device_action(device_id, request.action)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown device: {exc.args[0]}") from exc
    except RuntimeTransitionError as exc:
        raise HTTPException(422, str(exc)) from exc
    _apply_agent_lifecycle(runtime, result)
    return _after_change(result, "device_action")


@app.websocket("/api/v1/ws")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        await websocket.send_json({"type": "snapshot", "state": current_state().snapshot() if state else None})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)


@app.get("/api/v1/scenarios")
def list_scenarios():
    return [{"id": item.id, "title": item.title, "devices": len(item.devices)} for item in built_in_scenarios().values()]


@app.post("/api/v1/scenarios/{scenario_id}/load")
def load_scenario(scenario_id: str):
    runtime = start_scenario(scenario_id)
    _schedule_broadcast({"type": "topology_started", "topology_id": scenario_id, "revision": runtime.revision})
    return runtime.snapshot()


@app.get("/api/v1/state")
def get_state():
    runtime = current_state()
    snapshot = runtime.snapshot()
    snapshot["active_topology_id"] = active_topology_id
    snapshot["runtime_instances"] = runtime.runtime_instances_metadata()
    return snapshot


@app.post("/api/v1/devices/{device_id}/reachability")
def set_reachability(device_id: str, paused: bool):
    runtime = current_state()
    try:
        result = runtime.pause_device(device_id, paused)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown device: {exc.args[0]}") from exc
    except RuntimeTransitionError as exc:
        raise HTTPException(422, str(exc)) from exc
    _apply_agent_lifecycle(runtime, result)
    response = _after_change(result, "device_reachability")
    response["paused"] = runtime.is_paused(device_id)
    return response


@app.patch("/api/v1/devices/{device_id}/endpoints/{endpoint_id}")
def update_endpoint(device_id: str, endpoint_id: str, patch: EndpointStatePatch):
    try:
        result = current_state().patch_endpoint(device_id, endpoint_id, patch)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown endpoint: {exc.args[0]}") from exc
    return _after_change(result, "endpoint_state")


@app.patch("/api/v1/devices/{device_id}/routes/{route_id}")
def update_route(device_id: str, route_id: str, patch: RouteStatePatch):
    try:
        result = current_state().patch_route(device_id, route_id, patch)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown route: {exc.args[0]}") from exc
    return _after_change(result, "route_state")


@app.post("/api/v1/traps")
def send_trap(request: TrapRequest):
    runtime = current_state()
    device_ids = request.device_ids if request.device_ids is not None else ([request.device_id] if request.device_id else [])
    if not device_ids:
        raise HTTPException(422, "At least one target device is required")
    unique_device_ids = list(dict.fromkeys(device_ids))
    missing = [device_id for device_id in unique_device_ids if not _device_host(device_id)]
    if missing:
        raise HTTPException(404, f"Unknown trap target device(s): {', '.join(missing)}")
    preset_message = {
        "offline": "entered critical state: 'Offline'",
        "sfp_rx_power": "SFP Rx power changed",
        "display_changed": "Display connection state changed",
    }.get(request.preset or "")
    message = preset_message or request.message
    for device_id in unique_device_ids:
        send_formal_trap(
            request.level,
            message,
            TRAP_HOST,
            TRAP_PORT,
            COMMUNITY,
            source_host=_device_host(device_id),
            layout=request.layout,
        )
        _schedule_broadcast({"type": "trap_sent", "device_id": device_id, "level": request.level, "message": message, "layout": request.layout, "revision": runtime.revision})
    notification_oid = (
        LEGACY_TRAP["notification_oid"]
        if request.layout == "legacy"
        else FORMAL_TRAP["notification_oid"]
    )
    return {"sent": True, "count": len(unique_device_ids), "notification_oid": notification_oid}


@app.post("/api/v1/reset")
def reset_scenario():
    runtime = current_state()
    result = runtime.reset()
    reconcile = (
        {"skipped": "idempotent"}
        if result.idempotent
        else bridge.reconcile(runtime)
    )
    snapshot = runtime.snapshot()
    if not result.idempotent:
        _schedule_broadcast(
            {
                "type": "reset",
                "revision": result.revision,
                "changed_paths": list(result.changed_paths),
                "idempotent": False,
                "state": snapshot,
                "snapshot": snapshot,
            }
        )
    return {
        **snapshot,
        "changed_paths": list(result.changed_paths),
        "idempotent": result.idempotent,
        "bridge": {"reconcile": reconcile},
    }


@app.get("/", response_class=HTMLResponse)
def control_page():
    if UI_DIST.exists():
        return FileResponse(UI_DIST / "index.html")
    return """<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>KVM Simulator</title>
<style>body{font-family:system-ui;background:#101821;color:#dfe8f3;margin:32px;max-width:1100px}button,select{padding:8px;margin:3px;background:#213449;color:#dfe8f3;border:1px solid #4c718f;border-radius:4px}pre{background:#071018;padding:16px;overflow:auto;border-radius:6px}.offline{color:#ff7272}.active{color:#63d6a2}</style></head><body>
<h1>KVM SNMP Simulator</h1><p>REST/WS runtime topology API is available under <code>/api/v1</code>. Build simulator-ui to replace this fallback page.</p>
<label>拓扑 <select id='topology'></select></label><button onclick='startTopology()'>启动</button><button onclick='stopTopology()'>停止</button><button onclick='refresh()'>刷新</button><div id='content'></div>
<script>
async function api(path, options={}){const r=await fetch(path,{headers:{'Content-Type':'application/json'},...options});if(!r.ok)throw new Error(await r.text());return r.status===204?null:r.json()}
async function boot(){let topologies=await api('/api/v1/topologies');document.querySelector('#topology').innerHTML=topologies.map(s=>`<option value="${s.id}">${s.title}</option>`).join('');refresh()}
async function startTopology(){await api('/api/v1/topologies/'+topology.value+'/start',{method:'POST'});refresh()}
async function stopTopology(){await api('/api/v1/topologies/'+topology.value+'/stop',{method:'POST'});refresh()}
async function action(device,action){await api(`/api/v1/runtime/devices/${device}/actions`,{method:'POST',body:JSON.stringify({action})});refresh()}
async function refresh(){try{const x=await api('/api/v1/state');let h=`<p>Revision ${x.revision}</p>`;for(const d of x.scenario.devices){const paused=x.paused_devices.includes(d.id);h+=`<section><h2>${d.name} <small>${d.profile} / ${d.host}:${d.snmp_port}</small></h2><button onclick="action('${d.id}','${paused?'restore':'disconnect'}')">${paused?'恢复':'断网'}</button><button onclick="action('${d.id}','power_off')">下电</button></section>`}content.innerHTML=h+'<h3>完整状态</h3><pre>'+JSON.stringify(x,null,2)+'</pre>'}catch(e){content.innerHTML='<pre class="offline">'+e+'</pre>'}}
boot();setInterval(refresh,2000)
</script></body></html>"""
