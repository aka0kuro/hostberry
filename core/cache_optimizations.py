"""
Optimizaciones de caché para Raspberry Pi 3
"""

import time
import logging
from typing import Dict, Any, Optional, Union
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)

class RPi3Cache:
    """Sistema de caché optimizado para Raspberry Pi 3"""
    
    def __init__(self, max_size: int = 100, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.lock = Lock()
        
        # Estadísticas
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del caché con verificación de TTL"""
        with self.lock:
            if key in self.cache:
                # Verificar TTL
                if time.time() - self.timestamps[key] < self.ttl:
                    # Mover al final (LRU)
                    value = self.cache.pop(key)
                    self.cache[key] = value
                    self.hits += 1
                    return value
                else:
                    # Expirar
                    self._remove_expired(key)
                    self.misses += 1
                    return None
            else:
                self.misses += 1
                return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Establecer valor en el caché con TTL personalizado"""
        with self.lock:
            # Verificar si necesitamos hacer espacio
            if len(self.cache) >= self.max_size:
                self._evict_oldest()
            
            # Establecer valor
            self.cache[key] = value
            self.timestamps[key] = time.time()
            
            # Mover al final (LRU)
            self.cache.move_to_end(key)
    
    def delete(self, key: str) -> bool:
        """Eliminar clave del caché"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
                return True
            return False
    
    def clear(self) -> None:
        """Limpiar todo el caché"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
    
    def cleanup_expired(self) -> int:
        """Limpiar entradas expiradas del caché"""
        with self.lock:
            expired_keys = []
            current_time = time.time()
            
            for key, timestamp in self.timestamps.items():
                if current_time - timestamp >= self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_expired(key)
            
            return len(expired_keys)
    
    def _remove_expired(self, key: str) -> None:
        """Remover entrada expirada"""
        if key in self.cache:
            del self.cache[key]
        if key in self.timestamps:
            del self.timestamps[key]
    
    def _evict_oldest(self) -> None:
        """Eliminar la entrada más antigua (LRU)"""
        if self.cache:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]
            self.evictions += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del caché"""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'evictions': self.evictions,
                'hit_rate': round(hit_rate, 2),
                'ttl': self.ttl
            }
    
    def optimize_for_rpi3(self) -> None:
        """Aplicar optimizaciones específicas para RPi 3"""
        # Reducir tamaño máximo para ahorrar memoria
        if self.max_size > 50:
            self.max_size = 50
            logger.info("Tamaño de caché reducido a 50 para RPi 3")
        
        # Reducir TTL para liberar memoria más rápido
        if self.ttl > 180:
            self.ttl = 180
            logger.info("TTL de caché reducido a 3 minutos para RPi 3")
        
        # Limpiar entradas expiradas
        expired_count = self.cleanup_expired()
        if expired_count > 0:
            logger.info(f"Limpiadas {expired_count} entradas expiradas del caché")

class RPi3MemoryOptimizedCache:
    """Caché con optimizaciones de memoria para RPi 3"""
    
    def __init__(self, max_memory_mb: int = 50):
        self.max_memory_mb = max_memory_mb
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.current_memory = 0
        self.cache: Dict[str, Any] = {}
        self.sizes: Dict[str, int] = {}
        self.lock = Lock()
        
        # Estadísticas
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def _estimate_size(self, value: Any) -> int:
        """Estimar tamaño aproximado de un valor"""
        try:
            import sys
            return sys.getsizeof(value)
        except:
            return 100  # Tamaño por defecto
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del caché"""
        with self.lock:
            if key in self.cache:
                self.hits += 1
                return self.cache[key]
            else:
                self.misses += 1
                return None
    
    def set(self, key: str, value: Any) -> bool:
        """Establecer valor en el caché con control de memoria"""
        with self.lock:
            value_size = self._estimate_size(value)
            
            # Si la clave ya existe, liberar su espacio
            if key in self.cache:
                self.current_memory -= self.sizes[key]
            
            # Verificar si hay suficiente espacio
            while self.current_memory + value_size > self.max_memory_bytes:
                if not self._evict_smallest():
                    return False  # No se pudo hacer espacio
            
            # Establecer valor
            self.cache[key] = value
            self.sizes[key] = value_size
            self.current_memory += value_size
            
            return True
    
    def _evict_smallest(self) -> bool:
        """Eliminar la entrada más pequeña para hacer espacio"""
        if not self.cache:
            return False
        
        # Encontrar la entrada más pequeña
        smallest_key = min(self.sizes.keys(), key=lambda k: self.sizes[k])
        smallest_size = self.sizes[smallest_key]
        
        # Eliminar
        del self.cache[smallest_key]
        del self.sizes[smallest_key]
        self.current_memory -= smallest_size
        self.evictions += 1
        
        return True
    
    def clear(self) -> None:
        """Limpiar todo el caché"""
        with self.lock:
            self.cache.clear()
            self.sizes.clear()
            self.current_memory = 0
            self.hits = 0
            self.misses = 0
            self.evictions = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del caché"""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self.cache),
                'memory_used_mb': round(self.current_memory / (1024 * 1024), 2),
                'memory_max_mb': self.max_memory_mb,
                'hits': self.hits,
                'misses': self.misses,
                'evictions': self.evictions,
                'hit_rate': round(hit_rate, 2)
            }

# Instancias globales optimizadas para RPi 3
rpi3_cache = RPi3Cache(max_size=50, ttl=180)  # 50 entradas, 3 minutos TTL
rpi3_memory_cache = RPi3MemoryOptimizedCache(max_memory_mb=25)  # 25MB máximo

def get_optimized_cache() -> RPi3Cache:
    """Obtener caché optimizado para RPi 3"""
    return rpi3_cache

def get_memory_optimized_cache() -> RPi3MemoryOptimizedCache:
    """Obtener caché optimizado en memoria para RPi 3"""
    return rpi3_memory_cache
