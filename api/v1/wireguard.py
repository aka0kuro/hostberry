"""
Router de WireGuard para FastAPI
"""

import os
import subprocess
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from models.schemas import WireGuardConfig, WireGuardStatus, SuccessResponse
from core.security import get_current_active_user
from core.database import db
from core.hostberry_logging import get_logger
from core.i18n import get_text

router = APIRouter()
logger = get_logger("wireguard")

@router.get("/status", response_model=WireGuardStatus)
async def get_wireguard_status(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene el estado de WireGuard"""
    try:
        # Verificar si WireGuard está ejecutándose (async)
        from core.async_utils import run_subprocess_async
        returncode, stdout, stderr = await run_subprocess_async(
            ["systemctl", "is-active", "wg-quick@wg0"],
            timeout=5
        )
        
        running = returncode == 0
        
        # Obtener información de la interfaz
        interface = "wg0"
        public_key = None
        listen_port = None
        peers = []
        
        if running:
            try:
                # Obtener información de la interfaz (async)
                returncode2, stdout2, stderr2 = await run_subprocess_async(
                    ["wg", "show", "wg0"],
                    timeout=5
                )
                
                if returncode2 == 0:
                    result = type('obj', (object,), {'stdout': stdout2})()
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'public key:' in line:
                            public_key = line.split(':')[1].strip()
                        elif 'listening port:' in line:
                            listen_port = int(line.split(':')[1].strip())
                        elif 'peer:' in line:
                            peer_key = line.split(':')[1].strip()
                            peers.append({"public_key": peer_key})
            except:
                pass
        
        status = WireGuardStatus(
            running=running,
            interface=interface,
            public_key=public_key,
            listen_port=listen_port,
            peers=peers
        )
        
        return status
        
    except Exception as e:
        logger.error(f"Error obteniendo estado WireGuard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.wireguard_status_error", default="Error obteniendo estado WireGuard")
        )

@router.post("/start")
async def start_wireguard(
    config: WireGuardConfig,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Inicia WireGuard con la configuración proporcionada"""
    try:
        # Crear configuración WireGuard
        wg_config = f"""[Interface]
PrivateKey = {config.private_key}
Address = {config.address}
ListenPort = 51820
DNS = {config.dns or '8.8.8.8'}

[Peer]
PublicKey = {config.public_key}
Endpoint = {config.endpoint or 'example.com:51820'}
AllowedIPs = {config.allowed_ips or '0.0.0.0/0'}
PersistentKeepalive = 25
"""
        
        # Guardar configuración (async)
        config_path = "/etc/wireguard/wg0.conf"
        try:
            import aiofiles
            async with aiofiles.open(config_path, 'w') as f:
                await f.write(wg_config)
        except PermissionError:
            # Usar directorio temporal si no hay permisos
            os.makedirs('/tmp/hostberry', exist_ok=True)
            config_path = '/tmp/hostberry/wg0.conf'
            try:
                async with aiofiles.open(config_path, 'w') as f:
                    await f.write(wg_config)
            except ImportError:
                # Fallback síncrono
                with open(config_path, 'w') as f:
                    f.write(wg_config)
        except ImportError:
            # Fallback síncrono si aiofiles no está disponible
            with open(config_path, 'w') as f:
                f.write(wg_config)
        
        # Iniciar WireGuard (async)
        try:
            from core.async_utils import run_subprocess_async
            await run_subprocess_async(['systemctl', 'start', 'wg-quick@wg0'], timeout=10)
        except Exception as e:
            logger.warning(f"No se pudo iniciar WireGuard: {e}")
        
        # Log del inicio
        await db.insert_log("INFO", "WireGuard iniciado")
        
        logger.info("WireGuard iniciado")
        
        return {
            "success": True,
            "message": get_text("wireguard.started", default="WireGuard iniciado exitosamente")
        }
        
    except Exception as e:
        logger.error(f"Error iniciando WireGuard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.wireguard_start_error", default="Error iniciando WireGuard")
        )

@router.post("/stop")
async def stop_wireguard(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Detiene WireGuard"""
    try:
        # Detener WireGuard (async)
        from core.async_utils import run_subprocess_async
        await run_subprocess_async(['systemctl', 'stop', 'wg-quick@wg0'], timeout=10)
        
        # Log del detenimiento
        await db.insert_log("INFO", "WireGuard detenido")
        
        logger.info("WireGuard detenido")
        
        return {
            "success": True,
            "message": get_text("wireguard.stopped", default="WireGuard detenido exitosamente")
        }
        
    except Exception as e:
        logger.error(f"Error deteniendo WireGuard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.wireguard_stop_error", default="Error deteniendo WireGuard")
        )

@router.get("/peers")
async def get_wireguard_peers(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene la lista de peers de WireGuard"""
    try:
        peers = []
        
        # Obtener información de peers
        result = subprocess.run(
            ["wg", "show", "wg0"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            current_peer = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith('peer:'):
                    if current_peer:
                        peers.append(current_peer)
                    current_peer = {"public_key": line.split(':')[1].strip()}
                elif line.startswith('endpoint:'):
                    current_peer["endpoint"] = line.split(':')[1].strip()
                elif line.startswith('allowed ips:'):
                    current_peer["allowed_ips"] = line.split(':')[1].strip()
                elif line.startswith('latest handshake:'):
                    current_peer["last_handshake"] = line.split(':')[1].strip()
                elif line.startswith('transfer:'):
                    current_peer["transfer"] = line.split(':')[1].strip()
            
            # Agregar último peer
            if current_peer:
                peers.append(current_peer)
        
        return {
            "peers": peers,
            "total": len(peers)
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo peers WireGuard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.wireguard_peers_error", default="Error obteniendo peers WireGuard")
        ) 