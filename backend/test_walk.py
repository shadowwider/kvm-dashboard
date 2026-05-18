import asyncio
from pysnmp.hlapi.asyncio import *

async def run():
    snmpEngine = SnmpEngine()
    # SIM-1 CON Table base
    target = UdpTransportTarget(('127.0.0.1', 11162))
    auth = CommunityData('public', mpModel=1)
    
    # CON ID column
    base_oid = '1.3.6.1.4.1.32828.3.257.16.1.1.2.3.1000.1.2'
    
    print(f"Walking {base_oid} on 11162...")
    count = 0
    next_oid = ObjectType(ObjectIdentity(base_oid))
    
    while True:
        errorIndication, errorStatus, errorIndex, varBindTable = await bulkCmd(
            snmpEngine, auth, target, ContextData(), 0, 10, next_oid
        )
        if errorIndication or errorStatus:
            print(f"Error: {errorIndication or errorStatus}")
            break
        
        stop = False
        for varBinds in varBindTable:
            for oid, val in varBinds:
                if not str(oid).startswith(base_oid):
                    stop = True
                    break
                print(f"{oid} = {val}")
                count += 1
                next_oid = ObjectType(ObjectIdentity(oid))
            if stop: break
        if stop: break
        if not varBindTable: break

    print(f"Total rows found: {count}")

asyncio.run(run())
