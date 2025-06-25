from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user

def login_required(f):
    """
    Decorador para requerir que el usuario esté autenticado.
    Si no está autenticado, lo redirige a la página de login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Por favor inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    Decorador para requerir que el usuario sea administrador.
    Si no es admin, muestra un error 403.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function
