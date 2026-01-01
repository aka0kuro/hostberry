#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Utilidades de sistema ligeras para RPi 3
Reemplaza psutil con acceso directo a /proc y os
"""

import os
import time
import asyncio
from typing import Dict, Any, Optional, List
import socket
import subprocess

# Constantes de compatibilidad
AF_INET = socket.AF_INET

class SystemInfo:
    """Clase ligera para obtener información del sistema sin psutil"""
    
    def __init__(self):
        self._cache = {}
        self._cache_time = 0
        self._cache_duration = 30  # Cache por 30 segundos
    
    def _read_file(self, filepath: str) -> str:
        """Leer archivo de forma segura"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError):
            return ""
    
    def get_hostname(self) -> str:
        """Obtener hostname del sistema"""
        try:
            return os.uname().nodename
        except:
            return self._read_file("/proc/sys/kernel/hostname") or "unknown"
    
    def get_platform(self) -> str:
        """Obtener plataforma del sistema"""
        try:
            return os.uname().sysname
        except:
            return "linux"
    
    def get_cpu_count(self) -> int:
        """Obtener número de CPUs"""
        try:
            # Contar líneas en /proc/cpuinfo
            cpuinfo = self._read_file("/proc/cpuinfo")
            return cpuinfo.count("processor") if cpuinfo else 1
        except:
            return 1
    
    def get_memory_total(self) -> int:
        """Obtener memoria total en bytes"""
        try:
            meminfo = self._read_file("/proc/meminfo")
            for line in meminfo.split('\n'):
                if line.startswith("MemTotal:"):
                    # Formato: MemTotal:         1234567 kB
                    kb = int(line.split()[1])
                    return kb * 1024  # Convertir a bytes
            return 0
        except:
            return 0
    
    def get_memory_available(self) -> int:
        """Obtener memoria disponible en bytes"""
        try:
            meminfo = self._read_file("/proc/meminfo")
            for line in meminfo.split('\n'):
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    return kb * 1024
            return 0
        except:
            return 0
    
    def get_memory_usage_percent(self) -> float:
        """Calcular porcentaje de uso de memoria"""
        total = self.get_memory_total()
        available = self.get_memory_available()
        if total == 0:
            return 0.0
        used = total - available
        return (used / total) * 100
    
    def get_disk_usage(self, path: str = "/") -> Dict[str, Any]:
        """Obtener uso de disco"""
        try:
            stat = os.statvfs(path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            
            return {
                "total": total,
                "free": free,
                "used": used,
                "percent": (used / total) * 100 if total > 0 else 0
            }
        except:
            return {"total": 0, "free": 0, "used": 0, "percent": 0}
    
    def get_cpu_usage_percent(self) -> float:
        """Obtener porcentaje de uso de CPU"""
        try:
            # Leer tiempo de CPU de /proc/stat
            stat = self._read_file("/proc/stat")
            if stat.startswith("cpu "):
                times = list(map(int, stat.split()[1:5]))
                idle = times[3]
                total = sum(times)
                if total == 0:
                    return 0.0
                
                # Esperar un momento y volver a medir
                time.sleep(0.1)
                new_stat = self._read_file("/proc/stat")
                if new_stat.startswith("cpu "):
                    new_times = list(map(int, new_stat.split()[1:5]))
                    new_idle = new_times[3]
                    new_total = sum(new_times)
                    
                    idle_diff = new_idle - idle
                    total_diff = new_total - total
                    
                    if total_diff == 0:
                        return 0.0
                    
                    usage = 100.0 * (1.0 - idle_diff / total_diff)
                    return min(100.0, max(0.0, usage))
            
            return 0.0
        except:
            return 0.0
    
    def get_system_info(self, use_cache: bool = True) -> Dict[str, Any]:
        """Obtener información completa del sistema"""
        current_time = time.time()
        
        # Usar cache si está disponible y es reciente
        if use_cache and hasattr(self, '_cache') and (current_time - self._cache_time) < self._cache_duration:
            info = self._cache.copy()
            # Actualizar solo datos dinámicos
            info["memory_usage_percent"] = self.get_memory_usage_percent()
            info["cpu_usage_percent"] = self.get_cpu_usage_percent()
            disk_info = self.get_disk_usage()
            info["disk_usage_percent"] = disk_info["percent"]
            return info
        
        # Generar información completa
        info = {
            "hostname": self.get_hostname(),
            "platform": self.get_platform(),
            "cpu_count": self.get_cpu_count(),
            "memory_total": self.get_memory_total(),
            "memory_available": self.get_memory_available(),
            "memory_usage_percent": self.get_memory_usage_percent(),
            "cpu_usage_percent": self.get_cpu_usage_percent(),
        }
        
        # Agregar información de disco
        disk_info = self.get_disk_usage()
        info.update(disk_info)
        
        # Actualizar cache
        self._cache = info.copy()
        self._cache_time = current_time
        
        return info
    
    def get_boot_time(self) -> float:
        """Obtener tiempo de arranque del sistema"""
        try:
            stat_content = self._read_file("/proc/stat")
            for line in stat_content.split('\n'):
                if line.startswith('btime'):
                    return float(line.split()[1])
            return 0.0
        except:
            return 0.0

    def get_process_count(self) -> int:
        """Obtener número de procesos corriendo"""
        try:
            # Contar directorios numéricos en /proc
            return len([name for name in os.listdir('/proc') if name.isdigit()])
        except:
            return 0

    def get_network_io_counters(self) -> Dict[str, int]:
        """Obtener contadores de E/S de red (bytes sent/recv, packets sent/recv)"""
        try:
            content = self._read_file("/proc/net/dev")
            bytes_sent = 0
            bytes_recv = 0
            packets_sent = 0
            packets_recv = 0
            
            lines = content.split('\n')[2:] # Saltar headers
            for line in lines:
                if ':' in line:
                    parts = line.split(':')[1].split()
                    # recv: bytes(0), packets(1)
                    # sent: bytes(8), packets(9)
                    if len(parts) >= 16:
                        bytes_recv += int(parts[0])
                        packets_recv += int(parts[1])
                        bytes_sent += int(parts[8])
                        packets_sent += int(parts[9])
            
            return {
                'bytes_sent': bytes_sent,
                'bytes_recv': bytes_recv,
                'packets_sent': packets_sent,
                'packets_recv': packets_recv
            }
        except:
            return {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0}

    def get_load_average(self) -> List[float]:
        """Obtener promedio de carga (1, 5, 15 min)"""
        try:
            return list(os.getloadavg())
        except:
            return [0.0, 0.0, 0.0]

    def get_net_if_addrs(self) -> Dict[str, List[Any]]:
        """Obtener direcciones de interfaces de red (compatible con psutil)"""
        interfaces = {}
        try:
            # Usar ip addr para obtener direcciones
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
            if result.returncode != 0:
                return {}

            class snicaddr:
                def __init__(self, family, address, netmask, broadcast, ptp):
                    self.family = family
                    self.address = address
                    self.netmask = netmask
                    self.broadcast = broadcast
                    self.ptp = ptp

            import socket
            current_iface = None
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Nueva interfaz: "1: lo: ..."
                if line[0].isdigit() and ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_iface = parts[1].strip()
                        if current_iface not in interfaces:
                            interfaces[current_iface] = []
                
                # IPv4: "inet 127.0.0.1/8 scope host lo"
                elif line.startswith('inet ') and current_iface:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip_part = parts[1]
                        address = ip_part.split('/')[0]
                        # Calculo simple de netmask si es necesario, por ahora None o dummy
                        # psutil devuelve netmask real, aquí simplificamos
                        netmask = None 
                        broadcast = None
                        
                        # Buscar broadcast
                        for i, p in enumerate(parts):
                            if p == 'brd' and i + 1 < len(parts):
                                broadcast = parts[i+1]
                        
                        interfaces[current_iface].append(
                            snicaddr(socket.AF_INET, address, netmask, broadcast, None)
                        )
                
                # IPv6: "inet6 ::1/128 scope host"
                elif line.startswith('inet6 ') and current_iface:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip_part = parts[1]
                        address = ip_part.split('/')[0]
                        interfaces[current_iface].append(
                            snicaddr(socket.AF_INET6, address, None, None, None)
                        )
                        
        except Exception:
            pass
        return interfaces

    def get_net_if_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de interfaces de red (isup, speed, mtu)"""
        stats = {}
        try:
            for iface in os.listdir('/sys/class/net'):
                try:
                    operstate = self._read_file(f"/sys/class/net/{iface}/operstate")
                    isup = operstate == 'up'
                    
                    speed_str = self._read_file(f"/sys/class/net/{iface}/speed")
                    speed = int(speed_str) if speed_str.isdigit() else 0
                    
                    mtu_str = self._read_file(f"/sys/class/net/{iface}/mtu")
                    mtu = int(mtu_str) if mtu_str.isdigit() else 1500
                    
                    class NICStats:
                        def __init__(self, isup, speed, mtu):
                            self.isup = isup
                            self.speed = speed
                            self.mtu = mtu
                            
                    stats[iface] = NICStats(isup, speed, mtu)
                except:
                    continue
        except:
            pass
        return stats

    async def get_system_info_async(self) -> Dict[str, Any]:
        """Versión asíncrona para compatibilidad"""
        return self.get_system_info()

# Instancia global
system_info = SystemInfo()

# Funciones de compatibilidad para reemplazar psutil
def cpu_count() -> int:
    return system_info.get_cpu_count()

def virtual_memory() -> Any:
    """Objeto compatible con psutil.virtual_memory()"""
    class MemoryInfo:
        def __init__(self):
            self.total = system_info.get_memory_total()
            self.available = system_info.get_memory_available()
            self.percent = system_info.get_memory_usage_percent()
            self.used = self.total - self.available
    
    return MemoryInfo()

def disk_usage(path: str = "/") -> Any:
    """Objeto compatible con psutil.disk_usage()"""
    class DiskInfo:
        def __init__(self, data):
            self.total = data["total"]
            self.free = data["free"]
            self.used = data["used"]
            self.percent = data["percent"]
    
    return DiskInfo(system_info.get_disk_usage(path))

def cpu_percent(interval=None) -> float:
    # Ignoramos interval ya que nuestro método lee instantánea o diff simple
    return system_info.get_cpu_usage_percent()

def boot_time() -> float:
    return system_info.get_boot_time()

def pids() -> List[int]:
    # Retornamos solo lista de PIDs, get_process_count es más eficiente si solo se necesita el número
    try:
        return [int(name) for name in os.listdir('/proc') if name.isdigit()]
    except:
        return []

def net_io_counters() -> Any:
    """Objeto compatible con psutil.net_io_counters()"""
    data = system_info.get_network_io_counters()
    class NetIO:
        def __init__(self, d):
            self.bytes_sent = d['bytes_sent']
            self.bytes_recv = d['bytes_recv']
            self.packets_sent = d['packets_sent']
            self.packets_recv = d['packets_recv']
            self.errin = 0
            self.errout = 0
            self.dropin = 0
            self.dropout = 0
    return NetIO(data)

def net_if_addrs():
    return system_info.get_net_if_addrs()

def net_if_stats():
    return system_info.get_net_if_stats()

# Clase OS para compatibilidad
class OS:
    @staticmethod
    def uname():
        class UnameInfo:
            def __init__(self):
                self.nodename = system_info.get_hostname()
                self.sysname = system_info.get_platform()
        
        return UnameInfo()
    
    @staticmethod
    def getloadavg():
        return system_info.get_load_average()

os_info = OS()
# Alias para compatibilidad con llamadas tipo psutil.os.uname()
os = os_info
