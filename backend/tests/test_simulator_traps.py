import socket

from pyasn1.codec.ber import decoder as ber_decoder
from pysnmp.proto import api as snmp_api

from simulator.profiles import FORMAL_TRAP, LEGACY_TRAP
from simulator.snmp_agent import send_formal_trap


def _capture_trap(layout="formal"):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2)
        host, port = receiver.getsockname()
        send_formal_trap(3, "trap smoke", host, port, source_host="127.0.0.1", layout=layout)
        packet, address = receiver.recvfrom(65535)
    p_mod = snmp_api.protoModules[snmp_api.protoVersion2c]
    message, _ = ber_decoder.decode(packet, asn1Spec=p_mod.Message())
    pdu = p_mod.apiMessage.getPDU(message)
    varbinds = [(str(oid), value.prettyPrint()) for oid, value in p_mod.apiPDU.getVarBinds(pdu)]
    return address, varbinds


def test_formal_trap_layout_can_be_captured_over_udp():
    address, varbinds = _capture_trap("formal")

    assert address[0] == "127.0.0.1"
    assert ("1.3.6.1.6.3.1.1.4.1.0", FORMAL_TRAP["notification_oid"]) in varbinds
    assert (FORMAL_TRAP["level_oid"], "3") in varbinds
    assert (FORMAL_TRAP["message_oid"], "trap smoke") in varbinds


def test_legacy_trap_layout_can_be_captured_over_udp():
    _, varbinds = _capture_trap("legacy")

    assert ("1.3.6.1.6.3.1.1.4.1.0", LEGACY_TRAP["notification_oid"]) in varbinds
    assert (LEGACY_TRAP["level_oid"], "3") in varbinds
    assert (LEGACY_TRAP["message_oid"], "trap smoke") in varbinds
