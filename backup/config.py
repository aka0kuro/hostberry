import os
import secrets
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de la aplicación
class Config:
    # Clave secreta
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    if not SECRET_KEY or len(SECRET_KEY) < 32:
        SECRET_KEY = secrets.token_hex(32)
        with open('.env', 'a') as f:
            f.write(f"FLASK_SECRET_KEY={SECRET_KEY}\n")
    
    # Configuración de sesión
    SESSION_COOKIE_SECURE = False  # Cambiar a True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400
    
    # Configuración de internacionalización
    BABEL_DEFAULT_LOCALE = 'es'
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
    BABEL_SUPPORTED_LOCALES = ['en', 'es']
    
    # Configuración CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_CHECK_DEFAULT = True
    WTF_CSRF_HEADERS = ['X-CSRFToken']
    WTF_CSRF_TIME_LIMIT = 3600
    
    # Rutas
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Configuración de red
    NETWORK_CONFIG_PATH = '/etc/network/interfaces.d/'
    HOSTAPD_CONFIG = '/etc/hostapd/hostapd.conf'
    DHCPCD_CONFIG = '/etc/dhcpcd.conf'
    DNSMASQ_CONFIG = '/etc/dnsmasq.conf'
    
    # Configuración de VPN
    VPN_CONFIG_PATH = '/etc/openvpn/client.conf'
    
    # Configuración de logs
    LOG_FOLDER = os.path.join(BASE_DIR, 'logs')
    LOG_FILE = os.path.join(LOG_FOLDER, 'hostberry.log')
    
    @classmethod
    def init_app(cls, app):
        # Crear directorio de logs si no existe
        if not os.path.exists(cls.LOG_FOLDER):
            os.makedirs(cls.LOG_FOLDER)
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.handlers.RotatingFileHandler(
                    cls.LOG_FILE, maxBytes=10485760, backupCount=5
                ),
                logging.StreamHandler()
            ]
        )

# Configuración de desarrollo
class DevelopmentConfig(Config):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True

# Configuración de producción
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
