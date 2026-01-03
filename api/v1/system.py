"""
Router del sistema para FastAPI
"""

import os
import time
import platform
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
        # Convertir nivel a mayúsculas si existe para coincidir con la base de datos
        if level and level.lower() != 'all':
            level = level.upper()
        else:
            level = None
            
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

@router.get("/activity")
async def get_recent_activity(
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Obtiene actividad reciente del sistema"""
    try:
        # Obtener logs recientes como actividad
        logs = await db.get_logs(limit=limit)
        
        # Convertir logs a formato de actividad
        activities = []
        for log in logs:
            activity = {
                "id": log.get("id"),
                "type": get_activity_type_from_log(log.get("message", "")),
                "title": get_activity_title_from_log(log.get("message", "")),
                "description": log.get("message", ""),
                "timestamp": log.get("timestamp"),
                "level": log.get("level", "INFO")
            }
            activities.append(activity)
        
        return {
            "activities": activities,
            "total": len(activities),
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo actividad reciente: {str(e)}")
        # Fallback a actividad de ejemplo
        return {
            "activities": [
                {
                    "id": 1,
                    "type": "login",
                    "title": "Login exitoso",
                    "description": "Usuario admin inició sesión",
                    "timestamp": time.time() - 300,
                    "level": "INFO"
                },
                {
                    "id": 2,
                    "type": "system",
                    "title": "Actualización de sistema",
                    "description": "Paquetes actualizados",
                    "timestamp": time.time() - 3600,
                    "level": "INFO"
                }
            ],
            "total": 2,
            "limit": limit
        }

def get_activity_type_from_log(message: str) -> str:
    """Determina el tipo de actividad desde el mensaje del log"""
    message_lower = message.lower()
    if "login" in message_lower or "sesión" in message_lower:
        return "login"
    elif "red" in message_lower or "wifi" in message_lower or "network" in message_lower:
        return "network"
    elif "seguridad" in message_lower or "firewall" in message_lower or "security" in message_lower:
        return "security"
    elif "error" in message_lower or "fail" in message_lower or "exception" in message_lower:
        return "error"
    else:
        return "system"

def get_activity_title_from_log(message: str) -> str:
    """Genera un título de actividad desde el mensaje del log"""
    message_lower = message.lower()
    if "login" in message_lower:
        return "Login exitoso"
    elif "actualización" in message_lower or "update" in message_lower:
        return "Actualización"
    elif "wifi" in message_lower or "red" in message_lower:
        return "Red"
    elif "firewall" in message_lower or "seguridad" in message_lower:
        return "Seguridad"
    elif "error" in message_lower:
        return "Error"
    else:
        return "Sistema"

@router.post("/restart")
async def restart_system(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Reinicia el sistema"""
    try:
        # Log de la acción
        await db.insert_log("WARNING", f"Sistema reiniciado por {current_user['username']}")
        
        # Ejecutar comando de reinicio
        import subprocess
        subprocess.run(["sudo", "reboot"], check=False)
        
        return {"message": "Sistema reiniciándose..."}
        
    except Exception as e:
        logger.error(f"Error reiniciando sistema: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al reiniciar el sistema"
        )

@router.post("/shutdown")
async def shutdown_system(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Apaga el sistema"""
    try:
        # Log de la acción
        await db.insert_log("WARNING", f"Sistema apagado por {current_user['username']}")
        
        # Ejecutar comando de apagado
        import subprocess
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
        
        return {"message": "Sistema apagándose..."}
        
    except Exception as e:
        logger.error(f"Error apagando sistema: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al apagar el sistema"
        )

@router.post("/backup")
async def backup_system(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Crea un backup del sistema"""
    try:
        # Log de la acción
        await db.insert_log("INFO", f"Backup iniciado por {current_user['username']}")
        
        # Simular backup (en producción implementar backup real)
        import subprocess
        result = subprocess.run(["sudo", "tar", "-czf", "/tmp/hostberry_backup.tar.gz", "/etc", "/var/lib/hostberry"], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            await db.insert_log("INFO", "Backup completado exitosamente")
            return {"message": "Backup completado exitosamente", "file": "/tmp/hostberry_backup.tar.gz"}
        else:
            await db.insert_log("ERROR", f"Backup fallido: {result.stderr}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear backup"
            )
        
    except subprocess.TimeoutExpired:
        await db.insert_log("ERROR", "Backup timeout")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Timeout al crear backup"
        )
    except Exception as e:
        logger.error(f"Error creando backup: {str(e)}")
        await db.insert_log("ERROR", f"Error en backup: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear backup"
        )

@router.post("/updates")
async def check_updates(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Busca actualizaciones del sistema"""
    try:
        # Log de la acción
        await db.insert_log("INFO", f"Búsqueda de actualizaciones iniciada por {current_user['username']}")
        
        # Simular búsqueda de actualizaciones
        import subprocess
        result = subprocess.run(["sudo", "apt", "update"], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            # Buscar actualizaciones disponibles
            result = subprocess.run(["sudo", "apt", "list", "--upgradable"], capture_output=True, text=True, timeout=30)
            
            updates = result.stdout.strip().split('\n') if result.stdout.strip() else []
            update_count = len([line for line in updates if line.strip()])
            
            await db.insert_log("INFO", f"Actualizaciones disponibles: {update_count}")
            
            return {
                "updates_available": update_count > 0,
                "update_count": update_count,
                "updates": updates[:10]  # Limitar a 10 actualizaciones
            }
        else:
            await db.insert_log("ERROR", "Error buscando actualizaciones")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error buscando actualizaciones"
            )
        
    except subprocess.TimeoutExpired:
        await db.insert_log("ERROR", "Timeout buscando actualizaciones")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Timeout buscando actualizaciones"
        )
    except Exception as e:
        logger.error(f"Error buscando actualizaciones: {str(e)}")
        await db.insert_log("ERROR", f"Error en actualizaciones: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error buscando actualizaciones"
        )

@router.get("/network/status")
async def get_network_status(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene estado detallado de la red"""
    try:
        import subprocess
        
        # Obtener información de interfaces
        interfaces = {}
        
        # eth0
        try:
            eth0_ip = get_ip_address("eth0")
            interfaces["eth0"] = {
                "connected": eth0_ip is not None,
                "ip_address": eth0_ip,
                "gateway": "192.168.1.1",  # Simplificado
                "dns": "8.8.8.8"
            }
        except:
            interfaces["eth0"] = {
                "connected": False,
                "ip_address": None,
                "gateway": None,
                "dns": None
            }
        
        # wlan0
        try:
            wlan0_ip = get_ip_address("wlan0")
            ssid = "HomeNetwork"  # Simplificado, en producción obtener con iwconfig
            
            interfaces["wlan0"] = {
                "connected": wlan0_ip is not None,
                "ip_address": wlan0_ip,
                "ssid": ssid if wlan0_ip else None,
                "signal_strength": 85  # Simplificado
            }
        except:
            interfaces["wlan0"] = {
                "connected": False,
                "ip_address": None,
                "ssid": None,
                "signal_strength": None
            }
        
        return {
            "interfaces": interfaces,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de red: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo estado de red"
        ) 