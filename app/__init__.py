from flask import Flask
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect
from config import config
import os

# Inicializar extensiones
babel = Babel()
csrf = CSRFProtect()

def create_app(config_name='default'):
    """
    Factory function para crear la aplicación Flask
    """
    app = Flask(__name__)
    
    # Cargar configuración
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Inicializar extensiones
    babel.init_app(app)
    csrf.init_app(app)
    
    # Registrar blueprints
    from .routes import register_blueprints
    register_blueprints(app)
    
    # Registrar manejadores de error
    from .utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    # Configurar contexto de aplicación
    with app.app_context():
        from .services import init_services
        init_services(app)
    
    return app
