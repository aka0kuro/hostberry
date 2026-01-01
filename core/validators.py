import re
import os
from typing import Optional, Tuple
from core.i18n import get_text

def validate_ssid(ssid: str) -> Tuple[bool, str]:
    """Valida un SSID de WiFi"""
    if not ssid or len(ssid.strip()) == 0:
        return False, get_text("validators.ssid_empty", default="SSID no puede estar vacío")
    
    if len(ssid) > 32:
        return False, get_text("validators.ssid_too_long", default="SSID no puede tener más de 32 caracteres")
    
    # Verificar caracteres válidos (ASCII imprimible)
    if not all(32 <= ord(c) <= 126 for c in ssid):
        return False, get_text("validators.ssid_invalid_chars", default="SSID contiene caracteres inválidos")
    
    return True, get_text("validators.ssid_valid", default="SSID válido")

def validate_password(password: str, min_length: int = 8) -> Tuple[bool, str]:
    """Valida una contraseña"""
    if not password:
        return False, get_text("validators.password_empty", default="Contraseña no puede estar vacía")
    
    if len(password) < min_length:
        return False, get_text("validators.password_too_short", default=f"Contraseña debe tener al menos {min_length} caracteres", min_length=min_length)
    
    if len(password) > 63:
        return False, get_text("validators.password_too_long", default="Contraseña no puede tener más de 63 caracteres")
    
    return True, get_text("validators.password_valid", default="Contraseña válida")

def validate_ip_address(ip: str) -> Tuple[bool, str]:
    """Valida una dirección IP"""
    if not ip:
        return False, get_text("validators.ip_empty", default="Dirección IP no puede estar vacía")
    
    # Patrón básico para IPv4
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False, get_text("validators.ip_invalid_format", default="Formato de IP inválido")
    
    # Verificar que cada octeto esté en rango válido
    parts = ip.split('.')
    for part in parts:
        if not 0 <= int(part) <= 255:
            return False, get_text("validators.ip_out_of_range", default="Valores de IP fuera de rango")
    
    return True, get_text("validators.ip_valid", default="IP válida")

def validate_filename(filename: str, allowed_extensions: set = None) -> Tuple[bool, str]:
    """Valida un nombre de archivo"""
    if not filename:
        return False, get_text("validators.filename_empty", default="Nombre de archivo no puede estar vacío")
    
    if len(filename) > 255:
        return False, get_text("validators.filename_too_long", default="Nombre de archivo demasiado largo")
    
    # Verificar caracteres peligrosos
    dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in dangerous_chars:
        if char in filename:
            return False, get_text("validators.filename_invalid_chars", default=f"Nombre de archivo contiene caracteres inválidos: {char}", char=char)
    
    if allowed_extensions:
        ext = os.path.splitext(filename)[1].lower()
        if ext not in allowed_extensions:
            return False, get_text("validators.filename_extension_not_allowed", default=f"Extensión no permitida. Permitidas: {', '.join(allowed_extensions)}", extensions=', '.join(allowed_extensions))
    
    return True, get_text("validators.filename_valid", default="Nombre de archivo válido")

def validate_file_size(file_size: int, max_size: int) -> Tuple[bool, str]:
    """Valida el tamaño de un archivo"""
    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        return False, get_text("validators.file_too_large", default=f"Archivo demasiado grande. Máximo: {max_size_mb:.1f} MB", max_size_mb=f"{max_size_mb:.1f}")
    
    return True, get_text("validators.file_size_valid", default="Tamaño de archivo válido") 