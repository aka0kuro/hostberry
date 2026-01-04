"""
Lazy imports para optimizar carga inicial
Evita importar módulos pesados hasta que se necesiten
"""

import sys
from typing import Any, Optional


class LazyImport:
    """Proxy para importación lazy de módulos"""
    
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module: Optional[Any] = None
    
    def _import(self):
        """Importar el módulo cuando se accede por primera vez"""
        if self._module is None:
            self._module = __import__(self._module_name, fromlist=[''])
        return self._module
    
    def __getattr__(self, name: str):
        """Delegar acceso de atributos al módulo"""
        module = self._import()
        return getattr(module, name)
    
    def __call__(self, *args, **kwargs):
        """Permitir llamar al módulo directamente si es callable"""
        module = self._import()
        if callable(module):
            return module(*args, **kwargs)
        return module


# Lazy imports de módulos pesados
psutil = LazyImport('psutil')

# Función helper para obtener psutil de forma lazy
def get_psutil():
    """Obtener psutil de forma lazy"""
    try:
        import psutil
        return psutil
    except ImportError:
        return None

