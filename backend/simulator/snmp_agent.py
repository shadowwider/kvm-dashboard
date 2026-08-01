from __future__ import annotations

import socket
import threading
import time
import logging
from typing import Any

from pyasn1.codec.ber import decoder as ber_decoder, encoder as ber_encoder
from pyasn1.type.univ import ObjectIdentifier
from pysnmp.proto import api as snmp_api

from .profiles import FORMAL_TRAP, LEGACY_TRAP, RenderedValue, render_oid_map
from .state import ScenarioState

SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"
MAX_BULK_REPETITIONS = 100
logger = logging.getLogger(__name__)


def oid_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.strip(".").split("."))


def endpoint_oid_map(device: dict, profile_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Backward-compatible wrapper around the declarative profile renderer."""
    return render_oid_map(device, profile_state)


def _snmp_value(p_mod, value: Any):
    snmp_type = "auto"
    if isinstance(value, RenderedValue):
        snmp_type = value.snmp_type
        value = value.value
    if snmp_type in {"object_identifier", "oid"}:
        return p_mod.ObjectIdentifier(oid_tuple(str(value)))
    if snmp_type in {"integer", "enum"} or isinstance(value, int):
        return p_mod.Integer(int(value))
    if snmp_type == "gauge":
        return p_mod.Gauge32(int(value))
    if snmp_type == "counter":
        return p_mod.Counter32(int(value))
    if snmp_type == "counter64":
        return p_mod.Counter64(int(value))
    if snmp_type == "timeticks":
        return p_mod.TimeTicks(int(value))
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
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._protocol_error_count = 0
        self._last_protocol_error_type: str | None = None
        self._last_protocol_error_at: float | None = None
        self._snapshot_lock = threading.Lock()
        self._snapshot_revision: int | None = None
        self._snapshot_entries: tuple[tuple[tuple[int, ...], str, Any], ...] = ()

    def start(self) -> None:
        device = self.state.device(self.device_id)
        host = device.get("host", "127.0.0.1")
        port = device["snmp_port"]
        self._ready.clear()
        self._stop.clear()
        self._error = None
        with self._snapshot_lock:
            self._snapshot_revision = None
            self._snapshot_entries = ()
        self._thread = threading.Thread(target=self._run, args=(host, port), daemon=True, name=f"sim-snmp-{self.device_id}")
        self._thread.start()
        self._ready.wait(timeout=2)
        if self._error:
            self.stop()
            raise RuntimeError(f"Failed to bind SNMP agent {self.device_id} on {host}:{port}: {self._error}")
        if not self._ready.is_set():
            self.stop()
            raise RuntimeError(f"Timed out starting SNMP agent {self.device_id} on {host}:{port}")

    def stop(self) -> bool:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                self._error = RuntimeError("SNMP Agent thread did not stop")
                return False
        return True

    def status(self) -> dict:
        """Return binding/thread readiness without exposing the SNMP community."""
        device = self.state.device(self.device_id)
        thread_alive = bool(self._thread and self._thread.is_alive())
        return {
            "device_id": self.device_id,
            "host": device.get("host", "127.0.0.1"),
            "port": device["snmp_port"],
            "thread_alive": thread_alive,
            "ready": self._ready.is_set() and self._error is None,
            "error_type": type(self._error).__name__ if self._error else None,
            "error": str(self._error) if self._error else None,
            "protocol_error_count": self._protocol_error_count,
            "last_protocol_error_type": self._last_protocol_error_type,
        }

    def _oid_entries(self) -> tuple[tuple[tuple[int, ...], str, Any], ...]:
        """Capture one complete L3 state snapshot and cache its OID view by revision."""
        captured = self.state.renderable_snapshot(self.device_id)
        revision = captured["revision"]
        with self._snapshot_lock:
            if revision == self._snapshot_revision:
                return self._snapshot_entries
            device = captured["device"]
            mapping = render_oid_map(
                device,
                device.get("profile_state"),
                include_metadata=True,
            )
            entries = tuple(
                sorted((oid_tuple(oid), oid, value) for oid, value in mapping.items())
            )
            self._snapshot_revision = revision
            self._snapshot_entries = entries
            return entries

    def _record_protocol_error(self, exc: BaseException) -> None:
        self._protocol_error_count += 1
        self._last_protocol_error_type = type(exc).__name__
        self._last_protocol_error_at = time.monotonic()
        logger.warning(
            "simulator_snmp_protocol_error device_id=%s error_type=%s",
            self.device_id,
            type(exc).__name__,
        )

    def _run(self, host: str, port: int) -> None:
        p_mod = snmp_api.protoModules[snmp_api.protoVersion2c]
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        except BaseException as exc:
            self._error = exc
            self._ready.set()
            return
        with sock:
            sock.settimeout(0.2)
            self._ready.set()
            while not self._stop.is_set():
                try:
                    packet, address = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    # Windows UDP sockets can raise WSAECONNRESET when a previous peer
                    # becomes unreachable; keep the simulator agent alive.
                    continue
                try:
                    if self.state.is_paused(self.device_id):
                        continue
                    request, _ = ber_decoder.decode(packet, asn1Spec=p_mod.Message())
                    if p_mod.apiMessage.getCommunity(request).prettyPrint() != self.community:
                        continue
                    request_pdu = p_mod.apiMessage.getPDU(request)
                    response = self._respond(
                        p_mod, request, request_pdu, self._oid_entries()
                    )
                    sock.sendto(ber_encoder.encode(response), address)
                except Exception as exc:
                    self._record_protocol_error(exc)
                    continue

    @staticmethod
    def _respond(p_mod, request, request_pdu, entries):
        """Build a standards-shaped v2c response from one immutable OID snapshot."""
        if isinstance(entries, dict):  # retained for direct unit-level compatibility
            entries = tuple(
                sorted((oid_tuple(key), key, value) for key, value in entries.items())
            )
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
        value_by_oid = {text: value for _, text, value in entries}
        if request_pdu.tagSet == p_mod.SetRequestPDU.tagSet:
            p_mod.apiPDU.setErrorStatus(response_pdu, 17)  # notWritable: simulator state changes go through REST only.
            p_mod.apiPDU.setErrorIndex(response_pdu, 1 if request_vars else 0)
            response_vars = list(request_vars)
        elif request_pdu.tagSet == p_mod.GetRequestPDU.tagSet:
            for oid, _ in request_vars:
                text_oid = str(oid).lstrip(".")
                response_vars.append((oid, _snmp_value(p_mod, value_by_oid[text_oid]) if text_oid in value_by_oid else p_mod.NoSuchObject()))
        else:
            is_bulk = request_pdu.tagSet == p_mod.GetBulkRequestPDU.tagSet
            non_repeaters = (
                p_mod.apiBulkPDU.getNonRepeaters(request_pdu) if is_bulk else len(request_vars)
            )
            repetitions = (
                p_mod.apiBulkPDU.getMaxRepetitions(request_pdu) if is_bulk else 1
            )
            non_repeaters = min(len(request_vars), max(0, int(non_repeaters)))
            repetitions = min(MAX_BULK_REPETITIONS, max(0, int(repetitions)))
            cursors = [oid_tuple(str(oid)) for oid, _ in request_vars]
            for index, (oid, _) in enumerate(request_vars[:non_repeaters]):
                next_oid, value = next_value(cursors[index])
                response_vars.append((ObjectIdentifier(oid_tuple(next_oid)), _snmp_value(p_mod, value)) if next_oid else (oid, p_mod.EndOfMibView()))
                if next_oid:
                    cursors[index] = oid_tuple(next_oid)
            repeating_indexes = range(non_repeaters, len(request_vars))
            for _ in range(repetitions):
                for index in repeating_indexes:
                    original_oid, _original_value = request_vars[index]
                    next_oid, value = next_value(cursors[index])
                    if next_oid is None:
                        response_vars.append((original_oid, p_mod.EndOfMibView()))
                    else:
                        response_vars.append((ObjectIdentifier(oid_tuple(next_oid)), _snmp_value(p_mod, value)))
                        cursors[index] = oid_tuple(next_oid)
        p_mod.apiPDU.setVarBinds(response_pdu, response_vars)
        p_mod.apiMessage.setPDU(response, response_pdu)
        return response


def send_formal_trap(
    level: int,
    message: str,
    host: str,
    port: int,
    community: str = "public",
    source_host: str | None = None,
    layout: str = "formal",
) -> None:
    from pysnmp.proto.rfc1902 import TimeTicks
    from pysnmp.proto.rfc1905 import SNMPv2TrapPDU

    trap_layout = LEGACY_TRAP if layout == "legacy" else FORMAL_TRAP
    p_mod = snmp_api.protoModules[snmp_api.protoVersion2c]
    message_object = p_mod.Message()
    p_mod.apiMessage.setDefaults(message_object)
    p_mod.apiMessage.setCommunity(message_object, community)
    trap_pdu = SNMPv2TrapPDU()
    p_mod.apiPDU.setDefaults(trap_pdu)
    p_mod.apiPDU.setVarBinds(trap_pdu, [
        (ObjectIdentifier(oid_tuple(SYS_UPTIME)), TimeTicks(int(time.monotonic() * 100))),
        (ObjectIdentifier(oid_tuple(SNMP_TRAP_OID)), p_mod.ObjectIdentifier(oid_tuple(trap_layout["notification_oid"]))),
        (ObjectIdentifier(oid_tuple(trap_layout["level_oid"])), p_mod.Integer(level)),
        (ObjectIdentifier(oid_tuple(trap_layout["message_oid"])), p_mod.OctetString(message.encode("utf-8"))),
    ])
    p_mod.apiMessage.setPDU(message_object, trap_pdu)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        if source_host:
            try:
                sock.bind((source_host, 0))
            except OSError:
                # Source binding is best-effort so port-mode/Docker hosts can still emit traps.
                pass
        sock.sendto(ber_encoder.encode(message_object), (host, port))
