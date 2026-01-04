"""
API endpoints para traducciones
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import json
import os

from core.security import get_current_active_user
from core.i18n import get_html_translations, get_language_list, get_text
from core.hostberry_logging import logger

router = APIRouter()

@router.get("/{language}")
async def get_translations(
    language: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Obtiene las traducciones para un idioma específico
    
    Args:
        language: Código del idioma (es, en)
        current_user: Usuario autenticado
        
    Returns:
        Diccionario con las traducciones
    """
    try:
        # Validar idioma
        available_languages = get_language_list()
        if language not in available_languages:
            raise HTTPException(
                status_code=400, 
                detail=get_text("errors.language_not_supported", default=f"Language '{language}' not supported. Available: {list(available_languages.keys())}", language=language)
            )
        
        # Obtener traducciones
        translations = get_html_translations(language)
        
        logger.info('get_translations', language=language)
        return {
            "language": language,
            "translations": translations,
            "available_languages": available_languages
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error('get_translations_error', language=language, error=str(e))
        raise HTTPException(status_code=500, detail=get_text("errors.translations_error", default="Error getting translations"))

@router.get("/")
async def get_available_languages(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Obtiene la lista de idiomas disponibles
    
    Args:
        current_user: Usuario autenticado
        
    Returns:
        Diccionario con idiomas disponibles
    """
    try:
        languages = get_language_list()
        
        logger.info('get_available_languages', languages=languages)
        return {
            "available_languages": languages,
            "default_language": "es"
        }
    
    except Exception as e:
        logger.error('get_available_languages_error', error=str(e))
        raise HTTPException(status_code=500, detail=get_text("errors.languages_list_error", default="Error getting available languages")) 