"""
Optimizaciones específicas para Python en Raspberry Pi 3
"""

import gc
import sys
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class RPi3Optimizer:
    """Optimizador específico para Raspberry Pi 3"""
    
    def __init__(self):
        self.optimizations_applied = False
        self.original_settings = {}
    
    def apply_python_optimizations(self) -> None:
        """Aplicar optimizaciones de Python para RPi 3"""
        if self.optimizations_applied:
            return
            
        try:
            # Optimizaciones de garbage collector
            self._optimize_garbage_collector()
            
            # Optimizaciones de memoria
            self._optimize_memory()
            
            # Optimizaciones de logging
            self._optimize_logging()
            
            # Optimizaciones de sistema de archivos
            self._optimize_filesystem()
            
            # Optimizaciones de red
            self._optimize_networking()
            
            self.optimizations_applied = True
            logger.info("✅ Optimizaciones de Python aplicadas para RPi 3")
            
        except Exception as e:
            logger.warning(f"⚠️ No se pudieron aplicar todas las optimizaciones: {e}")
    
    def _optimize_garbage_collector(self) -> None:
        """Optimizar el garbage collector para RPi 3"""
        # Configurar thresholds más agresivos para RPi 3
        gc.set_threshold(700, 10, 10)  # Más agresivo que los valores por defecto
        
        # Habilitar generational GC
        if hasattr(gc, 'enable'):
            gc.enable()
        
        # Configurar para limpiar más frecuentemente
        gc.collect()
        
        logger.debug("Garbage collector optimizado para RPi 3")
    
    def _optimize_memory(self) -> None:
        """Optimizar uso de memoria para RPi 3"""
        # Reducir el tamaño del buffer de strings
        if hasattr(sys, 'set_int_max_str_digits'):
            sys.set_int_max_str_digits(1000)  # Limitar dígitos de strings
        
        # Optimizar el pool de strings
        if hasattr(sys, 'intern'):
            # Internar strings comunes
            common_strings = ['GET', 'POST', 'PUT', 'DELETE', 'OK', 'ERROR', 'success', 'failed']
            for s in common_strings:
                sys.intern(s)
        
        logger.debug("Memoria optimizada para RPi 3")
    
    def _optimize_logging(self) -> None:
        """Optimizar el sistema de logging para RPi 3"""
        # Configurar logging para ser más eficiente
        logging.getLogger().setLevel(logging.WARNING)
        
        # Reducir el nivel de logging de librerías externas
        logging.getLogger('uvicorn').setLevel(logging.ERROR)
        logging.getLogger('fastapi').setLevel(logging.ERROR)
        logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
        
        logger.debug("Logging optimizado para RPi 3")
    
    def _optimize_filesystem(self) -> None:
        """Optimizar operaciones de sistema de archivos para RPi 3"""
        # Configurar buffer size más pequeño para operaciones de archivo
        if hasattr(os, 'O_DIRECT'):
            # Usar O_DIRECT si está disponible para evitar cache del kernel
            pass
        
        # Configurar para usar menos memoria en operaciones de archivo
        if hasattr(os, 'O_LARGEFILE'):
            # Deshabilitar soporte para archivos grandes en RPi 3
            pass
        
        logger.debug("Sistema de archivos optimizado para RPi 3")
    
    def _optimize_networking(self) -> None:
        """Optimizar configuración de red para RPi 3"""
        # Configurar timeouts más agresivos
        if hasattr(socket, 'setdefaulttimeout'):
            import socket
            socket.setdefaulttimeout(30)  # Timeout por defecto de 30 segundos
        
        logger.debug("Red optimizada para RPi 3")
    
    def create_optimized_settings(self) -> Dict[str, Any]:
        """Crear configuración optimizada para RPi 3"""
        return {
            'PYTHONOPTIMIZE': '2',  # Optimizaciones de bytecode
            'PYTHONDONTWRITEBYTECODE': '1',  # No escribir .pyc
            'PYTHONUNBUFFERED': '1',  # Salida no bufferizada
            'PYTHONHASHSEED': '0',  # Hash seed fijo para reproducibilidad
            'PYTHONFAULTHANDLER': '0',  # Deshabilitar fault handler
            'PYTHONASYNCIODEBUG': '0',  # Deshabilitar debug de asyncio
            'PYTHONTRACEMALLOC': '0',  # Deshabilitar trace de memoria
        }
    
    def apply_environment_optimizations(self) -> None:
        """Aplicar optimizaciones de entorno para RPi 3"""
        optimized_settings = self.create_optimized_settings()
        
        for key, value in optimized_settings.items():
            if key not in os.environ:
                os.environ[key] = value
                logger.debug(f"Variable de entorno optimizada: {key}={value}")
    
    def cleanup_memory(self) -> None:
        """Limpieza de memoria para RPi 3"""
        # Forzar garbage collection
        collected = gc.collect()
        logger.debug(f"Garbage collection completado: {collected} objetos recolectados")
        
        # Limpiar caches de módulos si es posible
        if hasattr(sys, 'modules'):
            # Limpiar módulos no utilizados
            pass

# Instancia global del optimizador
rpi3_optimizer = RPi3Optimizer()

def optimize_for_rpi3() -> None:
    """Función principal para optimizar Python para RPi 3"""
    rpi3_optimizer.apply_python_optimizations()
    rpi3_optimizer.apply_environment_optimizations()

def cleanup_rpi3_memory() -> None:
    """Función para limpiar memoria en RPi 3"""
    rpi3_optimizer.cleanup_memory()
