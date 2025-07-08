"""
Middleware para agregar cabeceras de seguridad HTTP.

Este módulo proporciona un middleware para Flask que agrega cabeceras
de seguridad a todas las respuestas HTTP.
"""
from flask import request
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class SecurityHeadersMiddleware:
    """
    Middleware para agregar cabeceras de seguridad a las respuestas HTTP.
    
    Atributos:
        app: Aplicación Flask
        csp_config: Configuración de Content Security Policy
    """
    
    def __init__(self, app=None):
        """Inicializa el middleware.
        
        Args:
            app: Aplicación Flask (opcional)
        """
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa la aplicación con este middleware.
        
        Args:
            app: Aplicación Flask
        """
        # Configuración predeterminada de CSP
        default_csp = {
            'default-src': "'self'",
            'script-src': [
                "'self'",
                "'unsafe-inline'",  # Necesario para algunos componentes de Bootstrap
                "'unsafe-eval'"    # Necesario para algunos componentes de JavaScript
            ],
            'style-src': [
                "'self'",
                "'unsafe-inline'",  # Necesario para estilos en línea
                "https://stackpath.bootstrapcdn.com"
            ],
            'img-src': ["'self'", "data:", "https: http:"],
            'font-src': ["'self'", "https://stackpath.bootstrapcdn.com"],
            'connect-src': ["'self'"],
            'frame-ancestors': ["'self'"],
            'form-action': ["'self'"],
            'object-src': ["'none'"],
            'base-uri': ["'self'"],
            'frame-src': ["'self'"]
        }
        
        # Obtener la configuración de la aplicación o usar valores predeterminados
        self.csp = app.config.get('SECURITY_HEADERS_CSP', default_csp)
        
        # Registrar el middleware
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        
        logger.info("Middleware de cabeceras de seguridad inicializado")
    
    def _before_request(self):
        """Método ejecutado antes de cada solicitud."""
        # Aquí podríamos agregar lógica previa a la solicitud si es necesario
        pass
    
    def _after_request(self, response):
        """Agrega las cabeceras de seguridad a la respuesta.
        
        Args:
            response: Objeto de respuesta de Flask
            
        Returns:
            Respuesta con las cabeceras de seguridad
        """
        # Configuración de cabeceras de seguridad
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
            'Cross-Origin-Embedder-Policy': 'require-corp',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'same-origin',
        }
        
        # Agregar Content Security Policy
        if self.csp:
            csp_parts = []
            for key, values in self.csp.items():
                if isinstance(values, (list, tuple)):
                    values = ' '.join(values)
                csp_parts.append(f"{key} {values}")
            
            csp_header = '; '.join(csp_parts)
            security_headers['Content-Security-Policy'] = csp_header
        
        # No cachear respuestas por defecto
        if 'Cache-Control' not in response.headers:
            security_headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        
        # Agregar las cabeceras a la respuesta
        for header, value in security_headers.items():
            if header not in response.headers:
                response.headers[header] = value
        
        return response

def security_headers(f):
    """Decorador para agregar cabeceras de seguridad a una ruta específica.
    
    Args:
        f: Función de vista de Flask
        
    Returns:
        Función envuelta con las cabeceras de seguridad
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        
        # Agregar cabeceras de seguridad
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
            
        return response
    
    return decorated_function
