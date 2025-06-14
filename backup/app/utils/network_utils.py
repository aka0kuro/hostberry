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
    except Exception:
        return "No disponible"

def is_wifi_connected(interface: str = None) -> bool:
    """Verifica si hay conexión WiFi activa"""
    try:
        if not interface:
            interface = get_network_interface()
            
        result = subprocess.run(
            ["iwconfig", interface],
            capture_output=True,
            text=True
        )
        return "ESSID:off/any" not in result.stdout
    except Exception:
        return False

def get_cpu_temp() -> float:
    """Obtiene la temperatura del CPU en grados Celsius"""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = int(f.read().strip()) / 1000.0
        return temp
    except Exception:
        return 0.0

def run_command(cmd: str) -> Tuple[bool, str]:
    """Ejecuta un comando y devuelve (éxito, salida)"""
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
