import asyncio

from app.api.topology import get_device_topology
from app.models.device import Device
from app.models.endpoint import Endpoint
from app.models.simulator_run import SimulatorRun


class _Result:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values

    def __iter__(self):
        return iter(self.values)


class _TopologySession:
    def __init__(self, device, endpoints, run):
        self.device = device
        self.endpoints = endpoints
        self.run = run
        self.select_count = 0

    async def get(self, model, identifier):
        return self.device if model is Device and identifier == self.device.id else None

    async def execute(self, statement):
        self.select_count += 1
        return _Result(self.endpoints if self.select_count == 1 else [self.run])


def test_simulation_topology_marks_route_provenance():
    device = Device(
        id="sim_run_sim-ccdc-01",
        name="Simulator",
        host="127.0.0.1",
        port=11161,
        community="public",
        model_name="SIMULATION / ccdc_legacy_unverified",
        last_status="online",
    )
    endpoints = [
        Endpoint(id=f"{device.id}_cpu_1", device_id=device.id, name="CPU-1-001", index=1, module_type="cpu", last_status={"ep_device_status": "online"}),
        Endpoint(id=f"{device.id}_con_1", device_id=device.id, name="CON-1-001", index=13, module_type="con", last_status={"con_device_status": "online"}),
    ]
    run = SimulatorRun(
        id="run",
        scenario_id="ccdc-regression",
        revision=4,
        manifest={
            "scenario": {
                "devices": [{
                    "id": "sim-ccdc-01",
                    "profile": "ccdc_legacy_unverified",
                    "evidence": "legacy-compatibility",
                    "endpoints": [
                        {"id": "CPU-1-001", "module_type": "cpu", "row": 1},
                        {"id": "CON-1-001", "module_type": "con", "row": 1},
                    ],
                    "routes": [{
                        "id": "route-1",
                        "source_endpoint_id": "CPU-1-001",
                        "target_endpoint_id": "CON-1-001",
                        "state": "active",
                    }],
                }]
            }
        },
    )

    result = asyncio.run(get_device_topology(device.id, _TopologySession(device, endpoints, run)))

    assert result["simulation"]["revision"] == 4
    assert result["simulation"]["routes"] == [{
        "id": "route-1",
        "source": f"{device.id}_cpu_1",
        "target": f"{device.id}_con_1",
        "state": "active",
        "label": "Simulation route",
        "evidence": "simulation-declared",
    }]
