import os
import json
import shutil
import logging
from datetime import datetime

# Configurar logger específico
logger = logging.getLogger('HostBerryConfig')
logger.setLevel(logging.DEBUG)

# Crear directorio logs si no existe
log_dir = '/var/log/hostberry'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
    logger.info(f'Directorio de logs creado: {log_dir}')

# Handler para archivo
file_handler = logging.FileHandler(f'{log_dir}/hostberry_config.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Handler para consola
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(console_handler)

class HostBerryConfig:
    CONFIG_FILE = os.environ.get('HOSTBERRY_CONFIG_FILE', '/etc/hostberry/config.json')
    DEFAULT_CONFIG = {
        'AP_IFACE': 'wlan_ap0',
        'WIFI_IFACE': 'wlan0',
        'ETH_IFACE': 'eth0',
        'AP_SSID': 'Hostberry',
        'AP_PASSWORD': 'randompassword',
        'AP_IP': '192.168.90.1',
        'SUBNET': '192.168.90.0',
        'NETMASK': '255.255.255.0',
        'DHCP_RANGE': '192.168.90.10,192.168.90.50,24h',
        'SSH_ENABLED': True,
        'SSH_PORT': 22,
        'FIREWALL_ENABLED': True,
        'APPARMOR_ENABLED': True,
        'NETDATA_ENABLED': True,
        'SYSSTAT_ENABLED': True,
        'IP_WHITELIST': '',
        'FAILED_ATTEMPTS_LIMIT': 5,
        'ADBLOCK_ENABLED': False,
        'ADBLOCK_LISTS': [
            'easylist',
            'easyprivacy',
            'fanboy',
            'malware',
            'social',
            'kadhosts',
            'adobe',
            'firstparty',
            'stevenblack',
            'windows'
        ],
        'ADBLOCK_UPDATE_FREQUENCY': 'weekly'
    }

    def __init__(self):
        logger.info(f'Inicializando HostBerryConfig. Archivo: {self.CONFIG_FILE}')
        try:
            if not os.path.exists(os.path.dirname(self.CONFIG_FILE)):
                logger.info(f'Creando directorio: {os.path.dirname(self.CONFIG_FILE)}')
                os.makedirs(os.path.dirname(self.CONFIG_FILE))
            
            if not os.path.exists(self.CONFIG_FILE):
                logger.info('Creando archivo de configuración por defecto')
                self._create_default_config()
            
            logger.debug('Configuración inicializada correctamente')
        except Exception as e:
            logger.error(f'Error al inicializar configuración: {e}', exc_info=True)
            raise

    def _create_default_config(self):
        logger.info('Creando archivo de configuración por defecto')
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=4)
            logger.debug('Archivo de configuración creado correctamente')
        except Exception as e:
            logger.error(f'Error al crear archivo de configuración: {e}', exc_info=True)
            raise

    def get_current_config(self):
        logger.info('Obteniendo configuración actual')
        try:
            with open(self.CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f'Error al obtener configuración actual: {e}', exc_info=True)
            raise

    def update_config(self, new_config):
        logger.info('Actualizando configuración')
        try:
            # Validar valores
            for key, value in new_config.items():
                if key in self.DEFAULT_CONFIG and type(value) != type(self.DEFAULT_CONFIG[key]):
                    logger.error(f'Tipo inválido para {key}: esperado {type(self.DEFAULT_CONFIG[key])}, recibido {type(value)}')
                    return False
            # Obtener configuración actual
            current_config = self.get_current_config()
            current_config.update(new_config)
            # Backup automático
            backup_path = self.CONFIG_FILE + '.bak_' + datetime.now().strftime('%Y%m%d%H%M%S')
            if os.path.exists(self.CONFIG_FILE):
                shutil.copy2(self.CONFIG_FILE, backup_path)
                logger.info(f'Backup de configuración creado en {backup_path}')
            # Guardar en archivo temporal
            temp_path = '/tmp/hostberry_config.tmp'
            with open(temp_path, 'w') as f:
                json.dump(current_config, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            # Mover a ubicación final
            shutil.move(temp_path, self.CONFIG_FILE)
            logger.debug('Configuración actualizada correctamente')
            return True
        except Exception as e:
            logger.error(f'Error al guardar configuración: {e}', exc_info=True)
            return False

    def _update_new_script(self, config):
        import re
        logger.info('Actualizando script new_script.sh')
        def sanitize_iface(iface):
            return iface if re.match(r'^[a-zA-Z0-9_-]{1,15}$', iface) else 'wlan0'
        def sanitize_ssid(ssid):
            return ssid if ssid and len(ssid) <= 32 and all(ord(c) > 31 and ord(c) < 127 for c in ssid) else 'HostBerry'
        def sanitize_password(password):
            return password if password and 8 <= len(password) <= 63 else 'password1234'
        try:
            with open('/usr/local/bin/new_script.sh', 'r') as f:
                content = f.readlines()
            
            # Find and replace configuration lines
            for i, line in enumerate(content):
                if line.startswith('AP_IFACE='):
                    content[i] = f'AP_IFACE="{sanitize_iface(config["AP_IFACE"])}"\n'
                elif line.startswith('WIFI_IFACE='):
                    content[i] = f'WIFI_IFACE="{sanitize_iface(config["WIFI_IFACE"])}"\n'
                elif line.startswith('ETH_IFACE='):
                    content[i] = f'ETH_IFACE="{sanitize_iface(config["ETH_IFACE"])}"\n'
                elif line.startswith('AP_SSID='):
                    content[i] = f'AP_SSID="{sanitize_ssid(config["AP_SSID"])}"\n'
                elif line.startswith('AP_PASSWORD='):
                    content[i] = f'AP_PASSWORD="{sanitize_password(config["AP_PASSWORD"])}"\n'
                elif line.startswith('AP_IP='):
                    content[i] = f'AP_IP="{config["AP_IP"]}"\n'
                elif line.startswith('SUBNET='):
                    content[i] = f'SUBNET="{config["SUBNET"]}"\n'
                elif line.startswith('NETMASK='):
                    content[i] = f'NETMASK="{config["NETMASK"]}"\n'
                elif line.startswith('DHCP_RANGE='):
                    content[i] = f'DHCP_RANGE="{config["DHCP_RANGE"]}"\n'
                    content[i] = f'SSH_ENABLED={str(config["SSH_ENABLED"]).lower()}\n'
                elif line.startswith('SSH_PORT='):
                    content[i] = f'SSH_PORT={config["SSH_PORT"]}\n'
            
            # Validar y sanitizar parámetros críticos
            import re
            valid_ifaces = ['wlan0', 'wlan1', 'eth0', 'eth1']
            valid_ssids = re.compile(r'^[a-zA-Z0-9_-]{1,32}$')
            valid_passwords = re.compile(r'^[a-zA-Z0-9_-]{8,63}$')
            
            if config["AP_IFACE"] not in valid_ifaces:
                logger.warning(f'Interfaz AP_IFACE inválida: {config["AP_IFACE"]}. Usando wlan0 por defecto.')
                content[i] = f'AP_IFACE="wlan0"\n'
            if not valid_ssids.match(config["AP_SSID"]):
                logger.warning(f'SSID inválido: {config["AP_SSID"]}. Usando HostBerry por defecto.')
                content[i] = f'AP_SSID="HostBerry"\n'
            if not valid_passwords.match(config["AP_PASSWORD"]):
                logger.warning(f'Contraseña inválida: {config["AP_PASSWORD"]}. Usando password1234 por defecto.')
                content[i] = f'AP_PASSWORD="password1234"\n'
            
            with open('/usr/local/bin/new_script.sh', 'w') as f:
                f.writelines(content)
            # Set executable permissions
            os.chmod('/usr/local/bin/new_script.sh', 0o755)
            logger.debug('Script new_script.sh actualizado correctamente')
        except Exception as e:
            logger.error(f'Error al actualizar script new_script.sh: {e}', exc_info=True)
            raise