"""
Utilidades del sistema optimizadas para Raspberry Pi 3
"""

import os
import subprocess
from core import system_light as psutil
import time
from typing import Dict, Any, List, Optional
import logging

from config.settings import settings
from core.i18n import get_text

logger = logging.getLogger(__name__)

class RPISystemMonitor:
    """Monitor del sistema optimizado para Raspberry Pi 3"""
    
    def __init__(self):
        self.last_stats = {}
        self.stats_history = []
        self.max_history = settings.stats_history_size
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del sistema optimizadas para RPi 3"""
        try:
            # Información básica del sistema
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Temperatura (específico para RPi)
            temperature = self._get_temperature()
            
            # Información de red
            network_stats = self._get_network_stats()
            
            # Información de procesos
            process_count = len(psutil.pids())
            
            stats = {
                'cpu': {
                    'percent': cpu_percent,
                    'count': psutil.cpu_count(),
                    'frequency': self._get_cpu_frequency()
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'percent': memory.percent
                },
                'disk': {
                    'total': disk.total,
                    'free': disk.free,
                    'used': disk.used,
                    'percent': disk.percent
                },
                'temperature': temperature,
                'network': network_stats,
                'processes': process_count,
                'uptime': time.time() - psutil.boot_time(),
                'timestamp': time.time()
            }
            
            # Guardar en historial
            self._update_history(stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo estadísticas del sistema: {e}")
            return {}
    
    def _get_temperature(self) -> Optional[float]:
        """Obtener temperatura del RPi"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000
                return temp
        except:
            return None
    
    def _get_cpu_frequency(self) -> Optional[float]:
        """Obtener frecuencia de CPU"""
        try:
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq', 'r') as f:
                freq = float(f.read()) / 1000  # Convertir a MHz
                return freq
        except:
            return None
    
    def _get_network_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de red"""
        try:
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
        except:
            return {}
    
    def _update_history(self, stats: Dict[str, Any]):
        """Actualizar historial de estadísticas"""
        self.stats_history.append(stats)
        
        # Mantener solo el tamaño máximo
        if len(self.stats_history) > self.max_history:
            self.stats_history.pop(0)
    
    def get_network_interface(self, interface: str = "wlan0") -> Dict[str, Any]:
        """Obtener información de interfaz de red"""
        try:
            # Obtener información de la interfaz
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            
            if interface not in addrs:
                return {}
            
            addr_info = addrs[interface]
            stat_info = stats.get(interface, {})
            
            # Obtener dirección IP
            ip_address = None
            for addr in addr_info:
                if addr.family == psutil.AF_INET:  # IPv4
                    ip_address = addr.address
                    break
            
            return {
                'interface': interface,
                'ip_address': ip_address,
                'is_up': stat_info.get('isup', False),
                'speed': stat_info.get('speed', 0),
                'mtu': stat_info.get('mtu', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo información de red: {e}")
            return {}
    
    def get_ip_address(self, interface: str = "wlan0") -> Optional[str]:
        """Obtener dirección IP de una interfaz"""
        try:
            addrs = psutil.net_if_addrs()
            if interface in addrs:
                for addr in addrs[interface]:
                    if addr.family == psutil.AF_INET:  # IPv4
                        return addr.address
            return None
        except Exception as e:
            logger.error(f"❌ Error obteniendo IP: {e}")
            return None
    
    def get_cpu_temp(self) -> Optional[float]:
        """Obtener temperatura de CPU"""
        return self._get_temperature()
    
    def check_system_health(self) -> Dict[str, Any]:
        """Verificar salud del sistema"""
        try:
            stats = self.get_system_stats()
            
            warnings = []
            critical = []
            
            # Verificar CPU
            if stats.get('cpu', {}).get('percent', 0) > settings.cpu_throttle_threshold * 100:
                warnings.append(get_text("system.cpu_high", default=f"CPU usage high: {stats['cpu']['percent']}%", percent=stats['cpu']['percent']))
            
            # Verificar memoria
            if stats.get('memory', {}).get('percent', 0) > settings.memory_threshold * 100:
                warnings.append(get_text("system.memory_high", default=f"Memory usage high: {stats['memory']['percent']}%", percent=stats['memory']['percent']))
            
            # Verificar temperatura
            temp = stats.get('temperature')
            if temp and temp > settings.temp_threshold:
                critical.append(get_text("system.temp_critical", default=f"Temperature critical: {temp}°C", temp=temp))
            
            # Verificar disco
            if stats.get('disk', {}).get('percent', 0) > 90:
                warnings.append(get_text("system.disk_high", default=f"Disk usage high: {stats['disk']['percent']}%", percent=stats['disk']['percent']))
            
            return {
                'status': 'critical' if critical else 'warning' if warnings else 'healthy',
                'warnings': warnings,
                'critical': critical,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"❌ Error verificando salud del sistema: {e}")
            return {'status': 'error', 'message': str(e)}

# Instancia global del monitor
system_monitor = RPISystemMonitor()

def get_system_stats() -> Dict[str, Any]:
    """Obtener estadísticas del sistema"""
    return system_monitor.get_system_stats()

def get_network_interface(interface: str = "wlan0") -> Dict[str, Any]:
    """Obtener información de interfaz de red"""
    return system_monitor.get_network_interface(interface)

def get_ip_address(interface: str = "wlan0") -> Optional[str]:
    """Obtener dirección IP"""
    return system_monitor.get_ip_address(interface)

def get_cpu_temp() -> Optional[float]:
    """Obtener temperatura de CPU"""
    return system_monitor.get_cpu_temp()

def check_system_health() -> Dict[str, Any]:
    """Verificar salud del sistema"""
    return system_monitor.check_system_health()

def optimize_system_for_rpi():
    """Aplicar optimizaciones específicas para RPi 3"""
    try:
        # Verificar si estamos en un RPi
        if os.path.exists('/proc/device-tree/model'):
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().strip()
                if 'Raspberry Pi' in model:
                    logger.info(f"🖥️ Detectado: {model}")
                    
                    # Aplicar optimizaciones
                    _apply_rpi_optimizations()
                    
    except Exception as e:
        logger.error(f"❌ Error aplicando optimizaciones RPi: {e}")

def _apply_rpi_optimizations():
    """Aplicar optimizaciones específicas para RPi"""
    try:
        # Configurar governor de CPU para ahorrar energía
        governors = ['powersave', 'conservative', 'ondemand']
        for governor in governors:
            try:
                subprocess.run([
                    'sudo', 'sh', '-c', 
                    f'echo {governor} > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'
                ], check=True)
                logger.info(f"⚡ CPU governor configurado: {governor}")
                break
            except:
                continue
        
        # Deshabilitar servicios innecesarios
        unnecessary_services = [
            'bluetooth',
            'avahi-daemon',
            'triggerhappy'
        ]
        
        for service in unnecessary_services:
            try:
                subprocess.run(['sudo', 'systemctl', 'disable', service], check=False)
                subprocess.run(['sudo', 'systemctl', 'stop', service], check=False)
                logger.info(f"🛑 Servicio deshabilitado: {service}")
            except:
                pass
        
        # Configurar swap si es necesario
        memory_gb = psutil.virtual_memory().total / (1024**3)
        if memory_gb < 1.0:  # Menos de 1GB
            try:
                # Crear archivo de swap
                subprocess.run([
                    'sudo', 'fallocate', '-l', '512M', '/swapfile'
                ], check=True)
                subprocess.run(['sudo', 'chmod', '600', '/swapfile'], check=True)
                subprocess.run(['sudo', 'mkswap', '/swapfile'], check=True)
                subprocess.run(['sudo', 'swapon', '/swapfile'], check=True)
                logger.info("💾 Archivo de swap creado")
            except:
                pass
        
        logger.info("✅ Optimizaciones RPi aplicadas")
        
    except Exception as e:
        logger.error(f"❌ Error aplicando optimizaciones: {e}")

def get_wifi_networks() -> List[Dict[str, Any]]:
    """Obtener redes WiFi disponibles"""
    try:
        result = subprocess.run([
            'sudo', 'iwlist', 'wlan0', 'scan'
        ], capture_output=True, text=True, timeout=10)
        
        networks = []
        current_network = {}
        
        for line in result.stdout.split('\n'):
            if 'ESSID:' in line:
                if current_network:
                    networks.append(current_network)
                current_network = {'ssid': line.split('"')[1] if '"' in line else ''}
            elif 'Quality=' in line and current_network:
                # Extraer calidad de señal
                quality_part = line.split('Quality=')[1].split()[0]
                current_network['quality'] = quality_part
            elif 'Encryption key:' in line and current_network:
                current_network['encrypted'] = 'on' in line
        
        if current_network:
            networks.append(current_network)
        
        return networks
        
    except Exception as e:
        logger.error(f"❌ Error escaneando redes WiFi: {e}")
        return []

def get_service_status(service_name: str) -> Dict[str, Any]:
    """Obtener estado de un servicio"""
    try:
        result = subprocess.run([
            'systemctl', 'is-active', service_name
        ], capture_output=True, text=True, timeout=5)
        
        is_active = result.stdout.strip() == 'active'
        
        # Obtener información adicional
        status_result = subprocess.run([
            'systemctl', 'show', service_name, '--property=LoadState,ActiveState,SubState'
        ], capture_output=True, text=True, timeout=5)
        
        return {
            'service': service_name,
            'active': is_active,
            'status': result.stdout.strip(),
            'details': status_result.stdout.strip()
        }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estado de servicio {service_name}: {e}")
        return {
            'service': service_name,
            'active': False,
            'status': 'unknown',
            'error': str(e)
        }
