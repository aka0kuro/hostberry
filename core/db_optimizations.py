"""
Optimizaciones de base de datos para Raspberry Pi 3
"""

import sqlite3
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class RPi3DatabaseOptimizer:
    """Optimizador de base de datos para RPi 3"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.optimizations_applied = False
    
    def apply_sqlite_optimizations(self) -> None:
        """Aplicar optimizaciones de SQLite para RPi 3"""
        if self.optimizations_applied:
            return
            
        try:
            with self._get_connection() as conn:
                # Configurar SQLite para RPi 3
                self._configure_sqlite_settings(conn)
                
                # Crear índices optimizados
                self._create_optimized_indexes(conn)
                
                # Configurar WAL mode si es posible
                self._configure_wal_mode(conn)
                
                # Analizar la base de datos
                self._analyze_database(conn)
                
            self.optimizations_applied = True
            logger.info("✅ Optimizaciones de SQLite aplicadas para RPi 3")
            
        except Exception as e:
            logger.warning(f"⚠️ No se pudieron aplicar todas las optimizaciones de BD: {e}")
    
    @contextmanager
    def _get_connection(self):
        """Obtener conexión a SQLite con optimizaciones"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Configurar conexión para RPi 3
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -2000")  # 2MB cache
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 268435456")  # 256MB mmap
            
            yield conn
        finally:
            conn.close()
    
    def _configure_sqlite_settings(self, conn: sqlite3.Connection) -> None:
        """Configurar ajustes de SQLite para RPi 3"""
        pragmas = [
            ("journal_mode", "WAL"),  # Write-Ahead Logging
            ("synchronous", "NORMAL"),  # Balance entre seguridad y rendimiento
            ("cache_size", "-2000"),  # 2MB cache (negativo = KB)
            ("temp_store", "MEMORY"),  # Tablas temporales en memoria
            ("mmap_size", "268435456"),  # 256MB mmap
            ("page_size", "4096"),  # Tamaño de página estándar
            ("auto_vacuum", "INCREMENTAL"),  # Vacuum incremental
            ("incremental_vacuum", "1000"),  # Vacuum cada 1000 páginas
            ("wal_autocheckpoint", "1000"),  # Checkpoint cada 1000 páginas
            ("checkpoint_timeout", "30000"),  # Checkpoint cada 30 segundos
        ]
        
        for pragma, value in pragmas:
            try:
                conn.execute(f"PRAGMA {pragma} = {value}")
                logger.debug(f"PRAGMA {pragma} = {value}")
            except Exception as e:
                logger.debug(f"No se pudo configurar {pragma}: {e}")
    
    def _create_optimized_indexes(self, conn: sqlite3.Connection) -> None:
        """Crear índices optimizados para RPi 3"""
        # Índices para tablas comunes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)",
        ]
        
        for index_sql in indexes:
            try:
                conn.execute(index_sql)
                logger.debug(f"Índice creado: {index_sql}")
            except Exception as e:
                logger.debug(f"No se pudo crear índice: {e}")
    
    def _configure_wal_mode(self, conn: sqlite3.Connection) -> None:
        """Configurar WAL mode para mejor rendimiento"""
        try:
            # Verificar si WAL está disponible
            result = conn.execute("PRAGMA journal_mode").fetchone()
            if result and result[0] == "wal":
                logger.debug("WAL mode ya está habilitado")
            else:
                # Habilitar WAL
                conn.execute("PRAGMA journal_mode = WAL")
                logger.debug("WAL mode habilitado")
                
                # Configurar WAL
                conn.execute("PRAGMA wal_autocheckpoint = 1000")
                conn.execute("PRAGMA checkpoint_timeout = 30000")
                
        except Exception as e:
            logger.debug(f"No se pudo configurar WAL mode: {e}")
    
    def _analyze_database(self, conn: sqlite3.Connection) -> None:
        """Analizar la base de datos para optimizar consultas"""
        try:
            conn.execute("ANALYZE")
            logger.debug("Análisis de base de datos completado")
        except Exception as e:
            logger.debug(f"No se pudo analizar la BD: {e}")
    
    def optimize_queries(self) -> None:
        """Optimizar consultas comunes para RPi 3"""
        try:
            with self._get_connection() as conn:
                # Configurar para consultas más eficientes
                conn.execute("PRAGMA optimize")
                conn.execute("PRAGMA integrity_check")
                
            logger.debug("Consultas optimizadas para RPi 3")
            
        except Exception as e:
            logger.debug(f"No se pudieron optimizar las consultas: {e}")
    
    def cleanup_database(self) -> None:
        """Limpieza de base de datos para RPi 3"""
        try:
            with self._get_connection() as conn:
                # Vacuum incremental
                conn.execute("PRAGMA incremental_vacuum(1000)")
                
                # Limpiar cache
                conn.execute("PRAGMA cache_size = 0")
                conn.execute("PRAGMA cache_size = -2000")
                
                # Optimizar
                conn.execute("PRAGMA optimize")
                
            logger.debug("Limpieza de base de datos completada")
            
        except Exception as e:
            logger.debug(f"No se pudo limpiar la BD: {e}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de la base de datos"""
        try:
            with self._get_connection() as conn:
                stats = {}
                
                # Tamaño de la base de datos
                result = conn.execute("PRAGMA page_count").fetchone()
                if result:
                    page_count = result[0]
                    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
                    stats['size_bytes'] = page_count * page_size
                    stats['size_mb'] = round(stats['size_bytes'] / (1024 * 1024), 2)
                
                # Cache size
                result = conn.execute("PRAGMA cache_size").fetchone()
                if result:
                    stats['cache_size_kb'] = abs(result[0])
                
                # WAL mode
                result = conn.execute("PRAGMA journal_mode").fetchone()
                if result:
                    stats['journal_mode'] = result[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de BD: {e}")
            return {}

# Función de conveniencia
def optimize_database_for_rpi3(db_path: str) -> RPi3DatabaseOptimizer:
    """Función principal para optimizar base de datos para RPi 3"""
    optimizer = RPi3DatabaseOptimizer(db_path)
    optimizer.apply_sqlite_optimizations()
    return optimizer
