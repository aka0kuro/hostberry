"""
Configuración de HostBerry optimizada para Raspberry Pi 3
"""

import os
from typing import Optional, List
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    """Configuración de la aplicación optimizada para Raspberry Pi 3"""
    
    # Configuración básica
    app_name: str = "HostBerry"
    version: str = "2.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Configuración del servidor optimizada para RPi 3
    host: str = Field(default="127.0.0.1", env="HOST")  # Solo localhost para mayor seguridad
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")  # RPi 3: 1 worker para ahorrar memoria
    
    # Configuración de seguridad
    secret_key: str = Field(default="", env="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60  # Aumentado para reducir regeneración de tokens
    

    
    # Configuraciones de seguridad adicionales
    password_min_length: int = Field(default=8, env="PASSWORD_MIN_LENGTH")
    password_require_uppercase: bool = Field(default=True, env="PASSWORD_REQUIRE_UPPERCASE")
    password_require_lowercase: bool = Field(default=True, env="PASSWORD_REQUIRE_LOWERCASE")
    password_require_numbers: bool = Field(default=True, env="PASSWORD_REQUIRE_NUMBERS")
    password_require_special: bool = Field(default=True, env="PASSWORD_REQUIRE_SPECIAL")
    session_timeout_minutes: int = Field(default=30, env="SESSION_TIMEOUT_MINUTES")
    max_concurrent_sessions: int = Field(default=3, env="MAX_CONCURRENT_SESSIONS")
    
    # Configuración de rate limiting
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # segundos
    
    # Configuración de headers de seguridad
    security_headers_enabled: bool = Field(default=True, env="SECURITY_HEADERS_ENABLED")
    hsts_max_age: int = Field(default=31536000, env="HSTS_MAX_AGE")  # 1 año
    content_security_policy: str = Field(
        default="default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; img-src 'self' data:; font-src 'self' cdn.jsdelivr.net;",
        env="CONTENT_SECURITY_POLICY"
    )
    
    # Configuración de auditoría
    audit_log_enabled: bool = Field(default=True, env="AUDIT_LOG_ENABLED")
    audit_log_file: str = Field(default="", env="AUDIT_LOG_FILE")  # Se construirá dinámicamente
    sensitive_operations_logging: bool = Field(default=True, env="SENSITIVE_OPERATIONS_LOGGING")
    
    # Configuración de backup y recuperación
    auto_backup_enabled: bool = Field(default=True, env="AUTO_BACKUP_ENABLED")
    backup_interval_hours: int = Field(default=24, env="BACKUP_INTERVAL_HOURS")
    backup_retention_days: int = Field(default=30, env="BACKUP_RETENTION_DAYS")
    backup_encryption_enabled: bool = Field(default=True, env="BACKUP_ENCRYPTION_ENABLED")
    
    # Configuración de monitoreo de seguridad
    security_monitoring_enabled: bool = Field(default=True, env="SECURITY_MONITORING_ENABLED")
    failed_login_threshold: int = Field(default=5, env="FAILED_LOGIN_THRESHOLD")
    suspicious_activity_threshold: int = Field(default=10, env="SUSPICIOUS_ACTIVITY_THRESHOLD")
    
    # Configuración de IP whitelist/blacklist
    ip_whitelist_enabled: bool = Field(default=False, env="IP_WHITELIST_ENABLED")
    ip_blacklist_enabled: bool = Field(default=True, env="IP_BLACKLIST_ENABLED")
    ip_whitelist: List[str] = Field(default=[], env="IP_WHITELIST")
    ip_blacklist: List[str] = Field(default=[], env="IP_BLACKLIST")
    
    # Configuración de autenticación de dos factores
    two_factor_enabled: bool = Field(default=False, env="TWO_FACTOR_ENABLED")
    two_factor_required_for_admin: bool = Field(default=True, env="TWO_FACTOR_REQUIRED_FOR_ADMIN")
    
    # Configuración de encriptación de datos
    data_encryption_enabled: bool = Field(default=True, env="DATA_ENCRYPTION_ENABLED")
    encryption_key: str = Field(default="", env="ENCRYPTION_KEY")
    
    # Configuración de validación de entrada
    input_validation_enabled: bool = Field(default=True, env="INPUT_VALIDATION_ENABLED")
    max_request_size: int = Field(default=10 * 1024 * 1024, env="MAX_REQUEST_SIZE")  # 10MB
    max_upload_files: int = Field(default=5, env="MAX_UPLOAD_FILES")
    
    # Configuración de base de datos optimizada para RPi 3
    database_url: str = Field(default="sqlite:///./hostberry.db", env="DATABASE_URL")
    database_pool_size: int = Field(default=3, env="DB_POOL_SIZE")  # Pool muy reducido para RPi 3
    database_max_overflow: int = Field(default=5, env="DB_MAX_OVERFLOW")  # Overflow reducido para RPi 3
    database_echo: bool = Field(default=False, env="DB_ECHO")  # No mostrar SQL en logs
    database_pool_pre_ping: bool = Field(default=False, env="DB_POOL_PRE_PING")  # Deshabilitar pre-ping
    
    # Configuración de logging optimizada para RPi 3
    log_level: str = Field(default="WARNING", env="LOG_LEVEL")  # Reducido para ahorrar I/O
    log_file: str = Field(default="", env="LOG_FILE")  # Se construirá dinámicamente
    log_max_size: int = Field(default=2 * 1024 * 1024, env="LOG_MAX_SIZE")  # 2MB máximo para RPi 3
    log_backup_count: int = Field(default=2, env="LOG_BACKUP_COUNT")  # Solo 2 backups para RPi 3
    
    # Optimizaciones específicas para RPi 3
    rpi_optimization: bool = Field(default=True, env="RPI_OPTIMIZATION")
    auto_cleanup_logs: bool = Field(default=True, env="AUTO_CLEANUP_LOGS")
    auto_vacuum_db: bool = Field(default=True, env="AUTO_VACUUM_DB")
    compression_enabled: bool = Field(default=True, env="COMPRESSION_ENABLED")
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_ttl: int = Field(default=300, env="CACHE_TTL")  # 5 minutos
    max_connections: int = Field(default=50, env="MAX_CONNECTIONS")  # Limitado para RPi 3
    
    # Configuración de CORS
    cors_origins: List[str] = Field(default=["*"], env="CORS_ORIGINS")
    
    # Configuración de archivos optimizada para RPi
    upload_dir: str = Field(default="uploads", env="UPLOAD_DIR")
    max_file_size: int = Field(default=8 * 1024 * 1024, env="MAX_FILE_SIZE")  # 8MB máximo
    
    # Configuración de servicios optimizada
    hostapd_config_path: str = "/etc/hostapd/hostapd.conf"
    wpa_supplicant_path: str = "/etc/wpa_supplicant/wpa_supplicant.conf"
    wpa_supplicant_dir: str = "/var/run/wpa_supplicant"
    openvpn_config_path: str = "/etc/openvpn/client.conf"
    wireguard_config_path: str = "/etc/wireguard/wg0.conf"
    
    # Configuración de idioma
    default_language: str = Field(default="es", env="DEFAULT_LANGUAGE")
    supported_languages: List[str] = ["en", "es"]
    
    # Configuración de timezone
    default_timezone: str = Field(default="UTC", env="DEFAULT_TIMEZONE")
    
    # Configuración de AdBlock optimizada para RPi
    adblock_enabled: bool = Field(default=True, env="ADBLOCK_ENABLED")
    adblock_update_interval: int = Field(default=604800, env="ADBLOCK_UPDATE_INTERVAL")  # 7 días
    adblock_max_lists: int = Field(default=3, env="ADBLOCK_MAX_LISTS")  # Máximo 3 listas
    adblock_cache_size: int = Field(default=50 * 1024 * 1024, env="ADBLOCK_CACHE_SIZE")  # 50MB
    
    # Configuración de monitoreo optimizada
    monitoring_enabled: bool = Field(default=True, env="MONITORING_ENABLED")
    stats_update_interval: int = Field(default=60, env="STATS_UPDATE_INTERVAL")  # 60 segundos
    stats_history_size: int = Field(default=100, env="STATS_HISTORY_SIZE")  # Solo 100 registros
    
    # Configuración de autenticación
    default_username: str = Field(default="admin", env="DEFAULT_USERNAME")
    default_password: str = Field(default="hostberry", env="DEFAULT_PASSWORD")
    max_login_attempts: int = Field(default=3, env="MAX_LOGIN_ATTEMPTS")  # Reducido
    login_block_duration: int = Field(default=1800, env="LOGIN_BLOCK_DURATION")  # 30 minutos
    bcrypt_rounds: int = Field(default=12, env="BCRYPT_ROUNDS")  # Reducir si es necesario en RPi
    
    # Configuración específica para RPi 3
    rpi_optimization: bool = Field(default=True, env="RPI_OPTIMIZATION")
    cpu_throttle_threshold: float = Field(default=0.8, env="CPU_THROTTLE_THRESHOLD")  # 80%
    memory_threshold: float = Field(default=0.9, env="MEMORY_THRESHOLD")  # 90%
    temp_threshold: float = Field(default=70.0, env="TEMP_THRESHOLD")  # 70°C
    
    # Configuración de caché optimizada
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_max_size: int = Field(default=50, env="CACHE_MAX_SIZE")  # 50 elementos
    
    # Configuración de compresión
    compression_enabled: bool = Field(default=True, env="COMPRESSION_ENABLED")
    compression_level: int = Field(default=6, env="COMPRESSION_LEVEL")  # Nivel medio
    
    # Configuración de timeouts optimizada
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")  # 30 segundos
    database_timeout: int = Field(default=10, env="DB_TIMEOUT")  # 10 segundos
    service_timeout: int = Field(default=15, env="SERVICE_TIMEOUT")  # 15 segundos
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Generar secret_key si no está configurado
        if not self.secret_key:
            self.secret_key = os.urandom(32).hex()
        
        # Crear directorios necesarios usando rutas del sistema
        logs_dir = "/var/log/hostberry"
        uploads_dir = "/var/lib/hostberry/uploads"
        instance_dir = "/var/lib/hostberry/instance"
        
        os.makedirs(logs_dir, exist_ok=True)
        os.makedirs(uploads_dir, exist_ok=True)
        os.makedirs(instance_dir, exist_ok=True)
        
        # Establecer rutas de archivos dinámicamente
        if not self.audit_log_file:
            self.audit_log_file = os.path.join(logs_dir, "audit.log")
        if not self.log_file:
            self.log_file = os.path.join(logs_dir, "hostberry.log")
        
        # Optimizaciones específicas para RPi 3
        if self.rpi_optimization:
            self._apply_rpi_optimizations()
    
    def _apply_rpi_optimizations(self):
        """Aplicar optimizaciones específicas para Raspberry Pi 3"""
        # Reducir workers si hay poca memoria
        try:
            from core import system_light as psutil
            memory_gb = psutil.virtual_memory().total / (1024**3)
            if memory_gb < 1.0:  # Menos de 1GB
                self.workers = 1
                self.log_level = "ERROR"  # Solo errores críticos
                self.stats_update_interval = 120  # 2 minutos
                self.cache_max_size = 25  # Reducir caché
                # Reducir rounds de bcrypt para acelerar en RPi 3 (costo de CPU)
                self.bcrypt_rounds = min(self.bcrypt_rounds, 12)
        except Exception:
            pass  # Fallback si falla system_light

        # Ajustar según temperatura
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000
                if temp > 60:  # Si está caliente
                    self.stats_update_interval = 180  # 3 minutos
                    self.cache_enabled = False  # Deshabilitar caché
        except:
            pass  # Ignorar si no se puede leer temperatura

# Instancia global de configuración
settings = Settings() 