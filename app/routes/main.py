from flask import Blueprint, render_template, jsonify, redirect, request, url_for
from app.utils.i18n_utils import get_locale, inject_get_locale, set_language as set_language_util, check_lang
from app.utils.log_utils import get_logs
from app.utils.security_utils import FAILED_ATTEMPTS, BLOCKED_IPS
from flask_login import login_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    """Página principal de la aplicación"""
    return render_template('index.html')

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
    set_language_util(lang)
    return redirect(request.referrer or url_for('main.index'))
