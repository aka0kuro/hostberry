from flask import Blueprint

adblock_bp = Blueprint('adblock', __name__)

# Importar las rutas después de crear el blueprint
from .adblock_routes import *  # Esto importará todas las rutas definidas en adblock_routes.py 