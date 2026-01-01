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
    
    # ... (rest of methods)

    def get_current_language(self) -> str:
        """Obtiene el idioma actual del contexto o por defecto"""
        return _current_language_ctx.get()

    def set_context_language(self, language: str):
        """Establece el idioma para el contexto actual"""
        if language in self.supported_languages:
            _current_language_ctx.set(language)
        else:
            # Fallback a inglés si el idioma no está soportado (según requerimiento)
            _current_language_ctx.set("en")

    def get_text(self, key: str, language: str = None, **kwargs) -> str:
        # ...
        if language is None:
            language = self.get_current_language()
        # ...
        """Carga todas las traducciones desde archivos JSON"""
        locales_dir = Path("locales")
        
        if not locales_dir.exists():
            # Crear directorio si no existe
            locales_dir.mkdir(exist_ok=True)
            logger.warning("Directorio locales no encontrado, creando...")
            return
        
        for lang in self.supported_languages:
            lang_file = locales_dir / f"{lang}.json"
            if lang_file.exists():
                try:
                    with open(lang_file, 'r', encoding='utf-8') as f:
                        self.translations[lang] = json.load(f)
                    logger.info(f"Traducciones cargadas para {lang}")
                except Exception as e:
        """
        Obtiene el texto traducido para una clave específica
        
        Args:
            key: Clave de traducción (ej: "common.save")
            language: Idioma (es, en). Si es None, usa el idioma por defecto
            default: Valor por defecto si no se encuentra la traducción
            **kwargs: Variables para interpolación
            
        Returns:
            Texto traducido
        """
        if language is None:
            language = self.get_current_language()
        
        if language not in self.supported_languages:
            language = self.default_language
        
        # Buscar la traducción
        translation = self._get_nested_value(self.translations.get(language, {}), key)
        
        if translation is None:
            # Si no se encuentra, buscar en el idioma por defecto
            if language != self.default_language:
                translation = self._get_nested_value(self.translations.get(self.default_language, {}), key)
            
            # Si aún no se encuentra, devolver el valor por defecto o la clave
            if translation is None:
                # No loguear si se provee un default (comportamiento esperado durante desarrollo)
                if default is None:
                    logger.warning(f"Traducción no encontrada para clave: {key}")
                    return key
                return default
        
        # Interpolar variables si las hay
        if kwargs:
            try:
                return translation.format(**kwargs)
            except (KeyError, ValueError) as e:
                logger.warning(f"Error interpolando variables en traducción {key}: {e}")
                return translation
        
        return translation
    
    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Optional[str]:
        """
        Obtiene un valor anidado usando notación de punto
        
        Args:
            data: Diccionario de datos
            key: Clave con notación de punto (ej: "common.save")
            
        Returns:
            Valor encontrado o None
        """
        keys = key.split('.')
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        
        return current if isinstance(current, str) else None
    
    def get_language_list(self) -> Dict[str, str]:
        """Obtiene la lista de idiomas disponibles"""
        return {
            "es": "Español",
            "en": "English"
        }
    
    def is_language_supported(self, language: str) -> bool:
        """Verifica si un idioma está soportado"""
        return language in self.supported_languages
    
    def get_current_language(self) -> str:
        """Obtiene el idioma actual"""
        return self.default_language
    
    def set_language(self, language: str):
        """Establece el idioma por defecto"""
        if language in self.supported_languages:
            self.default_language = language
        else:
            logger.warning(f"Idioma no soportado: {language}")
    
    def get_translation_keys(self, language: str = None) -> Dict[str, Any]:
        """Obtiene todas las claves de traducción para un idioma"""
        if language is None:
            language = self.default_language
        
        return self.translations.get(language, {})
    
    def add_translation(self, key: str, value: str, language: str = None):
        """
        Agrega una nueva traducción
        
        Args:
            key: Clave de traducción
            value: Valor traducido
            language: Idioma (opcional)
        """
        if language is None:
            language = self.default_language
        
        if language not in self.supported_languages:
            logger.warning(f"Idioma no soportado: {language}")
            return
        
        # Crear estructura anidada si no existe
        keys = key.split('.')
        current = self.translations.setdefault(language, {})
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Asignar valor
        current[keys[-1]] = value
        
        logger.info(f"Traducción agregada: {key} = {value} ({language})")
    
    def save_translations(self, language: str):
        """Guarda las traducciones en archivo JSON"""
        try:
            locales_dir = Path("locales")
            locales_dir.mkdir(exist_ok=True)
            
            lang_file = locales_dir / f"{language}.json"
            with open(lang_file, 'w', encoding='utf-8') as f:
                json.dump(self.translations.get(language, {}), f, 
                         ensure_ascii=False, indent=2)
            
            logger.info(f"Traducciones guardadas para {language}")
            
        except Exception as e:
            logger.error(f"Error guardando traducciones para {language}: {e}")
    
    def reload_translations(self):
        """Recarga las traducciones desde archivos"""
        self.load_translations()

# Instancia global del gestor de internacionalización
i18n = I18nManager()

def get_text(key: str, language: str = None, default: str = None, **kwargs) -> str:
    """
    Función de conveniencia para obtener texto traducido
    
    Args:
        key: Clave de traducción
        language: Idioma (opcional)
        default: Valor por defecto (opcional)
        **kwargs: Variables para interpolación
        
    Returns:
        Texto traducido
    """
    return i18n.get_text(key, language, default, **kwargs)

def t(key: str, language: str = None, default: str = None, **kwargs) -> str:
    """
    Alias corto para get_text
    
    Args:
        key: Clave de traducción
        language: Idioma (opcional)
        default: Valor por defecto (opcional)
        **kwargs: Variables para interpolación
        
    Returns:
        Texto traducido
    """
    return get_text(key, language, default, **kwargs)

def get_language_list() -> Dict[str, str]:
    """Obtiene la lista de idiomas disponibles"""
    return i18n.get_language_list()

def is_language_supported(language: str) -> bool:
    """Verifica si un idioma está soportado"""
    return i18n.is_language_supported(language)

def get_current_language() -> str:
    """Obtiene el idioma actual"""
    return i18n.get_current_language()

def set_language(language: str):
    """Establece el idioma por defecto"""
    i18n.set_language(language)

def reload_translations():
    """Recarga las traducciones"""
    i18n.reload_translations()

# Funciones específicas para templates HTML
def get_html_translations(language: str = None) -> Dict[str, Any]:
    """
    Obtiene todas las traducciones para usar en templates HTML
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con todas las traducciones
    """
    if language is None:
        language = get_current_language()
    
    return i18n.get_translation_keys(language)

def get_common_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos comunes para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos comunes
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("common", {})

def get_navigation_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de navegación para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de navegación
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("navigation", {})

def get_dashboard_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos del dashboard para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos del dashboard
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("dashboard", {})

def get_auth_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de autenticación para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de autenticación
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("auth", {})

def get_system_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos del sistema para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos del sistema
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("system", {})

def get_network_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de red para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de red
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("network", {})

def get_wifi_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de WiFi para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de WiFi
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("wifi", {})

def get_vpn_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de VPN para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de VPN
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("vpn", {})

def get_wireguard_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de WireGuard para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de WireGuard
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("wireguard", {})

def get_adblock_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de AdBlock para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de AdBlock
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("adblock", {})

def get_hostapd_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de HostAPD para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de HostAPD
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("hostapd", {})

def get_settings_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de configuración para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de configuración
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("settings", {})

def get_errors_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de errores para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de errores
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("errors", {})

def get_messages_texts(language: str = None) -> Dict[str, str]:
    """
    Obtiene textos de mensajes para usar en templates
    
    Args:
        language: Idioma (opcional)
        
    Returns:
        Diccionario con textos de mensajes
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get("messages", {})

def get_context_translations(context: str, language: str = None) -> Dict[str, str]:
    """
    Obtiene traducciones para un contexto específico
    
    Args:
        context: Contexto (ej: "common", "navigation", "dashboard")
        language: Idioma (opcional)
        
    Returns:
        Diccionario con traducciones del contexto
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    return translations.get(context, {})

def get_multiple_contexts_translations(contexts: list, language: str = None) -> Dict[str, Dict[str, str]]:
    """
    Obtiene traducciones para múltiples contextos
    
    Args:
        contexts: Lista de contextos
        language: Idioma (opcional)
        
    Returns:
        Diccionario con traducciones de múltiples contextos
    """
    if language is None:
        language = get_current_language()
    
    translations = i18n.get_translation_keys(language)
    result = {}
    
    for context in contexts:
        if context in translations:
            result[context] = translations[context]
    
    return result 