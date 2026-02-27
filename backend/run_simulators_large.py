#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
import random
import threading
import time
import socket
from pysnmp.proto import api as snmp_api
from pyasn1.codec.ber import decoder as ber_decoder, encoder as ber_encoder
from pyasn1.type.univ import ObjectIdentifier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("simulators_large")

OID_BASE = "1.3.6.1.4.1.32828.3.257.16"

def build_oid_map(num_endpoints, switch_id):
    base = OID_BASE
    oid_map = {
        "1.3.6.1.2.1.1.2.0": base,
        f"{base}.2.1.1.0": f"SIM-{switch_id}",
        f"{base}.2.1.2.0": "257",
        f"{base}.2.1.3.0": "ControlCenter-Compact-8C",
        f"{base}.2.1.4.0": f"GD-SIM-{switch_id}",
        f"{base}.2.1.5.0": f"0x000ff402455{switch_id}",
        f"{base}.2.1.6.0": f"0x000ff402456{switch_id}",
        f"{base}.2.2.1.0": "1.7.000 (01165)",
        f"{base}.2.3.1.0": 1,
        f"{base}.2.3.2.0": 1,
        f"{base}.2.3.3.0": f"{random.uniform(30,50):.1f}",
        f"{base}.2.3.500.0": f"{random.uniform(1.2,2.0):.2f}",
        f"{base}.2.3.501.0": f"{random.uniform(11.5,12.5):.2f}",
        f"{base}.2.3.502.0": str(random.randint(2800, 3200)),
        f"{base}.2.3.503.0": str(random.randint(2800, 3200)),
        f"{base}.2.3.504.0": str(random.randint(2800, 3200)),
        f"{base}.2.3.505.0": str(random.randint(2800, 3200)),
        f"{base}.2.3.508.0": str(random.randint(2800, 3200)),
        f"{base}.2.3.509.0": str(random.randint(2800, 3200)),
        f"{base}.2.3.506.0": 1,
        f"{base}.2.3.507.0": 0,
    }

    ep_base = f"{base}.1.2.2.3.1000.1"
    for i in range(1, num_endpoints + 1):
        ep_id = f"CPU-ID SW{switch_id}-{i:03d}"
        oid_map[f"{ep_base}.2.{i}"] = f"0x0{switch_id}0{i:03d}"
        oid_map[f"{ep_base}.3.{i}"] = "0x00000401"
        oid_map[f"{ep_base}.4.{i}"] = ep_id
        oid_map[f"{ep_base}.5.{i}"] = random.choice([1, 2]) # 1=online, 2=ready
        oid_map[f"{ep_base}.6.{i}"] = 0
        oid_map[f"{ep_base}.7.{i}"] = 0
        oid_map[f"{ep_base}.8.{i}"] = f"{random.uniform(35, 50):.1f}"
        oid_map[f"{ep_base}.9.{i}"] = 0
        oid_map[f"{ep_base}.10.{i}"] = 0
        oid_map[f"{ep_base}.11.{i}"] = 0
        oid_map[f"{ep_base}.12.{i}"] = random.choice([0, 2])
        oid_map[f"{ep_base}.13.{i}"] = random.choice([0, 1])
        oid_map[f"{ep_base}.14.{i}"] = 0
        oid_map[f"{ep_base}.15.{i}"] = 0
        oid_map[f"{ep_base}.16.{i}"] = random.choice([0, 2, 5, 6])
        oid_map[f"{ep_base}.17.{i}"] = 0
        oid_map[f"{ep_base}.18.{i}"] = 0
        oid_map[f"{ep_base}.19.{i}"] = 0
        oid_map[f"{ep_base}.20.{i}"] = random.choice([0, 1])
        oid_map[f"{ep_base}.21.{i}"] = random.randint(400, 500)
        oid_map[f"{ep_base}.22.{i}"] = random.randint(350, 480)
        oid_map[f"{ep_base}.23.{i}"] = ""
        oid_map[f"{ep_base}.24.{i}"] = random.choice([0, 1])

    return oid_map

def start_simulator(port, num_endpoints, switch_id):
    pMod = snmp_api.protoModules[snmp_api.protoVersion2c]

    def find_next_oid(sorted_oids, current_tuple):
        for oid_t, oid_s, val in sorted_oids:
            if oid_t > current_tuple:
                return oid_s, val
        return None, None

    def to_snmp_val(val):
        if isinstance(val, int):
            return pMod.Integer(val)
        if isinstance(val, str) and val.startswith("1.3.6.1"):
            return pMod.ObjectIdentifier(tuple(int(x) for x in val.split(".")))
        return pMod.OctetString(str(val))

    def handle_request(data):
        try:
            msg, _ = ber_decoder.decode(data, asn1Spec=pMod.Message())
            community = msg.getComponentByPosition(1)
            pdu = snmp_api.decodeMessageVersion(data)

            req_msg, _ = ber_decoder.decode(data, asn1Spec=pMod.Message())
            req_pdu = pMod.apiMessage.getPDU(req_msg)

            oid_map = build_oid_map(num_endpoints, switch_id)
            sorted_oids = sorted(
                [(tuple(int(x) for x in k.split(".")), k, v) for k, v in oid_map.items()],
                key=lambda x: x[0]
            )

            resp_msg = pMod.Message()
            pMod.apiMessage.setDefaults(resp_msg)
            pMod.apiMessage.setCommunity(resp_msg, community)

            resp_pdu = pMod.GetResponsePDU()
            pMod.apiPDU.setDefaults(resp_pdu)
            pMod.apiPDU.setRequestID(resp_pdu, pMod.apiPDU.getRequestID(req_pdu))

            req_var_binds = pMod.apiPDU.getVarBinds(req_pdu)
            resp_var_binds = []

            pdu_tag = req_pdu.tagSet
            is_get = (pdu_tag == pMod.GetRequestPDU.tagSet)
            is_bulk = (pdu_tag == pMod.GetBulkRequestPDU.tagSet)
            is_next = (pdu_tag == pMod.GetNextRequestPDU.tagSet)

            if is_get:
                for oid, val in req_var_binds:
                    oid_str = str(oid).lstrip(".")
                    if oid_str in oid_map:
                        resp_var_binds.append((oid, to_snmp_val(oid_map[oid_str])))
                    else:
                        resp_var_binds.append((oid, pMod.NoSuchObject()))
            elif is_next:
                for oid, val in req_var_binds:
                    current_tuple = tuple(int(x) for x in str(oid).lstrip(".").split("."))
                    ns, nv = find_next_oid(sorted_oids, current_tuple)
                    if ns:
                        resp_var_binds.append((ObjectIdentifier(tuple(int(x) for x in ns.split("."))), to_snmp_val(nv)))
                    else:
                        resp_var_binds.append((oid, pMod.EndOfMibView()))
            elif is_bulk:
                non_repeaters = pMod.apiBulkPDU.getNonRepeaters(req_pdu)
                max_repetitions = pMod.apiBulkPDU.getMaxRepetitions(req_pdu)

                for i, (oid, val) in enumerate(req_var_binds):
                    current_tuple = tuple(int(x) for x in str(oid).lstrip(".").split("."))
                    if i < non_repeaters:
                        ns, nv = find_next_oid(sorted_oids, current_tuple)
                        if ns:
                            resp_var_binds.append((ObjectIdentifier(tuple(int(x) for x in ns.split("."))), to_snmp_val(nv)))
                        else:
                            resp_var_binds.append((oid, pMod.EndOfMibView()))
                    else:
                        ct = current_tuple
                        for _ in range(max_repetitions):
                            ns, nv = find_next_oid(sorted_oids, ct)
                            if ns:
                                resp_var_binds.append((ObjectIdentifier(tuple(int(x) for x in ns.split("."))), to_snmp_val(nv)))
                                ct = tuple(int(x) for x in ns.split("."))
                            else:
                                resp_var_binds.append((oid, pMod.EndOfMibView()))
                                break

            pMod.apiPDU.setVarBinds(resp_pdu, resp_var_binds)
            pMod.apiMessage.setPDU(resp_msg, resp_pdu)

            return ber_encoder.encode(resp_msg)
        except Exception as e:
            return None

    def run_sim():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        sock.settimeout(1.0)
        logger.info(f"Simulator Switch {switch_id} running on port {port} with {num_endpoints} endpoints.")
        while True:
            try:
                data, addr = sock.recvfrom(65535)
                response = handle_request(data)
                if response:
                    sock.sendto(response, addr)
            except socket.timeout:
                continue
            except Exception as e:
                pass

    t = threading.Thread(target=run_sim, daemon=True)
    t.start()
    return t


async def main():
    # 1. Start 3 simulators on consecutive ports
    base_port = 11161
    for i in range(1, 4):
        start_simulator(base_port + i, 20, i)

    # 2. Insert into the main database
    os.environ.setdefault("DB_MODE", "sqlite")
    from app.database import AsyncSessionLocal
    from app.models.device import Device
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        for i in range(1, 4):
            dev_id = f"sim_kvm_0{i}"
            res = await db.execute(select(Device).where(Device.id == dev_id))
            if not res.scalar_one_or_none():
                db.add(Device(
                    id=dev_id,
                    name=f"Large KVM Switch {i}",
                    host="127.0.0.1",
                    port=base_port + i,
                    community="public",
                    is_active=True,
                    poll_interval=10,
                ))
        await db.commit()
    
    logger.info("3 Swithes and their 20 endpoints registered to the live DB.")
    logger.info("Keep this script running to serve UDP port data... Backend poller will collect data automatically.")
    
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
