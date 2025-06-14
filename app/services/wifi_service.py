import subprocess
import logging
import os
import time
import re
from typing import Dict, List, Optional, Tuple

class WiFiService:
    """
    Servicio para manejar operaciones relacionadas con WiFi
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.wpa_supplicant_conf = "/etc/wpa_supplicant/wpa_supplicant.conf"
        self.network_interfaces = "/etc/network/interfaces"
    
    def scan_networks(self) -> List[Dict]:
        """
        Escanea redes WiFi disponibles
        
        Returns:
            List[Dict]: Lista de redes WiFi disponibles
        """
        try:
            # Comando para escanear redes WiFi
            cmd = "sudo iwlist wlan0 scan | grep -E 'ESSID|Encryption|Quality'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Error al escanear redes: {result.stderr}")
                return []
                
            # Procesar la salida del comando
            networks = []
            current_net = {}
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                if 'ESSID' in line:
                    if current_net:  # Guardar la red anterior
                        networks.append(current_net)
                    ssid = line.split('"')[1]
                    current_net = {'ssid': ssid, 'encryption': 'Open', 'signal': 0}
                elif 'Encryption key:on' in line:
                    current_net['encryption'] = 'WPA/WPA2'
                elif 'Quality' in line:
                    # Extraer la calidad de la señal (ej: Quality=70/100)
                    match = re.search(r'Quality=(\d+)/', line)
                    if match:
                        current_net['signal'] = int(match.group(1))
            
            # Asegurarse de agregar la última red
            if current_net:
                networks.append(current_net)
                
            return networks
            
        except Exception as e:
            self.logger.error(f"Error en scan_networks: {str(e)}")
            return []
    
    def connect_to_network(self, ssid: str, password: str = None, 
                         security_type: str = 'wpa2') -> bool:
        """
        Conecta a una red WiFi
        
        Args:
            ssid: Nombre de la red WiFi
            password: Contraseña de la red (opcional para redes abiertas)
            security_type: Tipo de seguridad (wpa2, wpa, wep, none)
            
        Returns:
            bool: True si la conexión fue exitosa, False en caso contrario
        """
        try:
            # Configurar wpa_supplicant
            config = f'network={{\n    ssid="{ssid}"\n'
            
            if password and security_type.lower() != 'none':
                if security_type.lower() == 'wep':
                    config += f'    key_mgmt=NONE\n    wep_key0="{password}"\n    wep_tx_keyidx=0\n'
                else:  # WPA/WPA2
                    config += f'    psk="{password}"\n    key_mgmt=WPA-PSK\n'
            else:
                config += '    key_mgmt=NONE\n'
            
            config += '}'
            
            # Hacer backup de la configuración actual
            self._backup_file(self.wpa_supplicant_conf)
            
            # Escribir nueva configuración
            with open(self.wpa_supplicant_conf, 'w') as f:
                f.write('ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n')
                f.write('update_config=1\n\n')
                f.write(config)
            
            # Reiniciar la interfaz de red
            self._restart_network_interface()
            
            # Verificar conexión
            time.sleep(10)  # Esperar a que la conexión se establezca
            return self._check_connection(ssid)
            
        except Exception as e:
            self.logger.error(f"Error en connect_to_network: {str(e)}")
            return False
    
    def get_connection_status(self) -> Dict:
        """
        Obtiene el estado actual de la conexión WiFi
        
        Returns:
            Dict: Información del estado de la conexión
        """
        try:
            # Obtener información de la red actual
            cmd = "iwgetid -r"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            connected_ssid = result.stdout.strip()
            
            # Obtener dirección IP
            cmd = "hostname -I | awk '{print $1}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            ip_address = result.stdout.strip()
            
            return {
                'connected': bool(connected_ssid),
                'ssid': connected_ssid or None,
                'ip_address': ip_address or None,
                'signal_strength': self._get_signal_strength() if connected_ssid else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error en get_connection_status: {str(e)}")
            return {'connected': False, 'error': str(e)}
    
    def enable_ap_mode(self, ssid: str, password: str = None, 
                      channel: int = 6) -> bool:
        """
        Habilita el modo punto de acceso
        
        Args:
            ssid: Nombre de la red del punto de acceso
            password: Contraseña (opcional)
            channel: Canal WiFi a utilizar
            
        Returns:
            bool: True si se configuró correctamente
        """
        try:
            # Configurar hostapd
            hostapd_conf = "/etc/hostapd/hostapd.conf"
            self._backup_file(hostapd_conf)
            
            with open(hostapd_conf, 'w') as f:
                f.write(f"interface=wlan0\n")
                f.write(f"driver=nl80211\n")
                f.write(f"ssid={ssid}\n")
                f.write(f"hw_mode=g\n")
                f.write(f"channel={channel}\n")
                f.write("ieee80211n=1\n")
                f.write("wmm_enabled=1\n")
                f.write("ht_capab=[HT40][SHORT-GI-20][DSSS_CCK-40]\n")
                
                if password:
                    f.write(f"wpa=2\n")
                    f.write(f"wpa_passphrase={password}\n")
                    f.write("wpa_key_mgmt=WPA-PSK\n")
                    f.write("wpa_pairwise=TKIP\n")
                    f.write("rsn_pairwise=CCMP\n")
                else:
                    f.write("auth_algs=1\n")
                    f.write("wmm_enabled=0\n")
            
            # Configurar dnsmasq
            dnsmasq_conf = "/etc/dnsmasq.conf"
            self._backup_file(dnsmasq_conf)
            
            with open(dnsmasq_conf, 'w') as f:
                f.write("interface=wlan0\n")
                f.write("dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h\n")
                f.write("server=8.8.8.8\n")
                f.write("log-queries\n")
                f.write("log-dhcp\n")
            
            # Configurar interfaz de red
            interfaces_conf = "/etc/network/interfaces.d/wlan0"
            self._backup_file(interfaces_conf)
            
            with open(interfaces_conf, 'w') as f:
                f.write("auto wlan0\n")
                f.write("iface wlan0 inet static\n")
                f.write("    address 192.168.4.1\n")
                f.write("    netmask 255.255.255.0\n")
            
            # Reiniciar servicios
            cmds = [
                "sudo systemctl stop dhcpcd",
                "sudo systemctl stop dnsmasq",
                "sudo systemctl stop hostapd",
                "sudo ifconfig wlan0 192.168.4.1",
                "sudo systemctl start dnsmasq",
                "sudo systemctl start hostapd",
                "sudo sysctl -w net.ipv4.ip_forward=1",
                "sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
                "sudo iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT",
                "sudo iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT",
                "sudo sh -c \"iptables-save > /etc/iptables.ipv4.nat\"",
                "sudo systemctl restart networking"
            ]
            
            for cmd in cmds:
                subprocess.run(cmd, shell=True, check=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en enable_ap_mode: {str(e)}")
            return False
    
    def disable_ap_mode(self) -> bool:
        """
        Desactiva el modo punto de acceso
        
        Returns:
            bool: True si se desactivó correctamente
        """
        try:
            # Detener servicios
            cmds = [
                "sudo systemctl stop hostapd",
                "sudo systemctl stop dnsmasq",
                "sudo systemctl start dhcpcd",
                "sudo ifconfig wlan0 down",
                "sudo ifconfig wlan0 up",
                "sudo systemctl restart wpa_supplicant",
                "sudo systemctl restart networking"
            ]
            
            for cmd in cmds:
                subprocess.run(cmd, shell=True, check=True)
            
            # Restaurar configuraciones originales
            self._restore_file("/etc/hostapd/hostapd.conf")
            self._restore_file("/etc/dnsmasq.conf")
            self._restore_file("/etc/network/interfaces.d/wlan0")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en disable_ap_mode: {str(e)}")
            return False
    
    def _check_connection(self, expected_ssid: str) -> bool:
        """Verifica si estamos conectados a la red esperada"""
        status = self.get_connection_status()
        return status.get('connected', False) and status.get('ssid') == expected_ssid
    
    def _get_signal_strength(self) -> int:
        """Obtiene la intensidad de la señal en porcentaje"""
        try:
            cmd = "iwconfig wlan0 | grep 'Signal level' | awk -F'=' '{print $3}' | awk '{print $1}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                # Convertir de dBm a porcentaje (aproximado)
                dbm = int(result.stdout.strip())
                if dbm >= -50:
                    return 100
                elif dbm <= -100:
                    return 0
                else:
                    return 2 * (dbm + 100)
        except Exception:
            pass
        return 0
    
    def _restart_network_interface(self) -> bool:
        """Reinicia la interfaz de red"""
        try:
            cmds = [
                "sudo ifdown wlan0",
                "sudo ifup wlan0",
                "sudo systemctl restart wpa_supplicant"
            ]
            for cmd in cmds:
                subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e:
            self.logger.error(f"Error al reiniciar interfaz de red: {str(e)}")
            return False
    
    def _backup_file(self, filepath: str) -> None:
        """Crea una copia de seguridad de un archivo"""
        if os.path.exists(filepath):
            backup_path = f"{filepath}.bak"
            if not os.path.exists(backup_path):
                with open(filepath, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
    
    def _restore_file(self, filepath: str) -> None:
        """Restaura un archivo desde su copia de seguridad"""
        backup_path = f"{filepath}.bak"
        if os.path.exists(backup_path):
            with open(backup_path, 'r') as src, open(filepath, 'w') as dst:
                dst.write(src.read())
