"""
API endpoints para gestión de WiFi
"""

from fastapi import APIRouter, HTTPException, Depends, Form
from typing import Dict, Any, List, Optional
import subprocess
import json
import re
import time
import os

from core.security import get_current_active_user
from core.hostberry_logging import logger
from config.settings import settings
from core.i18n import get_text

router = APIRouter()

def get_wifi_status() -> Dict[str, Any]:
    """Obtiene el estado actual de WiFi"""
    try:
        # Verificar si WiFi está habilitado
        result = subprocess.run(
            ["rfkill", "list", "wifi"], 
            capture_output=True, 
            text=True
        )
        
        wifi_enabled = "unblocked" in result.stdout
        
        # Obtener interfaz WiFi activa
        result = subprocess.run(
            ["iwconfig"], 
            capture_output=True, 
            text=True
        )
        
        interfaces = []
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'IEEE' in line:
                    interface = line.split()[0]
                    interfaces.append(interface)
        
        # Obtener redes disponibles
        networks = []
        if interfaces:
            result = subprocess.run(
                ["iwlist", interfaces[0], "scan"], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                # Parsear redes
                for line in result.stdout.split('\n'):
                    if 'ESSID:' in line:
                        ssid = line.split('"')[1] if '"' in line else line.split(':')[1].strip()
                        if ssid and ssid != '""':
                            networks.append({"ssid": ssid, "signal": -50})
        
        return {
            "enabled": wifi_enabled,
            "interfaces": interfaces,
            "networks": networks,
            "connected": len(interfaces) > 0
        }
    
    except Exception as e:
        logger.error('get_wifi_status_error', error=str(e))
        return {
            "enabled": False,
            "interfaces": [],
            "networks": [],
            "connected": False
        }

@router.get("/status")
async def wifi_status(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Obtiene el estado actual de WiFi"""
    try:
        status = get_wifi_status()
        logger.info('wifi_status', status=status)
        return status
    
    except Exception as e:
        logger.error('wifi_status_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.status_error", default="Error obteniendo estado de WiFi"))

@router.get("/networks")
async def get_networks(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Obtiene las redes WiFi disponibles"""
    try:
        status = get_wifi_status()
        logger.info('get_networks', count=len(status.get('networks', [])))
        return status.get('networks', [])
    
    except Exception as e:
        logger.error('get_networks_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.networks_error", default="Error obteniendo redes WiFi"))

@router.get("/clients")
async def get_clients(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Obtiene los clientes conectados a WiFi"""
    try:
        # Obtener clientes reales desde el sistema
        clients = []
        try:
            # Intentar obtener clientes desde arp o dhcp leases (async)
            from core.async_utils import run_subprocess_async
            returncode, stdout, stderr = await run_subprocess_async(
                ["arp", "-a"],
                timeout=5
            )
            result = type('obj', (object,), {'returncode': returncode, 'stdout': stdout})()
            if result.returncode == 0:
                # Parsear salida de arp (simplificado)
                for line in result.stdout.split('\n'):
                    if 'ether' in line.lower():
                        parts = line.split()
                        if len(parts) >= 4:
                            clients.append({
                                "mac": parts[3] if len(parts) > 3 else "unknown",
                                "ip": parts[1].strip('()') if len(parts) > 1 else "unknown",
                                "hostname": parts[0] if parts[0] else "unknown",
                                "signal": -50,  # Valor por defecto
                                "connected_time": "unknown"
                            })
        except Exception as e:
            logger.warning(f"No se pudieron obtener clientes reales: {e}")
            # Lista vacía en lugar de datos simulados
        
        logger.info('get_clients', count=len(clients))
        return clients
    
    except Exception as e:
        logger.error('get_clients_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.clients_error", default="Error obteniendo clientes WiFi"))

@router.post("/connect")
async def connect_wifi(
    ssid: str = Form(...),
    password: str = Form(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Conecta a una red WiFi"""
    try:
        # Generar configuración wpa_supplicant
        wpa_config = f"""ctrl_interface=DIR={settings.wpa_supplicant_dir} GROUP=netdev
update_config=1
country=ES

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}"""
        
        # Guardar configuración
        try:
            import aiofiles
            async with aiofiles.open(settings.wpa_supplicant_path, 'w') as f:
                await f.write(wpa_config)
        except PermissionError:
            raise HTTPException(status_code=403, detail=get_text("wifi.config_permission_error", default="Permiso denegado para escribir configuración WiFi"))
        except ImportError:
            # Fallback a modo síncrono si aiofiles no está disponible
            with open(settings.wpa_supplicant_path, 'w') as f:
                f.write(wpa_config)
        
        # Reiniciar wpa_supplicant (async)
        try:
            from core.async_utils import run_subprocess_async
            returncode, stdout, stderr = await run_subprocess_async(
                ["systemctl", "restart", "wpa_supplicant"],
                timeout=10
            )
            if returncode != 0:
                raise HTTPException(status_code=500, detail=get_text("wifi.service_restart_error", default="Error reiniciando servicio WiFi"))
            await asyncio.sleep(2)
        except Exception as e:
            raise HTTPException(status_code=500, detail=get_text("wifi.service_restart_error", default="Error reiniciando servicio WiFi"))
        
        logger.info('connect_wifi', ssid=ssid)
        return {
            "success": True,
            "message": get_text("wifi.connected_to", default=f"Conectado a {ssid}", ssid=ssid),
            "ssid": ssid
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error('connect_wifi_error', ssid=ssid, error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.connect_error", default="Error conectando a WiFi"))

@router.post("/disconnect")
async def disconnect_wifi(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Desconecta de la red WiFi actual"""
    try:
        # Desconectar WiFi
        try:
            subprocess.run(["wpa_cli", "disconnect"], check=True)
        except subprocess.CalledProcessError:
            pass
        
        logger.info('disconnect_wifi')
        return {
            "success": True,
            "message": get_text("wifi.disconnected", default="Desconectado de WiFi")
        }
    
    except Exception as e:
        logger.error('disconnect_wifi_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.disconnect_error", default="Error desconectando de WiFi"))

@router.post("/toggle")
async def toggle_wifi(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Activa/desactiva WiFi"""
    try:
        status = get_wifi_status()
        current_state = status.get('enabled', False)
        
        if current_state:
            # Desactivar WiFi
            subprocess.run(["rfkill", "block", "wifi"], check=True)
            new_state = False
            message = get_text("wifi.disabled", default="WiFi deshabilitado")
        else:
            # Activar WiFi
            subprocess.run(["rfkill", "unblock", "wifi"], check=True)
            new_state = True
            message = get_text("wifi.enabled", default="WiFi habilitado")
        
        logger.info('toggle_wifi', enabled=new_state)
        return {
            "success": True,
            "enabled": new_state,
            "message": message
        }
    
    except Exception as e:
        logger.error('toggle_wifi_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.toggle_error", default="Error cambiando estado de WiFi"))

@router.get("/scan")
async def scan_networks(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Escanea redes WiFi disponibles"""
    try:
        # Escanear redes reales usando iwlist (async)
        networks = []
        try:
            from core.async_utils import run_subprocess_async
            
            status = get_wifi_status()
            if status.get('interfaces'):
                interface = status['interfaces'][0]
                returncode, stdout, stderr = await run_subprocess_async(
                    ["iwlist", interface, "scan"],
                    timeout=10
                )
                
                if returncode == 0:
                    current_network = {}
                    for line in stdout.split('\n'):
                        if 'ESSID:' in line:
                            ssid = line.split('"')[1] if '"' in line else line.split(':')[1].strip()
                            if ssid and ssid != '""':
                                current_network['ssid'] = ssid
                        elif 'Signal level=' in line:
                            try:
                                signal_str = line.split('Signal level=')[1].split()[0]
                                signal = int(signal_str)
                                current_network['signal'] = signal
                            except:
                                current_network['signal'] = -70
                        elif 'Channel:' in line:
                            try:
                                channel = int(line.split('Channel:')[1].strip())
                                current_network['channel'] = channel
                            except:
                                pass
                        elif 'Encryption key:' in line:
                            current_network['security'] = 'WPA2' if 'on' in line.lower() else 'Open'
                        
                        if current_network.get('ssid') and current_network not in networks:
                            networks.append({
                                "ssid": current_network.get('ssid', 'Unknown'),
                                "signal": current_network.get('signal', -70),
                                "security": current_network.get('security', 'Unknown'),
                                "channel": current_network.get('channel', 1),
                                "frequency": "2.4 GHz"
                            })
                            current_network = {}
        except Exception as e:
            logger.warning(f"Error escaneando redes WiFi: {e}")
            # Retornar lista vacía en lugar de datos simulados
        
        logger.info('scan_networks', count=len(networks))
        return networks
    
    except Exception as e:
        logger.error('scan_networks_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.scan_error", default="Error escaneando redes WiFi"))

@router.get("/stored_networks")
async def get_stored_networks(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Obtiene las redes WiFi guardadas"""
    try:
        networks = []
        
        # Leer configuración guardada
        try:
            with open(settings.wpa_supplicant_path, 'r') as f:
                content = f.read()
                
            # Parsear redes guardadas
            network_blocks = re.findall(r'network\s*=\s*\{([^}]+)\}', content)
            
            for block in network_blocks:
                ssid_match = re.search(r'ssid\s*=\s*"([^"]+)"', block)
                if ssid_match:
                    networks.append({
                        "ssid": ssid_match.group(1),
                        "saved": True,
                        "connected": False
                    })
        except FileNotFoundError:
            pass
        
        logger.info('get_stored_networks', count=len(networks))
        return networks
    
    except Exception as e:
        logger.error('get_stored_networks_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.stored_error", default="Error obteniendo redes guardadas"))

@router.post("/guest/toggle")
async def toggle_guest_network(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Activa/desactiva red de invitados"""
    try:
        # Simular toggle de red de invitados
        logger.info('toggle_guest_network')
        return {
            "success": True,
            "enabled": True,
            "message": get_text("wifi.guest_enabled", default="Red de invitados habilitada")
        }
    
    except Exception as e:
        logger.error('toggle_guest_network_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.guest_toggle_error", default="Error cambiando estado de red de invitados"))

@router.get("/config")
async def get_wifi_config(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Obtiene la configuración de WiFi"""
    try:
        # Obtener configuración desde base de datos o usar valores por defecto desde settings
        from core.database import db
        
        # Intentar obtener configuración guardada
        wifi_ssid = await db.get_configuration("wifi_ssid")
        wifi_channel = await db.get_configuration("wifi_channel")
        guest_enabled = await db.get_configuration("guest_network_enabled")
        guest_ssid = await db.get_configuration("guest_network_ssid")
        
        config = {
            "ssid": wifi_ssid or "HostBerry_WiFi",
            "password": "********",  # Nunca exponer contraseña
            "channel": int(wifi_channel) if wifi_channel else 6,
            "security": "WPA2",
            "guest_network": {
                "enabled": guest_enabled == "true" if guest_enabled else False,
                "ssid": guest_ssid or "HostBerry_Guest",
                "password": "********"  # Nunca exponer contraseña
            },
            "advanced": {
                "bandwidth_limit": "10 Mbps",
                "max_clients": 20,
                "isolation": True
            }
        }
        
        logger.info('get_wifi_config')
        return config
    
    except Exception as e:
        logger.error('get_wifi_config_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("wifi.config_error", default="Error obteniendo configuración WiFi")) 