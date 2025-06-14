"""
Manejadores de errores HTTP personalizados para la aplicación.
"""
from flask import render_template, request, jsonify, current_app
from werkzeug.exceptions import HTTPException
import traceback

def init_app(app):
    """
    Inicializa los manejadores de errores en la aplicación Flask.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    # Manejador para errores 404 (Página no encontrada)
    @app.errorhandler(404)
    def not_found_error(error):
        return handle_http_error(404, error)
    
    # Manejador para errores 403 (Acceso prohibido)
    @app.errorhandler(403)
    def forbidden_error(error):
        return handle_http_error(403, error)
    
    # Manejador para errores 401 (No autorizado)
    @app.errorhandler(401)
    def unauthorized_error(error):
        return handle_http_error(401, error)
    
    # Manejador para errores 500 (Error interno del servidor)
    @app.errorhandler(500)
    def internal_error(error):
        return handle_http_error(500, error, error_info=str(error))
    
    # Manejador para excepciones generales
    @app.errorhandler(Exception)
    def handle_exception(error):
        # Si es un error HTTP estándar, usamos el manejador correspondiente
        if isinstance(error, HTTPException):
            return handle_http_error(error.code, error)
        
        # Para otros errores, registramos el error y mostramos la página 500
        current_app.logger.error(f"Error no manejado: {str(error)}")
        current_app.logger.error(traceback.format_exc())
        
        return handle_http_error(500, error, error_info=traceback.format_exc())

def handle_http_error(status_code, error, error_info=None):
    """
    Maneja los errores HTTP y devuelve la respuesta apropiada.
    
    Args:
        status_code: Código de estado HTTP
        error: Objeto de error
        error_info: Información adicional del error (opcional)
        
    Returns:
        Respuesta HTTP con la plantilla de error o un JSON
    """
    # Determinar si la solicitud espera una respuesta JSON
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
    
    # Para solicitudes HTML, renderizar la plantilla de error correspondiente
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
    
    # Contexto para la plantilla
    context = {
        'error': error,
        'status_code': status_code,
        'error_info': error_info if current_app.config.get('DEBUG') else None
    }
    
    return render_template(template, **context), status_code
