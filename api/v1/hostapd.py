"""
API endpoints para gestión de HostAPD
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
import subprocess
import json
import time
import os

from core.security import get_current_active_user
from core.hostberry_logging import logger
from config.settings import settings
from core.i18n import get_text

router = APIRouter()

def get_hostapd_status() -> Dict[str, Any]:
    """Obtiene el estado actual de HostAPD"""
    try:
        # Verificar si HostAPD está ejecutándose
        result = subprocess.run(
            ["systemctl", "is-active", "hostapd"], 
            capture_output=True, 
            text=True
        )
        
        is_running = result.stdout.strip() == "active"
        
        # Obtener configuración actual
        config = {}
        if os.path.exists(settings.hostapd_config_path):
            try:
                with open(settings.hostapd_config_path, "r") as f:
                    content = f.read()
                    
                # Parsear configuración básica
                for line in content.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
            except:
                pass
        
        return {
            "running": is_running,
            "enabled": is_running,
            "config": config
        }
    
    except Exception as e:
        logger.error('get_hostapd_status_error', error=str(e))
        return {
            "running": False,
            "enabled": False,
            "config": {}
        }

@router.get("/access-points")
async def get_access_points(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Obtiene los puntos de acceso configurados"""
    try:
        # Simular puntos de acceso
        access_points = [
            {
                "ssid": "HostBerry_AP",
                "channel": 6,
                "frequency": "2.4 GHz",
                "security": "WPA2",
                "clients": 3,
                "max_clients": 20
            },
            {
                "ssid": "HostBerry_Guest",
                "channel": 11,
                "frequency": "2.4 GHz",
                "security": "Open",
                "clients": 1,
                "max_clients": 10
            }
        ]
        
        logger.info('get_access_points', count=len(access_points))
        return access_points
    
    except Exception as e:
        logger.error('get_access_points_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("hostapd.get_access_points_error", default="Error getting access points"))

@router.get("/clients")
async def get_clients(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Obtiene los clientes conectados al punto de acceso"""
    try:
        # Obtener clientes reales desde hostapd_cli o arp
        clients = []
        try:
            from core.async_utils import run_subprocess_async
            
            # Intentar obtener desde hostapd_cli si está disponible
            returncode, stdout, stderr = await run_subprocess_async(
                ["hostapd_cli", "all_sta"],
                timeout=5
            )
            
            if returncode == 0 and stdout:
                for line in stdout.split('\n'):
                    if line.strip():
                        # Parsear salida de hostapd_cli
                        parts = line.split()
                        if len(parts) >= 1:
                            clients.append({
                                "mac": parts[0],
                                "ip": "unknown",
                                "hostname": "unknown",
                                "signal": -50,
                                "connected_time": "unknown",
                                "ssid": "HostBerry_AP"
                            })
        except Exception as e:
            logger.warning(f"No se pudieron obtener clientes reales de HostAPD: {e}")
            # Lista vacía en lugar de datos simulados
        
        logger.info('get_clients', count=len(clients))
        return clients
    
    except Exception as e:
        logger.error('get_clients_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("hostapd.get_clients_error", default="Error getting clients"))

@router.post("/toggle")
async def toggle_hostapd(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Activa/desactiva HostAPD"""
    try:
        status = get_hostapd_status()
        current_state = status.get('running', False)
        
        if current_state:
            # Detener HostAPD
            subprocess.run(["systemctl", "stop", "hostapd"], check=True)
            new_state = False
            message = "HostAPD stopped"
        else:
            # Iniciar HostAPD
            subprocess.run(["systemctl", "start", "hostapd"], check=True)
            new_state = True
            message = "HostAPD started"
        
        logger.info('toggle_hostapd', running=new_state)
        return {
            "success": True,
            "running": new_state,
            "message": message
        }
    
    except Exception as e:
        logger.error('toggle_hostapd_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("hostapd.toggle_error", default="Error toggling HostAPD"))

@router.post("/restart")
async def restart_hostapd(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Reinicia el servicio HostAPD"""
    try:
        # Reiniciar HostAPD
        subprocess.run(["systemctl", "restart", "hostapd"], check=True)
        time.sleep(2)
        
        # Verificar estado
        status = get_hostapd_status()
        
        logger.info('restart_hostapd', running=status.get('running', False))
        return {
            "success": True,
            "running": status.get('running', False),
            "message": "HostAPD restarted"
        }
    
    except Exception as e:
        logger.error('restart_hostapd_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("hostapd.restart_error", default="Error restarting HostAPD"))

@router.get("/config")
async def get_hostapd_config(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Obtiene la configuración de HostAPD"""
    try:
        config = {}
        
        if os.path.exists(settings.hostapd_config_path):
            try:
                with open(settings.hostapd_config_path, "r") as f:
                    content = f.read()
                    
                # Parsear configuración
                for line in content.split('\n'):
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
            except:
                pass
        
        # Configuración por defecto si no existe (desde base de datos o settings)
        if not config:
            from core.database import db
            from config.settings import settings
            
            # Intentar obtener desde base de datos
            ap_ssid = await db.get_configuration("hostapd_ssid")
            ap_channel = await db.get_configuration("hostapd_channel")
            ap_interface = await db.get_configuration("hostapd_interface")
            
            config = {
                "interface": ap_interface or "wlan0",
                "ssid": ap_ssid or "HostBerry_AP",
                "channel": ap_channel or "6",
                "hw_mode": "g",
                "wpa": "2",
                "wpa_passphrase": "",  # No exponer contraseña por defecto
                "wpa_key_mgmt": "WPA-PSK",
                "wpa_pairwise": "TKIP CCMP",
                "rsn_pairwise": "CCMP"
            }
        
        logger.info('get_hostapd_config')
        return {
            "config": config,
            "file_path": settings.hostapd_config_path
        }
    
    except Exception as e:
        logger.error('get_hostapd_config_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("hostapd.get_config_error", default="Error getting HostAPD config"))

@router.post("/config")
async def update_hostapd_config(
    config: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Actualiza la configuración de HostAPD"""
    try:
        # Generar configuración
        config_content = ""
        for key, value in config.items():
            config_content += f"{key}={value}\n"
        
        # Guardar configuración
        try:
            with open(settings.hostapd_config_path, "w") as f:
                f.write(config_content)
        except PermissionError:
            raise HTTPException(status_code=403, detail=get_text("hostapd.permission_denied", default="Permission denied to write HostAPD config"))
        
        # Reiniciar servicio
        try:
            subprocess.run(["systemctl", "restart", "hostapd"], check=True)
        except subprocess.CalledProcessError:
            raise HTTPException(status_code=500, detail=get_text("hostapd.restart_service_error", default="Error restarting HostAPD service"))
        
        logger.info('update_hostapd_config', config_keys=list(config.keys()))
        return {
            "success": True,
            "message": "HostAPD configuration updated"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error('update_hostapd_config_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("hostapd.update_config_error", default="Error updating HostAPD config")) 