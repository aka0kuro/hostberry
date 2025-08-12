"""
Base de datos optimizada para Raspberry Pi 3
"""

import sqlite3
import asyncio
import aiosqlite
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging

import os
from config.settings import settings

logger = logging.getLogger(__name__)

class Database:
    """Clase para manejo optimizado de base de datos SQLite en Raspberry Pi 3"""
    
    def __init__(self):
        # Determinar ruta de la base de datos de forma robusta
        # 1) Prioriza variable de entorno DB_PATH (inyectada por systemd/app.env)
        db_path_env = os.getenv("DB_PATH")
        if db_path_env:
            self.db_path = db_path_env
        else:
            # 2) Intentar derivar desde DATABASE_URL (sqlite)
            db_url = getattr(settings, "database_url", "sqlite:///./hostberry.db")
            if isinstance(db_url, str) and db_url.startswith("sqlite:"):
                # Formatos esperados:
                # - sqlite:///relative_path.db
                # - sqlite:////absolute/path.db
                if db_url.startswith("sqlite:////"):
                    # Ruta absoluta
                    self.db_path = db_url.replace("sqlite:////", "/", 1)
                elif db_url.startswith("sqlite:///"):
                    # Ruta relativa al WorkingDirectory
                    self.db_path = db_url.replace("sqlite:///", "", 1)
                else:
                    # Fallback genérico para variantes
                    self.db_path = db_url.split("sqlite:")[-1].lstrip("/")
            else:
                # 3) Fallback final
                self.db_path = "hostberry.db"
        self.connection_pool = []
        self.max_connections = settings.database_pool_size
        self.timeout = settings.database_timeout
        
    async def init_database(self):
        """Inicializar base de datos con optimizaciones para RPi 3"""
        logger.info("🗄️ Inicializando base de datos optimizada para Raspberry Pi 3")
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Configurar SQLite para RPi 3
                await db.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
                await db.execute("PRAGMA synchronous = NORMAL")  # Balance entre rendimiento y seguridad
                await db.execute("PRAGMA cache_size = 1000")  # Cache reducido para ahorrar memoria
                await db.execute("PRAGMA temp_store = MEMORY")  # Tablas temporales en memoria
                await db.execute("PRAGMA mmap_size = 268435456")  # 256MB para mmap
                await db.execute("PRAGMA page_size = 4096")  # Tamaño de página estándar
                
                # Crear tablas optimizadas
                await self._create_tables(db)
                
                # Asegurar usuario admin por defecto si no hay usuarios
                await self.ensure_default_admin()
                
                logger.info("✅ Base de datos inicializada correctamente")
                
        except Exception as e:
            logger.error(f"❌ Error inicializando base de datos: {e}")
            raise
    
    async def _create_tables(self, db):
        """Crear tablas con índices optimizados"""
        
        # Tabla de usuarios
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)
        
        # Tabla de logs optimizada
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Tabla de configuraciones
        await db.execute("""
            CREATE TABLE IF NOT EXISTS configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de estadísticas optimizada para RPi
        await db.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de servicios
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'stopped',
                enabled BOOLEAN DEFAULT 0,
                config TEXT,
                last_start TIMESTAMP,
                last_stop TIMESTAMP
            )
        """)
        
        # Crear índices para optimizar consultas
        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stats_timestamp ON statistics(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stats_metric ON statistics(metric_name)")
        
        await db.commit()
    
    @asynccontextmanager
    async def get_connection(self):
        """Obtener conexión de base de datos con timeout"""
        try:
            async with aiosqlite.connect(
                self.db_path,
                timeout=self.timeout,
                check_same_thread=False
            ) as conn:
                # Configurar conexión para RPi
                await conn.execute("PRAGMA journal_mode = WAL")
                await conn.execute("PRAGMA synchronous = NORMAL")
                await conn.execute("PRAGMA cache_size = 1000")
                yield conn
        except Exception as e:
            logger.error(f"❌ Error en conexión de base de datos: {e}")
            raise
    
    async def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Ejecutar consulta con timeout optimizado"""
        try:
            async with self.get_connection() as db:
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"❌ Error ejecutando consulta: {e}")
            raise
    
    async def execute_update(self, query: str, params: tuple = ()) -> int:
        """Ejecutar actualización con timeout optimizado"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(query, params)
                await db.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"❌ Error ejecutando actualización: {e}")
            raise
    
    # Métodos específicos optimizados para RPi 3
    
    async def insert_user(self, username: str, password_hash: str) -> bool:
        """Insertar usuario con validación"""
        try:
            # Importar aquí para evitar dependencias circulares
            from core.security import get_password_hash
            
            # Hashear la contraseña si no está hasheada
            if not password_hash.startswith('$2b$'):
                password_hash = get_password_hash(password_hash)
            
            query = """
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
            """
            await self.execute_update(query, (username, password_hash))
            logger.info(f"✅ Usuario creado: {username}")
            return True
        except Exception as e:
            logger.error(f"❌ Error creando usuario: {e}")
            return False
    
    async def ensure_default_admin(self):
        """Crear usuario admin por defecto si no existe ninguno"""
        try:
            rows = await self.execute_query("SELECT COUNT(*) as cnt FROM users")
            count = rows[0]["cnt"] if rows else 0
            if count == 0:
                from config.settings import settings
                ok = await self.insert_user(settings.default_username, settings.default_password)
                if ok:
                    logger.info("✅ Usuario admin por defecto creado")
                else:
                    logger.warning("⚠️ No se pudo crear el usuario admin por defecto")
        except Exception as e:
            logger.error(f"❌ Error asegurando usuario admin por defecto: {e}")

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Obtener usuario por username"""
        try:
            query = "SELECT * FROM users WHERE username = ?"
            result = await self.execute_query(query, (username,))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"❌ Error obteniendo usuario: {e}")
            return None
    
    async def insert_log(self, level: str, message: str, source: str = None, user_id: int = None):
        """Insertar log con limpieza automática"""
        try:
            query = """
                INSERT INTO logs (level, message, source, user_id)
                VALUES (?, ?, ?, ?)
            """
            await self.execute_update(query, (level, message, source, user_id))
            
            # Limpiar logs antiguos automáticamente
            await self._cleanup_old_logs()
            
        except Exception as e:
            logger.error(f"❌ Error insertando log: {e}")
    
    async def _cleanup_old_logs(self):
        """Limpiar logs antiguos para ahorrar espacio"""
        try:
            # Mantener solo los últimos 1000 logs
            query = """
                DELETE FROM logs 
                WHERE id NOT IN (
                    SELECT id FROM logs 
                    ORDER BY timestamp DESC 
                    LIMIT 1000
                )
            """
            await self.execute_update(query)
        except Exception as e:
            logger.error(f"❌ Error limpiando logs: {e}")
    
    async def insert_statistic(self, metric_name: str, metric_value: float):
        """Insertar estadística con limpieza automática"""
        try:
            query = """
                INSERT INTO statistics (metric_name, metric_value)
                VALUES (?, ?)
            """
            await self.execute_update(query, (metric_name, metric_value))
            
            # Limpiar estadísticas antiguas
            await self._cleanup_old_statistics()
            
        except Exception as e:
            logger.error(f"❌ Error insertando estadística: {e}")
    
    async def _cleanup_old_statistics(self):
        """Limpiar estadísticas antiguas"""
        try:
            # Mantener solo las últimas 1000 estadísticas por métrica
            query = """
                DELETE FROM statistics 
                WHERE id NOT IN (
                    SELECT id FROM statistics 
                    ORDER BY timestamp DESC 
                    LIMIT 1000
                )
            """
            await self.execute_update(query)
        except Exception as e:
            logger.error(f"❌ Error limpiando estadísticas: {e}")
    
    async def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtener logs recientes optimizado"""
        try:
            query = """
                SELECT * FROM logs 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            return await self.execute_query(query, (limit,))
        except Exception as e:
            logger.error(f"❌ Error obteniendo logs: {e}")
            return []
    
    async def get_system_stats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Obtener estadísticas del sistema optimizado"""
        try:
            query = """
                SELECT metric_name, AVG(metric_value) as avg_value, 
                       MAX(metric_value) as max_value, 
                       MIN(metric_value) as min_value
                FROM statistics 
                WHERE timestamp >= datetime('now', '-{} hours')
                GROUP BY metric_name
            """.format(hours)
            return await self.execute_query(query)
        except Exception as e:
            logger.error(f"❌ Error obteniendo estadísticas: {e}")
            return []
    
    async def update_user_password(self, username: str, new_password_hash: str) -> bool:
        """Actualizar contraseña de usuario"""
        try:
            query = "UPDATE users SET password_hash = ? WHERE username = ?"
            await self.execute_update(query, (new_password_hash, username))
            logger.info(f"✅ Contraseña actualizada para usuario: {username}")
            return True
        except Exception as e:
            logger.error(f"❌ Error actualizando contraseña: {e}")
            return False
    
    async def get_configuration(self, key: str) -> Optional[str]:
        """Obtener configuración por clave"""
        try:
            query = "SELECT value FROM configurations WHERE key = ?"
            result = await self.execute_query(query, (key,))
            return result[0]['value'] if result else None
        except Exception as e:
            logger.error(f"❌ Error obteniendo configuración: {e}")
            return None
    
    async def set_configuration(self, key: str, value: str) -> bool:
        """Establecer configuración"""
        try:
            query = """
                INSERT OR REPLACE INTO configurations (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
            """
            await self.execute_update(query, (key, value))
            logger.info(f"✅ Configuración actualizada: {key}={value}")
            return True
        except Exception as e:
            logger.error(f"❌ Error estableciendo configuración: {e}")
            return False
    
    async def update_service_status(self, service_name: str, status: str) -> bool:
        """Actualizar estado de servicio"""
        try:
            query = """
                INSERT OR REPLACE INTO services (name, status, updated_at)
                VALUES (?, ?, datetime('now'))
            """
            await self.execute_update(query, (service_name, status))
            return True
        except Exception as e:
            logger.error(f"❌ Error actualizando estado de servicio: {e}")
            return False
    
    async def get_logs(self, limit: int = 100, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtener logs con filtros"""
        try:
            if level:
                query = """
                    SELECT * FROM logs 
                    WHERE level = ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """
                return await self.execute_query(query, (level, limit))
            else:
                return await self.get_recent_logs(limit)
        except Exception as e:
            logger.error(f"❌ Error obteniendo logs: {e}")
            return []
    
    async def vacuum_database(self):
        """Optimizar base de datos (ejecutar periódicamente)"""
        try:
            async with self.get_connection() as db:
                await db.execute("VACUUM")
                await db.execute("ANALYZE")
                logger.info("✅ Base de datos optimizada")
        except Exception as e:
            logger.error(f"❌ Error optimizando base de datos: {e}")

# Instancia global de base de datos
db = Database()

async def init_db():
    """Inicializar base de datos"""
    await db.init_database() 