"""
Router del sistema para FastAPI
"""

import os
import time
from core import system_light as psutil
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from models.schemas import SystemStats, NetworkStats, SystemInfo, SuccessResponse
from core.security import get_current_active_user
from core.database import db
from core.logging import get_logger
from system.system_utils import get_system_stats, get_network_interface, get_ip_address, get_cpu_temp
from core.i18n import get_text

router = APIRouter()
logger = get_logger("system")

@router.get("/stats", response_model=SystemStats)
async def get_system_statistics(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene estadísticas del sistema"""
    try:
        # Obtener estadísticas básicas
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        cpu_temp = get_cpu_temp()
        
        # Obtener uptime
        uptime = int(time.time() - psutil.boot_time())
        
        stats = SystemStats(
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            cpu_temperature=cpu_temp,
            uptime=uptime
        )
        
        # Guardar estadísticas en base de datos
        await db.insert_statistic("cpu_usage", cpu_usage)
        await db.insert_statistic("memory_usage", memory.percent)
        await db.insert_statistic("disk_usage", disk.percent)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del sistema: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.system_stats_error", default="Error obteniendo estadísticas del sistema")
        )

@router.get("/network", response_model=NetworkStats)
async def get_network_statistics(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene estadísticas de red"""
    try:
        # Obtener información de red
        interface = get_network_interface()
        ip_address = get_ip_address()
        
        # Obtener estadísticas de red
        net_io = psutil.net_io_counters()
        
        # Calcular velocidades (simplificado)
        upload_speed = net_io.bytes_sent / 1024  # KB
        download_speed = net_io.bytes_recv / 1024  # KB
        
        stats = NetworkStats(
            interface=interface,
            ip_address=ip_address,
            upload_speed=upload_speed,
            download_speed=download_speed,
            bytes_sent=net_io.bytes_sent,
            bytes_recv=net_io.bytes_recv
        )
        
        # Guardar estadísticas en base de datos
        await db.insert_statistic("network_upload", upload_speed)
        await db.insert_statistic("network_download", download_speed)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de red: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.network_stats_error", default="Error obteniendo estadísticas de red")
        )

@router.get("/info", response_model=SystemInfo)
async def get_system_info(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene información del sistema"""
    try:
        # Información básica del sistema
        hostname = os.uname().nodename
        kernel = os.uname().release
        os_name = "Linux"  # Simplificado
        
        return SystemInfo(
            hostname=hostname,
            os_name=os_name,
            kernel_version=kernel,
            processor=os.uname().machine,
            python_version=platform.python_version()
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo información del sistema: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.system_info_error", default="Error obteniendo información del sistema")
        )

@router.get("/uptime")
async def get_uptime(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene el tiempo de actividad del sistema"""
    try:
        uptime_seconds = int(time.time() - psutil.boot_time())
        
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        
        return {
            "uptime_seconds": uptime_seconds,
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "formatted": f"{days}d {hours}h {minutes}m"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo uptime: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.uptime_error", default="Error obteniendo uptime")
        )

@router.get("/services")
async def get_services_status(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene el estado de los servicios del sistema"""
    try:
        services = {}
        
        # Verificar servicios comunes
        service_names = ["hostapd", "openvpn", "wg-quick", "dnsmasq", "hostberry"]
        
        for service in service_names:
            try:
                # Verificar si el servicio está ejecutándose
                result = os.system(f"systemctl is-active --quiet {service}")
                status = "running" if result == 0 else "stopped"
                
                services[service] = {
                    "status": status,
                    "last_check": time.time()
                }
                
                # Actualizar en base de datos
                await db.update_service_status(service, status)
                
            except Exception as e:
                logger.warning(f"Error verificando servicio {service}: {str(e)}")
                services[service] = {
                    "status": "unknown",
                    "last_check": time.time()
                }
        
        return {
            "services": services,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de servicios: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.services_status_error", default="Error obteniendo estado de servicios")
        )

@router.get("/logs")
async def get_system_logs(
    limit: int = 100,
    level: str = None,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Obtiene logs del sistema"""
    try:
        logs = await db.get_logs(limit=limit, level=level)
        return {
            "logs": logs,
            "total": len(logs),
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.logs_error", default="Error obteniendo logs")
        )

@router.get("/config")
async def get_system_config(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene la configuración del sistema"""
    try:
        configs = {}
        
        # Obtener configuraciones de la base de datos
        common_keys = ["adblock_enabled", "monitoring_enabled", "default_language", "debug_mode"]
        
        for key in common_keys:
            value = await db.get_configuration(key)
            if value is not None:
                configs[key] = value
        
        return {
            "configurations": configs,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo configuración: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.config_error", default="Error obteniendo configuración")
        )

@router.post("/config")
async def update_system_config(
    key: str,
    value: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Actualiza la configuración del sistema"""
    try:
        success = await db.set_configuration(key, value)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=get_text("errors.config_update_error", default="Error actualizando configuración")
            )
        
        # Log del cambio de configuración
        await db.insert_log("INFO", f"Configuración actualizada: {key}={value} por {current_user['username']}")
        
        return {"message": get_text("messages.config_updated", default="Configuración actualizada exitosamente")}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando configuración: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.config_update_error", default="Error actualizando configuración")
        ) 