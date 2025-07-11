"""
Manejadores de errores HTTP y globales para la aplicación.
Unifica manejo de errores para API y vistas HTML.
"""
from flask import render_template, request, jsonify, current_app
from werkzeug.exceptions import HTTPException
import traceback
import logging

def register_error_handlers(app):
    """
    Registra los manejadores de errores globales para la aplicación Flask.
    """
    app.config['TRAP_HTTP_EXCEPTIONS'] = False
    
    @app.errorhandler(400)
    def bad_request_error(error):
        return handle_http_error(400, error)
    
    @app.errorhandler(401)
    def unauthorized_error(error):
        return handle_http_error(401, error)
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return handle_http_error(403, error)
    
    @app.errorhandler(404)
    def not_found_error(error):
        return handle_http_error(404, error)
    
    @app.errorhandler(405)
    def method_not_allowed_error(error):
        return handle_http_error(405, error)
    
    @app.errorhandler(408)
    def request_timeout_error(error):
        return handle_http_error(408, error)
    
    @app.errorhandler(413)
    def request_entity_too_large_error(error):
        return handle_http_error(413, error)
    
    @app.errorhandler(429)
    def too_many_requests_error(error):
        return handle_http_error(429, error)
    
    @app.errorhandler(500)
    def internal_error(error):
        return handle_http_error(500, error, error_info=str(error))
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        if isinstance(error, HTTPException):
            return handle_http_error(error.code, error)
        current_app.logger.error(f"Error no manejado: {str(error)}")
        current_app.logger.error(traceback.format_exc())
        return handle_http_error(500, error, error_info=traceback.format_exc())

def handle_http_error(status_code, error, error_info=None):
    """
    Maneja los errores HTTP y devuelve la respuesta apropiada (JSON o HTML).
    """
    if request.is_json or request.path.startswith('/api/'):
        response = jsonify({
            'status': 'error',
            'code': status_code,
            'message': str(error),
            'error': error.name if hasattr(error, 'name') else 'Error',
            'path': request.path
        })
        response.status_code = status_code
        return response
    error_templates = {
        400: 'errors/400.html',
        401: 'errors/401.html',
        403: 'errors/403.html',
        404: 'errors/404.html',
        405: 'errors/405.html',
        408: 'errors/408.html',
        413: 'errors/413.html',
        429: 'errors/429.html',
        500: 'errors/500.html',
        502: 'errors/502.html',
        503: 'errors/503.html',
        504: 'errors/504.html'
    }
    template = error_templates.get(status_code, 'errors/error.html')
    context = {
        'error': error,
        'status_code': status_code,
        'error_info': error_info if current_app.config.get('DEBUG') else None
    }
    return render_template(template, **context), status_code
