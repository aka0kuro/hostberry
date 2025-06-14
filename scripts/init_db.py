#!/usr/bin/env python3
"""
Script para inicializar la base de datos y crear un usuario administrador por defecto.
"""
import os
import sys
from werkzeug.security import generate_password_hash

# Añadir el directorio raíz al path para poder importar la aplicación
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.user import User

def create_admin_user():
    """Crea un usuario administrador por defecto en la base de datos."""
    print("\n=== Creando Usuario Administrador por Defecto ===\n")
    
    # Credenciales por defecto
    username = "admin"
    password = "admin123"
    
    # Crear aplicación y contexto
    app = create_app('development')
    with app.app_context():
        # Crear tablas si no existen
        db.create_all()
        
        # Verificar si ya existe un usuario administrador
        if User.query.filter_by(username=username).first():
            print(f"[!] El usuario '{username}' ya existe en la base de datos.")
            return
        
        # Crear usuario administrador
        admin = User(
            username=username,
            email=f"{username}@localhost.local",  # Email por defecto
            is_admin=True
        )
        admin.set_password(password)
        
        # Guardar en la base de datos
        db.session.add(admin)
        db.session.commit()
        
        print(f"[+] Usuario administrador creado exitosamente!")
        print(f"[+] Usuario: {username}")
        print(f"[+] Contraseña: {password}")
        print("\n¡IMPORTANTE! Por seguridad, cambia esta contraseña después de iniciar sesión.")

if __name__ == "__main__":
    create_admin_user()
