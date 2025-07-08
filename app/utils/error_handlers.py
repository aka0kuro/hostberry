"""
Módulo de manejo de errores globales para la aplicación.

Este módulo proporciona manejadores de errores globales para la aplicación Flask,
asegurando que todas las excepciones sean capturadas y manejadas de manera consistente.
"""
import traceback
import logging
from functools import wraps
from typing import Callable, Any, Dict, Optional, Tuple

from flask import jsonify, request, current_app, render_template
from werkzeug.exceptions import HTTPException

# Obtener el logger
logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """
    Registra los manejadores de errores globales para la aplicación Flask.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    # Deshabilitar el manejo de errores predeterminado de Flask
    app.config['TRAP_HTTP_EXCEPTIONS'] = False
    
    # Registrar manejadores de errores HTTP
    @app.errorhandler(400)
    def bad_request_error(error: HTTPException) -> Tuple[Dict[str, Any], int]:
        """Maneja errores 400 - Solicitud incorrecta."""
        logger.warning('Bad request: %s - %s', request.path, str(error))
        
        if request.path.startswith('/api/'):
            return jsonify({
                'status': 'error',
                'code': 400,
                'message': 'Solicitud incorrecta',
                'error': str(error.description) if hasattr(error, 'description') else str(error),
                'path': request.path
            }), 400
            
        return render_template(
            'errors/400.html',
            error=error,
            title='Solicitud incorrecta'
        ), 400
    
    @app.errorhandler(401)
    def unauthorized_error(error: HTTPException) -> Tuple[Dict[str, Any], int]:
        """Maneja errores 401 - No autorizado."""
        logger.warning('Unauthorized access: %s', request.path)
        
        if request.path.startswith('/api/'):
            return jsonify({
                'status': 'error',
                'code': 401,
                'message': 'No autorizado',
                'error': 'Se requiere autenticación para acceder a este recurso',
                'path': request.path
            }), 401
            
        return render_template(
            'errors/401.html',
            error=error,
            title='Acceso no autorizado'
        ), 401
    
    @app.errorhandler(403)
    def forbidden_error(error: HTTPException) -> Tuple[Dict[str, Any], int]:
        """Maneja errores 403 - Prohibido."""
        logger.warning('Forbidden access: %s - %s', request.path, str(error))
        
        if request.path.startswith('/api/'):
            return jsonify({
                'status': 'error',
                'code': 403,
                'message': 'Acceso denegado',
                'error': 'No tienes permiso para acceder a este recurso',
                'path': request.path
            }), 403
            
        return render_template(
            'errors/403.html',
            error=error,
            title='Acceso denegado'
        ), 403
    
    @app.errorhandler(404)
    def not_found_error(error: HTTPException) -> Tuple[Dict[str, Any], int]:
        """Maneja errores 404 - Recurso no encontrado."""
        logger.warning('Resource not found: %s', request.path)
        
        if request.path.startswith('/api/'):
            return jsonify({
                'status': 'error',
                'code': 404,
                'message': 'Recurso no encontrado',
                'error': 'La ruta solicitada no existe',
                'path': request.path
            }), 404
            
        return render_template(
            'errors/404.html',
            error=error,
            title='Página no encontrada'
        ), 404
    
    @app.errorhandler(405)
    def method_not_allowed_error(error: HTTPException) -> Tuple[Dict[str, Any], int]:
        """Maneja errores 405 - Método no permitido."""
        logger.warning('Method not allowed: %s %s', request.method, request.path)
        
        if request.path.startswith('/api/'):
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
