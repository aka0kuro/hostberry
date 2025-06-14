from flask import Blueprint, render_template, jsonify
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
