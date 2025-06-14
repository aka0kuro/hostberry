from functools import wraps
from flask import request, jsonify, session
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

# Simulación de base de datos de usuarios (reemplazar con base de datos real)
USERS = {
    'admin': {
        'password': 'admin',  # En producción, usar hash de contraseña
        'role': 'admin',
        'enabled': True
    }
}

def login_required(f: Callable) -> Callable:
    """
    Decorador para requerir autenticación en una ruta.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'error',
                    'message': 'Se requiere autenticación'
                }), 401
            return {'status': 'error', 'message': 'Se requiere autenticación'}, 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f: Callable) -> Callable:
    """
    Decorador para requerir rol de administrador.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or USERS.get(session['user_id'], {}).get('role') != 'admin':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'error',
                    'message': 'Se requieren permisos de administrador'
                }), 403
            return {'status': 'error', 'message': 'Se requieren permisos de administrador'}, 403
        return f(*args, **kwargs)
    return decorated_function

def login_user(username: str, password: str) -> tuple[bool, Optional[dict]]:
    """
    Intenta autenticar a un usuario.
    
    Args:
        username: Nombre de usuario
        password: Contraseña sin encriptar
        
    Returns:
        tuple: (éxito, datos_del_usuario_o_error)
    """
    user = USERS.get(username)
    
    if not user or not user['enabled']:
        logger.warning(f'Intento de inicio de sesión fallido para el usuario: {username}')
        return False, {'error': 'Usuario o contraseña incorrectos'}
    
    # En producción, usar: check_password_hash(user['password'], password)
    if user['password'] != password:
        logger.warning(f'Contraseña incorrecta para el usuario: {username}')
        return False, {'error': 'Usuario o contraseña incorrectos'}
    
    # Iniciar sesión exitosamente
    logger.info(f'Usuario autenticado: {username}')
    return True, {'username': username, 'role': user['role']}

def logout_user() -> None:
    """Cierra la sesión del usuario actual"""
    if 'user_id' in session:
        username = session['user_id']
        session.pop('user_id', None)
        logger.info(f'Usuario desconectado: {username}')

def get_current_user() -> Optional[dict]:
    """Obtiene el usuario actualmente autenticado"""
    if 'user_id' in session:
        user = USERS.get(session['user_id'])
        if user:
            return {
                'username': session['user_id'],
                'role': user['role'],
                'is_authenticated': True
            }
    return None
