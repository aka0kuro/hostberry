#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HostBerry - FastAPI Application optimizada para Raspberry Pi 3
Aplicación web para gestionar servicios de red en Raspberry Pi
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.bccache import FileSystemBytecodeCache
import uvicorn

from config.settings import settings
from core.database import db, init_db
from core.logging import (
    setup_logging, log_system_info, log_performance_metrics, 
    logger, log_api_request, log_api_response, log_system_event,
    cleanup_old_logs
)
from core.cache import cache
from system.system_utils import optimize_system_for_rpi

# Importar routers
from api.v1 import auth, system, wifi, vpn, wireguard, adblock, hostapd
from web import routes as web_routes

# Configurar templates con caché (Jinja2)
def create_templates():
    env = Environment(
        loader=FileSystemLoader("website/templates"),
        autoescape=select_autoescape(["html", "xml"]),
        cache_size=200  # caché moderada para RPi 3
    )
    # Cacheo persistente de bytecode para plantillas (acelera arranque)
    try:
        env.bytecode_cache = FileSystemBytecodeCache(directory="instance/jinja_cache", pattern="%s.cache")
    except Exception:
        pass
    # Proveer función de traducción segura para templates
    env.globals["t"] = lambda key, default=None: default or key
    # Compatibilidad con versiones de Starlette sin soporte de parámetro env
    templates = Jinja2Templates(directory="website/templates")
    templates.env = env
    return templates

templates = create_templates()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    # Inicio de la aplicación
    log_system_event("app_startup", "Iniciando HostBerry FastAPI")
    setup_logging()
    log_system_info()
    
    # Optimizaciones para RPi
    if settings.rpi_optimization:
        optimize_system_for_rpi()
        log_system_event("rpi_optimization", "Optimizaciones RPi aplicadas")
    
    # Inicializar base de datos
    await db.init_database()
    log_system_event("database_initialized", "Base de datos inicializada")
    
    # Limpiar logs antiguos
    cleanup_old_logs()
    
    yield
    
    # Cierre de la aplicación
    log_system_event("app_shutdown", "Deteniendo HostBerry FastAPI")
    cache.clear()
    await db.vacuum_database()

# Crear aplicación FastAPI
app = FastAPI(
    title="HostBerry FastAPI",
    description="API optimizada para Raspberry Pi 3",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=JSONResponse
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Configurar middleware de seguridad
# if settings.security_headers_enabled:
#     from core.security_middleware import create_security_middleware
#     app.add_middleware(create_security_middleware())

# Configurar compresión GZip
if settings.compression_enabled:
    # aumentar tamaño mínimo para reducir CPU en Pi 3
    app.add_middleware(GZipMiddleware, minimum_size=4096)

# Middleware de logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware para logging de requests"""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Obtener información del request
    method = request.method
    endpoint = str(request.url.path)
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Evitar logging detallado para estáticos y health para ahorrar I/O
    if not (endpoint.startswith("/static") or endpoint in ("/health", "/favicon.ico")):
        log_api_request(
            request_id=request_id,
            method=method,
            endpoint=endpoint,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    # Procesar request
    try:
        response = await call_next(request)
        response_time = time.time() - start_time
        
        if not (endpoint.startswith("/static") or endpoint in ("/health", "/favicon.ico")):
            # Log de la respuesta
            log_api_response(
                request_id=request_id,
                status_code=response.status_code,
                response_time=response_time
            )
        
        return response
        
    except Exception as e:
        response_time = time.time() - start_time
        logger.error(f"Request error: {e}")
        
        # Log de error
        log_api_response(
            request_id=request_id,
            status_code=500,
            response_time=response_time
        )
        
        raise

# Manejador global de excepciones
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejador global de excepciones"""
    logger.error(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "detail": str(exc) if settings.debug else "Ha ocurrido un error inesperado",
        },
    )

# Montar archivos estáticos (carpeta consolidada en website/static)
app.mount("/static", StaticFiles(directory="website/static"), name="static")

# Incluir routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
app.include_router(wifi.router, prefix="/api/v1/wifi", tags=["wifi"])
app.include_router(vpn.router, prefix="/api/v1/vpn", tags=["vpn"])
app.include_router(wireguard.router, prefix="/api/v1/wireguard", tags=["wireguard"])
app.include_router(adblock.router, prefix="/api/v1/adblock", tags=["adblock"])
app.include_router(hostapd.router, prefix="/api/v1/hostapd", tags=["hostapd"])

# Incluir router de seguridad
from api.v1 import security
app.include_router(security.router, prefix="/api/v1", tags=["security"])

# Incluir rutas web

app.include_router(web_routes.router, tags=["web"])

# Endpoints básicos (mantener healthcheck)

@app.get("/health")
async def health_check():
    """Health check endpoint (ligero, sin dependencia de BD)"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "2.0.0"
    }

@app.get("/system/info")
async def system_info():
    """Información del sistema"""
    try:
        import psutil
        
        return {
            "hostname": psutil.os.uname().nodename,
            "platform": psutil.os.uname().sysname,
            "python_version": f"{psutil.os.uname().release}",
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_usage": psutil.disk_usage('/').percent
        }
    except Exception as e:
        logger.error(f"System info error: {e}")
        return {"error": "No se pudo obtener información del sistema"}

# Endpoints de caché
@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """Obtener estadísticas del caché"""
    try:
        return cache.get_stats()
    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        return {"error": "No se pudieron obtener estadísticas del caché"}

@app.post("/api/v1/cache/clear")
async def clear_cache():
    """Limpiar caché"""
    try:
        cache.clear()
        return {"message": "Caché limpiado correctamente"}
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return {"error": "No se pudo limpiar el caché"}

def run_app():
    """Función para ejecutar la aplicación"""
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        access_log=True if settings.debug else False,
        log_level=settings.log_level.lower()
    )

if __name__ == "__main__":
    run_app() 