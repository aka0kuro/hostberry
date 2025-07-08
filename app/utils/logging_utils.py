"""
Utilidades de logging para la aplicación.
Configura el sistema de registro centralizado.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

def configure_logging(app):
    """Configura el sistema de logging para la aplicación.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    # Crear directorio de logs si no existe
    log_dir = os.path.join(app.root_path, '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Nombre del archivo de log con fecha
    log_file = os.path.join(log_dir, f'hostberry_{datetime.now().strftime("%Y%m%d")}.log')
    
    # Configurar el nivel de log basado en el entorno
    log_level = logging.DEBUG if app.config.get('DEBUG', False) else logging.INFO
    
    # Configurar el formato del log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configurar el manejador de archivo con rotación
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Configurar el manejador de consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Eliminar manejadores existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Agregar manejadores
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Configurar el logger de la aplicación
    app.logger.handlers = []
    app.logger.propagate = True
    
    # Desactivar el logger de Werkzeug
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers = []
    werkzeug_logger.propagate = True
    
    app.logger.info('Sistema de logging configurado correctamente')

class RequestIdFilter(logging.Filter):
    """Filtro para agregar el ID de solicitud a los registros de log."""
    def filter(self, record):
        from flask import request
        record.request_id = getattr(request, 'request_id', 'no-request')
        return True
