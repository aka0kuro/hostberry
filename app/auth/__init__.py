from functools import wraps
from flask import request, jsonify, session, current_app, flash, redirect, url_for
from flask_login import current_user, login_user, logout_user, login_required as flask_login_required
from werkzeug.security import check_password_hash
import logging
from typing import Callable, Any, Optional, Union, Tuple

logger = logging.getLogger(__name__)

# Importar modelos
try:
    from ..models.user import User
except ImportError:
    # Para evitar errores de importación circular
    User = None

def login_required(f: Callable) -> Callable:
    """
    Decorador para requerir autenticación en una ruta.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({
                    'status': 'error',
                    'message': 'Se requiere autenticación',
                    'code': 401
                }), 401
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f: Callable) -> Callable:
    """
    Decorador para requerir rol de administrador.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({
                    'status': 'error',
                    'message': 'Acceso denegado: se requieren privilegios de administrador',
                    'code': 403
                }), 403
            flash('Acceso denegado: se requieren privilegios de administrador', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def authenticate_user(username: str, password: str, remember: bool = False) -> Tuple[bool, dict]:
    """
    Intenta autenticar a un usuario.
    
    Args:
        username: Nombre de usuario
        password: Contraseña sin encriptar
        remember: Si se debe recordar la sesión
        
    Returns:
        tuple: (éxito, datos_del_usuario_o_error)
    """
    user = User.query.filter_by(username=username).first()
    
    if user and user.check_password(password):
        login_user(user, remember=remember)
        user.update_last_seen()
        logger.info(f"Usuario autenticado: {username}")
        return True, {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin
        }
    
    logger.warning(f"Intento de inicio de sesión fallido para el usuario: {username}")
    return False, {'error': 'Usuario o contraseña incorrectos'}

def custom_logout_user() -> None:
    """Cierra la sesión del usuario actual"""
    if current_user.is_authenticated:
        logger.info(f"Usuario desconectado: {current_user.username}")
        logout_user()

def get_current_user() -> Optional[dict]:
    """Obtiene el usuario actualmente autenticado"""
    if current_user.is_authenticated:
        return {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'is_admin': current_user.is_admin,
            'last_seen': current_user.last_seen.isoformat() if current_user.last_seen else None
        }
    return None
