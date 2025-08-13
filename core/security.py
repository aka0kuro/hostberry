"""
Módulo de seguridad para FastAPI
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
import jwt
from jwt import PyJWTError as JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config.settings import settings

# Configurar logger
logger = logging.getLogger(__name__)

# Configuración de seguridad
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)

# Control de intentos de login
FAILED_LOGIN_ATTEMPTS: Dict[str, int] = {}
LOGIN_BLOCKED: Dict[str, float] = {}

# SECRET_KEY generada automáticamente
_AUTO_SECRET_KEY = None

def get_pwd_context():
    """Obtiene el contexto de contraseñas con la configuración correcta"""
    return CryptContext(
        schemes=["bcrypt"],
        deprecated="auto",
        bcrypt__rounds=12  # Valor fijo para evitar problemas con settings
    )

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña"""
    try:
        import bcrypt
        # Usar bcrypt directamente en lugar de passlib
        result = bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        return result
    except Exception as e:
        print(f"Error en verify_password: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Genera hash de contraseña"""
    try:
        import bcrypt
        # Usar bcrypt directamente en lugar de passlib
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))
        return hashed.decode('utf-8')
    except Exception as e:
        print(f"Error en get_password_hash: {e}")
        return ""

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un token de acceso JWT"""
    global _AUTO_SECRET_KEY
    
    logger.info("🔑 Función create_access_token ejecutándose")
    
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    
    # Usar SECRET_KEY configurada o generar una automáticamente
    secret_key = settings.secret_key
    if not secret_key:
        if _AUTO_SECRET_KEY is None:
            import secrets
            _AUTO_SECRET_KEY = secrets.token_urlsafe(32)
            logger.info(f"🔑 SECRET_KEY generada automáticamente: {_AUTO_SECRET_KEY[:10]}...")
        secret_key = _AUTO_SECRET_KEY
    
    logger.info(f"🔑 Usando SECRET_KEY: {secret_key[:10]}...")
    
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifica un token JWT"""
    global _AUTO_SECRET_KEY
    
    try:
        # Usar la misma SECRET_KEY que create_access_token
        secret_key = settings.secret_key
        if not secret_key:
            if _AUTO_SECRET_KEY is None:
                import secrets
                _AUTO_SECRET_KEY = secrets.token_urlsafe(32)
                logger.info(f"🔑 SECRET_KEY generada automáticamente: {_AUTO_SECRET_KEY[:10]}...")
            secret_key = _AUTO_SECRET_KEY
        
        payload = jwt.decode(token, secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            return None
        return payload
    except JWTError:
        return None

async def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Autentica un usuario"""
    logger.info(f"🔑 Autenticando usuario: {username}")
    
    # Verificar si el usuario está bloqueado
    if username in LOGIN_BLOCKED:
        if time.time() < LOGIN_BLOCKED[username]:
            remaining_time = int((LOGIN_BLOCKED[username] - time.time()) / 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Usuario bloqueado. Intente nuevamente en {remaining_time} minutos."
            )
        else:
            del LOGIN_BLOCKED[username]
            FAILED_LOGIN_ATTEMPTS[username] = 0
    
    try:
        # Importar aquí para evitar dependencias circulares
        from core.database import db
        
        # Obtener usuario de la base de datos
        user = await db.get_user_by_username(username)
        if not user:
            logger.info(f"🔑 Usuario no encontrado: {username}")
            # Usuario no existe (404 para diferenciar en el cliente)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no existe"
            )
        
        logger.info(f"🔑 Usuario encontrado: {username}, verificando contraseña")
        
        if not verify_password(password, user["password_hash"]):
            logger.info(f"🔑 Contraseña incorrecta para usuario: {username}")
            # Incrementar contador de intentos fallidos
            FAILED_LOGIN_ATTEMPTS[username] = FAILED_LOGIN_ATTEMPTS.get(username, 0) + 1
            
            # Bloquear usuario si excede el límite
            if FAILED_LOGIN_ATTEMPTS[username] >= settings.max_login_attempts:
                LOGIN_BLOCKED[username] = time.time() + settings.login_block_duration
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Demasiados intentos fallidos. Usuario bloqueado por {settings.login_block_duration // 60} minutos."
                )
            
            # Contraseña incorrecta (401)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Contraseña incorrecta"
            )
        
        # Resetear contador de intentos fallidos
        FAILED_LOGIN_ATTEMPTS[username] = 0
        
        logger.info(f"🔑 Usuario autenticado exitosamente: {username}")
        
        return {
            "username": user["username"],
            "full_name": user.get("full_name", ""),
            "email": user.get("email", ""),
            "disabled": user.get("disabled", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error autenticando usuario: {e}")
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Obtiene el usuario actual basado en el token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        # Importar aquí para evitar dependencias circulares
        from core.database import db
        
        user = await db.get_user_by_username(username)
        if user is None:
            raise credentials_exception
        
        return {
            "username": user["username"],
            "full_name": user.get("full_name", ""),
            "email": user.get("email", ""),
            "disabled": user.get("disabled", False)
        }
        
    except JWTError:
        raise credentials_exception

async def get_current_active_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Obtiene el usuario activo actual"""
    if current_user.get("disabled"):
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    return current_user

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional)
) -> Optional[Dict[str, Any]]:
    """Obtiene el usuario actual si hay credenciales, o None si no las hay o son inválidas"""
    if credentials is None:
        return None
    try:
        payload = verify_token(credentials.credentials)
        if payload is None:
            return None
        username: str = payload.get("sub")
        if username is None:
            return None
        from core.database import db
        user = await db.get_user_by_username(username)
        if user is None:
            return None
        return {
            "username": user["username"],
            "full_name": user.get("full_name", ""),
            "email": user.get("email", ""),
            "disabled": user.get("disabled", False)
        }
    except Exception:
        return None

def is_default_password(username: str, password: str) -> bool:
    """Verifica si la contraseña es la por defecto"""
    return username == settings.default_username and password == settings.default_password

def change_user_password(username: str, new_password: str) -> bool:
    """Cambia la contraseña de un usuario"""
    try:
        # Importar aquí para evitar dependencias circulares
        from core.database import db
        import asyncio
        
        # Hashear la nueva contraseña
        hashed_password = get_password_hash(new_password)
        
        # Actualizar en la base de datos
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si estamos en un contexto async, usar await
            import asyncio
            task = asyncio.create_task(db.update_user_password(username, hashed_password))
            return True  # Asumimos éxito
        else:
            # Si no estamos en un contexto async, ejecutar sincrónicamente
            result = loop.run_until_complete(db.update_user_password(username, hashed_password))
            return result
            
    except Exception as e:
        logger.error(f"Error cambiando contraseña: {e}")
        return False

def create_user(username: str, password: str, full_name: str = "", email: str = "") -> bool:
    """Crea un nuevo usuario"""
    try:
        # Importar aquí para evitar dependencias circulares
        from core.database import db
        import asyncio
        
        # Hashear la contraseña
        hashed_password = get_password_hash(password)
        
        # Crear en la base de datos
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si estamos en un contexto async, usar await
            task = asyncio.create_task(db.insert_user(username, hashed_password))
            return True  # Asumimos éxito
        else:
            # Si no estamos en un contexto async, ejecutar sincrónicamente
            result = loop.run_until_complete(db.insert_user(username, hashed_password))
            return result
            
    except Exception as e:
        logger.error(f"Error creando usuario: {e}")
        return False

def get_user_info(username: str) -> Optional[Dict[str, Any]]:
    """Obtiene información de un usuario"""
    try:
        # Importar aquí para evitar dependencias circulares
        from core.database import db
        import asyncio
        
        # Obtener de la base de datos
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si estamos en un contexto async, usar await
            task = asyncio.create_task(db.get_user_by_username(username))
            return None  # No podemos esperar el resultado en contexto async
        else:
            # Si no estamos en un contexto async, ejecutar sincrónicamente
            user = loop.run_until_complete(db.get_user_by_username(username))
            if user:
                return {
                    "username": user["username"],
                    "full_name": user.get("full_name", ""),
                    "email": user.get("email", ""),
                    "disabled": user.get("disabled", False)
                }
            return None
            
    except Exception as e:
        logger.error(f"Error obteniendo información de usuario: {e}")
        return None 