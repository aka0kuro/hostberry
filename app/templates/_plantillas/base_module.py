"""
Plantilla de módulo para app/
"""

from flask import Blueprint

bp = Blueprint('modulo', __name__)

@bp.route('/')
def index():
    return "Hola desde el módulo"
