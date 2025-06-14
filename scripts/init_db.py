#!/usr/bin/env python3
"""
Script para inicializar la base de datos y crear un usuario administrador por defecto.
"""
import os
import sys
import logging
from werkzeug.security import generate_password_hash

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Añadir el directorio raíz al path para poder importar la aplicación
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar después de modificar el path
try:
    from app import create_app, db
    from app.models.user import User
except ImportError as e:
    logger.error(f"Error al importar módulos: {e}")
    sys.exit(1)

def create_admin_user():
    """Crea un usuario administrador por defecto en la base de datos."""
    logger.info("Iniciando creación de usuario administrador...")
    
    # Credenciales por defecto
    username = os.getenv('DEFAULT_ADMIN_USER', 'admin')
    password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
    email = os.getenv('DEFAULT_ADMIN_EMAIL', f'{username}@localhost.local')
    
    try:
        # Crear aplicación y contexto
        app = create_app()  # Usar configuración por defecto
        
        with app.app_context():
            logger.info("Creando tablas de la base de datos...")
            db.create_all()
            
            # Verificar si ya existe un usuario administrador
            if User.query.filter_by(username=username).first():
                logger.warning(f"El usuario '{username}' ya existe en la base de datos.")
                return True
            
            logger.info(f"Creando usuario administrador: {username}")
            
            # Crear usuario administrador
            admin = User(
                username=username,
                email=email,
                is_admin=True
            )
            admin.set_password(password)
            
            # Guardar en la base de datos
            db.session.add(admin)
            db.session.commit()
            
            logger.info("Usuario administrador creado exitosamente")
            print("\n=== Usuario Administrador Creado ===\n")
            print(f"Usuario: {username}")
            print(f"Contraseña: {password}")
            print("\n¡IMPORTANTE! Por seguridad, cambia esta contraseña después de iniciar sesión.")
            return True
            
    except Exception as e:
        logger.error(f"Error al crear el usuario administrador: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    create_admin_user()
