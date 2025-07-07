# Utilidades de internacionalización
from flask import session, request, current_app as app
import logging

def get_locale():
    """
    Determina el idioma a utilizar basado en este orden de prioridad:
    1. Idioma guardado en la sesión del usuario
    2. Cookie de idioma
    3. Preferencias del navegador
    4. Idioma por defecto de la configuración
    
    Returns:
        str: Código de idioma (ej: 'es', 'en')
    """
    from flask import request, session, current_app
    
    try:
        app = current_app._get_current_object()
        supported_langs = app.config.get('BABEL_SUPPORTED_LOCALES', ['es'])
        default_lang = app.config.get('BABEL_DEFAULT_LOCALE', 'es')
        
        # 1. Verificar si hay un idioma guardado en la sesión
        if 'language' in session:
            lang = session['language']
            if lang in supported_langs:
                app.logger.debug(f'Idioma obtenido de la sesión: {lang}')
                return lang
            app.logger.warning(f'Idioma de sesión no soportado: {lang}. Idiomas soportados: {supported_langs}')
        
        # 2. Verificar cookie de idioma
        if 'language' in request.cookies:
            lang = request.cookies.get('language')
            if lang in supported_langs:
                app.logger.debug(f'Idioma obtenido de la cookie: {lang}')
                session['language'] = lang  # Actualizar sesión con el idioma de la cookie
                return lang
        
        # 3. Intentar detectar el idioma del navegador
        browser_lang = request.accept_languages.best_match(supported_langs)
        if browser_lang:
            app.logger.debug(f'Idioma detectado del navegador: {browser_lang}')
            session['language'] = browser_lang  # Guardar en sesión para futuras peticiones
            return browser_lang
        
        # 4. Usar el idioma por defecto de la configuración
        app.logger.debug(f'Usando idioma por defecto: {default_lang}')
        session['language'] = default_lang  # Guardar en sesión
        return default_lang
        
    except Exception as e:
        app.logger.error(f'Error al determinar el idioma: {str(e)}', exc_info=True)
        return default_lang if 'default_lang' in locals() else 'es'

def inject_get_locale():
    return dict(get_locale=get_locale)

def set_language(lang):
    from flask import session, redirect, request, url_for, current_app
    
    # Verificar que el idioma sea soportado
    if lang not in current_app.config.get('BABEL_SUPPORTED_LOCALES', ['es']):
        lang = current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    
    # Establecer el idioma en la sesión
    session['language'] = lang
    
    # Obtener la URL de redirección
    redirect_url = request.args.get('next') or request.referrer or url_for('main.index')
    
    # Crear la respuesta de redirección
    response = redirect(redirect_url)
    
    # Configurar cabeceras para prevenir caché
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Configurar cookie de idioma
    response.set_cookie('language', lang, max_age=60*60*24*30)  # 30 días
    
    return response

def check_lang():
    from flask import session, current_app as app
    return {
        'current_lang': get_locale(),
        'session': dict(session),
        'babel_config': app.config['BABEL_SUPPORTED_LOCALES']
    }
