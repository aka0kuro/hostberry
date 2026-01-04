"""
API v1 - Router principal que agrupa todos los endpoints
Estructura de blueprints/routers organizada
"""

from fastapi import APIRouter

# Importar todos los routers
from api.v1 import (
    auth,
    system,
    wifi,
    vpn,
    wireguard,
    adblock,
    hostapd,
    security,
    translations,
    stats
)

# Crear router principal de API v1
api_v1_router = APIRouter(prefix="/api/v1", tags=["api-v1"])

# Registrar todos los routers en el router principal
api_v1_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_v1_router.include_router(system.router, prefix="/system", tags=["system"])
api_v1_router.include_router(wifi.router, prefix="/wifi", tags=["wifi"])
api_v1_router.include_router(vpn.router, prefix="/vpn", tags=["vpn"])
api_v1_router.include_router(wireguard.router, prefix="/wireguard", tags=["wireguard"])
api_v1_router.include_router(adblock.router, prefix="/adblock", tags=["adblock"])
api_v1_router.include_router(hostapd.router, prefix="/hostapd", tags=["hostapd"])
api_v1_router.include_router(security.router, tags=["security"])
api_v1_router.include_router(translations.router, prefix="/translations", tags=["translations"])
api_v1_router.include_router(stats.router, prefix="/stats", tags=["statistics"])

# Exportar router principal
__all__ = ["api_v1_router"]
