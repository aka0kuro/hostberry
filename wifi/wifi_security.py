from cryptography.fernet import Fernet
import os
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

class WiFiSecurity:
    def __init__(self):
        self.key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wifi_key')
        self._key = None
        
    def get_encryption_key(self):
        """Obtiene o genera una clave de encriptación con rotación periódica"""
        if self._key and time.time() - self._key['created'] < 30 * 24 * 60 * 60:  # 30 días
            return self._key['key']
            
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, 'r') as f:
                    key_info = json.load(f)
                    if time.time() - key_info['created'] < 30 * 24 * 60 * 60:
                        self._key = key_info
                        return key_info['key']
            except Exception as e:
                logger.warning(f"Error al cargar clave existente: {e}")
                
        # Generar nueva clave
        new_key = Fernet.generate_key()
        key_info = {
            'key': new_key.decode(),
            'created': time.time()
        }
        
        try:
            with open(self.key_file, 'w') as f:
                json.dump(key_info, f)
        except Exception as e:
            logger.error(f"Error al guardar nueva clave: {e}")
            
        self._key = key_info
        return new_key
        
    def encrypt_password(self, password: str) -> str:
        """Encripta una contraseña"""
        key = self.get_encryption_key()
        cipher_suite = Fernet(key)
        return cipher_suite.encrypt(password.encode()).decode()
        
    def decrypt_password(self, encrypted_password: str) -> str:
        """Desencripta una contraseña"""
        key = self.get_encryption_key()
        cipher_suite = Fernet(key)
        return cipher_suite.decrypt(encrypted_password.encode()).decode()
        
    def validate_ssid(self, ssid: str) -> bool:
        """Valida un SSID de WiFi"""
        if not ssid:
            return False
        if len(ssid) > 32:  # Límite máximo de SSID
            return False
        if not all(c.isprintable() for c in ssid):  # Solo caracteres imprimibles
            return False
        return True
        
    def validate_password(self, password: str) -> bool:
        """Valida una contraseña de WiFi"""
        if not password:
            return False
        if len(password) < 8 or len(password) > 63:  # Rango típico de contraseñas WiFi
            return False
        return True

wifi_security = WiFiSecurity()
