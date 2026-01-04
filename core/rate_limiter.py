"""
Rate Limiter optimizado para Raspberry Pi 3
Implementación ligera de rate limiting con limpieza automática
"""

import time
from typing import Dict, List, Optional
from collections import defaultdict
import asyncio
import logging

from config.settings import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter simple y eficiente para RPi 3
    Usa sliding window con limpieza automática
    """
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.lock = asyncio.Lock()
        self.max_requests = settings.rate_limit_requests
        self.window_seconds = settings.rate_limit_window
        self._cleanup_interval = 300  # Limpiar cada 5 minutos
        self._last_cleanup = time.time()
    
    async def is_allowed(self, identifier: str) -> bool:
        """
        Verifica si una solicitud está permitida
        
        Args:
            identifier: Identificador único (IP, usuario, etc.)
            
        Returns:
            True si está permitido, False si excede el límite
        """
        if not settings.rate_limit_enabled:
            return True
        
        async with self.lock:
            current_time = time.time()
            
            # Limpieza periódica de datos antiguos
            if current_time - self._last_cleanup > self._cleanup_interval:
                await self._cleanup_old_entries(current_time)
                self._last_cleanup = current_time
            
            # Obtener solicitudes en la ventana de tiempo
            window_start = current_time - self.window_seconds
            requests = self.requests[identifier]
            
            # Filtrar solicitudes fuera de la ventana
            requests[:] = [req_time for req_time in requests if req_time > window_start]
            
            # Verificar límite
            if len(requests) >= self.max_requests:
                logger.warning(f"Rate limit excedido para {identifier}: {len(requests)}/{self.max_requests}")
                return False
            
            # Registrar nueva solicitud
            requests.append(current_time)
            return True
    
    async def _cleanup_old_entries(self, current_time: float):
        """Limpia entradas antiguas para ahorrar memoria"""
        window_start = current_time - self.window_seconds
        
        # Limpiar identificadores sin solicitudes recientes
        to_remove = []
        for identifier, requests in self.requests.items():
            # Filtrar solicitudes antiguas
            requests[:] = [req_time for req_time in requests if req_time > window_start]
            
            # Eliminar identificadores sin solicitudes
            if not requests:
                to_remove.append(identifier)
        
        for identifier in to_remove:
            del self.requests[identifier]
    
    def get_remaining(self, identifier: str) -> int:
        """Obtiene el número de solicitudes restantes"""
        if not settings.rate_limit_enabled:
            return self.max_requests
        
        current_time = time.time()
        window_start = current_time - self.window_seconds
        requests = self.requests.get(identifier, [])
        requests[:] = [req_time for req_time in requests if req_time > window_start]
        
        return max(0, self.max_requests - len(requests))
    
    def reset(self, identifier: Optional[str] = None):
        """Resetea el rate limiter para un identificador o todos"""
        if identifier:
            if identifier in self.requests:
                del self.requests[identifier]
        else:
            self.requests.clear()


# Instancia global del rate limiter
rate_limiter = RateLimiter()

