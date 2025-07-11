"""
Módulo principal de la aplicación HostBerry.

Este módulo contiene la fábrica de la aplicación Flask y la configuración principal.
"""
import os
import sys
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any

from flask import Flask, request, current_app
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Importar extensiones después de cargar las variables de entorno
from .extensions import (
    db,
    login_manager,
    csrf,
    babel,
    migrate,
    limiter,
    cache,
    cors
)

# Importar utilidades
from .utils.logging_utils import configure_logging
from .utils.error_handlers import register_error_handlers
from .middleware.security_headers import SecurityHeadersMiddleware

def create_app(config_name: Optional[str] = None) -> Flask:
    """Fábrica de la aplicación Flask.
    
    Args:
        config_name: Nombre de la configuración a cargar (development, production, testing).
                    Si es None, se usará FLASK_ENV o 'development'.
    
    Returns:
        Instancia de la aplicación Flask configurada.
    """
    # Crear instancia de la aplicación
    app = Flask(__name__)
    
    # Configuración inicial para permitir el acceso a la configuración en las extensiones
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Cargar configuración
    from app.config import get_config
    
    # Obtener la configuración adecuada para el entorno
    config_obj = get_config(config_name)
    
    # Aplicar configuración
    app.config.from_object(config_obj)
    
    # Asegurar que los directorios necesarios existan
    ensure_directories(app)
    
    # Configurar logging
    configure_logging(app)
    
    # Inicializar extensiones
    initialize_extensions(app)
    
    # Registrar blueprints
    register_blueprints(app)
    
    # Registrar manejadores de errores
    register_error_handlers(app)
    
    # Configurar middlewares
    SecurityHeadersMiddleware(app)
    
    # Registrar comandos CLI
    register_commands(app)
    
    app.logger.info('Aplicación inicializada en modo: %s', app.config['ENV'])
    return app

def ensure_directories(app: Flask) -> None:
    """Asegura que los directorios necesarios existan."""
    # Directorio para bases de datos
    db_dir = os.path.join(app.root_path, '..', 'data')
    os.makedirs(db_dir, exist_ok=True)
    
    # Directorio para logs
    logs_dir = os.path.join(app.root_path, '..', 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Directorio para subidas de archivos
    uploads_dir = os.path.join(app.root_path, '..', 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)

def initialize_extensions(app: Flask) -> None:
    """Inicializa las extensiones de Flask."""
    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    babel.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    cache.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", ["http://localhost"])}})
    
    # Configuración específica de extensiones
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    login_manager.session_protection = 'strong'
    
    # Configuración de CORS
    if app.config.get('CORS_ENABLED', False):
        cors = CORS(
            app,
            resources={
                r"/api/*": {
                    "origins": app.config.get('CORS_ORIGINS', '*'),
                    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                    "allow_headers": ["Content-Type", "Authorization"],
                    "supports_credentials": True
                }
            },
            supports_credentials=True
        )

def register_blueprints(app: Flask) -> None:
    """Registra los blueprints de la aplicación."""
    from app.routes import register_blueprints as register_app_blueprints
    register_app_blueprints(app)

def register_commands(app: Flask) -> None:
    """Registra comandos personalizados de Flask."""
    @app.cli.command('init-db')
    def init_db():
        """Inicializa la base de datos."""
        with app.app_context():
            db.create_all()
            app.logger.info('Base de datos inicializada')
    
    @app.cli.command('create-admin')
    def create_admin():
        """Crea un usuario administrador."""
        from app.models.user import User
        from werkzeug.security import generate_password_hash
        
        username = input('Nombre de usuario: ')
        email = input('Correo electrónico: ')
        password = input('Contraseña: ')
        
        admin = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            is_admin=True,
            is_active=True
        )
        
        db.session.add(admin)
        db.session.commit()
        app.logger.info(f'Usuario administrador {username} creado exitosamente')
    
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
