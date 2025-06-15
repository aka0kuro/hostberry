import os
import json
from datetime import timedelta
from pathlib import Path
from typing import Dict, Any, Optional

class Config:
    """Clase base de configuración"""
    # Configuración general
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-key-123')
    
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

# Configuración disponible
config = {
    'development': DevelopmentConfig(),
    'production': ProductionConfig(),
    'default': DevelopmentConfig()
}

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

def save_config(key: str, value: Any) -> bool:
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
