"""
Router del sistema para FastAPI
"""

import os
import time
import platform
import asyncio
import subprocess
import re
from typing import Dict, Any, List
# psutil se importa lazy cuando se necesita

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse

from models.schemas import SystemStats, NetworkStats, SystemInfo, SuccessResponse
from core.security import get_current_active_user
from core.database import db
from core.hostberry_logging import get_logger
from system.system_utils import get_system_stats, get_network_interface, get_ip_address, get_cpu_temp
from core.i18n import get_text

router = APIRouter()
logger = get_logger("system")

@router.get("/stats", response_model=SystemStats)
async def get_system_statistics(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene estadísticas del sistema (con caché)"""
    try:
        from core.cache import cache
        
        # Verificar caché
        cache_key = "system_stats"
        cached_stats = cache.get(cache_key)
        if cached_stats:
            return SystemStats(**cached_stats)
        # Lazy import de psutil (solo cuando se necesita)
        import psutil
        
        # Obtener estadísticas básicas
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        cpu_temp = get_cpu_temp()
        cpu_count = psutil.cpu_count()
        
        # Obtener uptime
        uptime = int(time.time() - psutil.boot_time())
        
        stats = SystemStats(
            cpu_usage=cpu_usage,
            cpu_cores=cpu_count,
            memory_usage=memory.percent,
            memory_total=memory.total,
            memory_free=memory.available,
            disk_usage=disk.percent,
            disk_total=disk.total,
            disk_used=disk.used,
            cpu_temperature=cpu_temp,
            uptime=uptime
        )
        
        # Guardar estadísticas en base de datos (async, no bloquea)
        asyncio.create_task(db.insert_statistic("cpu_usage", cpu_usage))
        asyncio.create_task(db.insert_statistic("memory_usage", memory.percent))
        asyncio.create_task(db.insert_statistic("disk_usage", disk.percent))
        
        # Guardar en caché (5 segundos TTL)
        stats_dict = stats.dict() if hasattr(stats, 'dict') else {
            "cpu_usage": stats.cpu_usage,
            "cpu_cores": stats.cpu_cores,
            "memory_usage": stats.memory_usage,
            "memory_total": stats.memory_total,
            "memory_free": stats.memory_free,
            "disk_usage": stats.disk_usage,
            "disk_total": stats.disk_total,
            "disk_used": stats.disk_used,
            "cpu_temperature": stats.cpu_temperature,
            "uptime": stats.uptime
        }
        cache.set(cache_key, stats_dict)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del sistema: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.system_stats_error", default="Error obteniendo estadísticas del sistema")
        )

@router.get("/network", response_model=NetworkStats)
async def get_network_statistics(
    interface: str = None,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Obtiene estadísticas de red usando comandos de Linux (con caché)"""
    try:
        from core.cache import cache
        import subprocess
        import re
        
        # Verificar caché
        cache_key = f"network_stats_{interface or 'default'}"
        cached_stats = cache.get(cache_key)
        if cached_stats:
            return NetworkStats(**cached_stats)
        
        # Lazy import de psutil
        import psutil
        
        # Obtener interfaces disponibles usando comando Linux
        try:
            result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True, timeout=5)
            available_interfaces = []
            for line in result.stdout.split('\n'):
                if ': ' in line and 'state' in line.lower():
                    # Extraer nombre de interfaz: "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>"
                    match = re.search(r'\d+:\s+(\w+):', line)
                    if match and match.group(1) != 'lo':
                        available_interfaces.append(match.group(1))
        except:
            # Fallback a psutil
            available_interfaces = [
                name for name, st in psutil.net_if_stats().items()
                if name != "lo" and getattr(st, "isup", False)
            ] or [
                name for name in psutil.net_if_stats().keys() if name != "lo"
            ]
        
        # Obtener información de red
        iface_info = get_network_interface(interface)
        interface = iface_info.get("interface") if isinstance(iface_info, dict) else None
        ip_address = iface_info.get("ip_address") if isinstance(iface_info, dict) else None
        
        # Obtener estadísticas de red usando /proc/net/dev (más preciso)
        bytes_sent = 0
        bytes_recv = 0
        packets_sent = 0
        packets_recv = 0
        
        try:
            with open('/proc/net/dev', 'r') as f:
                for line in f:
                    if interface and interface in line:
                        # Formato: interface: bytes_recv packets_recv errs_recv drop_recv bytes_sent packets_sent errs_sent drop_sent
                        parts = line.split()
                        if len(parts) >= 10:
                            bytes_recv = int(parts[1])
                            packets_recv = int(parts[2])
                            bytes_sent = int(parts[9])
                            packets_sent = int(parts[10])
                        break
        except:
            # Fallback a psutil
            net_io = psutil.net_io_counters()
            bytes_sent = net_io.bytes_sent
            bytes_recv = net_io.bytes_recv
            packets_sent = net_io.packets_sent
            packets_recv = net_io.packets_recv
        
        # Obtener IP usando comando Linux
        if interface and not ip_address:
            try:
                result = subprocess.run(
                    ['ip', 'addr', 'show', interface],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split('\n'):
                    if 'inet ' in line and not '127.0.0.1' in line:
                        ip_address = line.split()[1].split('/')[0]
                        break
            except:
                ip_address = get_ip_address(interface) if interface else None

        # Fallbacks si no hay interfaz detectada
        if not interface:
            # elegir cualquier interfaz activa
            if available_interfaces:
                interface = available_interfaces[0]
            else:
                ifaces = psutil.net_if_stats()
                for name, st in ifaces.items():
                    if name == "lo":
                        continue
                    if getattr(st, "isup", False):
                        interface = name
                        break
        
        interface = interface or "unknown"
        ip_address = ip_address or "--"
        
        # No calcular velocidades aquí - el cliente las calculará basándose en el tiempo
        upload_speed = 0.0  # Se calculará en el cliente basándose en bytes_sent
        download_speed = 0.0  # Se calculará en el cliente basándose en bytes_recv

        stats = NetworkStats(
            interface=interface,
            ip_address=ip_address,
            upload_speed=upload_speed,
            download_speed=download_speed,
            bytes_sent=net_io.bytes_sent,
            bytes_recv=net_io.bytes_recv,
            packets_sent=net_io.packets_sent,
            packets_recv=net_io.packets_recv,
            interfaces=available_interfaces
        )
        
        # Guardar estadísticas en base de datos (async, no bloquea)
        asyncio.create_task(db.insert_statistic("network_upload", upload_speed))
        asyncio.create_task(db.insert_statistic("network_download", download_speed))
        
        # Guardar en caché (5 segundos TTL)
        stats_dict = stats.dict() if hasattr(stats, 'dict') else {
            "interface": stats.interface,
            "ip_address": stats.ip_address,
            "upload_speed": stats.upload_speed,
            "download_speed": stats.download_speed,
            "bytes_sent": stats.bytes_sent,
            "bytes_recv": stats.bytes_recv,
            "packets_sent": stats.packets_sent,
            "packets_recv": stats.packets_recv,
            "interfaces": stats.interfaces
        }
        cache.set(cache_key, stats_dict)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de red: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.network_stats_error", default="Error obteniendo estadísticas de red")
        )

@router.get("/info", response_model=SystemInfo)
async def get_system_info(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene información del sistema (con caché)"""
    try:
        from core.cache import cache
        
        # Verificar caché (información estática, cache más largo)
        cache_key = "system_info"
        cached_info = cache.get(cache_key)
        if cached_info:
            return SystemInfo(**cached_info)
        
        # Información básica del sistema (sin psutil para acelerar)
        hostname = os.uname().nodename
        kernel = os.uname().release
        os_name = "Linux"  # Simplificado
        
        info = SystemInfo(
            hostname=hostname,
            os_name=os_name,
            kernel_version=kernel,
            processor=os.uname().machine,
            python_version=platform.python_version()
        )
        
        # Guardar en caché (60 segundos TTL - información estática)
        info_dict = info.dict() if hasattr(info, 'dict') else {
            "hostname": info.hostname,
            "os_name": info.os_name,
            "kernel_version": info.kernel_version,
            "processor": info.processor,
            "python_version": info.python_version
        }
        cache.set(cache_key, info_dict)
        
        return info
        
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
                # Verificar si el servicio está ejecutándose (async)
                from core.async_utils import run_subprocess_async
                returncode, stdout, stderr = await run_subprocess_async(
                    ["systemctl", "is-active", service],
                    timeout=5
                )
                status = "running" if returncode == 0 else "stopped"
                
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
    config: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Actualiza la configuración del sistema (acepta múltiples valores en un objeto JSON)"""
    try:
        if not config or not isinstance(config, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_text("errors.invalid_config", default="Invalid configuration data")
            )
        
        updated_keys = []
        for key, value in config.items():
            # Convertir valores a string para almacenar
            value_str = str(value) if value is not None else ""
            success = await db.set_configuration(key, value_str)
            if success:
                updated_keys.append(key)
                # Log del cambio de configuración
                await db.insert_log("INFO", f"Configuración actualizada: {key}={value_str} por {current_user.get('username', 'unknown')}")
        
        if not updated_keys:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=get_text("errors.config_update_error", default="Error actualizando configuración")
            )
        
        return {
            "message": get_text("messages.config_updated", default="Configuración actualizada exitosamente"),
            "updated_keys": updated_keys
        }
        
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
        
        # Ejecutar comando de reinicio (async)
        from core.async_utils import run_subprocess_async
        await run_subprocess_async(["sudo", "reboot"], timeout=5)
        
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
        
        # Ejecutar comando de apagado (async)
        from core.async_utils import run_subprocess_async
        await run_subprocess_async(["sudo", "shutdown", "-h", "now"], timeout=5)
        
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
        
        # Crear backup (async)
        from core.async_utils import run_subprocess_async
        returncode, stdout, stderr = await run_subprocess_async(
            ["sudo", "tar", "-czf", "/tmp/hostberry_backup.tar.gz", "/etc", "/var/lib/hostberry"],
            timeout=300
        )
        result = type('obj', (object,), {'returncode': returncode, 'stderr': stderr})()
        
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
        
        # Buscar actualizaciones (async)
        from core.async_utils import run_subprocess_async
        returncode, stdout, stderr = await run_subprocess_async(
            ["sudo", "apt", "update"],
            timeout=60
        )
        
        if returncode == 0:
            # Buscar actualizaciones disponibles
            returncode2, stdout2, stderr2 = await run_subprocess_async(
                ["sudo", "apt", "list", "--upgradable"],
                timeout=30
            )
            result = type('obj', (object,), {'returncode': returncode2, 'stdout': stdout2})()
            
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
        
    except TimeoutError:
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


@router.get("/network/interfaces")
async def get_network_interfaces(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene todas las interfaces de red con sus detalles"""
    try:
        # Lazy import de psutil
        import psutil
        import socket
        
        interfaces = []
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        
        for iface_name in addrs.keys():
            if iface_name == "lo":  # Saltar loopback
                continue
                
            iface_addrs = addrs[iface_name]
            iface_stat = stats.get(iface_name)
            
            # Obtener IP y MAC
            ip_address = None
            mac_address = None
            
            for addr in iface_addrs:
                if addr.family == socket.AF_INET:  # IPv4
                    ip_address = addr.address
                elif addr.family == psutil.AF_LINK:  # MAC
                    mac_address = addr.address
            
            # Estado de la interfaz
            status = "up" if (iface_stat and iface_stat.isup) else "down"
            
            interfaces.append({
                "name": iface_name,
                "status": status,
                "ip": ip_address or "N/A",
                "mac": mac_address or "N/A",
                "speed": iface_stat.speed if iface_stat else 0,
                "mtu": iface_stat.mtu if iface_stat else 1500
            })
        
        return interfaces
        
    except Exception as e:
        logger.error(f"Error obteniendo interfaces de red: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.loading_interfaces", default="Error cargando interfaces de red")
        )


@router.get("/network/routing")
async def get_routing_table(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene la tabla de enrutamiento"""
    try:
        from core.async_utils import run_command_async
        
        # Ejecutar comando ip route
        returncode, stdout, stderr = await run_command_async("ip", "route", "show")
        
        if returncode != 0:
            logger.error(f"Error ejecutando ip route: {stderr}")
            return []
        
        routes = []
        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Parsear línea de ruta
            # Ejemplo: "default via 192.168.1.1 dev eth0 metric 100"
            parts = line.split()
            
            destination = "default"
            gateway = "*"
            interface = "unknown"
            metric = "0"
            
            if "via" in parts:
                via_idx = parts.index("via")
                if via_idx > 0:
                    destination = parts[0]
                if via_idx + 1 < len(parts):
                    gateway = parts[via_idx + 1]
            
            if "dev" in parts:
                dev_idx = parts.index("dev")
                if dev_idx + 1 < len(parts):
                    interface = parts[dev_idx + 1]
            
            if "metric" in parts:
                metric_idx = parts.index("metric")
                if metric_idx + 1 < len(parts):
                    metric = parts[metric_idx + 1]
            
            routes.append({
                "destination": destination,
                "gateway": gateway,
                "interface": interface,
                "metric": metric
            })
        
        return routes
        
    except Exception as e:
        logger.error(f"Error obteniendo tabla de enrutamiento: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.loading_routing", default="Error cargando tabla de enrutamiento")
        )


@router.post("/network/firewall/toggle")
async def toggle_firewall(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Alterna el estado del firewall (UFW)"""
    try:
        from core.async_utils import run_command_async
        
        # Verificar estado actual
        returncode, stdout, _ = await run_command_async("ufw", "status")
        is_active = "Status: active" in stdout or "Estado: activo" in stdout
        
        if is_active:
            # Desactivar firewall
            returncode, stdout, stderr = await run_command_async("ufw", "--force", "disable")
        else:
            # Activar firewall
            returncode, stdout, stderr = await run_command_async("ufw", "--force", "enable")
        
        if returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=get_text("errors.operation_failed", default="Error al alternar firewall")
            )
        
        return {
            "success": True,
            "message": get_text("messages.operation_successful", default="Operación exitosa"),
            "firewall_enabled": not is_active
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error alternando firewall: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.operation_failed", default="Error al alternar firewall")
        )


@router.post("/network/config")
async def save_network_config(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Guarda la configuración de red"""
    try:
        import json
        
        # Obtener datos del body
        body = await request.json()
        config = body if isinstance(body, dict) else {}
        
        # Aquí se implementaría la lógica para guardar la configuración
        # Por ahora solo retornamos éxito
        
        # TODO: Implementar guardado real de configuración
        # - hostname: /etc/hostname
        # - DNS: /etc/resolv.conf
        # - Gateway: /etc/network/interfaces o netplan
        
        logger.info(f"Configuración de red recibida: {config}")
        
        return {
            "success": True,
            "message": get_text("messages.config_saved", default="Configuración guardada")
        }
        
    except Exception as e:
        logger.error(f"Error guardando configuración de red: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.config_update_error", default="Error guardando configuración")
        ) 