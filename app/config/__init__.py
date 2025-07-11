"""
Configuración de la aplicación HostBerry.
Incluye función get_config para seleccionar configuración por entorno.
"""
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(32).hex())
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///hostberry.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # Solo enviar cookies por HTTPS
    SESSION_COOKIE_HTTPONLY = True  # No accesible por JS
    SESSION_COOKIE_SAMESITE = 'Lax'  # Protección CSRF básica
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    # Puedes añadir más variables globales aquí
    # Permitir solo CORS desde la red local (ajusta según tu rango)
    CORS_ORIGINS = [
        "http://localhost",
        "http://127.0.0.1",
        "http://192.168.0.0/16",
        "http://10.0.0.0/8"
    ]

class ProductionConfig(Config):
    DEBUG = False
    ENV = 'production'
    # Configuración específica para producción

class DevelopmentConfig(Config):
    DEBUG = True
    ENV = 'development'
    SESSION_COOKIE_SECURE = False  # Permitir HTTP en desarrollo
    REMEMBER_COOKIE_SECURE = False
    # Configuración específica para desarrollo

def get_config(env=None):
    env = env or os.environ.get('FLASK_ENV', 'production')
    if env == 'development':
        return DevelopmentConfig
    return ProductionConfig
