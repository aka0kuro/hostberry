"""
Router web mínimo para asegurar arranque del backend.
"""

from fastapi import APIRouter, Request, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
import json

router = APIRouter()

# Configurar Jinja2 local y proveer función t por defecto
_env = Environment(
    loader=FileSystemLoader("website/templates"),
    autoescape=select_autoescape(["html", "xml"]),
    cache_size=200,
)

# Carga simple de traducciones desde locales/{lang}.json
def _load_translations(lang: str) -> dict:
    lang = (lang or "es").lower()
    locales_dir = Path("locales")
    file_path = locales_dir / f"{lang}.json"
    if not file_path.exists():
        file_path = locales_dir / "es.json"
    try:
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _make_t(translations: dict):
    def t(key: str, default: str = None):
        # Navegación por claves con puntos, p. ej. "auth.username"
        cur = translations
        for part in key.split('.'):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default if default is not None else key
        # Si es dict, no imprimible
        if isinstance(cur, dict):
            return default if default is not None else key
        return cur
    return t

templates = Jinja2Templates(directory="website/templates")
templates.env = _env


@router.get("/")
async def root_redirect():
    return RedirectResponse("/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, response: Response, lang: str | None = Query(default=None)) -> HTMLResponse:
    # Resolver idioma desde query, cookie o por defecto 'es'
    resolved_lang = lang or request.cookies.get("lang") or "es"
    if lang:
        response.set_cookie("lang", resolved_lang, max_age=60*60*24*365)
    translations = _load_translations(resolved_lang)
    # Actualizar función t del entorno
    templates.env.globals["t"] = _make_t(translations)
    context = {"request": request, "language": resolved_lang}
    resp = templates.TemplateResponse("login.html", context)
    if lang:
        resp.set_cookie("lang", resolved_lang, max_age=60*60*24*365)
    return resp


@router.get("/first-login", response_class=HTMLResponse)
async def first_login_page(request: Request, response: Response, lang: str | None = Query(default=None)) -> HTMLResponse:
    # Resolver idioma desde query, cookie o por defecto 'es'
    resolved_lang = lang or request.cookies.get("lang") or "es"
    if lang:
        response.set_cookie("lang", resolved_lang, max_age=60*60*24*365)
    translations = _load_translations(resolved_lang)
    # Actualizar función t del entorno
    templates.env.globals["t"] = _make_t(translations)
    context = {"request": request, "language": resolved_lang}
    resp = templates.TemplateResponse("first_login.html", context)
    if lang:
        resp.set_cookie("lang", resolved_lang, max_age=60*60*24*365)
    return resp