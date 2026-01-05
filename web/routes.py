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


def _get_system_stats() -> dict[str, float]:
    """Obtener estadísticas del sistema con lazy import de psutil"""
    cpu = 0.0
    memory = 0.0
    disk = 0.0
    temperature = 0.0

    try:
        # Lazy import de psutil
        import psutil
        cpu = float(psutil.cpu_percent(interval=None))
    except Exception:
        cpu = 0.0

    try:
        import psutil
        memory = float(psutil.virtual_memory().percent)
    except Exception:
        memory = 0.0

    try:
        import psutil
        disk = float(psutil.disk_usage("/").percent)
    except Exception:
        disk = 0.0

    try:
        # Intentar leer temperatura desde /sys/class/thermal
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_raw = int(f.read().strip())
                temperature = temp_raw / 1000
        except:
            # Fallback a psutil si está disponible
            import psutil
            get_temp = getattr(psutil, "sensors_temperatures", None)
            if callable(get_temp):
                temps = get_temp()
                if temps:
                    for name, entries in temps.items():
                        if entries:
                            temperature = float(entries[0].current) or 0.0
                            break
    except Exception:
        temperature = 45.0  # Valor por defecto

    return {
        "cpu_percent": round(cpu, 1),
        "memory_percent": round(memory, 1),
        "disk_percent": round(disk, 1),
        "temperature": round(temperature, 1),
    }


def _calculate_health_status(stats: dict[str, float]) -> dict[str, str]:
    """Calcular estado de salud del sistema basado en estadísticas reales"""
    cpu = stats.get("cpu_percent", 0)
    memory = stats.get("memory_percent", 0)
    disk = stats.get("disk_percent", 0)
    temperature = stats.get("temperature", 45)
    
    def get_status(value: float, thresholds: dict[str, float]) -> str:
        """Obtener estado basado en umbrales"""
        if value >= thresholds.get("critical", 90):
            return "critical"
        elif value >= thresholds.get("warning", 75):
            return "warning"
        else:
            return "healthy"
    
    cpu_status = get_status(cpu, {"warning": 70, "critical": 90})
    memory_status = get_status(memory, {"warning": 75, "critical": 90})
    disk_status = get_status(disk, {"warning": 80, "critical": 95})
    
    # Temperatura: healthy < 60, warning 60-80, critical > 80
    if temperature >= 80:
        temp_status = "critical"
    elif temperature >= 60:
        temp_status = "warning"
    else:
        temp_status = "normal"  # Para temperatura usamos "normal" en lugar de "healthy"
    
    # Estado general: si alguno es crítico, general es crítico; si alguno es warning, general es warning
    if cpu_status == "critical" or memory_status == "critical" or disk_status == "critical" or temp_status == "critical":
        overall = "critical"
    elif cpu_status == "warning" or memory_status == "warning" or disk_status == "warning" or temp_status == "warning":
        overall = "warning"
    else:
        overall = "healthy"
    
    return {
        "overall": overall,
        "cpu": cpu_status,
        "memory": memory_status,
        "disk": disk_status,
        "temperature": temp_status,
    }
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
import psutil
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

#
# Configuración UI global (language/theme/timezone) desde DB
#
_UI_SETTINGS_CACHE: dict[str, Any] = {"ts": 0.0, "value": None}


async def _get_ui_settings() -> dict[str, Any]:
    """Lee settings básicos desde DB con un caché pequeño para evitar demasiadas lecturas."""
    now = time.time()
    cached = _UI_SETTINGS_CACHE.get("value")
    if cached and (now - float(_UI_SETTINGS_CACHE.get("ts") or 0.0)) < 10:
        return cached

    from core.database import db

    async def _get(key: str) -> str | None:
        try:
            return await db.get_configuration(key)
        except Exception:
            return None

    language = await _get("language")
    if language not in ("en", "es"):
        language = None

    theme = await _get("theme")
    if theme not in ("light", "dark", "auto"):
        theme = None

    timezone = await _get("timezone")
    timezone = timezone or None

    result = {"language": language, "theme": theme, "timezone": timezone}
    _UI_SETTINGS_CACHE["ts"] = now
    _UI_SETTINGS_CACHE["value"] = result
    return result


async def _resolve_language(request: Request, lang: str | None) -> tuple[str, bool]:
    """Resolver idioma: query -> cookie -> DB -> accept-language -> default."""
    if lang in ("en", "es"):
        i18n.set_context_language(lang)
        return lang, True

    cookie_lang = request.cookies.get("lang")
    if cookie_lang in ("en", "es"):
        i18n.set_context_language(cookie_lang)
        return cookie_lang, False

    ui = await _get_ui_settings()
    db_lang = ui.get("language")
    if db_lang in ("en", "es"):
        i18n.set_context_language(db_lang)
        # Si no hay cookie, persistimos el idioma global de DB en cookie para toda la app
        return db_lang, True

    accept = request.headers.get("accept-language", "")
    if accept:
        accept_lang = accept.split(",")[0].split("-")[0].strip().lower()
        if accept_lang in ("en", "es"):
            i18n.set_context_language(accept_lang)
            return accept_lang, False

    current = i18n.get_current_language()
    if current not in ("en", "es"):
        current = "en"
        i18n.set_context_language(current)
    return current, False


async def _base_context(request: Request, current_lang: str) -> dict:
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

    # Obtener username desde cookie o usar valor por defecto desde settings
    from config.settings import settings
    username = request.cookies.get("username") or settings.default_username

    ui = await _get_ui_settings()
    settings_ctx = {
        "language": current_lang,
        "theme": ui.get("theme") or "dark",
        "timezone": ui.get("timezone") or "UTC",
    }

    return {
        "request": request,
        "language": current_lang,
        "translations": get_html_translations(current_lang),
        "last_update": int(time.time()),
        "pytz": pytz,
        "current_user": {"username": username},
        "settings": settings_ctx,
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
        "system_stats": _get_system_stats(),
        "system_health": _calculate_health_status(_get_system_stats()),
        "services": _get_service_statuses(),
    }


async def _render(template_name: str, request: Request, lang: str | None, extra: dict | None = None) -> HTMLResponse:
    current_lang, should_set_cookie = await _resolve_language(request, lang)
    context = await _base_context(request, current_lang)
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
    from config.settings import settings
    current_user = {"username": settings.default_username}
    
    return await _render(
        "index.html",
        request,
        lang,
        extra={
            "current_user": current_user
        }
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, response: Response, lang: str | None = Query(default=None)) -> HTMLResponse:
    current_lang, _ = await _resolve_language(request, lang)
    context = await _base_context(request, current_lang)
    context.update({
        "current_user": {"username": "usuario"},  # Ensure current_user is available
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
    })
    return await _render("login.html", request, lang, extra=context)


@router.get("/system", response_class=HTMLResponse)
async def system_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    # Obtener información del sistema
    system_stats = _get_system_stats()
    services = _get_service_statuses()
    
    return await _render(
        "system.html",
        request,
        lang,
        extra={
            "system_info": {
                "hostname": platform.node(),
                "os_version": f"{platform.system()} {platform.release()}",
                "kernel_version": platform.release(),
                "architecture": platform.machine(),
                "uptime": boot_time(),
                "cpu_cores": psutil.cpu_count(),
            },
            "system_stats": system_stats,
            "services": services,
        },
    )


@router.get("/network", response_class=HTMLResponse)
async def network_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return await _render("network.html", request, lang)


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
    # Cargar configuración persistida desde la DB para que la página refleje cambios guardados
    from core.database import db

    def _as_bool(v, default: bool = False) -> bool:
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("1", "true", "yes", "on", "enabled"):
            return True
        if s in ("0", "false", "no", "off", "disabled", ""):
            return False
        return default

    def _as_int(v, default: int) -> int:
        try:
            return int(v)
        except Exception:
            return default

    def _as_str(v, default: str) -> str:
        if v is None:
            return default
        s = str(v)
        return s if s != "" else default

    # Preferir language guardado si es válido; si no, usar el resuelto por cookie/query
    try:
        cfg_language = await db.get_configuration("language")
    except Exception:
        cfg_language = None
    language_value = cfg_language if cfg_language in ("en", "es") else current_lang

    try:
        cfg_theme = await db.get_configuration("theme")
    except Exception:
        cfg_theme = None
    theme_value = cfg_theme if cfg_theme in ("light", "dark", "auto") else "dark"

    try:
        cfg_timezone = await db.get_configuration("timezone")
    except Exception:
        cfg_timezone = None
    timezone_value = cfg_timezone or "UTC"

    # System
    try:
        log_level = await db.get_configuration("log_level")
        auto_backup = await db.get_configuration("auto_backup")
        backup_interval = await db.get_configuration("backup_interval")
    except Exception:
        log_level, auto_backup, backup_interval = None, None, None

    # Network
    try:
        dhcp_enabled = await db.get_configuration("dhcp_enabled")
        dns_server = await db.get_configuration("dns_server")
        firewall_enabled = await db.get_configuration("firewall_enabled")
    except Exception:
        dhcp_enabled, dns_server, firewall_enabled = None, None, None

    # Security
    try:
        ssl_enabled = await db.get_configuration("ssl_enabled")
        max_login_attempts = await db.get_configuration("max_login_attempts")
        session_timeout = await db.get_configuration("session_timeout")
    except Exception:
        ssl_enabled, max_login_attempts, session_timeout = None, None, None

    # Performance
    try:
        cache_enabled = await db.get_configuration("cache_enabled")
        cache_size = await db.get_configuration("cache_size")
        compression_enabled = await db.get_configuration("compression_enabled")
    except Exception:
        cache_enabled, cache_size, compression_enabled = None, None, None

    # Notifications
    try:
        email_notifications = await db.get_configuration("email_notifications")
        email_address = await db.get_configuration("email_address")
        system_alerts = await db.get_configuration("system_alerts")
    except Exception:
        email_notifications, email_address, system_alerts = None, None, None

    return _render(
        "settings.html",
        request,
        lang,
        extra={
            "settings": {"language": language_value, "theme": theme_value, "timezone": timezone_value},
            "system_config": {
                "log_level": _as_str(log_level, "INFO"),
                "auto_backup": _as_bool(auto_backup, False),
                "backup_interval": _as_str(backup_interval, "daily"),
            },
            "network_config": {
                "dhcp_enabled": _as_bool(dhcp_enabled, False),
                "dns_server": _as_str(dns_server, "8.8.8.8"),
                "firewall_enabled": _as_bool(firewall_enabled, True),
            },
            "security_config": {
                "ssl_enabled": _as_bool(ssl_enabled, False),
                "max_login_attempts": _as_int(max_login_attempts, 3),
                "session_timeout": _as_int(session_timeout, 30),
            },
            "performance_config": {
                "cache_enabled": _as_bool(cache_enabled, True),
                "cache_size": _as_int(cache_size, 50),
                "compression_enabled": _as_bool(compression_enabled, True),
            },
            "notification_config": {
                "email_notifications": _as_bool(email_notifications, False),
                "email_address": _as_str(email_address, ""),
                "system_alerts": _as_bool(system_alerts, True),
            },
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
            "user": {"username": settings.default_username, "role": "admin", "timezone": "UTC"},
            "recent_activities": [],
        },
    )


@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    current_lang, _ = _resolve_language(request, lang)
    support_stats = [
        {"label_key": "help.stats.active_tickets", "value": "128", "trend": "+8%", "status": "warning"},
        {"label_key": "help.stats.resolution_rate", "value": "94%", "trend": "+2%", "status": "success"},
        {"label_key": "help.stats.system_uptime", "value": "99.98%", "trend": "24h", "status": "info"},
        {"label_key": "help.stats.response_time", "value": "12m", "trend": "-3m", "status": "success"},
    ]
    faqs = [
        {"id": "faq_monitoring", "question_key": "help.faqs.monitoring_q", "answer_key": "help.faqs.monitoring_a"},
        {"id": "faq_security", "question_key": "help.faqs.security_q", "answer_key": "help.faqs.security_a"},
        {"id": "faq_updates", "question_key": "help.faqs.updates_q", "answer_key": "help.faqs.updates_a"},
    ]
    guide_cards = [
        {
            "icon": "bi bi-speedometer2",
            "title_key": "help.guides.getting_started_title",
            "description_key": "help.guides.getting_started_desc",
            "link": "/guide/getting-started",
            "variant": "primary",
        },
        {
            "icon": "bi bi-wifi",
            "title_key": "help.guides.wifi_title",
            "description_key": "help.guides.wifi_desc",
            "link": "/guide/wifi-setup",
            "variant": "success",
        },
        {
            "icon": "bi bi-shield-check",
            "title_key": "help.guides.security_title",
            "description_key": "help.guides.security_desc",
            "link": "/guide/security-setup",
            "variant": "warning",
        },
        {
            "icon": "bi bi-gear",
            "title_key": "help.guides.advanced_title",
            "description_key": "help.guides.advanced_desc",
            "link": "/guide/advanced-config",
            "variant": "info",
        },
    ]
    support_links = [
        {"icon": "bi bi-book", "title_key": "help.links.docs_title", "desc_key": "help.links.docs_desc", "href": "/documentation"},
        {"icon": "bi bi-code-slash", "title_key": "help.links.api_title", "desc_key": "help.links.api_desc", "href": "/api/docs"},
        {"icon": "bi bi-tools", "title_key": "help.links.troubleshoot_title", "desc_key": "help.links.troubleshoot_desc", "href": "/troubleshooting"},
        {"icon": "bi bi-headset", "title_key": "help.links.support_title", "desc_key": "help.links.support_desc", "href": "/support"},
    ]
    contact_channels = [
        {"icon": "bi bi-envelope", "label_key": "help.contact.email", "value": "support@hostberry.com"},
        {"icon": "bi bi-discord", "label_key": "help.contact.community", "value": "discord.gg/hostberry"},
        {"icon": "bi bi-github", "label_key": "help.contact.repo", "value": "github.com/hostberry"},
    ]
    return _render(
        "help.html",
        request,
        current_lang,
        extra={
            "support_stats": support_stats,
            "faqs": faqs,
            "guide_cards": guide_cards,
            "support_links": support_links,
            "contact_channels": contact_channels,
        },
    )


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    return _render("about.html", request, lang, extra={"app_info": {}})


@router.get("/first-login", response_class=HTMLResponse)
async def first_login(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    from config.settings import settings
    # Resolver idioma desde query, cookie o usar el del contexto (middleware)
    # Si viene por query, forzamos el cambio y seteamos cookie
    if lang:
        i18n.set_context_language(lang)
    elif request.cookies.get("lang"):
        i18n.set_context_language(request.cookies.get("lang"))
    
    current_lang = i18n.get_current_language()
    
    # Obtener usuario desde cookie o usar valor por defecto
    username = request.cookies.get("username") or settings.default_username
    current_user = {"username": username}
    
    context = _base_context(request, current_lang)
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
    
    # Obtener estadísticas reales del sistema
    system_stats = _get_system_stats()
    system_health = _calculate_health_status(system_stats)
    
    return _render(
        "dashboard.html",
        request,
        current_lang,
        extra={
            "current_user": current_user,
            "system_stats": system_stats,
            "system_health": system_health,
            "services": _get_service_statuses(),
            "network_status": {
                "eth0": {"status": "connected", "ip": "0.0.0.0", "gateway": "0.0.0.0"},
                "wlan0": {"status": "connected", "ip": "0.0.0.0", "ssid": "Unknown", "signal": 0},
            },
            "recent_activity": [],
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


@router.get("/update", response_class=HTMLResponse)
async def update_page(request: Request, lang: str | None = Query(default=None)) -> HTMLResponse:
    current_lang, _ = _resolve_language(request, lang)
    
    return _render(
        "update.html",
        request,
        current_lang,
        extra={},
    )


@router.get("/test-dashboard")
async def test_dashboard():
    return get_text("test_dashboard_working", default="TEST DASHBOARD FUNCIONANDO - OK")