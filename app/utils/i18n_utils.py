# Utilidades de internacionalización
from flask import session, request, current_app as app
import logging

def get_locale():
    try:
        if 'language' in session:
            return session['language']
        browser_lang = request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES'])
        if browser_lang:
            return browser_lang
        return app.config['BABEL_DEFAULT_LOCALE']
    except Exception as e:
        logging.getLogger(__name__).error(f"Locale selection error: {str(e)}")
        return app.config['BABEL_DEFAULT_LOCALE']

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
