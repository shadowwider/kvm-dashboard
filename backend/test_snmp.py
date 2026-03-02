import asyncio
from pysnmp.hlapi.asyncio import *

async def run():
    engine = SnmpEngine()
    
    # Try with string OID
    oid1 = "1.3.6.1.2.1.1.2.0"
    try:
        err_ind, err_st, err_idx, binds = await getCmd(
            engine,
            CommunityData('public', mpModel=1),
            UdpTransportTarget(('127.0.0.1', 11162), timeout=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid1))
        )
        print("Test 1 success:", binds)
    except Exception as e:
        print("Test 1 failed:", repr(e))

    # Try with tuple OID
    oid2 = tuple(int(x) for x in oid1.split('.'))
    try:
        err_ind, err_st, err_idx, binds = await getCmd(
            engine,
            CommunityData('public', mpModel=1),
            UdpTransportTarget(('127.0.0.1', 11162), timeout=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid2))
        )
        print("Test 2 success:", binds)
    except Exception as e:
        print("Test 2 failed:", repr(e))
        
    # Try with unpacked tuple OID
    try:
        err_ind, err_st, err_idx, binds = await getCmd(
            engine,
            CommunityData('public', mpModel=1),
            UdpTransportTarget(('127.0.0.1', 11162), timeout=2),
            ContextData(),
            ObjectType(ObjectIdentity(*oid2))
        )
        print("Test 3 success:", binds)
    except Exception as e:
        print("Test 3 failed:", repr(e))

asyncio.run(run())
