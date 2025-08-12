"""
API de seguridad para HostBerry FastAPI
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any, List
import time

from models.schemas import SuccessResponse, ErrorResponse
from core.security import get_current_active_user
from core.audit import audit_security_violation, audit_sensitive_operation
from core.backup import create_system_backup, list_system_backups, get_backup_details
from core.security_middleware import validate_input_sanitization, generate_secure_token
from core.logging import logger

router = APIRouter()

@router.get("/security/status")
async def get_security_status(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtener estado de seguridad del sistema"""
    try:
        from config.settings import settings
        
        security_status = {
            "audit_logging_enabled": settings.audit_log_enabled,
            "rate_limiting_enabled": settings.rate_limit_enabled,
            "security_headers_enabled": settings.security_headers_enabled,
            "backup_encryption_enabled": settings.backup_encryption_enabled,
            "two_factor_enabled": settings.two_factor_enabled,
            "ip_blacklist_enabled": settings.ip_blacklist_enabled,
            "ip_whitelist_enabled": settings.ip_whitelist_enabled,
            "failed_login_threshold": settings.failed_login_threshold,
            "suspicious_activity_threshold": settings.suspicious_activity_threshold
        }
        
        audit_sensitive_operation(
            "security_status_check",
            current_user.get("username"),
            None,
            {"status": "success"}
        )
        
        return SuccessResponse(
            message="Estado de seguridad obtenido",
            data=security_status
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de seguridad: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/security/backup")
async def create_backup(
    include_logs: bool = True,
    include_uploads: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Crear backup del sistema"""
    try:
        backup_path = create_system_backup(include_logs, include_uploads)
        
        if backup_path:
            audit_sensitive_operation(
                "backup_created",
                current_user.get("username"),
                None,
                {
                    "backup_path": backup_path,
                    "include_logs": include_logs,
                    "include_uploads": include_uploads
                }
            )
            
            return SuccessResponse(
                message="Backup creado exitosamente",
                data={"backup_path": backup_path}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creando backup"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/security/backups")
async def list_backups(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Listar backups disponibles"""
    try:
        backups = list_system_backups()
        
        audit_sensitive_operation(
            "backups_listed",
            current_user.get("username"),
            None,
            {"backup_count": len(backups)}
        )
        
        return SuccessResponse(
            message="Backups listados exitosamente",
            data={"backups": backups}
        )
        
    except Exception as e:
        logger.error(f"Error listando backups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/security/backup/{backup_name}")
async def get_backup_info(
    backup_name: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Obtener información de un backup específico"""
    try:
        backup_info = get_backup_details(f"backups/{backup_name}")
        
        if backup_info:
            audit_sensitive_operation(
                "backup_info_accessed",
                current_user.get("username"),
                None,
                {"backup_name": backup_name}
            )
            
            return SuccessResponse(
                message="Información de backup obtenida",
                data={"backup_info": backup_info}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup no encontrado"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo información de backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/security/validate-input")
async def validate_input(
    input_data: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Validar sanitización de entrada"""
    try:
        is_valid = validate_input_sanitization(input_data)
        
        audit_sensitive_operation(
            "input_validation",
            current_user.get("username"),
            None,
            {"input_length": len(input_data), "is_valid": is_valid}
        )
        
        return SuccessResponse(
            message="Validación de entrada completada",
            data={
                "is_valid": is_valid,
                "input_length": len(input_data)
            }
        )
        
    except Exception as e:
        logger.error(f"Error validando entrada: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/security/generate-token")
async def generate_token(
    data: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Generar token seguro"""
    try:
        secure_token = generate_secure_token(data)
        
        audit_sensitive_operation(
            "secure_token_generated",
            current_user.get("username"),
            None,
            {"data_length": len(data)}
        )
        
        return SuccessResponse(
            message="Token seguro generado",
            data={"token": secure_token}
        )
        
    except Exception as e:
        logger.error(f"Error generando token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/security/log-violation")
async def log_security_violation(
    violation_type: str,
    details: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Registrar violación de seguridad"""
    try:
        audit_security_violation(violation_type, None, details)
        
        return SuccessResponse(
            message="Violación de seguridad registrada",
            data={"violation_type": violation_type}
        )
        
    except Exception as e:
        logger.error(f"Error registrando violación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        ) 