import os
import sys
import time
import json

# Add project root to path
sys.path.append(os.getcwd())

try:
    from core import system_light as psutil
    from system.system_utils import get_system_stats, get_network_interface
    
    print("--- Diagnostic Info ---")
    print(f"Current User: {os.getlogin() if hasattr(os, 'getlogin') else os.getenv('USER')}")
    print(f"Python Version: {sys.version}")
    
    print("\n--- System Light (psutil replacement) ---")
    print(f"CPU Count: {psutil.cpu_count()}")
    print(f"CPU Percent (instant): {psutil.cpu_percent()}")
    mem = psutil.virtual_memory()
    print(f"Memory: Total={mem.total}, Available={mem.available}, Percent={mem.percent}%")
    disk = psutil.disk_usage('/')
    print(f"Disk: Total={disk.total}, Used={disk.used}, Percent={disk.percent}%")
    print(f"Boot Time: {psutil.boot_time()}")
    print(f"Uptime: {time.time() - psutil.boot_time()} seconds")
    
    print("\n--- System Utils ---")
    stats = get_system_stats()
    print(f"Stats Keys: {list(stats.keys())}")
    print(f"CPU Percent from Utils: {stats.get('cpu', {}).get('percent')}%")
    
    print("\n--- Network ---")
    net = get_network_interface()
    print(f"Active Interface Info: {net}")
    
    import socket
    print(f"Hostname: {socket.gethostname()}")
    
except Exception as e:
    print(f"\n❌ Error during diagnostic: {str(e)}")
    import traceback
    traceback.print_exc()
