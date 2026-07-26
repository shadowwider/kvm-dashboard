from __future__ import annotations

import socket
import threading
import time
from typing import Any

from pyasn1.codec.ber import decoder as ber_decoder, encoder as ber_encoder
from pyasn1.type.univ import ObjectIdentifier
from pysnmp.proto import api as snmp_api

from .profiles import FORMAL_TRAP
from .state import ScenarioState

SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"


def oid_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.strip(".").split("."))


def endpoint_oid_map(device: dict) -> dict[str, Any]:
    """Emit legacy CCDC-shaped fields only for regression-compatible profiles.

    Other profiles deliberately expose identity only until the production collector gains
    profile-aware poll plans; this prevents a simulator fixture from claiming unsupported
    collector compatibility.
    """
    base = device["system_oid"]
    result: dict[str, Any] = {
        SYS_OBJECT_ID: base,
        f"{base}.2.1.1.0": device["id"],
        f"{base}.2.1.3.0": device["name"],
        f"{base}.2.2.1.0": "SIM-2026.07",
    }
    if device["profile"] != "ccdc_legacy_unverified":
        return result

    result.update({
        f"{base}.2.3.1.0": 1,
        f"{base}.2.3.2.0": 1,
        f"{base}.2.3.3.0": "42.0",
        f"{base}.2.3.502.0": 3200,
        f"{base}.2.3.503.0": 3150,
        f"{base}.2.3.504.0": 3100,
        f"{base}.2.3.505.0": 3050,
        f"{base}.2.3.506.0": 1,
        f"{base}.2.3.507.0": 1,
    })
    cpu_base = f"{base}.1.2.2.3.1000.1"
    con_base = f"{base}.1.1.2.3.1000.1"
    port_base = f"{base}.2.3.1000.1"
    for endpoint in device["endpoints"]:
        row = endpoint["row"]
        status = endpoint["status"]
        if endpoint["module_type"] == "cpu":
            values = {
                1: endpoint["port_index"], 2: endpoint["id"], 3: "0x00000401",
                4: endpoint.get("display_name") or endpoint["id"], 5: status, 6: 1,
                7: 1, 8: "40.0", 12: 2, 13: 1 if endpoint.get("video_connected", True) else 0,
                16: 5, 19: 1, 21: 500, 22: 480, 23: "SIM-SFP", 24: 1,
            }
            for column, value in values.items():
                result[f"{cpu_base}.{column}.{row}"] = value
        else:
            values = {
                1: endpoint["port_index"], 2: endpoint["id"], 3: "0x00000101",
                4: endpoint.get("display_name") or endpoint["id"], 5: status, 6: 1,
                7: 1, 8: "38.0", 9: 3, 10: 3,
                11: 1 if endpoint.get("display_connected", True) else 0,
                14: "SIM-DISPLAY", 17: 1 if endpoint.get("frozen", False) else 0,
                20: 510, 23: 490, 26: "SIM-SFP", 29: 1, 30: 1,
            }
            for column, value in values.items():
                result[f"{con_base}.{column}.{row}"] = value
    for port in device["ports"]:
        values = {2: {"noModule": 0, "moduleDeactivated": 1, "down": 2, "up": 3}[port["status"]], 3: 3}
        for column, value in values.items():
            result[f"{port_base}.{column}.{port['index']}"] = value
    return result


def _snmp_value(p_mod, value: Any):
    if isinstance(value, int):
        return p_mod.Integer(value)
    value_text = str(value)
    if value_text.startswith("1.3.6."):
        return p_mod.ObjectIdentifier(oid_tuple(value_text))
    return p_mod.OctetString(value_text.encode("utf-8"))


class SnmpAgent:
    def __init__(self, state: ScenarioState, device_id: str, community: str = "public"):
        self.state = state
        self.device_id = device_id
        self.community = community
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        device = self.state.device(self.device_id)
        self._thread = threading.Thread(target=self._run, args=(device["snmp_port"],), daemon=True, name=f"sim-snmp-{self.device_id}")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self, port: int) -> None:
        p_mod = snmp_api.protoModules[snmp_api.protoVersion2c]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.settimeout(0.2)
            while not self._stop.is_set():
                try:
                    packet, address = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                try:
                    if self.state.is_paused(self.device_id):
                        continue
                    request, _ = ber_decoder.decode(packet, asn1Spec=p_mod.Message())
                    if p_mod.apiMessage.getCommunity(request).prettyPrint() != self.community:
                        continue
                    request_pdu = p_mod.apiMessage.getPDU(request)
                    mapping = endpoint_oid_map(self.state.device(self.device_id))
                    response = self._respond(p_mod, request, request_pdu, mapping)
                    sock.sendto(ber_encoder.encode(response), address)
                except Exception:
                    continue

    @staticmethod
    def _respond(p_mod, request, request_pdu, mapping: dict[str, Any]):
        entries = sorted((oid_tuple(key), key, value) for key, value in mapping.items())
        response = p_mod.Message()
        p_mod.apiMessage.setDefaults(response)
        p_mod.apiMessage.setCommunity(response, p_mod.apiMessage.getCommunity(request))
        response_pdu = p_mod.GetResponsePDU()
        p_mod.apiPDU.setDefaults(response_pdu)
        p_mod.apiPDU.setRequestID(response_pdu, p_mod.apiPDU.getRequestID(request_pdu))
        request_vars = p_mod.apiPDU.getVarBinds(request_pdu)

        def next_value(current):
            for numeric_oid, text_oid, value in entries:
                if numeric_oid > current:
                    return text_oid, value
            return None, None

        response_vars = []
        if request_pdu.tagSet == p_mod.GetRequestPDU.tagSet:
            for oid, _ in request_vars:
                text_oid = str(oid).lstrip(".")
                response_vars.append((oid, _snmp_value(p_mod, mapping[text_oid]) if text_oid in mapping else p_mod.NoSuchObject()))
        else:
            is_bulk = request_pdu.tagSet == p_mod.GetBulkRequestPDU.tagSet
            non_repeaters = p_mod.apiBulkPDU.getNonRepeaters(request_pdu) if is_bulk else len(request_vars)
            repetitions = p_mod.apiBulkPDU.getMaxRepetitions(request_pdu) if is_bulk else 1
            for index, (oid, _) in enumerate(request_vars):
                current = oid_tuple(str(oid))
                count = 1 if index < non_repeaters else repetitions
                for _ in range(count):
                    next_oid, value = next_value(current)
                    if next_oid is None:
                        response_vars.append((oid, p_mod.EndOfMibView()))
                        break
                    response_vars.append((ObjectIdentifier(oid_tuple(next_oid)), _snmp_value(p_mod, value)))
                    current = oid_tuple(next_oid)
        p_mod.apiPDU.setVarBinds(response_pdu, response_vars)
        p_mod.apiMessage.setPDU(response, response_pdu)
        return response


def send_formal_trap(level: int, message: str, host: str, port: int, community: str = "public") -> None:
    from pysnmp.proto.rfc1902 import TimeTicks
    from pysnmp.proto.rfc1905 import SNMPv2TrapPDU

    p_mod = snmp_api.protoModules[snmp_api.protoVersion2c]
    message_object = p_mod.Message()
    p_mod.apiMessage.setDefaults(message_object)
    p_mod.apiMessage.setCommunity(message_object, community)
    trap_pdu = SNMPv2TrapPDU()
    p_mod.apiPDU.setDefaults(trap_pdu)
    p_mod.apiPDU.setVarBinds(trap_pdu, [
        (ObjectIdentifier(oid_tuple(SYS_UPTIME)), TimeTicks(int(time.monotonic() * 100))),
        (ObjectIdentifier(oid_tuple(SNMP_TRAP_OID)), p_mod.ObjectIdentifier(oid_tuple(FORMAL_TRAP["notification_oid"]))),
        (ObjectIdentifier(oid_tuple(FORMAL_TRAP["level_oid"])), p_mod.Integer(level)),
        (ObjectIdentifier(oid_tuple(FORMAL_TRAP["message_oid"])), p_mod.OctetString(message.encode("utf-8"))),
    ])
    p_mod.apiMessage.setPDU(message_object, trap_pdu)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(ber_encoder.encode(message_object), (host, port))
