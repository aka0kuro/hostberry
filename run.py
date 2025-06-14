#!/usr/bin/env python3
"""
Punto de entrada para ejecutar la aplicación HostBerry
"""
import os
from app import create_app

# Crear la aplicación Flask
app = create_app()

if __name__ == "__main__":
    # Obtener el puerto de la variable de entorno o usar 5000 por defecto
    port = int(os.environ.get('PORT', 5000))
    
    # Ejecutar la aplicación
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    )
