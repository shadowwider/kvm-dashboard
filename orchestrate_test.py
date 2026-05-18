import subprocess
import time
import os

# 启动模拟器
print("[*] 正在启动模拟器...")
sim_proc = subprocess.Popen(["python", "help/sim_pro.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

time.sleep(3) # 等待启动

# 运行调试脚本
print("[*] 正在运行诊断脚本...")
debug_proc = subprocess.run(["python", "backend/debug_snmp.py"], capture_output=True, text=True)
print(debug_proc.stdout)
print(debug_proc.stderr)

# 打印模拟器输出
print("[*] 模拟器输出:")
try:
    stdout, _ = sim_proc.communicate(timeout=2)
    print(stdout)
except subprocess.TimeoutExpired:
    sim_proc.kill()
    stdout, _ = sim_proc.communicate()
    print(stdout)
