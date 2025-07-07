from flask import Blueprint, render_template, jsonify, redirect, request, url_for, current_app
from flask_babel import _
from app.utils.i18n_utils import get_locale, inject_get_locale, set_language as set_language_util, check_lang
from app.utils.log_utils import get_logs
from app.utils.security_utils import FAILED_ATTEMPTS, BLOCKED_IPS
from flask_login import login_required

main_bp = Blueprint('main', __name__)

# Registrar la función _ en el contexto de Jinja2
@main_bp.app_context_processor
def inject_babel():
    from flask_babel import gettext as _
    return dict(_=_)

@main_bp.route('/')
@login_required
def index():
    """Página principal de la aplicación"""
    # Ejemplo de uso de traducción
    welcome_message = _('Welcome to HostBerry')
    return render_template('index.html', welcome_message=welcome_message)

@main_bp.route('/api/status')
def status():
    """Endpoint para verificar el estado de la API"""
    return jsonify({
        'status': 'ok',
        'version': '1.0.0',
        'environment': 'development'
    })

@main_bp.route('/set_language/<lang>')
def set_language(lang):
    """Establece el idioma de la sesión."""
    response = set_language_util(lang)
    # Asegurarse de que la respuesta tenga las cabeceras de caché correctas
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response
