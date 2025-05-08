from flask import Blueprint

hostapd_bp = Blueprint('hostapd', __name__)

# Importar las rutas después de crear el blueprint
from .hostapd_routes import *  # Esto importará todas las rutas definidas en hostapd_routes.py 