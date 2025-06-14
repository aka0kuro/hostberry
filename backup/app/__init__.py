import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from flask import Flask, session
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

# Inicializar extensiones
babel = Babel()
csrf = CSRFProtect()

# Cargar variables de entorno
load_dotenv()

def create_app(config_name='default'):
    """
    Factory function para crear la aplicación Flask con configuración mejorada
    """
    # Crear instancia de la aplicación
    app = Flask(__name__)
    
    # Cargar configuración
    from config import config
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Configurar logging
    if not app.debug and not app.testing:
        logs_dir = os.path.join(app.root_path, '..', 'logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            
        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'hostberry.log'),
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('HostBerry iniciando...')
    
    # Inicializar extensiones
    babel.init_app(app)
    csrf.init_app(app)
    
    # Configuración de Babel
    from app.utils.i18n import get_locale
    babel.init_app(app, locale_selector=get_locale)
    
    # Registrar blueprints
    from .routes import register_blueprints
    register_blueprints(app)
    
    # Registrar manejadores de error
    from .utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    # Configuración de la sesión
    @app.before_request
    def before_request():
        session.permanent = True
        app.permanent_session_lifetime = timedelta(days=1)
    
    # Configurar contexto de aplicación
    with app.app_context():
        from .services import init_services
        init_services(app)
    
    return app
