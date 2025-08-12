import re
import os
from typing import Optional, Tuple

def validate_ssid(ssid: str) -> Tuple[bool, str]:
    """Valida un SSID de WiFi"""
    if not ssid or len(ssid.strip()) == 0:
        return False, "SSID no puede estar vacío"
    
    if len(ssid) > 32:
        return False, "SSID no puede tener más de 32 caracteres"
    
    # Verificar caracteres válidos (ASCII imprimible)
    if not all(32 <= ord(c) <= 126 for c in ssid):
        return False, "SSID contiene caracteres inválidos"
    
    return True, "SSID válido"

def validate_password(password: str, min_length: int = 8) -> Tuple[bool, str]:
    """Valida una contraseña"""
    if not password:
        return False, "Contraseña no puede estar vacía"
    
    if len(password) < min_length:
        return False, f"Contraseña debe tener al menos {min_length} caracteres"
    
    if len(password) > 63:
        return False, "Contraseña no puede tener más de 63 caracteres"
    
    return True, "Contraseña válida"

def validate_ip_address(ip: str) -> Tuple[bool, str]:
    """Valida una dirección IP"""
    if not ip:
        return False, "Dirección IP no puede estar vacía"
    
    # Patrón básico para IPv4
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False, "Formato de IP inválido"
    
    # Verificar que cada octeto esté en rango válido
    parts = ip.split('.')
    for part in parts:
        if not 0 <= int(part) <= 255:
            return False, "Valores de IP fuera de rango"
    
    return True, "IP válida"

def validate_filename(filename: str, allowed_extensions: set = None) -> Tuple[bool, str]:
    """Valida un nombre de archivo"""
    if not filename:
        return False, "Nombre de archivo no puede estar vacío"
    
    if len(filename) > 255:
        return False, "Nombre de archivo demasiado largo"
    
    # Verificar caracteres peligrosos
    dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in dangerous_chars:
        if char in filename:
            return False, f"Nombre de archivo contiene caracteres inválidos: {char}"
    
    if allowed_extensions:
        ext = os.path.splitext(filename)[1].lower()
        if ext not in allowed_extensions:
            return False, f"Extensión no permitida. Permitidas: {', '.join(allowed_extensions)}"
    
    return True, "Nombre de archivo válido"

def validate_file_size(file_size: int, max_size: int) -> Tuple[bool, str]:
    """Valida el tamaño de un archivo"""
    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        return False, f"Archivo demasiado grande. Máximo: {max_size_mb:.1f} MB"
    
    return True, "Tamaño de archivo válido" 