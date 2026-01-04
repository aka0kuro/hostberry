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
        # ... (código existente de resolución de ruta) ...
        db_path_env = os.getenv("DB_PATH")
        if db_path_env:
            self.db_path = db_path_env
        else:
            db_url = getattr(settings, "database_url", "sqlite:///./hostberry.db")
            if isinstance(db_url, str) and db_url.startswith("sqlite:"):
                if db_url.startswith("sqlite:////"):
                    self.db_path = db_url.replace("sqlite:////", "/", 1)
                elif db_url.startswith("sqlite:///"):
                    self.db_path = db_url.replace("sqlite:///", "", 1)
                else:
                    self.db_path = db_url.split("sqlite:")[-1].lstrip("/")
            else:
                self.db_path = "hostberry.db"
        
        self.timeout = settings.database_timeout
        self._connection = None
        self._lock = asyncio.Lock()

    async def _create_tables(self, db):
        """Crear tablas de la base de datos con índices optimizados"""
        try:
            # Tabla de usuarios
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            """)
            
            # Índice para búsquedas por username (muy frecuente)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
            """)
            
            # Tabla de logs
            await db.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    source TEXT,
                    user_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # Índices para logs (queries frecuentes)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id)
            """)
            
            # Tabla de estadísticas
            await db.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Índices para estadísticas (queries frecuentes)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_statistics_metric_name ON statistics(metric_name)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_statistics_timestamp ON statistics(timestamp DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_statistics_metric_timestamp ON statistics(metric_name, timestamp DESC)
            """)
            
            # Tabla de configuraciones
            await db.execute("""
                CREATE TABLE IF NOT EXISTS configurations (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla de servicios
            await db.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    config TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info("✅ Tablas creadas/verificadas")
            
        except Exception as e:
            logger.error(f"❌ Error creando tablas: {e}")
            raise

    async def init_database(self):
        """Inicializar base de datos con conexión persistente"""
        logger.info("🗄️ Inicializando base de datos optimizada para Raspberry Pi 3")
        logger.info(f"🗄️ Ruta de base de datos: {self.db_path}")
        
        try:
            # Asegurar que el directorio padre existe
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            if db_dir and not os.path.exists(db_dir):
                logger.warning(f"Directorio de base de datos no existe: {db_dir}, creándolo...")
                os.makedirs(db_dir, mode=0o755, exist_ok=True)
            
            # Verificar permisos del directorio
            if os.path.exists(self.db_path):
                if not os.access(self.db_path, os.W_OK):
                    logger.error(f"Sin permisos de escritura en: {self.db_path}")
                    raise PermissionError(f"No se puede escribir en {self.db_path}")
            elif db_dir and not os.access(db_dir, os.W_OK):
                logger.error(f"Sin permisos de escritura en el directorio: {db_dir}")
                raise PermissionError(f"No se puede escribir en el directorio {db_dir}")
            
            # Establecer conexión persistente
            if not self._connection:
                self._connection = await aiosqlite.connect(
                    self.db_path,
                    timeout=self.timeout,
                    check_same_thread=False
                )
                
                # Configurar SQLite para RPi 3 (optimizado para rendimiento)
                await self._connection.execute("PRAGMA journal_mode = WAL")
                await self._connection.execute("PRAGMA synchronous = NORMAL")
                await self._connection.execute("PRAGMA foreign_keys = ON")
                # Optimizaciones de rendimiento (habilitadas para mejor performance)
                await self._connection.execute("PRAGMA cache_size = -2000")  # 2MB cache
                await self._connection.execute("PRAGMA temp_store = MEMORY")
                await self._connection.execute("PRAGMA mmap_size = 268435456")  # 256MB mmap
                # Connection pooling implícito con aiosqlite (reutiliza conexiones)
                await self._connection.execute("PRAGMA busy_timeout = 5000")  # 5 segundos timeout
                
                # Crear tablas
                await self._create_tables(self._connection)
                
                # Asegurar admin
                await self.ensure_default_admin()
                
                logger.info("✅ Base de datos inicializada y conectada")
                
        except Exception as e:
            logger.error(f"❌ Error inicializando base de datos: {e}")
            raise

    async def close(self):
        """Cerrar conexión persistente"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("🗄️ Conexión de base de datos cerrada")

    @asynccontextmanager
    async def get_connection(self):
        """Obtener la conexión persistente (thread-safe con lock y pooling)"""
        if not self._connection:
            await self.init_database()
        
        # Verificar si la conexión está cerrada y reconectar si es necesario
        try:
            # Test simple para verificar conexión
            await self._connection.execute("SELECT 1")
        except Exception:
            # Reconectar si la conexión está cerrada
            logger.warning("Conexión cerrada, reconectando...")
            self._connection = None
            await self.init_database()
            
        async with self._lock:
            yield self._connection

    async def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Ejecutar consulta usando conexión persistente"""
        try:
            async with self.get_connection() as db:
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    if cursor.description:
                        columns = [description[0] for description in cursor.description]
                        return [dict(zip(columns, row)) for row in rows]
                    return []
        except Exception as e:
            logger.error(f"❌ Error ejecutando consulta: {e}")
            # Si hay error de conexión, intentar reconectar
            if "closed" in str(e).lower():
                self._connection = None
            raise

    async def execute_update(self, query: str, params: tuple = ()) -> int:
        """Ejecutar actualización usando conexión persistente"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(query, params)
                await db.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"❌ Error ejecutando actualización: {e}")
            if "closed" in str(e).lower():
                self._connection = None
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
            # Usar conexión directa ya que estamos en init_database
            if not self._connection:
                return
            
            async with self._lock:
                cursor = await self._connection.execute("SELECT COUNT(*) as cnt FROM users")
                row = await cursor.fetchone()
                count = row[0] if row else 0
                
                if count == 0:
                    from config.settings import settings
                    from core.security import get_password_hash
                    
                    password_hash = get_password_hash(settings.default_password)
                    await self._connection.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (settings.default_username, password_hash)
                    )
                    await self._connection.commit()
                    logger.info("✅ Usuario admin por defecto creado")
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
            # Si user_id es un string (username), intentar obtener el ID numérico
            user_id_int = None
            if user_id:
                if isinstance(user_id, str):
                    # Intentar obtener ID del usuario por username
                    try:
                        user = await self.get_user_by_username(user_id)
                        if user and 'id' in user:
                            user_id_int = user['id']
                    except Exception:
                        pass
                else:
                    user_id_int = user_id
            
            query = """
                INSERT INTO logs (level, message, source, user_id)
                VALUES (?, ?, ?, ?)
            """
            await self.execute_update(query, (level, message, source, user_id_int))
            
            # Limpiar logs antiguos automáticamente (solo cada 100 logs para no sobrecargar)
            import random
            if random.randint(1, 100) == 1:  # 1% de probabilidad
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
        """Obtener logs recientes optimizado (con índice)"""
        try:
            # Query optimizada usando índice idx_logs_timestamp
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
        """Obtener estadísticas del sistema optimizado (con índices)"""
        try:
            # Query optimizada usando índices idx_statistics_metric_timestamp
            query = """
                SELECT metric_name, AVG(metric_value) as avg_value, 
                       MAX(metric_value) as max_value, 
                       MIN(metric_value) as min_value
                FROM statistics 
                WHERE timestamp >= datetime('now', '-{} hours')
                GROUP BY metric_name
                ORDER BY metric_name
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
        """Obtener logs con filtros (optimizado con índices)"""
        try:
            if level:
                # Query optimizada usando índices idx_logs_level y idx_logs_timestamp
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