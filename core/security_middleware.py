"""
Middleware de seguridad para HostBerry FastAPI
"""

import time
import hashlib
import hmac
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import Response
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    """Middleware para implementar medidas de seguridad"""
    
    def __init__(self):
        self.rate_limit_store: Dict[str, List[float]] = {}
        self.ip_blacklist: set = set(settings.ip_blacklist)
        self.ip_whitelist: set = set(settings.ip_whitelist)
        self.suspicious_ips: Dict[str, int] = {}
    
    async def __call__(self, request: Request, call_next):
        """Procesar request con medidas de seguridad"""
        
        # Obtener IP del cliente
        client_ip = self._get_client_ip(request)
        
        # Verificar IP blacklist
        if self._is_ip_blacklisted(client_ip):
            logger.warning(f"IP bloqueada intentando acceder: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado"
            )
        
        # Verificar IP whitelist si está habilitada
        if settings.ip_whitelist_enabled and not self._is_ip_whitelisted(client_ip):
            logger.warning(f"IP no autorizada: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP no autorizada"
            )
        
        # Rate limiting
        if settings.rate_limit_enabled and not self._check_rate_limit(client_ip):
            logger.warning(f"Rate limit excedido para IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes"
            )
        
        # Procesar request
        response = await call_next(request)
        
        # Agregar headers de seguridad
        if settings.security_headers_enabled:
            self._add_security_headers(response)
        
        # Monitorear actividad sospechosa
        self._monitor_suspicious_activity(client_ip, request, response)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Obtener IP real del cliente"""
        # Verificar headers de proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _is_ip_blacklisted(self, ip: str) -> bool:
        """Verificar si IP está en blacklist"""
        return ip in self.ip_blacklist
    
    def _is_ip_whitelisted(self, ip: str) -> bool:
        """Verificar si IP está en whitelist"""
        return ip in self.ip_whitelist
    
    def _check_rate_limit(self, ip: str) -> bool:
        """Verificar rate limiting"""
        current_time = time.time()
        
        if ip not in self.rate_limit_store:
            self.rate_limit_store[ip] = []
        
        # Limpiar requests antiguos
        self.rate_limit_store[ip] = [
            req_time for req_time in self.rate_limit_store[ip]
            if current_time - req_time < settings.rate_limit_window
        ]
        
        # Verificar límite
        if len(self.rate_limit_store[ip]) >= settings.rate_limit_requests:
            return False
        
        # Agregar request actual
        self.rate_limit_store[ip].append(current_time)
        return True
    
    def _add_security_headers(self, response: Response):
        """Agregar headers de seguridad"""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # HSTS
        if settings.security_headers_enabled:
            response.headers["Strict-Transport-Security"] = f"max-age={settings.hsts_max_age}; includeSubDomains"
        
        # Content Security Policy
        if settings.content_security_policy:
            response.headers["Content-Security-Policy"] = settings.content_security_policy
    
    def _monitor_suspicious_activity(self, ip: str, request: Request, response: Response):
        """Monitorear actividad sospechosa"""
        if not settings.security_monitoring_enabled:
            return
        
        # Detectar patrones sospechosos
        suspicious_patterns = [
            "/admin", "/wp-admin", "/phpmyadmin", "/mysql",
            "union select", "script", "javascript:", "data:text/html"
        ]
        
        user_agent = request.headers.get("user-agent", "").lower()
        path = str(request.url.path).lower()
        query = str(request.url.query).lower()
        
        # Verificar patrones sospechosos
        for pattern in suspicious_patterns:
            if pattern in path or pattern in query or pattern in user_agent:
                self._log_suspicious_activity(ip, request, f"Patrón sospechoso: {pattern}")
                break
        
        # Verificar códigos de error 4xx/5xx
        if response.status_code >= 400:
            self.suspicious_ips[ip] = self.suspicious_ips.get(ip, 0) + 1
            
            if self.suspicious_ips[ip] >= settings.suspicious_activity_threshold:
                logger.warning(f"Actividad sospechosa detectada de IP: {ip}")
                # Opcional: agregar a blacklist temporal
                # self.ip_blacklist.add(ip)

def create_security_middleware():
    """Crear instancia del middleware de seguridad"""
    return SecurityMiddleware()

# Funciones de utilidad de seguridad
def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validar fortaleza de contraseña"""
    if len(password) < settings.password_min_length:
        return False, f"La contraseña debe tener al menos {settings.password_min_length} caracteres"
    
    if settings.password_require_uppercase and not any(c.isupper() for c in password):
        return False, "La contraseña debe contener al menos una letra mayúscula"
    
    if settings.password_require_lowercase and not any(c.islower() for c in password):
        return False, "La contraseña debe contener al menos una letra minúscula"
    
    if settings.password_require_numbers and not any(c.isdigit() for c in password):
        return False, "La contraseña debe contener al menos un número"
    
    if settings.password_require_special and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "La contraseña debe contener al menos un carácter especial"
    
    return True, "Contraseña válida"

def generate_secure_token(data: str, salt: str = None) -> str:
    """Generar token seguro"""
    if not salt:
        salt = settings.secret_key
    
    message = f"{data}:{salt}:{int(time.time())}"
    return hmac.new(
        settings.secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

def validate_input_sanitization(input_data: str) -> bool:
    """Validar sanitización de entrada"""
    dangerous_patterns = [
        "<script", "javascript:", "data:text/html", "vbscript:",
        "onload=", "onerror=", "onclick=", "onmouseover="
    ]
    
    input_lower = input_data.lower()
    for pattern in dangerous_patterns:
        if pattern in input_lower:
            return False
    
    return True

def log_security_event(event_type: str, details: Dict, ip_address: str = None):
    """Registrar evento de seguridad"""
    if settings.audit_log_enabled:
        log_entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "ip_address": ip_address,
            "details": details
        }
        logger.warning(f"Evento de seguridad: {log_entry}")

def _log_suspicious_activity(self, ip: str, request: Request, reason: str):
    """Registrar actividad sospechosa"""
    log_security_event("suspicious_activity", {
        "reason": reason,
        "path": str(request.url.path),
        "method": request.method,
        "user_agent": request.headers.get("user-agent", "")
    }, ip) 