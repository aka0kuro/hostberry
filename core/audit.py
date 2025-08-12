"""
Sistema de auditoría para HostBerry FastAPI
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

class AuditLogger:
    """Sistema de auditoría para registrar eventos de seguridad"""
    
    def __init__(self):
        self.audit_file = Path(settings.audit_log_file)
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_event(self, event_type: str, user_id: str = None, 
                  ip_address: str = None, details: Dict[str, Any] = None,
                  severity: str = "INFO"):
        """Registrar evento de auditoría"""
        if not settings.audit_log_enabled:
            return
        
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "severity": severity,
            "details": details or {}
        }
        
        try:
            with open(self.audit_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Error escribiendo en log de auditoría: {e}")
    
    def log_login_attempt(self, username: str, ip_address: str, success: bool):
        """Registrar intento de login"""
        severity = "WARNING" if not success else "INFO"
        self.log_event(
            "login_attempt",
            user_id=username,
            ip_address=ip_address,
            details={"success": success},
            severity=severity
        )
    
    def log_password_change(self, username: str, ip_address: str):
        """Registrar cambio de contraseña"""
        self.log_event(
            "password_change",
            user_id=username,
            ip_address=ip_address,
            details={"action": "password_changed"},
            severity="WARNING"
        )
    
    def log_sensitive_operation(self, operation: str, username: str, 
                               ip_address: str, details: Dict[str, Any]):
        """Registrar operación sensible"""
        self.log_event(
            "sensitive_operation",
            user_id=username,
            ip_address=ip_address,
            details=details,
            severity="WARNING"
        )
    
    def log_configuration_change(self, username: str, ip_address: str,
                                config_key: str, old_value: str, new_value: str):
        """Registrar cambio de configuración"""
        self.log_event(
            "configuration_change",
            user_id=username,
            ip_address=ip_address,
            details={
                "config_key": config_key,
                "old_value": old_value,
                "new_value": new_value
            },
            severity="WARNING"
        )
    
    def log_security_violation(self, violation_type: str, ip_address: str,
                              details: Dict[str, Any]):
        """Registrar violación de seguridad"""
        self.log_event(
            "security_violation",
            ip_address=ip_address,
            details=details,
            severity="ERROR"
        )
    
    def log_file_access(self, username: str, ip_address: str, 
                       file_path: str, operation: str):
        """Registrar acceso a archivos"""
        self.log_event(
            "file_access",
            user_id=username,
            ip_address=ip_address,
            details={
                "file_path": file_path,
                "operation": operation
            },
            severity="INFO"
        )
    
    def log_system_event(self, event_type: str, details: Dict[str, Any]):
        """Registrar evento del sistema"""
        self.log_event(
            f"system_{event_type}",
            details=details,
            severity="INFO"
        )

# Instancia global del auditor
audit_logger = AuditLogger()

# Funciones de conveniencia
def audit_login_attempt(username: str, ip_address: str, success: bool):
    """Auditar intento de login"""
    audit_logger.log_login_attempt(username, ip_address, success)

def audit_password_change(username: str, ip_address: str):
    """Auditar cambio de contraseña"""
    audit_logger.log_password_change(username, ip_address)

def audit_sensitive_operation(operation: str, username: str, 
                            ip_address: str, details: Dict[str, Any]):
    """Auditar operación sensible"""
    audit_logger.log_sensitive_operation(operation, username, ip_address, details)

def audit_configuration_change(username: str, ip_address: str,
                             config_key: str, old_value: str, new_value: str):
    """Auditar cambio de configuración"""
    audit_logger.log_configuration_change(username, ip_address, config_key, old_value, new_value)

def audit_security_violation(violation_type: str, ip_address: str, details: Dict[str, Any]):
    """Auditar violación de seguridad"""
    audit_logger.log_security_violation(violation_type, ip_address, details)

def audit_file_access(username: str, ip_address: str, file_path: str, operation: str):
    """Auditar acceso a archivos"""
    audit_logger.log_file_access(username, ip_address, file_path, operation)

def audit_system_event(event_type: str, details: Dict[str, Any]):
    """Auditar evento del sistema"""
    audit_logger.log_system_event(event_type, details) 