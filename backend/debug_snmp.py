import asyncio
from pysnmp.hlapi.asyncio import *

async def test_snmp():
    host = "127.0.0.1"
    port = 1161
    community = "public"
    oid = "1.3.6.1.2.1.1.2.0"
    
    print(f"[*] 正在尝试连接 {host}:{port} ...")
    
    engine = SnmpEngine()
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            CommunityData(community, mpModel=1),
            UdpTransportTarget((host, port), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        
        if error_indication:
            print(f"[!] 错误指示 (ErrorIndication): {error_indication}")
        elif error_status:
            print(f"[!] 错误状态 (ErrorStatus): {error_status.prettyPrint()} at {error_index}")
        else:
            for var_bind in var_binds:
                print(f"[+] 成功! 响应: {' = '.join([x.prettyPrint() for x in var_bind])}")
                
    except Exception as e:
        print(f"[!!] 发生异常: {e}")
    finally:
        engine.transportDispatcher.closeDispatcher()

if __name__ == "__main__":
    asyncio.run(test_snmp())
