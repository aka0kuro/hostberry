"""
Módulo para inicializar las extensiones de Flask.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel
from flask_migrate import Migrate

# Inicializar extensiones
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

# Configuración de Babel
babel = Babel()

# Configuración de Flask-Login
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'warning'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
login_manager.session_protection = 'strong'
