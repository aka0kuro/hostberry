"""
Gestión centralizada de versionado
"""

from config.settings import settings


def get_version() -> str:
    """
    Obtiene la versión de la aplicación desde settings
    
    Returns:
        str: Versión de la aplicación
    """
    return getattr(settings, 'version', '2.0.0')


def get_app_name() -> str:
    """
    Obtiene el nombre de la aplicación desde settings
    
    Returns:
        str: Nombre de la aplicación
    """
    return getattr(settings, 'app_name', 'HostBerry')


def get_api_version() -> str:
    """
    Obtiene la versión de la API
    
    Returns:
        str: Versión de la API (actualmente v1)
    """
    return "v1"


def get_full_version_info() -> dict:
    """
    Obtiene información completa de versionado
    
    Returns:
        dict: Información de versiones
    """
    return {
        "app_name": get_app_name(),
        "app_version": get_version(),
        "api_version": get_api_version(),
        "environment": getattr(settings, 'environment', 'production')
    }

