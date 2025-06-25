import subprocess
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

def get_wifi_networks() -> List[Dict[str, str]]:
    """
    Escanea y devuelve las redes WiFi disponibles
    """
    try:
        # Usar nmcli para escanear redes WiFi
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'],
            capture_output=True, text=True, check=True
        )
        
        networks = []
        for line in result.stdout.splitlines():
            parts = line.split(':')
            if len(parts) >= 3:
                ssid = parts[0]
                signal = parts[1]
                security = parts[2] if len(parts) > 2 else '--'
                
                networks.append({
                    'ssid': ssid,
                    'signal': f"{signal}%",
                    'security': security
                })
        
        return networks
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al escanear redes WiFi: {e}")
        return []
    except Exception as e:
        logger.error(f"Error inesperado al escanear redes WiFi: {e}")
        return []

def connect_to_wifi(ssid: str, password: str) -> Tuple[bool, str]:
    """
    Intenta conectarse a una red WiFi
    """
    try:
        # Eliminar conexión existente si existe
        subprocess.run(
            ['nmcli', 'connection', 'delete', ssid],
            capture_output=True, text=True
        )
        
        # Intentar conectar a la red
        result = subprocess.run(
            ['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            return True, "Conexión exitosa"
        else:
            return False, result.stderr or "Error desconocido al conectar"
            
    except Exception as e:
        return False, str(e)

def get_network_interfaces() -> List[Dict[str, str]]:
    """
    Obtiene la lista de interfaces de red disponibles
    """
    try:
        import psutil
        interfaces = []
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == psutil.AF_LINK:  # Dirección MAC
                    mac = addr.address
                    break
            else:
                mac = "No disponible"
                
            interfaces.append({
                'name': name,
                'mac': mac,
                'ip': next((addr.address for addr in addrs if addr.family == 2), "No asignada"),
                'netmask': next((addr.netmask for addr in addrs if addr.family == 2), "")
            })
        return interfaces
    except Exception as e:
        logger.error(f"Error al obtener interfaces de red: {e}")
        return []
