from flask import Blueprint

security_bp = Blueprint('security', __name__)

# Importar las rutas después de crear el blueprint
from .security_routes import *  # Esto importará todas las rutas definidas en security_routes.py 