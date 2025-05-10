import subprocess
import shutil
import tempfile
import re
import os
import json
from cryptography.fernet import Fernet
from flask import current_app as app
import time
import logging

logger = logging.getLogger(__name__)

class WiFiUtils:
    def __init__(self):
        self._key = None
        self._credentials_path = os.path.join(os.path.dirname(__file__), 'wifi_credentials.json')
        self._key_file = os.path.join(os.path.dirname(__file__), '.wifi_key')
        
    def get_encryption_key(self):
        """Obtener o generar la clave de encriptación"""
        if self._key:
            return self._key
            
        if os.path.exists(self._key_file):
            try:
                with open(self._key_file, 'rb') as f:
                    key = f.read()
                    if key:
                        self._key = key
                        return key
            except Exception as e:
                logger.warning(f"Error al cargar clave existente: {e}")
                
        # Generar nueva clave
        key = Fernet.generate_key()
        try:
            with open(self._key_file, 'wb') as f:
                f.write(key)
            os.chmod(self._key_file, 0o600)
        except Exception as e:
            logger.error(f"Error al guardar nueva clave: {e}")
        
        self._key = key
        return key
        
    def get_credentials_path(self):
        """Obtener la ruta del archivo de credenciales"""
        return self._credentials_path
        
    def save_credentials(self, ssid, password, security=None):
        """Guardar credenciales WiFi de forma segura, incluyendo el tipo de seguridad"""
        try:
            key = self.get_encryption_key()
            cipher_suite = Fernet(key)
            
            # Cargar credenciales existentes
            credentials = {}
            if os.path.exists(self._credentials_path):
                try:
                    with open(self._credentials_path, 'r') as f:
                        encrypted_data = f.read()
                        if encrypted_data:
                            decrypted_data = cipher_suite.decrypt(encrypted_data.encode())
                            credentials = json.loads(decrypted_data)
                except Exception as e:
                    logger.warning(f"Error al cargar credenciales existentes: {e}")
                    
            # Actualizar credenciales (incluyendo tipo de seguridad)
            cred_entry = {
                'password': cipher_suite.encrypt(password.encode()).decode(),
                'last_used': time.time(),
                'encrypted': True
            }
            if security:
                cred_entry['security'] = security
            credentials[ssid] = cred_entry
            
            # Actualizar historial de últimas conexiones
            last_connected = credentials.get('last_connected', [])
            if ssid in last_connected:
                last_connected.remove(ssid)
            last_connected.insert(0, ssid)
            last_connected = last_connected[:5]  # Mantener solo las últimas 5 conexiones
            credentials['last_connected'] = last_connected
            
            # Guardar credenciales encriptadas
            encrypted_data = cipher_suite.encrypt(json.dumps(credentials).encode())
            with open(self._credentials_path, 'w') as f:
                f.write(encrypted_data.decode())
            os.chmod(self._credentials_path, 0o600)
        
            logger.info(f"Credenciales para {ssid} guardadas exitosamente")
            return True
            
        except Exception as e:
            logger.error(f'Error guardando credenciales WiFi: {str(e)}')
            return False
            
    def get_credentials(self, ssid=None):
        """Obtener credenciales WiFi guardadas (incluyendo tipo de seguridad si existe)"""
        try:
            if not os.path.exists(self._credentials_path):
                return None if ssid else {}
                
            key = self.get_encryption_key()
            cipher_suite = Fernet(key)
            
            with open(self._credentials_path, 'r') as f:
                encrypted_data = f.read()
                if not encrypted_data:
                    return None if ssid else {}
                    
                decrypted_data = cipher_suite.decrypt(encrypted_data.encode())
                credentials = json.loads(decrypted_data)
                
                if ssid:
                    cred = credentials.get(ssid)
                    if not cred:
                        return None
                    result = {}
                    # Devuelve password y security si existe
                    if cred.get('encrypted', False):
                        try:
                            result['password'] = cipher_suite.decrypt(cred['password'].encode()).decode()
                        except:
                            logger.warning(f"Error al desencriptar contraseña para {ssid}")
                            return None
                    else:
                        result['password'] = cred.get('password')
                    if 'security' in cred:
                        result['security'] = cred['security']
                    return result
                
                # Devolver todas las credenciales (password y security)
                result = {}
                for ssid, cred in credentials.items():
                    entry = {}
                    if cred.get('encrypted', False):
                        try:
                            entry['password'] = cipher_suite.decrypt(cred['password'].encode()).decode()
                        except:
                            logger.warning(f"Error al desencriptar contraseña para {ssid}")
                            continue
                    else:
                        entry['password'] = cred.get('password', '')
                    if 'security' in cred:
                        entry['security'] = cred['security']
                    result[ssid] = entry
                
                return result
                
        except Exception as e:
            logger.error(f'Error obteniendo credenciales WiFi: {str(e)}')
            return None if ssid else {}

wifi_utils = WiFiUtils() 