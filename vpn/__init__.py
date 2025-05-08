from flask import Blueprint

vpn_bp = Blueprint('vpn', __name__)

# Importar las rutas después de crear el blueprint
from .vpn_routes import *  # Esto importará todas las rutas definidas en vpn_routes.py
