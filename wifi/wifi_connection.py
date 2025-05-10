import subprocess
import time
import logging
from functools import lru_cache
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class WiFiConnection:
    def __init__(self):
        self.interface = 'wlan0'
        self._last_scan = None
        self._networks_cache = {}

    def get_ssid(self):
        """Obtiene el SSID actual usando iwgetid."""
        try:
            result = subprocess.run(['iwgetid', self.interface, '--raw'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                ssid = result.stdout.strip()
                return ssid if ssid else None
            return None
        except Exception as e:
            logger.error(f"Error al obtener SSID: {e}")
            return None

    def is_connected(self):
        """Verifica si la interfaz está conectada a una red WiFi."""
        try:
            # Verifica si hay un SSID activo
            ssid = self.get_ssid()
            if not ssid:
                return False
            # Verifica si la interfaz está UP
            result = subprocess.run(['cat', f'/sys/class/net/{self.interface}/operstate'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and 'up' in result.stdout.lower():
                return True
            return False
        except Exception as e:
            logger.error(f"Error al verificar conexión WiFi: {e}")
            return False

    def __init__(self):
        self.interface = 'wlan0'
        self._last_scan = None
        self._networks_cache = {}
        
    def exponential_backoff(self, attempt: int, base: float = 1.0, max_delay: float = 30.0) -> float:
        """Implementa un algoritmo de backoff exponencial"""
        delay = base * (2 ** attempt)
        return min(delay, max_delay)
        
    def check_connection_quality(self) -> dict:
        """Verifica la calidad de la conexión WiFi actual"""
        try:
            result = subprocess.run(
                ['iwconfig', self.interface],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                stats = {}
                for line in result.stdout.splitlines():
                    if 'Link Quality' in line:
                        stats['quality'] = line.split('=')[1].split('/')[0]
                    if 'Signal level' in line:
                        stats['signal'] = line.split('=')[1].split(' ')[0]
                return stats
        except Exception as e:
            logger.error(f"Error al verificar calidad de conexión: {e}")
        return {'quality': 'unknown', 'signal': 'unknown'}
        
    def scan_networks(self) -> list:
        """Escanea redes WiFi disponibles con caché"""
        if self._last_scan and (datetime.now() - self._last_scan).total_seconds() < 30:
            return self._networks_cache
            
        try:
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY,BSSID', 'device', 'wifi', 'list'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                raise Exception(result.stderr or 'Failed to scan networks')
                
            networks = []
            for line in result.stdout.splitlines():
                if line and line.count(':') >= 3:
                    parts = line.split(':')
                    networks.append({
                        'ssid': parts[0] if parts[0] else 'Hidden Network',
                        'signal': f'{min(100, int(parts[1]))}%',
                        'security': parts[2] if parts[2] else 'Open',
                        'bssid': parts[3]
                    })
                    
            self._networks_cache = networks
            self._last_scan = datetime.now()
            return networks
        except Exception as e:
            logger.error(f"Error al escanear redes: {e}")
            return []
            
    def connect(self, ssid: str, password: str = None, security: str = None) -> bool:
        """Conecta a una red WiFi con reintentos"""
        # Validación de parámetros
        if not ssid or len(ssid) > 32 or not all(ord(c) > 31 and ord(c) < 127 for c in ssid):
            logger.error(f"SSID inválido: {ssid}")
            return False
        if password and (len(password) < 8 or len(password) > 63):
            logger.error("Contraseña WiFi inválida")
            return False
        try:
            for attempt in range(3):
                try:
                    # Asegurarse de que la interfaz WiFi esté habilitada
                    subprocess.run(['nmcli', 'radio', 'wifi', 'on'], 
                                 capture_output=True, check=False, timeout=5)
                    time.sleep(1)
                    
                    # Asegurarse de que la interfaz esté lista 
                    subprocess.run(['ifconfig', self.interface, 'up'], 
                                 capture_output=True, check=False, timeout=5)
                    time.sleep(1)
                    
                    # Desconectar de cualquier red actual
                    disconnect_result = subprocess.run(
                        ['nmcli', 'device', 'disconnect', self.interface], 
                        capture_output=True, text=True, timeout=10, check=False
                    )
                    time.sleep(2)
                    
                    # Eliminar cualquier conexión previa guardada para el SSID
                    try:
                        del_result = subprocess.run(
                            ['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
                            capture_output=True, text=True, timeout=10, check=False
                        )
                        for line in del_result.stdout.splitlines():
                            if line.startswith(f"{ssid}:") and ":wifi" in line:
                                subprocess.run(['nmcli', 'connection', 'delete', ssid], capture_output=True, text=True, timeout=5, check=False)
                    except Exception as del_exc:
                        logger.warning(f"No se pudo eliminar conexión previa para {ssid}: {del_exc}")
                        
                    # Preparar el comando de conexión
                    command = ['nmcli', 'device', 'wifi', 'connect', ssid, 'ifname', self.interface]
                    if password:
                        command.extend(['password', password])
                    # Ajustar el tipo de seguridad si es necesario
                    if security:
                        sec = security.lower()
                        if 'wep' in sec:
                            command.extend(['wep-key-type', 'key'])
                        elif 'wpa' in sec:
                            # WPA/WPA2/WPA3 suelen funcionar sin especificar, pero forzamos key-mgmt por robustez
                            command.extend(['--', 'wifi-sec.key-mgmt', 'wpa-psk'])
                    logger.info(f"Comando nmcli ejecutado: {' '.join(command)}")
                        
                    # Ejecutar con tiempo de espera extendido
                    result = subprocess.run(
                        command, 
                        capture_output=True, 
                        text=True, 
                        timeout=60
                    )
                    
                    if result.returncode == 0:
                        # Verificar calidad de la conexión
                        quality = self.check_connection_quality()
                        logger.info(f"Conexión exitosa a {ssid}. Calidad: {quality}")
                        return True
                        
                    timeout = self.exponential_backoff(attempt)
                    time.sleep(timeout)
                    
                except subprocess.TimeoutExpired:
                    continue
                
            return False
            
        except Exception as e:
            logger.error(f"Error al conectar a WiFi {ssid}: {e}")
            return False
            
    def disconnect(self) -> bool:
        """Desconecta de la red WiFi actual"""
        try:
            result = subprocess.run(
                ['nmcli', 'device', 'disconnect', self.interface],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error al desconectar: {e}")
            return False

wifi_connection = WiFiConnection()
