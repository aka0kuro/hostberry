import subprocess
import shutil
import tempfile
import re
import os
import json
from cryptography.fernet import Fernet
from flask import current_app as app

def get_wifi_ssid():
    """Obtener el SSID de la red WiFi usando wpa_cli"""
    try:
        result = subprocess.run(['wpa_cli', '-i', 'wlan0', 'status'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith('ssid='):
                    return line.split('=', 1)[1]
        return None
    except Exception as e:
        app.logger.error(f'Error al obtener SSID: {str(e)}')
        return None

def is_wifi_connected():
    """Verificar si está conectado a WiFi usando wpa_cli"""
    try:
        result = subprocess.run(['wpa_cli', '-i', 'wlan0', 'status'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith('wpa_state=') and 'COMPLETED' in line:
                    return True
        return False
    except Exception:
        return False

def connect_wifi_wpasupplicant(ssid, password=None):
    """Conectar a una red WiFi usando wpa_supplicant"""
    WPA_SUPPLICANT_CONF = '/etc/wpa_supplicant/wpa_supplicant.conf'
    network_block = f'\nnetwork={{\n    ssid="{ssid}"\n'
    if password:
        network_block += f'    psk="{password}"\n'
    else:
        network_block += '    key_mgmt=NONE\n'
    network_block += '}\n'
    try:
        shutil.copy(WPA_SUPPLICANT_CONF, WPA_SUPPLICANT_CONF + '.bak')
        with open(WPA_SUPPLICANT_CONF, 'r') as f:
            conf = f.read()
        conf = re.sub(r'network=\{[^}]*ssid="'+re.escape(ssid)+r'"[^}]*\}', '', conf, flags=re.DOTALL)
        conf += network_block
        with tempfile.NamedTemporaryFile('w', delete=False) as tf:
            tf.write(conf)
            temp_path = tf.name
        shutil.move(temp_path, WPA_SUPPLICANT_CONF)
        subprocess.run(['wpa_cli', '-i', 'wlan0', 'reconfigure'], check=True)
        subprocess.run(['dhclient', 'wlan0'], check=True)
        return True
    except Exception as e:
        app.logger.error(f'Error conectando a WiFi con wpa_supplicant: {e}')
        return False

def get_wifi_credentials_path():
    """Obtener la ruta del archivo de credenciales WiFi"""
    return os.path.join(os.path.dirname(__file__), 'wifi_credentials.json')

def get_encryption_key():
    """Obtener o generar la clave de encriptación para las credenciales WiFi"""
    key_file = os.path.join(os.path.dirname(__file__), '.wifi_key')
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    key = Fernet.generate_key()
    with open(key_file, 'wb') as f:
        f.write(key)
    return key

def save_wifi_credentials(ssid, password):
    """Guardar credenciales WiFi de forma segura"""
    try:
        credentials_path = get_wifi_credentials_path()
        key = get_encryption_key()
        f = Fernet(key)
        
        # Cargar credenciales existentes
        credentials = {}
        if os.path.exists(credentials_path):
            with open(credentials_path, 'r') as file:
                encrypted_data = file.read()
                if encrypted_data:
                    decrypted_data = f.decrypt(encrypted_data.encode())
                    credentials = json.loads(decrypted_data)
        
        # Actualizar credenciales
        credentials[ssid] = password
        
        # Guardar credenciales encriptadas
        encrypted_data = f.encrypt(json.dumps(credentials).encode())
        with open(credentials_path, 'w') as file:
            file.write(encrypted_data.decode())
        
        return True
    except Exception as e:
        app.logger.error(f'Error guardando credenciales WiFi: {str(e)}')
        return False

def get_wifi_credentials(ssid):
    """Obtener credenciales WiFi guardadas"""
    try:
        credentials_path = get_wifi_credentials_path()
        if not os.path.exists(credentials_path):
            return None
        
        key = get_encryption_key()
        f = Fernet(key)
        
        with open(credentials_path, 'r') as file:
            encrypted_data = file.read()
            if not encrypted_data:
                return None
            
            decrypted_data = f.decrypt(encrypted_data.encode())
            credentials = json.loads(decrypted_data)
            return credentials.get(ssid)
    except Exception as e:
        app.logger.error(f'Error obteniendo credenciales WiFi: {str(e)}')
        return None 