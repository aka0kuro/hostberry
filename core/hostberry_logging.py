"""
Sistema de logging optimizado para Raspberry Pi 3
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import psutil
import structlog
from config.settings import settings

# Configuración de idiomas
SUPPORTED_LANGUAGES = ['es', 'en']
DEFAULT_LANGUAGE = 'es'

# Mensajes de log en diferentes idiomas
LOG_MESSAGES = {
    'es': {
        'app_start': 'HostBerry FastAPI iniciado',
        'app_stop': 'HostBerry FastAPI detenido',
        'db_connected': 'Base de datos conectada',
        'db_error': 'Error de base de datos',
        'auth_success': 'Autenticación exitosa',
        'auth_failed': 'Autenticación fallida',
        'api_request': 'Solicitud API recibida',
        'api_response': 'Respuesta API enviada',
        'system_check': 'Verificación del sistema',
        'resource_warning': 'Advertencia de recursos',
        'error_occurred': 'Error ocurrido',
        'info_message': 'Mensaje informativo',
        'debug_message': 'Mensaje de depuración',
        'warning_message': 'Mensaje de advertencia',
        'critical_error': 'Error crítico',
        'performance_metric': 'Métrica de rendimiento',
        'security_event': 'Evento de seguridad',
        'user_action': 'Acción de usuario',
        'system_event': 'Evento del sistema',
        'network_event': 'Evento de red',
        'service_event': 'Evento de servicio',
        'cache_event': 'Evento de caché',
        'database_event': 'Evento de base de datos',
        'file_event': 'Evento de archivo',
        'config_event': 'Evento de configuración',
        'backup_event': 'Evento de backup',
        'update_event': 'Evento de actualización',
        'monitoring_event': 'Evento de monitoreo',
        'optimization_event': 'Evento de optimización'
    },
    'en': {
        'app_start': 'HostBerry FastAPI started',
        'app_stop': 'HostBerry FastAPI stopped',
        'db_connected': 'Database connected',
        'db_error': 'Database error',
        'auth_success': 'Authentication successful',
        'auth_failed': 'Authentication failed',
        'api_request': 'API request received',
        'api_response': 'API response sent',
        'system_check': 'System check',
        'resource_warning': 'Resource warning',
        'error_occurred': 'Error occurred',
        'info_message': 'Information message',
        'debug_message': 'Debug message',
        'warning_message': 'Warning message',
        'critical_error': 'Critical error',
        'performance_metric': 'Performance metric',
        'security_event': 'Security event',
        'user_action': 'User action',
        'system_event': 'System event',
        'network_event': 'Network event',
        'service_event': 'Service event',
        'cache_event': 'Cache event',
        'database_event': 'Database event',
        'file_event': 'File event',
        'config_event': 'Configuration event',
        'backup_event': 'Backup event',
        'update_event': 'Update event',
        'monitoring_event': 'Monitoring event',
        'optimization_event': 'Optimization event'
    }
}

class JSONFormatter(logging.Formatter):
    """Formateador personalizado para logs en JSON"""
    
    def __init__(self, language: str = DEFAULT_LANGUAGE):
        super().__init__()
        self.language = language
    
    def format(self, record: logging.LogRecord) -> str:
        """Formatea el registro de log como JSON"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'language': self.language
        }
        
        # Agregar información adicional si está disponible
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        
        if hasattr(record, 'ip_address'):
            log_entry['ip_address'] = record.ip_address
        
        return json.dumps(log_entry, ensure_ascii=False)

class MultiLanguageLogger:
    """Logger multilingüe para HostBerry"""
    
    def __init__(self, name: str = "hostberry"):
        self.name = name
        self.setup_loggers()
    
    def setup_loggers(self):
        """Configura los loggers para diferentes idiomas"""
        # Crear directorio de logs si no existe. Ojo: puede fallar si /var/log/... no es escribible.
        log_file = getattr(settings, "log_file", "/var/log/hostberry/hostberry.log")
        log_dir = Path(log_file).parent
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback: escribir en /tmp si no se puede crear /var/log/...
            log_file = "/tmp/hostberry.log"
            log_dir = Path(log_file).parent
        except Exception:
            # Fallback genérico
            log_file = "/tmp/hostberry.log"
            log_dir = Path(log_file).parent
        
        # Configurar logger principal
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(getattr(logging, settings.log_level.upper()))
        
        # Evitar duplicación de handlers
        if not self.logger.handlers:
            # Handler para archivo (con fallback si hay permisos)
            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=getattr(settings, "log_max_size", 5 * 1024 * 1024),
                    backupCount=getattr(settings, "log_backup_count", 3),
                    encoding='utf-8'
                )
                file_handler.setFormatter(JSONFormatter())
                self.logger.addHandler(file_handler)
            except PermissionError:
                # Si no podemos escribir en el log, no rompemos la app: usamos stdout.
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(JSONFormatter())
                self.logger.addHandler(console_handler)
            except Exception:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(JSONFormatter())
                self.logger.addHandler(console_handler)
            
            # Handler para consola solo en modo debug
            if settings.debug:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(JSONFormatter())
                self.logger.addHandler(console_handler)
    
    def log(self, level: str, message_key: str, language: str = DEFAULT_LANGUAGE, 
            **kwargs) -> None:
        """
        Registra un mensaje en el idioma especificado
        
        Args:
            level: Nivel de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message_key: Clave del mensaje
            language: Idioma (es, en)
            **kwargs: Variables adicionales para el mensaje
        """
        if language not in SUPPORTED_LANGUAGES:
            language = DEFAULT_LANGUAGE
        
        # Obtener mensaje traducido
        message = LOG_MESSAGES.get(language, {}).get(message_key, message_key)
        
        # Formatear mensaje con variables
        if kwargs:
            try:
                message = message.format(**kwargs)
            except (KeyError, ValueError):
                pass
        
        # Crear registro de log
        log_record = logging.LogRecord(
            name=self.name,
            level=getattr(logging, level.upper()),
            pathname='',
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        
        # Agregar variables adicionales al registro
        for key, value in kwargs.items():
            setattr(log_record, key, value)
        
        self.logger.handle(log_record)
    
    def info(self, message_key: str, language: str = DEFAULT_LANGUAGE, **kwargs):
        self.log('INFO', message_key, language, **kwargs)
    
    def warning(self, message_key: str, language: str = DEFAULT_LANGUAGE, **kwargs):
        self.log('WARNING', message_key, language, **kwargs)
    
    def error(self, message_key: str, language: str = DEFAULT_LANGUAGE, **kwargs):
        self.log('ERROR', message_key, language, **kwargs)
    
    def debug(self, message_key: str, language: str = DEFAULT_LANGUAGE, **kwargs):
        self.log('DEBUG', message_key, language, **kwargs)
    
    def critical(self, message_key: str, language: str = DEFAULT_LANGUAGE, **kwargs):
        self.log('CRITICAL', message_key, language, **kwargs)
    
    def log_both_languages(self, level: str, message_key: str, **kwargs):
        """Registra el mensaje en ambos idiomas"""
        self.log(level, message_key, 'es', **kwargs)
        self.log(level, message_key, 'en', **kwargs)

# Instancia global del logger
logger = MultiLanguageLogger()

def setup_logging():
    """Configura el sistema de logging"""
    try:
        # Configurar structlog para logging estructurado
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        logger.info('logging_configured', language='es')
        
    except Exception as e:
        # Fallback a logging básico si hay error
        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(settings.log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout) if settings.debug else logging.NullHandler()
            ]
        )

def log_system_info():
    """Registra información del sistema"""
    try:
        import psutil
        
        system_info = {
            'hostname': psutil.os.uname().nodename,
            'platform': psutil.os.uname().sysname,
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'disk_total': psutil.disk_usage('/').total
        }
        
        logger.info('system_info', language='es', **system_info)
        
    except Exception as e:
        logger.error('system_info_error', language='es', error=str(e))

def log_performance_metrics():
    """Registra métricas de rendimiento"""
    try:
        import psutil
        
        metrics = {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }
        
        logger.info('performance_metrics', language='es', **metrics)
        
    except Exception as e:
        logger.error('performance_metrics_error', language='es', error=str(e))

def log_api_request(request_id: str, method: str, endpoint: str, 
                   ip_address: str, user_agent: str, user_id: Optional[str] = None):
    """Registra una solicitud API"""
    logger.info('api_request', language='es', 
                request_id=request_id, method=method, endpoint=endpoint,
                ip_address=ip_address, user_agent=user_agent, user_id=user_id)

def log_api_response(request_id: str, status_code: int, response_time: float):
    """Registra una respuesta API"""
    logger.info('api_response', language='es', 
                request_id=request_id, status_code=status_code, response_time=response_time)

def log_auth_event(event_type: str, user_id: Optional[str] = None, 
                   ip_address: Optional[str] = None, success: bool = True):
    """Registra un evento de autenticación"""
    logger.info('auth_event', language='es', 
                event_type=event_type, user_id=user_id, ip_address=ip_address, success=success)

def log_database_event(event_type: str, operation: str, table: Optional[str] = None,
                      error: Optional[str] = None):
    """Registra un evento de base de datos"""
    logger.info('database_event', language='es', 
                event_type=event_type, operation=operation, table=table, error=error)

def log_cache_event(event_type: str, cache_key: Optional[str] = None,
                   cache_stats: Optional[Dict[str, Any]] = None):
    """Registra un evento de caché"""
    logger.info('cache_event', language='es', 
                event_type=event_type, cache_key=cache_key, cache_stats=cache_stats)

def log_security_event(event_type: str, ip_address: Optional[str] = None,
                      user_id: Optional[str] = None, details: Optional[str] = None):
    """Registra un evento de seguridad"""
    logger.info('security_event', language='es', 
                event_type=event_type, ip_address=ip_address, user_id=user_id, details=details)

def log_user_action(action: str, user_id: Optional[str] = None,
                   ip_address: Optional[str] = None, details: Optional[str] = None):
    """Registra una acción de usuario"""
    logger.info('user_action', language='es', 
                action=action, user_id=user_id, ip_address=ip_address, details=details)

def log_system_event(event_type: str, details: Optional[str] = None,
                    resource_usage: Optional[Dict[str, Any]] = None):
    """Registra un evento del sistema"""
    logger.info('system_event', language='es', 
                event_type=event_type, details=details, resource_usage=resource_usage)

def log_network_event(event_type: str, endpoint: Optional[str] = None,
                     ip_address: Optional[str] = None, details: Optional[str] = None):
    """Registra un evento de red"""
    logger.info('network_event', language='es', 
                event_type=event_type, endpoint=endpoint, ip_address=ip_address, details=details)

def log_service_event(event_type: str, service_name: str,
                     status: Optional[str] = None, details: Optional[str] = None):
    """Registra un evento de servicio"""
    logger.info('service_event', language='es', 
                event_type=event_type, service_name=service_name, status=status, details=details)

def log_file_event(event_type: str, file_path: Optional[str] = None,
                   file_size: Optional[int] = None, details: Optional[str] = None):
    """Registra un evento de archivo"""
    logger.info('file_event', language='es', 
                event_type=event_type, file_path=file_path, file_size=file_size, details=details)

def log_config_event(event_type: str, config_key: Optional[str] = None,
                    old_value: Optional[str] = None, new_value: Optional[str] = None):
    """Registra un evento de configuración"""
    logger.info('config_event', language='es', 
                event_type=event_type, config_key=config_key, old_value=old_value, new_value=new_value)

def log_backup_event(event_type: str, backup_path: Optional[str] = None,
                    backup_size: Optional[int] = None, details: Optional[str] = None):
    """Registra un evento de backup"""
    logger.info('backup_event', language='es', 
                event_type=event_type, backup_path=backup_path, backup_size=backup_size, details=details)

def log_update_event(event_type: str, version: Optional[str] = None,
                    details: Optional[str] = None):
    """Registra un evento de actualización"""
    logger.info('update_event', language='es', 
                event_type=event_type, version=version, details=details)

def log_monitoring_event(event_type: str, metric_name: Optional[str] = None,
                        metric_value: Optional[float] = None, threshold: Optional[float] = None):
    """Registra un evento de monitoreo"""
    logger.info('monitoring_event', language='es', 
                event_type=event_type, metric_name=metric_name, metric_value=metric_value, threshold=threshold)

def log_optimization_event(event_type: str, optimization_type: Optional[str] = None,
                          performance_improvement: Optional[float] = None, details: Optional[str] = None):
    """Registra un evento de optimización"""
    logger.info('optimization_event', language='es', 
                event_type=event_type, optimization_type=optimization_type, 
                performance_improvement=performance_improvement, details=details)

def cleanup_old_logs():
    """Limpia logs antiguos"""
    try:
        log_dir = Path(settings.log_file).parent
        current_time = datetime.now()
        
        for log_file in log_dir.glob("*.log.*"):
            file_age = current_time - datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_age.days > 30:  # Eliminar logs de más de 30 días
                log_file.unlink()
                logger.info('old_log_cleaned', language='es', file=str(log_file))
                
    except Exception as e:
        logger.error('cleanup_error', language='es', error=str(e))

def get_logger(name: str = "hostberry") -> MultiLanguageLogger:
    """Obtiene un logger multilingüe"""
    return MultiLanguageLogger(name) 