from flask import jsonify
import logging

def register_error_handlers(app):
    """
    Registra los manejadores de errores globales para la aplicación
    """
    logger = logging.getLogger(__name__)
    
    @app.errorhandler(400)
    def bad_request_error(error):
        logger.warning(f'Bad request: {str(error)}')
        return jsonify({
            'status': 'error',
            'message': 'Solicitud incorrecta',
            'error': str(error)
        }), 400
    
    @app.errorhandler(401)
    def unauthorized_error(error):
        logger.warning(f'Unauthorized: {str(error)}')
        return jsonify({
            'status': 'error',
            'message': 'No autorizado',
            'error': 'Se requiere autenticación para acceder a este recurso'
        }), 401
    
    @app.errorhandler(403)
    def forbidden_error(error):
        logger.warning(f'Forbidden: {str(error)}')
        return jsonify({
            'status': 'error',
            'message': 'Acceso denegado',
            'error': 'No tienes permiso para acceder a este recurso'
        }), 403
    
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f'Not found: {str(error)}')
        return jsonify({
            'status': 'error',
            'message': 'Recurso no encontrado',
            'error': 'La ruta solicitada no existe'
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed_error(error):
        logger.warning(f'Method not allowed: {str(error)}')
        return jsonify({
            'status': 'error',
            'message': 'Método no permitido',
            'error': 'El método HTTP utilizado no está permitido para este recurso'
        }), 405
    
    @app.errorhandler(409)
    def conflict_error(error):
        logger.warning(f'Conflict: {str(error)}')
        return jsonify({
            'status': 'error',
            'message': 'Conflicto',
            'error': 'El recurso que intentas crear ya existe'
        }), 409
    
    @app.errorhandler(429)
    def too_many_requests_error(error):
        logger.warning(f'Too many requests: {str(error)}')
        return jsonify({
            'status': 'error',
            'message': 'Demasiadas solicitudes',
            'error': 'Has excedido el límite de solicitudes. Por favor, espera un momento.'
        }), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        logger.error(f'Internal server error: {str(error)}', exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Error interno del servidor',
            'error': 'Ha ocurrido un error inesperado. Por favor, inténtalo de nuevo más tarde.'
        }), 500
    
    @app.errorhandler(Exception)
    def handle_generic_exception(error):
        logger.error(f'Unhandled exception: {str(error)}', exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Error inesperado',
            'error': 'Ha ocurrido un error inesperado. Por favor, contacta al administrador.'
        }), 500
