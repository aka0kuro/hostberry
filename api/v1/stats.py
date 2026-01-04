"""
API endpoints para estadísticas del sistema
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import time
import os
# psutil se importa lazy cuando se necesita

from core.security import get_current_active_user
from core.hostberry_logging import logger
from core.i18n import get_text

router = APIRouter()

@router.get("/{stat_type}")
async def get_stat(
    stat_type: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Obtiene estadísticas específicas del sistema
    
    Args:
        stat_type: Tipo de estadística (cpu, memory, disk, temperature, network)
        current_user: Usuario autenticado
        
    Returns:
        Diccionario con la estadística solicitada
    """
    try:
        # Lazy import de psutil
        import psutil
        
        if stat_type == "cpu":
            cpu_percent = psutil.cpu_percent(interval=1)
            return {
                "value": cpu_percent,
                "status": "healthy" if cpu_percent < 80 else "warning",
                "timestamp": time.time()
            }
        
        elif stat_type == "memory":
            memory = psutil.virtual_memory()
            status = "healthy"
            if memory.percent > 90:
                status = "danger"
            elif memory.percent > 80:
                status = "warning"
            
            return {
                "value": memory.percent,
                "status": status,
                "timestamp": time.time(),
                "details": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used
                }
            }
        
        elif stat_type == "disk":
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            status = "healthy"
            if disk_percent > 90:
                status = "danger"
            elif disk_percent > 80:
                status = "warning"
            
            return {
                "value": disk_percent,
                "status": status,
                "timestamp": time.time(),
                "details": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free
                }
            }
        
        elif stat_type == "temperature":
            temperature = None
            try:
                # Intentar leer temperatura de RPi
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp_raw = int(f.read().strip())
                    temperature = temp_raw / 1000
            except:
                # Fallback: simular temperatura
                temperature = 45.0
            
            status = "healthy"
            if temperature > 80:
                status = "danger"
            elif temperature > 70:
                status = "warning"
            
            return {
                "value": temperature,
                "status": status,
                "timestamp": time.time()
            }
        
        elif stat_type == "network":
            try:
                net_io = psutil.net_io_counters()
                return {
                    "value": "connected",
                    "status": "healthy",
                    "timestamp": time.time(),
                    "details": {
                        "bytes_sent": net_io.bytes_sent,
                        "bytes_recv": net_io.bytes_recv,
                        "packets_sent": net_io.packets_sent,
                        "packets_recv": net_io.packets_recv
                    }
                }
            except:
                return {
                    "value": "disconnected",
                    "status": "danger",
                    "timestamp": time.time()
                }
        
        else:
            raise HTTPException(status_code=404, detail=get_text("errors.stat_type_not_found", default=f"Stat type '{stat_type}' not found", stat_type=stat_type))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error('get_stat_error', stat_type=stat_type, error=str(e))
        raise HTTPException(status_code=500, detail=get_text("errors.system_stats_error", default="Error getting system statistics"))

@router.get("/")
async def get_all_stats(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Obtiene todas las estadísticas del sistema
    
    Args:
        current_user: Usuario autenticado
        
    Returns:
        Diccionario con todas las estadísticas
    """
    try:
        # Lazy import de psutil
        import psutil
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory
        memory = psutil.virtual_memory()
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        
        # Temperature
        temperature = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_raw = int(f.read().strip())
                temperature = temp_raw / 1000
        except:
            temperature = 45.0
        
        # Network
        network_status = "connected"
        try:
            net_io = psutil.net_io_counters()
        except:
            network_status = "disconnected"
        
        stats = {
            "cpu": {
                "value": cpu_percent,
                "status": "healthy" if cpu_percent < 80 else "warning"
            },
            "memory": {
                "value": memory.percent,
                "status": "healthy" if memory.percent < 80 else "warning"
            },
            "disk": {
                "value": disk_percent,
                "status": "healthy" if disk_percent < 80 else "warning"
            },
            "temperature": {
                "value": temperature,
                "status": "healthy" if temperature < 70 else "warning"
            },
            "network": {
                "value": network_status,
                "status": "healthy" if network_status == "connected" else "danger"
            },
            "timestamp": time.time()
        }
        
        logger.info('get_all_stats', stats=stats)
        return stats
    
    except Exception as e:
        logger.error('get_all_stats_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("errors.system_stats_error", default="Error getting system statistics")) 