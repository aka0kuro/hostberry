class HostBerryException(Exception):
    """Excepción base para HostBerry"""
    pass

class ConfigurationError(HostBerryException):
    """Error de configuración"""
    pass

class SecurityError(HostBerryException):
    """Error de seguridad"""
    pass

class NetworkError(HostBerryException):
    """Error de red"""
    pass

class ServiceError(HostBerryException):
    """Error de servicio"""
    pass 