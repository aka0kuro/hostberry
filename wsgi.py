#!/usr/bin/env python3
"""
WSGI entry point para la aplicación HostBerry
"""
import os
from app import create_app

# Crear la aplicación Flask para WSGI
application = create_app()
