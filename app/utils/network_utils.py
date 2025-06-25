import subprocess
import socket
import psutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def get_network_interface() -> Optional[str]:
    """
    Obtiene la interfaz de red activa (por ejemplo, 'eth0' o 'wlan0').
    Prioritiza interfaces WiFi, luego ethernet.
    """
    try:
        stats = psutil.net_if_stats()
        active_interfaces = {iface for iface, stat in stats.items() if stat.isup}
        
        # Prioridad 1: WiFi (wlan, wlp)
        for iface in active_interfaces:
            if iface.startswith(('wlan', 'wlp')):
                logger.debug(f"Interfaz WiFi activa encontrada: {iface}")
                return iface
        
        # Prioridad 2: Ethernet (eth, enp)
        for iface in active_interfaces:
            if iface.startswith(('eth', 'enp')):
                logger.debug(f"Interfaz Ethernet activa encontrada: {iface}")
                return iface

        # Fallback: cualquier otra interfaz activa que no sea loopback
        for iface in active_interfaces:
            if iface != 'lo':
                logger.debug(f"Interfaz activa (fallback) encontrada: {iface}")
                return iface
                
    except Exception as e:
        logger.error(f"Error al obtener la interfaz de red con psutil: {e}")

    # Fallback con comando 'ip route' si psutil falla
    try:
        result = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        parts = output.split()
        if 'dev' in parts:
            interface = parts[parts.index('dev') + 1]
            logger.debug(f"Interfaz de red activa detectada (comando ip): {interface}")
            return interface
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError) as e:
        logger.error(f"Error al obtener la interfaz de red con 'ip route': {e}.")
    
    logger.warning("No se pudo determinar la interfaz de red activa. Devolviendo None.")
    return None


def get_ip_address() -> str:
    """
    Obtiene la dirección IP local del dispositivo.
    """
    interface = get_network_interface()
    if not interface:
        logger.warning("No se pudo obtener la interfaz de red para buscar la IP.")
        return "127.0.0.1"
        
    try:
        addrs = psutil.net_if_addrs().get(interface, [])
        for addr in addrs:
            if addr.family == socket.AF_INET:
                logger.debug(f"Dirección IP encontrada para {interface}: {addr.address}")
                return addr.address
    except Exception as e:
        logger.error(f"Error al obtener IP con psutil para la interfaz {interface}: {e}")

    # Fallback si psutil no funciona
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        logger.debug(f"Dirección IP encontrada (fallback socket): {ip}")
        return ip
    except Exception as e:
        logger.error(f"Error al obtener la IP (fallback socket): {e}. Usando '127.0.0.1' por defecto.")
        return '127.0.0.1'


def is_wifi_connected() -> bool:
    """
    Verifica si el dispositivo está conectado a una red WiFi.
    """
    interface = get_network_interface()
    return interface is not None and interface.startswith(('wlan', 'wlp'))


def get_wifi_ssid() -> Optional[str]:
    """
    Obtiene el SSID de la red WiFi si está conectado.
    """
    interface = get_network_interface()
    if interface and is_wifi_connected():
        try:
            # Usamos el nombre de la interfaz para ser más específicos
            result = subprocess.run(['iwgetid', interface, '-r'], capture_output=True, text=True, check=True)
            ssid = result.stdout.strip()
            if ssid:
                logger.debug(f"SSID de WiFi encontrado: {ssid}")
                return ssid
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # FileNotFoundError si iwgetid no está, CalledProcessError si no está conectado
            logger.warning(f"No se pudo obtener el SSID de WiFi para {interface}: {e}")
    return None
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()
