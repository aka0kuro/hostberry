"""
Router de VPN para FastAPI
"""

import os
import subprocess
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from models.schemas import VPNConfig, VPNStatus, SuccessResponse
from core.security import get_current_active_user
from core.database import db
from core.logging import get_logger

router = APIRouter()
logger = get_logger("vpn")

@router.get("/status", response_model=VPNStatus)
async def get_vpn_status(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene el estado de la conexión VPN"""
    try:
        # Verificar si OpenVPN está ejecutándose
        result = subprocess.run(
            ["systemctl", "is-active", "openvpn"],
            capture_output=True,
            text=True
        )
        
        running = result.returncode == 0
        
        # Obtener información de la conexión si está activa
        server = None
        ip_address = None
        bytes_sent = 0
        bytes_recv = 0
        
        if running:
            try:
                # Obtener IP pública
                result = subprocess.run(
                    ["curl", "-s", "ifconfig.me"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    ip_address = result.stdout.strip()
            except:
                pass
        
        status = VPNStatus(
            connected=running,
            server=server,
            ip_address=ip_address,
            bytes_sent=bytes_sent,
            bytes_recv=bytes_recv
        )
        
        return status
        
    except Exception as e:
        logger.error(f"Error obteniendo estado VPN: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo estado VPN"
        )

@router.post("/connect")
async def connect_vpn(
    vpn_config: VPNConfig,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Conecta a un servidor VPN"""
    try:
        # Crear configuración OpenVPN
        config_content = f"""client
dev tun
proto {vpn_config.protocol}
remote {vpn_config.server} {vpn_config.port}
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher AES-256-CBC
verb 3
"""
        
        if vpn_config.username and vpn_config.password:
            config_content += f"auth-user-pass\n"
        
        # Guardar configuración
        config_path = "/etc/openvpn/client.conf"
        try:
            with open(config_path, 'w') as f:
                f.write(config_content)
        except PermissionError:
            # Usar directorio temporal si no hay permisos
            os.makedirs('/tmp/hostberry', exist_ok=True)
            config_path = '/tmp/hostberry/client.conf'
            with open(config_path, 'w') as f:
                f.write(config_content)
        
        # Iniciar OpenVPN
        try:
            subprocess.run(['systemctl', 'start', 'openvpn'], check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"No se pudo iniciar OpenVPN: {e}")
        
        # Log de la conexión
        await db.insert_log("INFO", f"Conexión VPN iniciada a: {vpn_config.server}")
        
        logger.info(f"Conexión VPN iniciada a: {vpn_config.server}")
        
        return {
            "success": True,
            "message": f"Conectando a VPN: {vpn_config.server}",
            "server": vpn_config.server
        }
        
    except Exception as e:
        logger.error(f"Error conectando a VPN: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error conectando a VPN"
        )

@router.post("/disconnect")
async def disconnect_vpn(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Desconecta de la VPN"""
    try:
        # Detener OpenVPN
        subprocess.run(['systemctl', 'stop', 'openvpn'], check=True)
        
        # Log de la desconexión
        await db.insert_log("INFO", "Desconexión VPN iniciada")
        
        logger.info("Desconexión VPN iniciada")
        
        return {
            "success": True,
            "message": "Desconectando de VPN"
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error desconectando VPN: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error desconectando de VPN"
        )
    except Exception as e:
        logger.error(f"Error desconectando VPN: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error desconectando de VPN"
        )

@router.post("/upload-config")
async def upload_vpn_config(
    file: bytes,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Sube un archivo de configuración VPN"""
    try:
        # Guardar archivo
        config_path = "/etc/openvpn/client.conf"
        try:
            with open(config_path, 'wb') as f:
                f.write(file)
        except PermissionError:
            # Usar directorio temporal si no hay permisos
            os.makedirs('/tmp/hostberry', exist_ok=True)
            config_path = '/tmp/hostberry/client.conf'
            with open(config_path, 'wb') as f:
                f.write(file)
        
        # Log de la subida
        await db.insert_log("INFO", "Archivo de configuración VPN subido")
        
        logger.info("Archivo de configuración VPN subido")
        
        return {
            "success": True,
            "message": "Archivo de configuración VPN subido exitosamente"
        }
        
    except Exception as e:
        logger.error(f"Error subiendo configuración VPN: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error subiendo configuración VPN"
        ) 