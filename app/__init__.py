import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from flask import Flask, session, redirect, url_for, flash, request, jsonify
from dotenv import load_dotenv

# Importar extensiones
from .extensions import db, login_manager, csrf, babel

# Cargar variables de entorno
load_dotenv()

def create_app(config_name='default'):
    """
    Factory function para crear la aplicación Flask con configuración mejorada
    """
    # Crear instancia de la aplicación
    app = Flask(__name__)
    
    # Cargar configuración
    from app.config import config
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
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    babel.init_app(app)
    
    # Configuración de Babel
    from app.utils.i18n_utils import get_locale
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
        
        # Actualizar última vez que se vio al usuario
        if current_user.is_authenticated:
            current_user.update_last_seen()
    
    # Manejar rutas protegidas
    @login_manager.unauthorized_handler
    def unauthorized():
        if request.blueprint == 'api':
            return jsonify({'error': 'No autorizado'}), 401
        flash('Por favor inicia sesión para acceder a esta página.', 'warning')
        return redirect(url_for('auth.login', next=request.url))
    
    # Configurar contexto de aplicación
    with app.app_context():
        from .services import init_services
        init_services(app)
    
    return app
