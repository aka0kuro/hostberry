"""
Router web mínimo para asegurar arranque del backend.
"""

from fastapi import APIRouter, Request, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape
from core.i18n import get_text, i18n, get_html_translations

router = APIRouter()

# Configurar templates
env = Environment(
    loader=FileSystemLoader("website/templates"),
    autoescape=select_autoescape(["html", "xml"])
)
# Asignar la función de traducción global
env.globals["t"] = get_text

templates = Jinja2Templates(directory="website/templates")
templates.env = env


@router.get("/")
async def root_redirect(request: Request):
    # Verificar si hay un token en el header Authorization
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # Si hay un token, redirigir al dashboard
        return RedirectResponse("/dashboard", status_code=302)
    else:
        # Si no hay token, redirigir al login
        return RedirectResponse("/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, response: Response, lang: str | None = Query(default=None)) -> HTMLResponse:
    # Resolver idioma desde query, cookie o usar el del contexto (middleware)
    # Si viene por query, forzamos el cambio y seteamos cookie
    if lang:
        i18n.set_context_language(lang)
        response.set_cookie("lang", lang, max_age=60*60*24*365)
    elif request.cookies.get("lang"):
        i18n.set_context_language(request.cookies.get("lang"))
    
    current_lang = i18n.get_current_language()
    
    context = {"request": request, "language": current_lang,
        "system_stats": {
            "cpu_percent": 25,
            "memory_percent": 45,
            "disk_percent": 60,
            "temperature": 45
        },
        "system_health": {
            "overall": "healthy",
            "cpu": "healthy",
            "memory": "healthy",
            "disk": "healthy",
            "network": "healthy",
            "temperature": "healthy"
        },
        "services": {
            "hostberry": "running",
            "nginx": "running",
            "ssh": "running",
            "ufw": "running",
            "fail2ban": "running"
        },
        "recent_activities": [
            {"title": "Login exitoso", "description": "Usuario admin inició sesión", "timestamp": "Hace 5 minutos"},
            {"title": "Actualización de sistema", "description": "Paquetes actualizados", "timestamp": "Hace 1 hora"}
        ]
    }
    resp = templates.TemplateResponse("login.html", context)
    if lang:
        resp.set_cookie("lang", lang, max_age=60*60*24*365)
    return resp


@router.get("/first-login", response_class=HTMLResponse)
async def first_login_page(request: Request, response: Response, lang: str | None = Query(default=None)) -> HTMLResponse:
    if lang:
        i18n.set_context_language(lang)
        response.set_cookie("lang", lang, max_age=60*60*24*365)
    elif request.cookies.get("lang"):
        i18n.set_context_language(request.cookies.get("lang"))
        
    current_lang = i18n.get_current_language()

    context = {"request": request, "language": current_lang,
        "system_stats": {
            "cpu_percent": 25,
            "memory_percent": 45,
            "disk_percent": 60,
            "temperature": 45
        },
        "system_health": {
            "overall": "healthy",
            "cpu": "healthy",
            "memory": "healthy",
            "disk": "healthy",
            "network": "healthy",
            "temperature": "healthy"
        },
        "services": {
            "hostberry": "running",
            "nginx": "running",
            "ssh": "running",
            "ufw": "running",
            "fail2ban": "running"
        },
        "recent_activities": [
            {"title": "Login exitoso", "description": "Usuario admin inició sesión", "timestamp": "Hace 5 minutos"},
            {"title": "Actualización de sistema", "description": "Paquetes actualizados", "timestamp": "Hace 1 hora"}
        ]
    }
    resp = templates.TemplateResponse("first_login.html", context)
    if lang:
        resp.set_cookie("lang", lang, max_age=60*60*24*365)
    return resp


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, response: Response, lang: str | None = Query(default=None)) -> HTMLResponse:
    if lang:
        i18n.set_context_language(lang)
        response.set_cookie("lang", lang, max_age=60*60*24*365)
    elif request.cookies.get("lang"):
        i18n.set_context_language(request.cookies.get("lang"))
        
    current_lang = i18n.get_current_language()
    
    # Contexto simple para el dashboard
    context = {
        "request": request, 
        "language": current_lang,
        "system_stats": {
            "cpu_percent": 25,
            "memory_percent": 45,
            "disk_percent": 60,
            "temperature": 45
        },
        "system_health": {
            "overall": "healthy",
            "cpu": "healthy",
            "memory": "healthy",
            "disk": "healthy",
            "network": "healthy",
            "temperature": "healthy"
        },
        "services": {
            "hostberry": "running",
            "nginx": "running",
            "ssh": "running",
            "ufw": "running",
            "fail2ban": "running"
        },
        "recent_activities": [
            {"title": "Login exitoso", "description": "Usuario admin inició sesión", "timestamp": "Hace 5 minutos"},
            {"title": "Actualización de sistema", "description": "Paquetes actualizados", "timestamp": "Hace 1 hora"}
        ]
    }
    
    # Usar TemplateResponse con el template dashboard.html
    resp = templates.TemplateResponse("dashboard.html", context)
    if lang:
        resp.set_cookie("lang", lang, max_age=60*60*24*365)
    return resp


@router.get("/test-dashboard")
async def test_dashboard():
    return get_text("test_dashboard_working", default="TEST DASHBOARD FUNCIONANDO - OK")