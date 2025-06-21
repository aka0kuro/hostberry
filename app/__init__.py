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
    from app.config import config, current_config
    
    # Usar la configuración solicitada o la predeterminada
    config_obj = config.get(config_name, config['default'])
    
    # Cargar configuración en la aplicación
    app.config.from_object(config_obj)
    
    # Inicializar la configuración
    if hasattr(config_obj, 'init_app'):
        config_obj.init_app(app)
    
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
    
    # Configurar Babel
    from app.utils.i18n_utils import get_locale
    
    # Inicializar Babel con la aplicación
    babel.init_app(app)
    
    # Asegurarse de que la configuración de Babel sea correcta
    if 'BABEL_DEFAULT_LOCALE' not in app.config:
        app.config['BABEL_DEFAULT_LOCALE'] = 'es'
    if 'BABEL_SUPPORTED_LOCALES' not in app.config:
        app.config['BABEL_SUPPORTED_LOCALES'] = ['es', 'en']
    
    # Registrar el selector de idioma para Babel
    @babel.localeselector
    def babel_get_locale():
        try:
            locale = get_locale()
            app.logger.debug(f'Babel locale seleccionado: {locale}')
            return locale
        except Exception as e:
            app.logger.error(f'Error al obtener el locale: {str(e)}')
            return app.config['BABEL_DEFAULT_LOCALE']
    
    # Registrar función get_locale como global de Jinja2
    app.jinja_env.globals['get_locale'] = get_locale
    app.logger.info('Configuración de internacionalización inicializada correctamente')
    
    # Registrar blueprints
    from .routes import register_blueprints
    register_blueprints(app)
    
    # Registrar manejadores de error
    from .utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    # Configuración de la sesión
    @app.before_request
    def before_request():
        from flask_login import current_user
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
    
    # La función get_locale ya está registrada como global de Jinja2

    # Configurar contexto de aplicación
    with app.app_context():
        from .services import init_services
        init_services(app)
        
            # Verificar y registrar la configuración de Babel
        app.logger.info(f'BABEL_DEFAULT_LOCALE: {app.config.get("BABEL_DEFAULT_LOCALE")}')
        app.logger.info(f'BABEL_SUPPORTED_LOCALES: {app.config.get("BABEL_SUPPORTED_LOCALES")}')
        
        # Verificar que la función get_locale esté disponible en el contexto de Jinja2
        if 'get_locale' not in app.jinja_env.globals:
            app.logger.error('get_locale no está disponible en el contexto de Jinja2')
        else:
            app.logger.info('get_locale está correctamente registrado en el contexto de Jinja2')
    
    return app
