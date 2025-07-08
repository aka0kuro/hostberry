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
                'code': 405,
                'message': 'Método no permitido',
                'error': 'El método HTTP utilizado no está permitido para este recurso',
                'path': request.path
            }), 405
            
        return render_template(
            'errors/405.html',
            error=error,
            title='Método no permitido'
        ), 405
    
    @app.errorhandler(429)
    def too_many_requests_error(error: HTTPException) -> Tuple[Dict[str, Any], int]:
        """Maneja errores 429 - Demasiadas solicitudes."""
        logger.warning('Too many requests: %s', request.path)
        
        retry_after = error.retry_after if hasattr(error, 'retry_after') else 60
        
        if request.path.startswith('/api/'):
            return jsonify({
                'status': 'error',
                'code': 429,
                'message': 'Demasiadas solicitudes',
                'error': 'Has superado el límite de solicitudes permitidas',
                'retry_after': retry_after,
                'path': request.path
            }), 429
            
        return render_template(
            'errors/429.html',
            error=error,
            retry_after=retry_after,
            title='Demasiadas solicitudes'
        ), 429
    
    @app.errorhandler(500)
    def internal_server_error(error: HTTPException) -> Tuple[Dict[str, Any], int]:
        """Maneja errores 500 - Error interno del servidor."""
        error_id = error.error_id if hasattr(error, 'error_id') else None
        
        if not error_id:
            error_id = str(uuid.uuid4())
            logger.error('Error ID: %s', error_id)
        
        logger.error(
            'Internal server error: %s\nPath: %s\nMethod: %s\nTraceback: %s',
            str(error),
            request.path,
            request.method,
            traceback.format_exc(),
            extra={'error_id': error_id}
        )
        
        if request.path.startswith('/api/'):
            return jsonify({
                'status': 'error',
                'code': 500,
                'message': 'Error interno del servidor',
                'error': 'Ha ocurrido un error inesperado',
                'error_id': error_id,
                'path': request.path
            }), 500
            
        return render_template(
            'errors/500.html',
            error_id=error_id,
            title='Error interno del servidor'
        ), 500
    
    # Manejador de excepciones no controladas
    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> Tuple[Dict[str, Any], int]:
        """Maneja excepciones no controladas."""
        error_id = str(uuid.uuid4())
        
        logger.critical(
            'Unhandled exception: %s\nPath: %s\nMethod: %s\nTraceback: %s',
            str(error),
            request.path,
            request.method,
            traceback.format_exc(),
            extra={
                'error_id': error_id,
                'stack_trace': traceback.format_exc()
            }
        )
        
        if request.path.startswith('/api/'):
            return jsonify({
                'status': 'error',
                'code': 500,
                'message': 'Error inesperado',
                'error': 'Ha ocurrido un error inesperado',
                'error_id': error_id,
                'path': request.path
            }), 500
            
        return render_template(
            'errors/500.html',
            error_id=error_id,
            title='Error inesperado'
        ), 500

def create_error_response(
    message: str,
    status_code: int = 400,
    error: Optional[str] = None,
    **kwargs: Any
) -> Tuple[Dict[str, Any], int]:
    """Crea una respuesta de error estandarizada.
    
    Args:
        message: Mensaje descriptivo del error
        status_code: Código de estado HTTP
        error: Tipo de error (opcional)
        **kwargs: Datos adicionales para incluir en la respuesta
        
    Returns:
        Tupla con la respuesta JSON y el código de estado
    """
    response = {
        'status': 'error',
        'code': status_code,
        'message': message,
        **kwargs
    }
    
    if error:
        response['error'] = error
    
    return response, status_code

class APIError(Exception):
    """Excepción base para errores de la API."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        payload: Optional[Dict[str, Any]] = None,
        error_id: Optional[str] = None
    ) -> None:
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}
        self.error_id = error_id or str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el error a un diccionario."""
        rv = dict(self.payload or {})
        rv['status'] = 'error'
        rv['code'] = self.status_code
        rv['message'] = self.message
        rv['error_id'] = self.error_id
        return rv
    
    def __str__(self) -> str:
        return f"{self.status_code}: {self.message}"
    
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
