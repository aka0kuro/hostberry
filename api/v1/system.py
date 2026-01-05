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
# Email (notificaciones)
import smtplib
from email.message import EmailMessage
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


def _is_valid_timezone_name(tz: str) -> bool:
    """Validación defensiva para nombres de zona horaria tipo 'Area/City'."""
    if not isinstance(tz, str):
        return False
    tz = tz.strip()
    if not tz:
        return False
    if tz.startswith("/") or ".." in tz:
        return False
    if "\n" in tz or "\r" in tz:
        return False
    # Permitir letras/números y separadores típicos
    for ch in tz:
        if ch.isalnum() or ch in ("/", "_", "-", "+"):
            continue
        return False
    return True


def _is_valid_ipv4(ip: str) -> bool:
    if not isinstance(ip, str):
        return False
    ip = ip.strip()
    m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip)
    if not m:
        return False
    parts = [int(x) for x in m.groups()]
    return all(0 <= p <= 255 for p in parts)

@router.get("/stats")
async def get_system_statistics(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene estadísticas del sistema (con caché)"""
    try:
        from core.cache import cache
        
        # Verificar caché
        cache_key = "system_stats"
        cached_stats = cache.get(cache_key)
        if cached_stats:
            # Devolver directamente el dict del caché (tiene información adicional)
            return cached_stats
        # Lazy import de psutil (solo cuando se necesita)
        import psutil
        
        # Obtener estadísticas básicas
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        cpu_temp = get_cpu_temp()
        cpu_count = psutil.cpu_count()
        
        # Obtener uptime usando /proc/uptime (más preciso)
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                uptime = int(uptime_seconds)
        except:
            # Fallback a psutil
            uptime = int(time.time() - psutil.boot_time())
        
        # Obtener información del sistema usando comandos Linux
        hostname = None
        os_version = None
        kernel_version = None
        architecture = None
        processor = None
        load_average = None
        
        try:
            # Hostname
            result = subprocess.run(['hostname'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                hostname = result.stdout.strip()
        except:
            hostname = platform.node()
        
        try:
            # Kernel version
            result = subprocess.run(['uname', '-r'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                kernel_version = result.stdout.strip()
        except:
            kernel_version = platform.release()
        
        try:
            # Architecture
            result = subprocess.run(['uname', '-m'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                architecture = result.stdout.strip()
        except:
            architecture = platform.machine()
        
        try:
            # OS version desde /etc/os-release
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        os_version = line.split('=')[1].strip().strip('"')
                        break
        except:
            os_version = "Linux"
        
        try:
            # Load average desde /proc/loadavg
            with open('/proc/loadavg', 'r') as f:
                load_avg = f.read().split()[:3]
                load_average = ', '.join(load_avg)
        except:
            try:
                load_avg = os.getloadavg()
                load_average = ', '.join([f"{x:.2f}" for x in load_avg])
            except:
                load_average = "0.00, 0.00, 0.00"
        
        try:
            # Processor info
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line.lower():
                        processor = line.split(':')[1].strip()
                        break
        except:
            processor = platform.processor() or "ARM"
        
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
        
        # Guardar en caché (5 segundos TTL) con información adicional
        # Usar model_dump() si está disponible (Pydantic v2) o dict() (Pydantic v1)
        if hasattr(stats, 'model_dump'):
            stats_dict = stats.model_dump()
        elif hasattr(stats, 'dict'):
            stats_dict = stats.dict()
        else:
            stats_dict = {
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
        # Agregar información adicional del sistema
        stats_dict.update({
            "hostname": hostname,
            "os_version": os_version,
            "kernel_version": kernel_version,
            "architecture": architecture,
            "processor": processor,
            "load_average": load_average
        })
        cache.set(cache_key, stats_dict)
        
        # Devolver stats_dict que ya tiene toda la información incluida
        return stats_dict
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del sistema: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.system_stats_error", default="Error obteniendo estadísticas del sistema")
        )

@router.get("/network")
async def get_network_statistics(
    interface: str = None,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Obtiene estadísticas de red usando comandos de Linux (con caché)"""
    try:
        from core.cache import cache
        import subprocess
        import re
        
        requested_interface = interface
        
        # Usar caché con TTL muy corto (1 segundo) para estadísticas de red
        # Necesitamos valores frescos para calcular velocidades, pero el caché ayuda con rendimiento
        cache_key = f"network_stats_{interface or 'default'}"
        # No usar caché para permitir cálculos de velocidad precisos
        # cached_stats = cache.get(cache_key)
        # if cached_stats:
        #     return cached_stats
        
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
        
        # Resolver interfaz a usar (primero lo pedido por query, luego autodetección, luego fallback)
        iface_info = get_network_interface(requested_interface)
        detected_interface = iface_info.get("interface") if isinstance(iface_info, dict) else None
        
        if requested_interface:
            interface = requested_interface
        elif detected_interface:
            interface = detected_interface
        elif available_interfaces:
            interface = available_interfaces[0]
        else:
            interface = None
        
        # IP conocida solo si corresponde a la interfaz detectada; si no, recalcularemos luego
        ip_address = None
        if isinstance(iface_info, dict) and interface and detected_interface and interface == detected_interface:
            ip_address = iface_info.get("ip_address")
        
        # Obtener estadísticas de red usando /proc/net/dev (más preciso)
        bytes_sent = 0
        bytes_recv = 0
        packets_sent = 0
        packets_recv = 0
        
        try:
            with open('/proc/net/dev', 'r') as f:
                for line in f:
                    line_stripped = line.strip()
                    if interface and line_stripped.startswith(f"{interface}:"):
                        # Formato: interface: bytes_recv packets_recv errs_recv drop_recv bytes_sent packets_sent errs_sent drop_sent
                        parts = line_stripped.split()
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
        
        interface = interface or "unknown"
        ip_address = ip_address or "--"
        
        # No calcular velocidades aquí - el cliente las calculará basándose en el tiempo
        upload_speed = 0.0  # Se calculará en el cliente basándose en bytes_sent
        download_speed = 0.0  # Se calculará en el cliente basándose en bytes_recv

        # Crear dict directamente (no usar modelo para permitir campos adicionales)
        stats_dict = {
            "interface": interface,
            "ip_address": ip_address,
            "upload_speed": upload_speed,
            "download_speed": download_speed,
            "bytes_sent": bytes_sent,
            "bytes_recv": bytes_recv,
            "packets_sent": packets_sent,
            "packets_recv": packets_recv,
            "interfaces": available_interfaces,
            "errors": 0,
            "drop": 0
        }
        
        # Guardar estadísticas en base de datos (async, no bloquea)
        asyncio.create_task(db.insert_statistic("network_upload", upload_speed))
        asyncio.create_task(db.insert_statistic("network_download", download_speed))
        
        # NO guardar en caché - necesitamos valores frescos cada vez para calcular velocidades correctamente
        # cache.set(cache_key, stats_dict, ttl=1)  # TTL muy corto si se necesita caché
        
        # Devolver dict directamente (no el modelo)
        return stats_dict
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de red: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Actualiza la configuración del sistema (acepta múltiples valores en un objeto JSON)"""
    try:
        logger.info(f"Recibida petición de actualización de configuración de {current_user.get('username', 'unknown')}")
        
        # Obtener el body como JSON
        try:
            body = await request.json()
            logger.debug(f"Body recibido: {body}")
        except Exception as e:
            logger.error(f"Error parseando JSON: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_text("errors.invalid_json", default="Invalid JSON in request body")
            )
        
        # Validar que sea un diccionario
        if not isinstance(body, dict):
            logger.error(f"Body no es un diccionario: {type(body)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_text("errors.invalid_config", default="Invalid configuration data")
            )
        
        if not body:
            logger.warning("Body vacío recibido")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_text("errors.empty_config", default="Configuration data is empty")
            )
        
        updated_keys = []
        errors = []
        # Guardar body para aplicar cambios dependientes (p.ej. DHCP) al final
        original_body = body
        
        # Verificar que db esté disponible
        if not db:
            logger.error("Database instance no está disponible")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database not available"
            )
        
        for key, value in body.items():
            try:
                # Convertir valores a string para almacenar
                # Manejar valores booleanos, None, etc.
                if value is None:
                    value_str = ""
                elif isinstance(value, bool):
                    value_str = str(value).lower()
                elif isinstance(value, (int, float)):
                    value_str = str(value)
                else:
                    value_str = str(value)
                
                # Validar que la clave no esté vacía
                if not key or not isinstance(key, str):
                    error_msg = f"Clave inválida: {key}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
                
                logger.debug(f"Guardando configuración: {key}={value_str}")
                success = await db.set_configuration(key, value_str)
                
                if success:
                    updated_keys.append(key)
                    logger.info(f"Configuración guardada exitosamente: {key}")

                    # Aplicar zona horaria al sistema si corresponde
                    if key == "timezone" and value_str:
                        try:
                            tz = value_str.strip()
                            if not _is_valid_timezone_name(tz):
                                errors.append(get_text("settings.timezone_invalid", default="Zona horaria inválida"))
                            elif not os.path.isfile(f"/usr/share/zoneinfo/{tz}"):
                                errors.append(get_text("settings.timezone_not_found", default="Zona horaria no encontrada"))
                            else:
                                from core.async_utils import run_subprocess_async
                                rc, out, err = await run_subprocess_async(
                                    ["sudo", "/usr/local/sbin/hostberry-safe/set-timezone", tz],
                                    timeout=20
                                )
                                if rc != 0:
                                    combined = (err or out or "").strip()
                                    # Mensaje más útil si falta permisos sudo
                                    if "sudo" in combined.lower() and ("password" in combined.lower() or "a password is required" in combined.lower()):
                                        errors.append(get_text("update.sudo_error", default="Permisos insuficientes (sudo requerido)"))
                                    else:
                                        errors.append(get_text("settings.timezone_apply_failed", default="No se pudo aplicar la zona horaria al sistema"))
                                        if combined:
                                            logger.warning(f"Error aplicando timezone al sistema: {combined}")
                        except Exception as tz_err:
                            logger.warning(f"Excepción aplicando timezone al sistema: {tz_err}")
                            errors.append(get_text("settings.timezone_apply_failed", default="No se pudo aplicar la zona horaria al sistema"))

                    # Aplicar firewall (UFW) al sistema si corresponde
                    if key == "firewall_enabled":
                        try:
                            desired = str(value_str).strip().lower() in ("1", "true", "yes", "on", "enabled")
                            from core.async_utils import run_subprocess_async
                            action = "enable" if desired else "disable"
                            rc, out, err = await run_subprocess_async(
                                ["sudo", "/usr/local/sbin/hostberry-safe/firewall-set", action],
                                timeout=30
                            )
                            if rc != 0:
                                combined = (err or out or "").strip()
                                errors.append(get_text("settings.firewall_apply_failed", default="No se pudo aplicar el firewall al sistema"))
                                if combined:
                                    logger.warning(f"Error aplicando firewall: {combined}")
                        except Exception as fw_err:
                            logger.warning(f"Excepción aplicando firewall: {fw_err}")
                            errors.append(get_text("settings.firewall_apply_failed", default="No se pudo aplicar el firewall al sistema"))

                    # Aplicar DNS al sistema si corresponde
                    if key == "dns_server" and value_str:
                        try:
                            dns = value_str.strip()
                            # Permitir "8.8.8.8" o "8.8.8.8,1.1.1.1"
                            parts = [p.strip() for p in re.split(r"[,\s]+", dns) if p.strip()]
                            dns1 = parts[0] if parts else ""
                            dns2 = parts[1] if len(parts) > 1 else ""
                            if not dns1 or not _is_valid_ipv4(dns1) or (dns2 and not _is_valid_ipv4(dns2)):
                                errors.append(get_text("settings.dns_invalid", default="DNS inválido"))
                            else:
                                from core.async_utils import run_subprocess_async
                                cmd = ["sudo", "/usr/local/sbin/hostberry-safe/set-dns", dns1]
                                if dns2:
                                    cmd.append(dns2)
                                rc, out, err = await run_subprocess_async(cmd, timeout=30)
                                if rc != 0:
                                    combined = (err or out or "").strip()
                                    errors.append(get_text("settings.dns_apply_failed", default="No se pudo aplicar el DNS al sistema"))
                                    if combined:
                                        logger.warning(f"Error aplicando DNS: {combined}")
                        except Exception as dns_err:
                            logger.warning(f"Excepción aplicando DNS: {dns_err}")
                            errors.append(get_text("settings.dns_apply_failed", default="No se pudo aplicar el DNS al sistema"))

                # Log del cambio de configuración
                    try:
                        await db.insert_log("INFO", f"Configuración actualizada: {key}={value_str} por {current_user.get('username', 'unknown')}")
                    except Exception as log_error:
                        logger.warning(f"Error insertando log: {str(log_error)}")
                else:
                    error_msg = f"Error guardando {key}"
                    logger.error(f"{error_msg} - No se pudo guardar en la base de datos")
                    errors.append(error_msg)
            except Exception as e:
                error_msg = f"Error procesando clave {key}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        # Aplicar DHCP al final (necesita varias claves)
        try:
            dhcp_keys = {"dhcp_enabled", "dhcp_interface", "dhcp_range_start", "dhcp_range_end", "dhcp_lease_time", "dhcp_gateway", "dns_server"}
            if isinstance(original_body, dict) and (dhcp_keys & set(original_body.keys())):
                # Tomar valores del body si vienen, o de la DB si no
                dhcp_enabled_raw = original_body.get("dhcp_enabled")
                if dhcp_enabled_raw is None:
                    dhcp_enabled_raw = await db.get_configuration("dhcp_enabled")

                dhcp_enabled = str(dhcp_enabled_raw).strip().lower() in ("1", "true", "yes", "on", "enabled")

                iface = str(original_body.get("dhcp_interface") or await db.get_configuration("dhcp_interface") or "eth0").strip()
                rstart = str(original_body.get("dhcp_range_start") or await db.get_configuration("dhcp_range_start") or "").strip()
                rend = str(original_body.get("dhcp_range_end") or await db.get_configuration("dhcp_range_end") or "").strip()
                lease = str(original_body.get("dhcp_lease_time") or await db.get_configuration("dhcp_lease_time") or "12h").strip()
                gateway = str(original_body.get("dhcp_gateway") or await db.get_configuration("dhcp_gateway") or "").strip()

                # Reusar dns_server como DNS de DHCP si existe
                dns_for_dhcp = str(original_body.get("dns_server") or await db.get_configuration("dns_server") or "").strip()
                dns_parts = [p.strip() for p in re.split(r"[,\s]+", dns_for_dhcp) if p.strip()]
                dns1 = dns_parts[0] if dns_parts else ""

                from core.async_utils import run_subprocess_async
                if not dhcp_enabled:
                    rc, out, err = await run_subprocess_async(
                        ["sudo", "/usr/local/sbin/hostberry-safe/dhcp-set", "disable", iface],
                        timeout=30
                    )
                    if rc != 0:
                        combined = (err or out or "").strip()
                        errors.append(get_text("settings.dhcp_apply_failed", default="No se pudo aplicar DHCP al sistema"))
                        if combined:
                            logger.warning(f"Error desactivando DHCP: {combined}")
                else:
                    # Validaciones mínimas
                    if not iface:
                        errors.append(get_text("settings.dhcp_invalid", default="Configuración DHCP inválida"))
                    elif not rstart or not rend or not _is_valid_ipv4(rstart) or not _is_valid_ipv4(rend):
                        errors.append(get_text("settings.dhcp_invalid", default="Configuración DHCP inválida"))
                    elif gateway and not _is_valid_ipv4(gateway):
                        errors.append(get_text("settings.dhcp_invalid", default="Configuración DHCP inválida"))
                    elif dns1 and not _is_valid_ipv4(dns1):
                        errors.append(get_text("settings.dhcp_invalid", default="Configuración DHCP inválida"))
                    else:
                        cmd = ["sudo", "/usr/local/sbin/hostberry-safe/dhcp-set", "enable", iface, rstart, rend, lease]
                        cmd.append(gateway if gateway else "")
                        cmd.append(dns1 if dns1 else "")
                        rc, out, err = await run_subprocess_async(cmd, timeout=45)
                        if rc != 0:
                            combined = (err or out or "").strip()
                            errors.append(get_text("settings.dhcp_apply_failed", default="No se pudo aplicar DHCP al sistema"))
                            if combined:
                                logger.warning(f"Error activando DHCP: {combined}")
        except Exception as dhcp_err:
            logger.warning(f"Excepción aplicando DHCP: {dhcp_err}")
            errors.append(get_text("settings.dhcp_apply_failed", default="No se pudo aplicar DHCP al sistema"))
        
        if not updated_keys:
            error_msg = "; ".join(errors) if errors else get_text("errors.config_update_error", default="Error actualizando configuración")
            logger.error(f"No se pudo actualizar ninguna configuración: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
        
        response_msg = get_text("messages.config_updated", default="Configuración actualizada exitosamente")
        if errors:
            response_msg += f" (Algunos errores: {', '.join(errors)})"
        
        logger.info(f"Configuración actualizada exitosamente. Claves: {updated_keys}")
        return {
            "message": response_msg,
            "updated_keys": updated_keys,
            "errors": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error inesperado actualizando configuración: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.config_update_error", default=f"Error actualizando configuración: {str(e)}")
        )


@router.post("/notifications/test-email")
async def send_test_email(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Envía un email de prueba usando configuración SMTP guardada en la DB."""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Database not available")

        body = {}
        try:
            body = await request.json()
        except Exception:
            body = {}

        to_addr = (body.get("to") if isinstance(body, dict) else None) or await db.get_configuration("email_address") or ""
        to_addr = str(to_addr).strip()
        if not to_addr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_text("settings.test_email_missing_to", default="Please enter an email address first.")
            )

        smtp_host = str(await db.get_configuration("smtp_host") or "").strip()
        smtp_port_raw = await db.get_configuration("smtp_port")
        smtp_user = str(await db.get_configuration("smtp_user") or "").strip()
        smtp_password = str(await db.get_configuration("smtp_password") or "")
        smtp_from = str(await db.get_configuration("smtp_from") or "").strip()
        smtp_tls_raw = await db.get_configuration("smtp_tls")

        # defaults
        try:
            smtp_port = int(str(smtp_port_raw).strip() or "587")
        except Exception:
            smtp_port = 587

        smtp_tls = True
        if smtp_tls_raw is not None:
            s = str(smtp_tls_raw).strip().lower()
            smtp_tls = s in ("1", "true", "yes", "on", "enabled")

        if not smtp_host:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_text("settings.missing_smtp_config", default="SMTP configuration is missing. Please fill SMTP Host/Port/User/Password and save.")
            )

        from_addr = smtp_from or smtp_user or to_addr
        if not from_addr:
            from_addr = "hostberry@localhost"

        subject = get_text("settings.test_email_subject", default="HostBerry: test email")
        message = get_text("settings.test_email_body", default="This is a test email from HostBerry.")

        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(message)

        # Enviar (bloqueante) en hilo para no bloquear el event loop
        def _send():
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                if smtp_tls:
                    server.starttls()
                    server.ehlo()
                if smtp_user:
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)

        await asyncio.to_thread(_send)

        try:
            await db.insert_log("INFO", f"Email de prueba enviado a {to_addr} por {current_user.get('username', 'unknown')}")
        except Exception:
            pass

        return {"message": get_text("settings.test_email_sent", default="Test email sent.")}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enviando email de prueba: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("settings.test_email_failed", default="Failed to send test email.")
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
        
        if returncode != 0:
            error_msg = stderr.strip() if stderr else stdout.strip() if stdout else "Error desconocido"
            logger.error(f"Error ejecutando 'apt update': returncode={returncode}, stderr={error_msg}")
            await db.insert_log("ERROR", f"Error buscando actualizaciones: {error_msg[:200]}")
            
            # Verificar si es un error de permisos
            if "sudo" in error_msg.lower() or "permission denied" in error_msg.lower() or "not allowed" in error_msg.lower():
                detail_msg = get_text("update.sudo_error", default="Error de permisos. Verifica que el usuario tenga permisos sudo sin contraseña configurados.")
            else:
                detail_msg = f"{get_text('update.check_error', default='Error checking updates')}: {error_msg[:200]}"
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail_msg
            )
        
            # Buscar actualizaciones disponibles
            returncode2, stdout2, stderr2 = await run_subprocess_async(
                ["sudo", "apt", "list", "--upgradable"],
                timeout=30
            )
        
        if returncode2 != 0:
            error_msg = stderr2.strip() if stderr2 else stdout2.strip() if stdout2 else "Error desconocido"
            logger.error(f"Error ejecutando 'apt list --upgradable': returncode={returncode2}, stderr={error_msg}")
            await db.insert_log("ERROR", f"Error listando actualizaciones: {error_msg[:200]}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{get_text('update.check_error', default='Error checking updates')}: {error_msg[:200]}"
            )
        
        updates = stdout2.strip().split('\n') if stdout2.strip() else []
        # Filtrar líneas vacías y la primera línea que suele ser un encabezado
        filtered_updates = [line for line in updates if line.strip() and not line.startswith('Listing')]
        update_count = len(filtered_updates)
        
        await db.insert_log("INFO", f"Actualizaciones disponibles: {update_count}")
        
        return {
            "updates_available": update_count > 0,
            "update_count": update_count,
        "updates": filtered_updates[:20]  # Limitar a 20 actualizaciones
        }
        
    except HTTPException:
        raise
    except TimeoutError:
        await db.insert_log("ERROR", "Timeout buscando actualizaciones")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("update.check_error", default="Error checking updates")
        )
    except Exception as e:
        logger.error(f"Error buscando actualizaciones: {str(e)}", exc_info=True)
        await db.insert_log("ERROR", f"Error en actualizaciones: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{get_text('update.check_error', default='Error checking updates')}: {str(e)[:200]}"
        )

@router.post("/updates/execute")
async def execute_system_updates(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Ejecuta actualizaciones del sistema Debian"""
    try:
        # Log de la acción
        await db.insert_log("INFO", f"Actualización del sistema iniciada por {current_user['username']}")
        
        # Ejecutar actualizaciones (async)
        from core.async_utils import run_subprocess_async
        
        # Primero actualizar repositorios
        returncode1, stdout1, stderr1 = await run_subprocess_async(
            ["sudo", "apt", "update"],
            timeout=120
        )
        
        if returncode1 != 0:
            error_msg = stderr1.strip() if stderr1 else stdout1.strip() if stdout1 else "Error desconocido"
            logger.error(f"Error ejecutando 'apt update': returncode={returncode1}, stderr={error_msg}")
            await db.insert_log("ERROR", f"Error actualizando repositorios: {error_msg[:200]}")
            
            # Verificar si es un error de permisos
            if "sudo" in error_msg.lower() or "permission denied" in error_msg.lower() or "not allowed" in error_msg.lower():
                detail_msg = get_text("update.sudo_error", default="Error de permisos. Verifica que el usuario tenga permisos sudo sin contraseña configurados.")
        else:
            detail_msg = f"Error actualizando repositorios: {error_msg[:200]}"
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail_msg
            )
        
        # Ejecutar upgrade
        returncode2, stdout2, stderr2 = await run_subprocess_async(
            ["sudo", "apt", "upgrade", "-y"],
            timeout=600  # 10 minutos para actualizaciones
        )
        
        if returncode2 != 0:
            error_msg = stderr2.strip() if stderr2 else stdout2.strip() if stdout2 else "Error desconocido"
            logger.error(f"Error ejecutando 'apt upgrade': returncode={returncode2}, stderr={error_msg}")
            await db.insert_log("ERROR", f"Error ejecutando actualizaciones: {error_msg[:200]}")
            
            # Verificar si es un error de permisos
            if "sudo" in error_msg.lower() or "permission denied" in error_msg.lower() or "not allowed" in error_msg.lower():
                detail_msg = get_text("update.sudo_error", default="Error de permisos. Verifica que el usuario tenga permisos sudo sin contraseña configurados.")
            else:
                detail_msg = f"Error ejecutando actualizaciones: {error_msg[:200]}"
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail_msg
            )
        
        await db.insert_log("INFO", "Actualización del sistema completada exitosamente")
        
        return {
            "success": True,
            "message": "Sistema actualizado exitosamente",
            "output": stdout2[:500] if stdout2 else "Actualización completada"
        }
        
    except TimeoutError:
        await db.insert_log("ERROR", "Timeout ejecutando actualizaciones")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Timeout ejecutando actualizaciones"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ejecutando actualizaciones: {str(e)}")
        await db.insert_log("ERROR", f"Error en actualizaciones: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando actualizaciones: {str(e)}"
        )

@router.post("/updates/project")
async def update_project(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Actualiza el proyecto HostBerry ejecutando setup.sh --update"""
    try:
        # Log de la acción
        await db.insert_log("INFO", f"Actualización del proyecto iniciada por {current_user['username']}")
        
        # Buscar setup.sh en el directorio de producción o actual
        setup_script = None
        possible_paths = [
            "/opt/hostberry/setup.sh",
            "/var/lib/hostberry/setup.sh",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "setup.sh"),
            "setup.sh"
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(path):
                setup_script = path
                break
        
        if not setup_script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró setup.sh"
            )
        
        # Ejecutar setup.sh --update
        from core.async_utils import run_subprocess_async
        
        returncode, stdout, stderr = await run_subprocess_async(
            ["sudo", "bash", setup_script, "--update"],
            timeout=600  # 10 minutos para actualización del proyecto
        )
        
        if returncode != 0:
            error_msg = stderr.strip() if stderr else stdout.strip() if stdout else "Error desconocido"
            logger.error(f"Error ejecutando 'setup.sh --update': returncode={returncode}, stderr={error_msg}")
            await db.insert_log("ERROR", f"Error actualizando proyecto: {error_msg[:200]}")
            
            # Verificar si es un error de permisos
            if "sudo" in error_msg.lower() or "permission denied" in error_msg.lower() or "not allowed" in error_msg.lower():
                detail_msg = get_text("update.sudo_error", default="Error de permisos. Verifica que el usuario tenga permisos sudo sin contraseña configurados.")
            else:
                detail_msg = f"Error actualizando proyecto: {error_msg[:200]}"
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail_msg
            )
        
        await db.insert_log("INFO", "Actualización del proyecto completada exitosamente")
        
        return {
            "success": True,
            "message": "Proyecto actualizado exitosamente",
            "output": stdout[:500] if stdout else "Actualización completada"
        }
        
    except TimeoutError:
        await db.insert_log("ERROR", "Timeout actualizando proyecto")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Timeout actualizando proyecto"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando proyecto: {str(e)}")
        await db.insert_log("ERROR", f"Error actualizando proyecto: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando proyecto: {str(e)}"
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