"""
Sistema de caché optimizado para Raspberry Pi 3
"""

import time
import threading
from typing import Any, Optional, Dict
from collections import OrderedDict
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

class RPICache:
    """Sistema de caché optimizado para Raspberry Pi 3 con límites de memoria"""
    
    def __init__(self):
        self.cache: OrderedDict = OrderedDict()
        self.max_size = settings.cache_max_size
        self.ttl = settings.cache_ttl
        self.lock = threading.Lock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'size': 0
        }
        
        # Iniciar limpieza automática
        if settings.cache_enabled:
            self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Iniciar thread de limpieza automática"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(60)  # Limpiar cada minuto
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"❌ Error en limpieza de caché: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("🔄 Thread de limpieza de caché iniciado")
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del caché"""
        if not settings.cache_enabled:
            return None
        
        with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                
                # Verificar si ha expirado
                if time.time() - timestamp > self.ttl:
                    del self.cache[key]
                    self.stats['misses'] += 1
                    return None
                
                # Mover al final (LRU)
                self.cache.move_to_end(key)
                self.stats['hits'] += 1
                return value
            
            self.stats['misses'] += 1
            return None
    
    def set(self, key: str, value: Any) -> bool:
        """Establecer valor en caché"""
        if not settings.cache_enabled:
            return False
        
        with self.lock:
            # Verificar si hay espacio
            if len(self.cache) >= self.max_size:
                self._evict_oldest()
            
            # Insertar valor
            self.cache[key] = (value, time.time())
            self.stats['size'] = len(self.cache)
            return True
    
    def delete(self, key: str) -> bool:
        """Eliminar valor del caché"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                self.stats['size'] = len(self.cache)
                return True
            return False
    
    def clear(self):
        """Limpiar todo el caché"""
        with self.lock:
            self.cache.clear()
            self.stats['size'] = 0
            logger.info("🗑️ Caché limpiado")
    
    def _evict_oldest(self):
        """Eliminar el elemento más antiguo (LRU)"""
        if self.cache:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.stats['evictions'] += 1
            self.stats['size'] = len(self.cache)
    
    def _cleanup_expired(self):
        """Limpiar elementos expirados"""
        current_time = time.time()
        expired_keys = []
        
        with self.lock:
            for key, (value, timestamp) in self.cache.items():
                if current_time - timestamp > self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
            
            if expired_keys:
                self.stats['size'] = len(self.cache)
                logger.debug(f"🗑️ Limpiados {len(expired_keys)} elementos expirados del caché")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del caché"""
        with self.lock:
            hit_rate = 0
            if self.stats['hits'] + self.stats['misses'] > 0:
                hit_rate = self.stats['hits'] / (self.stats['hits'] + self.stats['misses'])
            
            return {
                'size': self.stats['size'],
                'max_size': self.max_size,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions'],
                'hit_rate': hit_rate,
                'enabled': settings.cache_enabled
            }
    
    def optimize_for_memory(self):
        """Optimizar caché según uso de memoria"""
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            
            with self.lock:
                if memory_percent > 80:  # Si uso de memoria > 80%
                    # Reducir tamaño del caché
                    while len(self.cache) > self.max_size // 2:
                        self._evict_oldest()
                    logger.warning(f"⚠️ Caché reducido por alto uso de memoria: {memory_percent}%")
                    
        except ImportError:
            pass  # psutil no disponible
        except Exception as e:
            logger.error(f"❌ Error optimizando caché: {e}")

# Instancia global de caché
cache = RPICache()

def get_cached_data(key: str, default: Any = None) -> Any:
    """Obtener datos del caché con valor por defecto"""
    return cache.get(key) or default

def set_cached_data(key: str, value: Any) -> bool:
    """Establecer datos en caché"""
    return cache.set(key, value)

def clear_cache():
    """Limpiar caché"""
    cache.clear()

def get_cache_stats() -> Dict[str, Any]:
    """Obtener estadísticas del caché"""
    return cache.get_stats() 