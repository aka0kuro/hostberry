"""
API - Módulo principal de la API
Organización de blueprints/routers por versión
"""

# Exportar router principal de v1
from api.v1 import api_v1_router

__all__ = ["api_v1_router"]

