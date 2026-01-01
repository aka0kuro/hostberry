"""
Router de AdBlock para FastAPI
"""

import os
import subprocess
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from models.schemas import AdBlockConfig, AdBlockStatus, SuccessResponse
from core.security import get_current_active_user
from core.database import db
from core.logging import get_logger
from core.i18n import get_text

router = APIRouter()
logger = get_logger("adblock")

@router.get("/status", response_model=AdBlockStatus)
async def get_adblock_status(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene el estado de AdBlock"""
    try:
        # Verificar si AdBlock está habilitado
        enabled = await db.get_configuration("adblock_enabled")
        enabled = enabled == "true" if enabled else False
        
        # Obtener última actualización
        last_update = None
        try:
            result = subprocess.run(
                ["stat", "-c", "%Y", "/etc/hosts"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                last_update = int(result.stdout.strip())
        except:
            pass
        
        # Contar dominios bloqueados
        total_domains = 0
        try:
            with open("/etc/hosts", "r") as f:
                lines = f.readlines()
                total_domains = len([line for line in lines if line.strip().startswith("127.0.0.1")])
        except:
            pass
        
        status = AdBlockStatus(
            enabled=enabled,
            last_update=last_update,
            total_domains=total_domains,
            blocked_requests=0,  # No implementado aún
            update_progress=None
        )
        
        return status
        
    except Exception as e:
        logger.error(f"Error obteniendo estado AdBlock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.adblock_status_error", default="Error obteniendo estado AdBlock")
        )

@router.post("/enable")
async def enable_adblock(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Habilita AdBlock"""
    try:
        # Habilitar AdBlock
        await db.set_configuration("adblock_enabled", "true")
        
        # Actualizar hosts
        await update_hosts_file()
        
        # Log de la habilitación
        await db.insert_log("INFO", "AdBlock habilitado")
        
        logger.info("AdBlock habilitado")
        
        return {
            "success": True,
            "message": get_text("adblock.enabled", default="AdBlock habilitado exitosamente")
        }
        
    except Exception as e:
        logger.error(f"Error habilitando AdBlock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.adblock_enable_error", default="Error habilitando AdBlock")
        )

@router.post("/disable")
async def disable_adblock(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Deshabilita AdBlock"""
    try:
        # Deshabilitar AdBlock
        await db.set_configuration("adblock_enabled", "false")
        
        # Restaurar hosts original
        await restore_hosts_file()
        
        # Log de la deshabilitación
        await db.insert_log("INFO", "AdBlock deshabilitado")
        
        logger.info("AdBlock deshabilitado")
        
        return {
            "success": True,
            "message": get_text("adblock.disabled", default="AdBlock deshabilitado exitosamente")
        }
        
    except Exception as e:
        logger.error(f"Error deshabilitando AdBlock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.adblock_disable_error", default="Error deshabilitando AdBlock")
        )

@router.post("/update")
async def update_adblock_lists(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Actualiza las listas de AdBlock"""
    try:
        logger.info("Iniciando actualización de listas AdBlock...")
        
        # Ejecutar script de actualización
        script_path = "scripts/adblock.sh"
        if os.path.exists(script_path):
            result = subprocess.run(
                [script_path, "update"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos
            )
            
            if result.returncode == 0:
                # Log de la actualización
                await db.insert_log("INFO", "Listas AdBlock actualizadas")
                
                logger.info("Listas AdBlock actualizadas exitosamente")
                
                return {
                    "success": True,
                    "message": get_text("adblock.updated", default="Listas AdBlock actualizadas exitosamente")
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=get_text("errors.adblock_update_script_error", default=f"Error actualizando listas: {result.stderr}", error=result.stderr)
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=get_text("errors.adblock_script_missing", default="Script de actualización no encontrado")
            )
        
    except subprocess.TimeoutExpired:
        logger.error("Timeout actualizando listas AdBlock")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.adblock_update_timeout", default="Timeout actualizando listas AdBlock")
        )
    except Exception as e:
        logger.error(f"Error actualizando listas AdBlock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.adblock_update_error", default="Error actualizando listas AdBlock")
        )

@router.get("/config", response_model=AdBlockConfig)
async def get_adblock_config(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Obtiene la configuración de AdBlock"""
    try:
        # Obtener configuraciones de la base de datos
        enabled = await db.get_configuration("adblock_enabled")
        enabled = enabled == "true" if enabled else True
        
        update_interval = await db.get_configuration("adblock_update_interval")
        update_interval = int(update_interval) if update_interval else 86400
        
        block_youtube = await db.get_configuration("adblock_youtube")
        block_youtube = block_youtube == "true" if block_youtube else True
        
        whitelist_mode = await db.get_configuration("adblock_whitelist_mode")
        whitelist_mode = whitelist_mode == "true" if whitelist_mode else False
        
        config = AdBlockConfig(
            enabled=enabled,
            update_interval=update_interval,
            block_youtube_ads=block_youtube,
            whitelist_mode=whitelist_mode,
            custom_domains=[],
            whitelist_domains=[]
        )
        
        return config
        
    except Exception as e:
        logger.error(f"Error obteniendo configuración AdBlock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.adblock_config_error", default="Error obteniendo configuración AdBlock")
        )

@router.post("/config")
async def update_adblock_config(
    config: AdBlockConfig,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Actualiza la configuración de AdBlock"""
    try:
        # Guardar configuraciones
        await db.set_configuration("adblock_enabled", str(config.enabled).lower())
        await db.set_configuration("adblock_update_interval", str(config.update_interval))
        await db.set_configuration("adblock_youtube", str(config.block_youtube_ads).lower())
        await db.set_configuration("adblock_whitelist_mode", str(config.whitelist_mode).lower())
        
        # Log de la actualización
        await db.insert_log("INFO", "Configuración AdBlock actualizada")
        
        logger.info("Configuración AdBlock actualizada")
        
        return {
            "success": True,
            "message": get_text("adblock.config_updated", default="Configuración AdBlock actualizada exitosamente")
        }
        
    except Exception as e:
        logger.error(f"Error actualizando configuración AdBlock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.adblock_config_update_error", default="Error actualizando configuración AdBlock")
        )

async def update_hosts_file():
    """Actualiza el archivo hosts con listas de AdBlock"""
    try:
        # Crear backup del archivo hosts original
        if not os.path.exists("/etc/hosts.backup"):
            subprocess.run(["cp", "/etc/hosts", "/etc/hosts.backup"], check=True)
        
        # Descargar listas de AdBlock
        lists = [
            "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
            "https://raw.githubusercontent.com/PolishFiltersTeam/KADhosts/master/KADhosts.txt"
        ]
        
        blocked_domains = set()
        
        for url in lists:
            try:
                result = subprocess.run(
                    ["curl", "-s", url],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#') and '127.0.0.1' in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                domain = parts[1]
                                blocked_domains.add(domain)
            except:
                continue
        
        # Crear nuevo archivo hosts
        hosts_content = """# HostBerry AdBlock
# Archivo generado automáticamente
127.0.0.1 localhost
::1 localhost ip6-localhost ip6-loopback
"""
        
        for domain in sorted(blocked_domains):
            hosts_content += f"127.0.0.1 {domain}\n"
        
        # Guardar archivo hosts
        try:
            with open("/etc/hosts", "w") as f:
                f.write(hosts_content)
        except PermissionError:
            # Si no hay permisos, guardar en directorio temporal
            os.makedirs("/tmp/hostberry", exist_ok=True)
            with open("/tmp/hostberry/hosts", "w") as f:
                f.write(hosts_content)
        
    except Exception as e:
        logger.error(f"Error actualizando archivo hosts: {str(e)}")
        raise

async def restore_hosts_file():
    """Restaura el archivo hosts original"""
    try:
        if os.path.exists("/etc/hosts.backup"):
            subprocess.run(["cp", "/etc/hosts.backup", "/etc/hosts"], check=True)
    except Exception as e:
        logger.error(f"Error restaurando archivo hosts: {str(e)}")
        raise 