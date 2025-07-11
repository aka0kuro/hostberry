"""
Inicialización del módulo de autenticación.
Importa decoradores y utilidades necesarias.
"""

from .decorators import login_required, admin_required
from .routes import auth_bp

__all__ = ['login_required', 'admin_required', 'auth_bp']
