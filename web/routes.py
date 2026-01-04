SERVICE_NAMES = [
    "hostberry",
    "nginx",
    "ssh",
    "ufw",
    "fail2ban",
    "hostapd",
    "openvpn",
    "wg-quick",
    "dnsmasq",
]


def _get_service_statuses() -> dict[str, str]:
    statuses: dict[str, str] = {}
    for service in SERVICE_NAMES:
        try:
            result = os.system(f"systemctl is-active --quiet {service}")
            statuses[service] = "running" if result == 0 else "stopped"
        except Exception:
            statuses[service] = "unknown"
    if not statuses:
        return {
            "hostberry": "running",
            "nginx": "running",
            "ssh": "running",
        }
    return statuses
"""
Router web mínimo para asegurar arranque del backend.
"""

from fastapi import APIRouter, Request, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from core.i18n import get_text, i18n, get_html_translations
from core.system_light import boot_time
import json
import time
import os
import platform
from types import SimpleNamespace
from datetime import datetime, timezone
import pytz

router = APIRouter()

# Configurar templates
env = Environment(
    loader=FileSystemLoader("website/templates"),
    autoescape=select_autoescape(["html", "xml"]),
    extensions=["jinja2.ext.i18n"],
)

# Función wrapper para traducción que usa el idioma del contexto
def template_t(key: str, default: str = None, **kwargs):
    """Función de traducción para templates que usa el idioma del contexto"""
    return get_text(key, None, default, **kwargs)


def template_gettext(message: str, default: str | None = None, **kwargs) -> str:
    # Support Jinja {% trans %} and _() calls.
    # Here, "message" is treated as a translation key; fallback is the message itself.
    return get_text(message, default=(default or message), **kwargs)


def template_ngettext(singular: str, plural: str, n: int) -> str:
    key = singular if n == 1 else plural
    return get_text(key, default=key)

def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    """Format a datetime object"""
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime(format)
    return str(value)

# Asignar la función de traducción global
env.globals["t"] = template_t
env.globals["_"] = template_gettext
env.filters['datetimeformat'] = datetimeformat


def tojson_filter(value) -> Markup:
    try:
        return Markup(json.dumps(value, ensure_ascii=False))
    except Exception:
        return Markup("{}")


env.filters["tojson"] = tojson_filter

env.install_gettext_callables(template_gettext, template_ngettext, newstyle=True)

templates = Jinja2Templates(directory="website/templates")
templates.env = env


class DummyForm:
    csrf_token = ""

    def hidden_tag(self):
        return ""


def _resolve_language(request: Request, lang: str | None) -> tuple[str, bool]:
    if lang:
        i18n.set_context_language(lang)
        return lang, True
    cookie_lang = request.cookies.get("lang")
    if cookie_lang:
        i18n.set_context_language(cookie_lang)
        return cookie_lang, False
    return i18n.get_current_language(), False


def _base_context(request: Request, current_lang: str) -> dict:
    bt = 0.0
    try:
        bt = float(boot_time() or 0.0)
    except Exception:
        bt = 0.0

    uptime_seconds = 0
    if bt > 0:
        uptime_seconds = max(0, int(time.time() - bt))

    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60

    hostname = "hostberry"
    try:
        hostname = platform.node() or hostname
    except Exception:
        hostname = hostname

    os_version = "Raspberry Pi OS"
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
            for line in data.splitlines():
                if line.startswith("PRETTY_NAME="):
                    os_version = line.split("=", 1)[1].strip().strip('"') or os_version
                    break
    except Exception:
        os_version = os_version

    kernel_version = "Linux"
    try:
        kernel_version = platform.release() or kernel_version
    except Exception:
        kernel_version = kernel_version

    architecture = "unknown"
    try:
        architecture = platform.machine() or architecture
    except Exception:
        architecture = architecture

    processor = ""
    try:
        processor = platform.processor() or ""
    except Exception:
        processor = ""

    load_average = "0.00, 0.00, 0.00"
    try:
        la = os.getloadavg()
        load_average = f"{la[0]:.2f}, {la[1]:.2f}, {la[2]:.2f}"
    except Exception:
        load_average = load_average

    cpu_cores = "0"
    try:
        cpu_cores = str(os.cpu_count() or 0)
    except Exception:
        cpu_cores = cpu_cores

    username = request.cookies.get("username") or "admin"

    return {
        "request": request,
        "language": current_lang,
        "translations": get_html_translations(current_lang),
        "last_update": int(time.time()),
        "pytz": pytz,
        "current_user": {"username": username},
        "system_info": {
            "hostname": hostname,
            "os_version": os_version,
            "kernel_version": kernel_version,
            "architecture": architecture,
            "processor": processor or "ARM",
            "uptime": f"{days}d {hours}h {minutes}m",
            "load_average": load_average,
            "cpu_cores": cpu_cores,
        },
        "system_stats": {
            "cpu_percent": 25,
            "memory_percent": 45,
            "disk_percent": 60,
            "temperature": 45,
        },
        "system_health": {
            "overall": "healthy",
            "cpu": "healthy",
            "memory": "healthy",
            "disk": "healthy",
            "network": "healthy",
            "temperature": "healthy",
        },
        "services": {
            "hostberry": "running",
            "nginx": "running",
            "ssh": "running",
            "ufw": "running",
            "fail2ban": "running",
            "wifi": "running",
        },
    }


def _render(template_name: str, request: Request, lang: str | None, extra: dict | None = None) -> HTMLResponse:
    current_lang, should_set_cookie = _resolve_language(request, lang)
    context = _base_context(request, current_lang)
    if extra:
        context.update(extra)
    resp = templates.TemplateResponse(template_name, context)
    if should_set_cookie:
        resp.set_cookie("lang", current_lang, max_age=60 * 60 * 24 * 365)
    return resp


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


@router.get("/", response_class=HTMLResponse)
async def root(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    # Simular usuario logueado (en una app real vendría del token/sesión)
    # Usar un nombre de usuario dinámico - en producción esto vendría de la autenticación
    current_user = {"username": "usuario"}  # Cambiado de 'admin' a 'usuario'
    
    return _render(
        "index.html",
        request,
        lang,
        extra={
            "current_user": current_user
        }
    )


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
        "current_user": {"username": "usuario"},  # Ensure current_user is available
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
        "services": _get_service_statuses(),
        "recent_activities": [
            {"title": "Login exitoso", "description": "Usuario admin inició sesión", "timestamp": "Hace 5 minutos"},
            {"title": "Actualización de sistema", "description": "Paquetes actualizados", "timestamp": "Hace 1 hora"}
        ],
        "current_user": {"username": "admin"}  # Add current_user to context
    }
    resp = templates.TemplateResponse("login.html", context)
    if lang:
        resp.set_cookie("lang", lang, max_age=60*60*24*365)
    return resp


@router.get("/system", response_class=HTMLResponse)
async def system_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render(
        "system.html",
        request,
        lang,
        extra={
            "system_info": {},
        },
    )


@router.get("/network", response_class=HTMLResponse)
async def network_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render("network.html", request, lang)


@router.get("/wifi", response_class=HTMLResponse)
async def wifi_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render(
        "wifi.html",
        request,
        lang,
        extra={
            "wifi_stats": {},
            "wifi_status": {"enabled": True, "connected": True},
            "wifi_config": {},
            "guest_network": {"enabled": False},
        },
    )


@router.get("/hostapd", response_class=HTMLResponse)
async def hostapd_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render(
        "hostapd.html",
        request,
        lang,
        extra={
            "hostapd_stats": {},
            "hostapd_status": {"enabled": False, "running": False},
            "hostapd_config": {},
        },
    )


@router.get("/vpn", response_class=HTMLResponse)
async def vpn_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render(
        "vpn.html",
        request,
        lang,
        extra={
            "vpn_stats": {},
            "vpn_status": {"enabled": False, "connected": False},
            "vpn_config": {},
            "vpn_security": {},
        },
    )


@router.get("/wireguard", response_class=HTMLResponse)
async def wireguard_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render(
        "wireguard.html",
        request,
        lang,
        extra={
            "wireguard_stats": {},
            "wireguard_status": {"enabled": False},
            "wireguard_config": {},
        },
    )


@router.get("/adblock", response_class=HTMLResponse)
async def adblock_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render(
        "adblock.html",
        request,
        lang,
        extra={
            "adblock_stats": {},
            "adblock_status": {"enabled": False, "running": False},
            "adblock_config": {},
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    current_lang, _ = _resolve_language(request, lang)
    return _render(
        "settings.html",
        request,
        lang,
        extra={
            "settings": {"language": current_lang, "theme": "dark", "timezone": "UTC"},
            "system_config": {},
            "network_config": {},
            "security_config": {},
            "performance_config": {},
            "notification_config": {},
            "system_info": {},
        },
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render(
        "profile.html",
        request,
        lang,
        extra={
            "user": {"username": "admin", "role": "admin", "timezone": "UTC"},
            "recent_activities": [],
        },
    )


@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render("help.html", request, lang)


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render("about.html", request, lang, extra={"app_info": {}})


@router.get("/first-login", response_class=HTMLResponse)
async def first_login(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    # Simular usuario logueado (en una app real vendría del token/sesión)
    current_user = {"username": "admin"}  # Reemplazar con lógica real de autenticación
    
    context = _base_context(request, lang or request.cookies.get("lang", "en"))
    context.update({
        "current_user": current_user,
        "services": _get_service_statuses(),
        "recent_activities": [
            {"title": "Login exitoso", "description": "Usuario admin inició sesión", "timestamp": "Hace 5 minutos"},
            {"title": "Actualización de sistema", "description": "Paquetes actualizados", "timestamp": "Hace 1 hora"}
        ]
    })
    resp = templates.TemplateResponse("first_login.html", context)
    if lang:
        resp.set_cookie("lang", lang, max_age=60*60*24*365)
    return resp


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    # Simular usuario logueado (en una app real vendría del token/sesión)
    # Usar un nombre de usuario dinámico - en producción esto vendría de la autenticación
    current_user = {"username": "admin"}  # Reemplazar con lógica real de autenticación
    
    current_lang, _ = _resolve_language(request, lang)
    return _render(
        "dashboard.html",
        request,
        current_lang,
        extra={
            "current_user": current_user,
            "system_stats": {
                "cpu_percent": 25,
                "memory_percent": 45,
                "disk_percent": 60,
                "temperature": 45,
            },
            "services": _get_service_statuses(),
            "network_status": {
                "eth0": {"status": "connected", "ip": "192.168.1.100", "gateway": "192.168.1.1"},
                "wlan0": {"status": "connected", "ip": "192.168.1.101", "ssid": "HomeNetwork", "signal": 85},
            },
            "recent_activity": [],
            "system_health": {
                "overall": "healthy",
                "cpu": "healthy",
                "memory": "healthy",
                "disk": "healthy",
            },
        },
    )


@router.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    current_lang, _ = _resolve_language(request, lang)
    return _render(
        "monitoring.html",
        request,
        current_lang,
        extra={
            "system_info": {
                "hostname": "hostberry",
                "os_version": "Raspberry Pi OS",
                "kernel_version": "Linux 6.8.0",
                "architecture": "armv7l",
                "processor": "ARM Cortex-A53",
                "uptime": "2 days, 5 hours",
                "load_average": "0.25, 0.30, 0.35",
                "cpu_cores": "4",
            },
            "system_stats": {
                "cpu_percent": 25,
                "memory_percent": 45,
                "disk_percent": 60,
                "temperature": 45,
            },
        },
    )


@router.get("/security", response_class=HTMLResponse)
async def security_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    current_lang, _ = _resolve_language(request, lang)
    
    cfg = SimpleNamespace(
        FIREWALL_ENABLED=True,
        BLOCK_ICMP=True,
        TIMEZONE="UTC",
        TIME_FORMAT="%Y-%m-%d %H:%M:%S",
    )
    sec = SimpleNamespace(
        blocked_ips=12,
        last_attack=None,
        last_check=datetime.now(timezone.utc),
    )
    dummy_form = DummyForm()
    timezones = ["UTC", "Europe/Madrid", "America/Mexico_City", "America/Bogota"]
    time_formats = ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%H:%M:%S"]
    current_time = datetime.now(timezone.utc)
    
    return _render(
        "security.html",
        request,
        current_lang,
        extra={
            "config": cfg,
            "security_status": sec,
            "form": dummy_form,
            "timezones": timezones,
            "time_formats": time_formats,
            "current_time": current_time,
            "system_info": {
                "hostname": "hostberry",
                "os_version": "Raspberry Pi OS",
                "kernel_version": "Linux 6.8.0",
                "architecture": "armv7l",
                "processor": "ARM Cortex-A53",
                "uptime": "2 days, 5 hours",
                "load_average": "0.25, 0.30, 0.35",
                "cpu_cores": "4",
            },
        },
    )


@router.get("/test-dashboard")
async def test_dashboard():
    return get_text("test_dashboard_working", default="TEST DASHBOARD FUNCIONANDO - OK")