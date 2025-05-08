from flask import Blueprint

wireguard_bp = Blueprint('wireguard', __name__)

# Importar las rutas después de crear el blueprint
from .wireguard_routes import *  # Esto importará todas las rutas definidas en wireguard_routes.py 