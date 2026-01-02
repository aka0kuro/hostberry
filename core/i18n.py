"""
Sistema de internacionalización para HostBerry FastAPI
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from contextvars import ContextVar
from config.settings import settings

# Configurar logger
logger = logging.getLogger(__name__)

# ContextVar para el idioma actual del request
_current_language_ctx = ContextVar("current_language", default="es")

class I18nManager:
    """Gestor de internacionalización para la aplicación"""
    
    def __init__(self, default_language: str = "es"):
        self.default_language = default_language
        self.supported_languages = ["es", "en"]
        self.translations = {}
        self.load_translations()
    
    def load_translations(self):
        """Carga todas las traducciones desde archivos JSON"""
        # Intentar ruta absoluta primero, luego relativa
        locales_dir = Path("/opt/hostberry/locales")
        if not locales_dir.exists():
            locales_dir = Path("locales")
        
        if not locales_dir.exists():
            # Crear directorio si no existe (solo si estamos en un path escribible)
            try:
                locales_dir.mkdir(exist_ok=True)
            except Exception:
                pass
            logger.warning(f"Directorio locales no encontrado en {locales_dir}")
            return
        
        for lang in self.supported_languages:
            lang_file = locales_dir / f"{lang}.json"
            if lang_file.exists():
                try:
                    with open(lang_file, 'r', encoding='utf-8') as f:
                        self.translations[lang] = json.load(f)
                    logger.info(f"Traducciones cargadas para {lang}")
                except Exception as e:
                    logger.error(f"Error cargando traducciones para {lang}: {e}")

    def get_current_language(self) -> str:
        """Obtiene el idioma actual del contexto o por defecto"""
        return _current_language_ctx.get()

    def set_context_language(self, language: str):
        """Establece el idioma para el contexto actual"""
        if language in self.supported_languages:
            _current_language_ctx.set(language)
        else:
            _current_language_ctx.set("en")

    def get_text(self, key: str, language: str = None, default: str = None, **kwargs) -> str:
        if language is None:
            language = self.get_current_language()
        
        if language not in self.supported_languages:
            language = self.default_language
        
        translation = self._get_nested_value(self.translations.get(language, {}), key)
        
        if translation is None:
            if language != self.default_language:
                translation = self._get_nested_value(self.translations.get(self.default_language, {}), key)
            
            if translation is None:
                if default is None:
                    return key
                return default
        
        if kwargs:
            try:
                return translation.format(**kwargs)
            except (KeyError, ValueError):
                return translation
        
        return translation

    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Optional[str]:
        keys = key.split('.')
        current = data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current if isinstance(current, str) else None

    def get_language_list(self) -> Dict[str, str]:
        return {"es": "Español", "en": "English"}
    
    def is_language_supported(self, language: str) -> bool:
        return language in self.supported_languages
    
    def set_language(self, language: str):
        if language in self.supported_languages:
            self.default_language = language
    
    def get_translation_keys(self, language: str = None) -> Dict[str, Any]:
        if language is None:
            language = self.default_language
        return self.translations.get(language, {})
    
    def reload_translations(self):
        self.load_translations()
    
    def add_translation(self, key: str, value: str, language: str = None):
        if language is None:
            language = self.default_language
        if language not in self.supported_languages:
            return
        keys = key.split('.')
        current = self.translations.setdefault(language, {})
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
    
    def save_translations(self, language: str):
        pass # Implementación simplificada para evitar errores de escritura

# Instancia global
i18n = I18nManager()

# Wrapper functions
def get_text(key: str, language: str = None, default: str = None, **kwargs) -> str:
    return i18n.get_text(key, language, default, **kwargs)

def t(key: str, language: str = None, default: str = None, **kwargs) -> str:
    return get_text(key, language, default, **kwargs)

def get_language_list() -> Dict[str, str]:
    return i18n.get_language_list()

def is_language_supported(language: str) -> bool:
    return i18n.is_language_supported(language)

def get_current_language() -> str:
    return i18n.get_current_language()

def set_language(language: str):
    i18n.set_language(language)

def reload_translations():
    i18n.reload_translations()

# Funciones específicas para templates HTML
def get_html_translations(language: str = None) -> Dict[str, Any]:
    return i18n.get_translation_keys(language)

def get_common_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("common", {})

def get_navigation_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("navigation", {})

def get_dashboard_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("dashboard", {})

def get_auth_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("auth", {})

def get_system_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("system", {})

def get_network_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("network", {})

def get_wifi_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("wifi", {})

def get_vpn_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("vpn", {})

def get_wireguard_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("wireguard", {})

def get_adblock_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("adblock", {})

def get_hostapd_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("hostapd", {})

def get_settings_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("settings", {})

def get_errors_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("errors", {})

def get_messages_texts(language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get("messages", {})

def get_context_translations(context: str, language: str = None) -> Dict[str, str]:
    return i18n.get_translation_keys(language).get(context, {})

def get_multiple_contexts_translations(contexts: list, language: str = None) -> Dict[str, Dict[str, str]]:
    translations = i18n.get_translation_keys(language)
    return {ctx: translations[ctx] for ctx in contexts if ctx in translations}
