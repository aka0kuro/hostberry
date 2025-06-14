#!/usr/bin/env python3
"""
WSGI entry point para la aplicación HostBerry
"""
import os
from app import create_app

# Crear la aplicación Flask
app = create_app()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
