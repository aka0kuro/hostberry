import subprocess
import re
import socket
import psutil
from typing import Optional, Dict, List, Tuple

def get_network_interface() -> Optional[str]:
    """Obtiene la interfaz de red activa"""
    try:
        gateways = psutil.net_if_addrs()
        for interface, addrs in gateways.items():
            if interface != 'lo' and 'wlan' in interface:
                return interface
        return next(iter(gateways.keys()), None)
    except Exception:
        return 'wlan0'

def get_ip_address(interface: str = None) -> str:
    """Obtiene la dirección IP de una interfaz específica"""
    try:
        if not interface:
            interface = get_network_interface()
            
        addrs = psutil.net_if_addrs().get(interface, [])
        for addr in addrs:
            if addr.family == socket.AF_INET:
                return addr.address
        return "No disponible"
    except Exception:
        return "Error al obtener IP"

def get_wifi_ssid(interface: str = None) -> str:
    """Obtiene el SSID de la red WiFi actual"""
    try:
        if not interface:
            interface = get_network_interface()
            
        result = subprocess.run(
            ["iwgetid", "-r", interface],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() or "No conectado"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        logger.debug(f"Dirección IP encontrada (fallback): {ip}")
        return ip
    except Exception as e:
        logger.error(f"Error al obtener la IP (fallback): {e}. Usando '127.0.0.1' por defecto.")
        return '127.0.0.1'

def is_wifi_connected():
    """
    Verifica si el dispositivo está conectado a una red WiFi.
    """
    interface = get_network_interface()
    return interface.startswith('wlan')

def get_wifi_ssid():
    """
    Obtiene el SSID de la red WiFi si está conectado.
    """
    if is_wifi_connected():
        try:
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, check=True)
            ssid = result.stdout.strip()
            logger.debug(f"SSID de WiFi encontrado: {ssid}")
            return ssid
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"Error al obtener el SSID de WiFi: {e}")
    return None

def get_cpu_temp():
    """
    Obtiene la temperatura del CPU en grados Celsius.
    """
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = int(f.read().strip()) / 1000.0
        return temp
    except Exception:
        return 0.0

def run_command(cmd: str) -> tuple:
    """
    Ejecuta un comando y devuelve (éxito, salida).
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()
