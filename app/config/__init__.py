"""
Módulo de configuración de la aplicación.

Este módulo maneja la configuración de la aplicación en diferentes entornos
y proporciona utilidades para cargar y validar configuraciones.
"""
import os
import json
import secrets
import warnings
from datetime import timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Type, TypeVar, Union

# Tipo genérico para las clases de configuración
T = TypeVar('T', bound='Config')

# Constantes para entornos
ENV_DEVELOPMENT = 'development'
ENV_PRODUCTION = 'production'
ENV_TESTING = 'testing'

# Validar variables de entorno requeridas
REQUIRED_ENV_VARS = {
    ENV_DEVELOPMENT: [],
    ENV_PRODUCTION: [
        'FLASK_SECRET_KEY',
        'SECURITY_PASSWORD_SALT',
        'DATABASE_URL'
    ],
    ENV_TESTING: []
}

class Config:
    """Clase base de configuración.
    
    Esta clase define la configuración predeterminada para la aplicación.
    Las configuraciones específicas del entorno deben heredar de esta clase.
    """
    
    # Configuración general
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32)
    
    # Configuración de la aplicación
    APP_NAME = "HostBerry"
    VERSION = "1.0.0"
    
    # Rutas
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / 'data'
    LOGS_DIR = BASE_DIR / 'logs'
    
    # Configuración de la base de datos
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATA_DIR}/hostberry.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # Configuración de seguridad
    SECURITY_PASSWORD_SALT = os.getenv('SECURITY_PASSWORD_SALT', 'dev-salt-123')
    SECURITY_PASSWORD_HASH = 'bcrypt'
    
    # Configuración de sesión
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Configuración de tokens CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hora
    
    # Configuración de Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_PROTECTION = 'strong'
    
    # Configuración de red
    DEFAULT_NETWORK_INTERFACE = "wlan0"
    
    # Configuración de Babel
    BABEL_DEFAULT_LOCALE = 'es'
    BABEL_SUPPORTED_LOCALES = ['es', 'en']
    BABEL_TRANSLATION_DIRECTORIES = os.path.join(BASE_DIR, 'translations')
    
    def __init__(self):
        # Crear directorios necesarios
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.LOGS_DIR, exist_ok=True)

class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    TESTING = True
    
    # Sobrescribir configuración para desarrollo
    DATABASE_URI = "sqlite:///:memory:"

class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    TESTING = False

def get_config(env: Optional[str] = None) -> Type[Config]:
    """Obtiene la configuración para el entorno especificado.
    
    Args:
        env: Entorno para el que se desea la configuración.
             Si es None, se usará FLASK_ENV o 'development'.
             
    Returns:
        Clase de configuración para el entorno especificado.
        
    Raises:
        ValueError: Si el entorno especificado no es válido.
    """
    if env is None:
        env = os.getenv('FLASK_ENV', ENV_DEVELOPMENT).lower()
    
    config_map = {
        ENV_DEVELOPMENT: DevelopmentConfig,
        ENV_PRODUCTION: ProductionConfig,
        ENV_TESTING: DevelopmentConfig  # Usamos DevelopmentConfig para testing también
    }
    
    config_class = config_map.get(env)
    if config_class is None:
        raise ValueError(f"Entorno no válido: {env}")
    
    # Validar variables de entorno requeridas
    validate_environment(env)
    
    return config_class

def validate_environment(env: str) -> None:
    """Valida que todas las variables de entorno requeridas estén configuradas.
    
    Args:
        env: Entorno a validar.
        
    Raises:
        RuntimeError: Si faltan variables de entorno requeridas.
    """
    missing = []
    for var in REQUIRED_ENV_VARS.get(env, []):
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        raise RuntimeError(
            f"Faltan variables de entorno requeridas para el entorno '{env}': "
            f"{', '.join(missing)}"
        )

# Configuración actual basada en el entorno
current_env = os.getenv('FLASK_ENV', ENV_DEVELOPMENT).lower()
ConfigClass = get_config(current_env)
config = ConfigClass()

# Advertencia si se usa la clave secreta por defecto
if (ConfigClass.SECRET_KEY == 'dev-key-123' and 
    current_env == ENV_PRODUCTION):
    warnings.warn(
        '¡ADVERTENCIA: Se está utilizando una clave secreta por defecto en producción!',
        RuntimeWarning
    )

# Configuración actual basada en entorno
current_env = os.getenv('FLASK_ENV', 'development')
current_config = config.get(current_env, config['default'])

# Cargar configuración adicional desde archivo .env si existe
if (current_config.BASE_DIR / '.env').exists():
    from dotenv import load_dotenv
    load_dotenv(current_config.BASE_DIR / '.env')
    
    # Actualizar configuración desde variables de entorno
    current_config.SECRET_KEY = os.getenv('FLASK_SECRET_KEY', current_config.SECRET_KEY)
    current_config.SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', current_config.SQLALCHEMY_DATABASE_URI)
    current_config.DEFAULT_NETWORK_INTERFACE = os.getenv('DEFAULT_NETWORK_INTERFACE', current_config.DEFAULT_NETWORK_INTERFACE)

    # Actualizar configuración con variables de entorno
    for key, value in os.environ.items():
        if hasattr(current_config, key):
            setattr(current_config, key, value)
        elif key.startswith('FLASK_'):
            # Convertir FLASK_* a atributos de configuración
            config_key = key[6:]
            try:
                # Intentar convertir a tipos de Python
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)
                elif value.replace('.', '', 1).isdigit() and value.count('.') < 2:
                    value = float(value)
                setattr(config, config_key, value)
            except (ValueError, AttributeError):
                setattr(config, config_key, value)

def save_env_config(key: str, value: Any) -> bool:
    """Guarda una configuración en el archivo .env"""
    try:
        from app import create_app
        app = create_app()
        env_path = app.config['BASE_DIR'] / '.env'
        env_lines = []
        key_found = False
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                env_lines = f.readlines()
        
        # Buscar y actualizar la clave si existe
        for i, line in enumerate(env_lines):
            if line.startswith(f"{key}="):
                env_lines[i] = f"{key}={value}\n"
                key_found = True
                break
        
        # Si no existe, agregar al final
        if not key_found:
            env_lines.append(f"{key}={value}\n")
        
        # Escribir de vuelta al archivo
        with open(env_path, 'w') as f:
            f.writelines(env_lines)
        
        # Actualizar el entorno actual
        os.environ[key] = str(value)
        if hasattr(current_config, key):
            setattr(current_config, key, value)
            
        return True
    except Exception as e:
        print(f"Error al guardar configuración: {e}")
        return False
