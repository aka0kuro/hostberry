"""
Utilidades asíncronas para operaciones del sistema
Optimizado para Raspberry Pi 3
"""

import asyncio
import subprocess
from typing import Optional, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


async def run_subprocess_async(
    cmd: list[str],
    timeout: Optional[int] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None
) -> Tuple[int, str, str]:
    """
    Ejecuta un comando subprocess de forma asíncrona sin bloquear el event loop
    
    Returns:
        Tuple[int, str, str]: (returncode, stdout, stderr)
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise TimeoutError(f"Comando '{' '.join(cmd)}' excedió el timeout de {timeout}s")
        
        return (
            process.returncode,
            stdout.decode('utf-8', errors='replace'),
            stderr.decode('utf-8', errors='replace')
        )
    except Exception as e:
        logger.error(f"Error ejecutando subprocess async: {e}")
        raise


async def run_subprocess_shell_async(
    cmd: str,
    timeout: Optional[int] = None,
    cwd: Optional[str] = None
) -> Tuple[int, str, str]:
    """
    Ejecuta un comando shell de forma asíncrona
    
    Returns:
        Tuple[int, str, str]: (returncode, stdout, stderr)
    """
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise TimeoutError(f"Comando shell '{cmd}' excedió el timeout de {timeout}s")
        
        return (
            process.returncode,
            stdout.decode('utf-8', errors='replace'),
            stderr.decode('utf-8', errors='replace')
        )
    except Exception as e:
        logger.error(f"Error ejecutando subprocess shell async: {e}")
        raise


def get_version() -> str:
    """Obtiene la versión de la aplicación desde settings (deprecated - usar core.version)"""
    from core.version import get_version as get_app_version
    return get_app_version()

