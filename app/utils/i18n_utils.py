# Utilidades de internacionalización
from flask import session, request, current_app as app
import logging

def get_locale():
    """
    Determina el idioma a utilizar basado en la sesión del usuario o en las preferencias del navegador.
    
    Returns:
        str: Código de idioma (ej: 'es', 'en')
    """
    try:
        # 1. Verificar si hay un idioma guardado en la sesión
        if 'language' in session:
            lang = session['language']
            if lang in app.config.get('BABEL_SUPPORTED_LOCALES', ['es']):
                app.logger.debug(f'Idioma obtenido de la sesión: {lang}')
                return lang
            app.logger.warning(f'Idioma de sesión no soportado: {lang}')
        
        # 2. Intentar detectar el idioma del navegador
        supported_langs = app.config.get('BABEL_SUPPORTED_LOCALES', ['es'])
        browser_lang = request.accept_languages.best_match(supported_langs)
        
        if browser_lang:
            app.logger.debug(f'Idioma detectado del navegador: {browser_lang}')
            return browser_lang
        
        # 3. Usar el idioma por defecto de la configuración
        default_lang = app.config.get('BABEL_DEFAULT_LOCALE', 'es')
        app.logger.debug(f'Usando idioma por defecto: {default_lang}')
        return default_lang
        
    except Exception as e:
        error_msg = f'Error al determinar el idioma: {str(e)}'
        app.logger.error(error_msg, exc_info=True)
        return app.config.get('BABEL_DEFAULT_LOCALE', 'es')

def inject_get_locale():
    return dict(get_locale=get_locale)

def set_language(lang):
    from flask import session, redirect, request, url_for
    if lang in ['en', 'es']:
        session['language'] = lang
        response = redirect(request.args.get('next') or request.referrer or url_for('index'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        return response

def check_lang():
    from flask import session, current_app as app
    return {
        'current_lang': get_locale(),
        'session': dict(session),
        'babel_config': app.config['BABEL_SUPPORTED_LOCALES']
    }
