#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HostBerry - FastAPI Application OPTIMIZADA para Raspberry Pi 3
Aplicación web para gestionar servicios de red en Raspberry Pi
"""

# Imports optimizados - solo lo necesario
import time  # Necesario para cache de system_info
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.bccache import FileSystemBytecodeCache

# Imports locales optimizados
from config.settings import settings
from core.database import db
from core.logging import (
    setup_logging, log_system_info, logger, 
    log_system_event, cleanup_old_logs
)
from core.cache import cache
from system.system_utils import optimize_system_for_rpi

# Importar routers
from api.v1 import auth, system, wifi, vpn, wireguard, adblock, hostapd
from web import routes as web_routes

# Configurar templates con caché optimizada para RPi 3
def create_templates():
    env = Environment(
        loader=FileSystemLoader("website/templates"),
        autoescape=select_autoescape(["html", "xml"]),
        cache_size=100,  # caché reducida para RPi 3 (menos memoria)
        auto_reload=False,  # deshabilitar auto-reload en producción
        trim_blocks=True,  # optimizar espacios en blanco
        lstrip_blocks=True  # optimizar bloques
    )
    
    # Cacheo persistente de bytecode para plantillas (acelera arranque)
    try:
        env.bytecode_cache = FileSystemBytecodeCache(
            directory="instance/jinja_cache", 
            pattern="%s.cache"
        )
    except Exception:
        pass
    
    # Función de traducción optimizada
    env.globals["t"] = lambda key, default=None: default or key
    
    # Compatibilidad con versiones de Starlette
    templates = Jinja2Templates(directory="website/templates")
    templates.env = env
    return templates

templates = create_templates()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación optimizada para RPi 3"""
    try:
        # Inicio de la aplicación
        log_system_event("app_startup", "Iniciando HostBerry FastAPI")
        setup_logging()
        
        # Solo log_system_info si está en modo debug
        if settings.debug:
            log_system_info()
        
        # Optimizaciones para RPi (solo si está habilitado)
        if getattr(settings, 'rpi_optimization', False):
            optimize_system_for_rpi()
            log_system_event("rpi_optimization", "Optimizaciones RPi aplicadas")
        
        # Inicializar base de datos
        await db.init_database()
        log_system_event("database_initialized", "Base de datos inicializada")
        
        # Limpiar logs antiguos solo si es necesario
        if getattr(settings, 'auto_cleanup_logs', True):
            cleanup_old_logs()
        
    except Exception as e:
        logger.error(f"Error durante el inicio: {e}")
        raise
    
    yield
    
    try:
        # Cierre de la aplicación
        log_system_event("app_shutdown", "Deteniendo HostBerry FastAPI")
        cache.clear()
        
        # Vacuum de base de datos solo si es necesario
        if getattr(settings, 'auto_vacuum_db', True):
            await db.vacuum_database()
            
    except Exception as e:
        logger.error(f"Error durante el cierre: {e}")

# Crear aplicación FastAPI optimizada para RPi 3
app = FastAPI(
    title="HostBerry FastAPI",
    description="API optimizada para Raspberry Pi 3",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=JSONResponse,
    # Optimizaciones para RPi 3
    docs_url="/api/docs" if settings.debug else None,  # Solo docs en debug
    redoc_url="/api/redoc" if settings.debug else None,  # Solo redoc en debug
    openapi_url="/api/openapi.json" if settings.debug else None,  # Solo openapi en debug
)

# Configurar CORS optimizado para RPi 3
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    # Optimizaciones para RPi 3
    max_age=3600,  # Cache CORS por 1 hora
)

# Configurar middleware de seguridad
# if settings.security_headers_enabled:
#     from core.security_middleware import create_security_middleware
#     app.add_middleware(create_security_middleware())

# Configurar compresión GZip
if settings.compression_enabled:
    # aumentar tamaño mínimo para reducir CPU en Pi 3
    # Configurar GZip optimizado para RPi 3
app.add_middleware(
    GZipMiddleware, 
    minimum_size=500,   # Comprimir archivos > 500B (más eficiente para RPi)
    compresslevel=6     # Nivel de compresión balanceado (velocidad vs tamaño)
)

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
    """Health check endpoint optimizado para RPi 3"""
    return {
        "status": "healthy",
        "version": "2.0.0"
    }

@app.get("/system/info")
async def system_info():
    """Información del sistema optimizada para RPi 3"""
    try:
        import psutil
        
        # Cache de información del sistema para evitar cálculos repetidos
        if not hasattr(system_info, '_cache') or not getattr(system_info, '_cache_time', 0):
            system_info._cache = {
                "hostname": psutil.os.uname().nodename,
                "platform": psutil.os.uname().sysname,
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total
            }
            system_info._cache_time = time.time()
        
        # Solo actualizar información dinámica
        current_info = system_info._cache.copy()
        current_info["disk_usage"] = psutil.disk_usage('/').percent
        
        return current_info
        
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
    """Función para ejecutar la aplicación optimizada para RPi 3"""
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        access_log=settings.debug,  # Solo logs de acceso en debug
        log_level=settings.log_level.lower(),
        # Optimizaciones para RPi 3
        loop="asyncio",  # Loop más eficiente para RPi 3
        http="h11",      # Protocolo HTTP más ligero
        limit_concurrency=100,  # Limitar conexiones concurrentes
        limit_max_requests=1000,  # Reiniciar worker después de 1000 requests
        timeout_keep_alive=30,  # Timeout de keep-alive reducido
    )

if __name__ == "__main__":
    run_app() 