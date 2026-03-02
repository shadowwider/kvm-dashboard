import asyncio
from pysnmp.hlapi.asyncio import *

async def run():
    engine = SnmpEngine()
    
    # Try with ObjectType(ObjectIdentity((1,3,6,1,2,1,1,2,0)))
    try:
        err_ind, err_st, err_idx, binds = await getCmd(
            engine,
            CommunityData('public', mpModel=1),
            UdpTransportTarget(('127.0.0.1', 11162), timeout=2),
            ContextData(),
            ObjectType(ObjectIdentity((1,3,6,1,2,1,1,2,0)))
        )
        print("Tuple success:", binds)
    except Exception as e:
        print("Tuple failed:", repr(e))

asyncio.run(run())
