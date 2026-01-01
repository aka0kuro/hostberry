"""
Router de autenticación para FastAPI
"""

from datetime import timedelta
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import time

from models.schemas import UserLogin, UserResponse, Token, PasswordChange, TokenResponse, UserCreate, FirstLoginChange
from core.security import (
    authenticate_user, 
    create_access_token, 
    get_current_active_user,
    change_user_password,
    is_default_password,
    verify_token
)
from core.database import db
from core.logging import logger, log_auth_event, log_user_action, log_security_event
from core.i18n import get_text

router = APIRouter()
@router.post("/first-login/change")
async def first_login_change(data: FirstLoginChange):
    """Cambiar usuario/contraseña en primer login y eliminar admin por defecto"""
    try:
        from config.settings import settings
        from core.security import get_password_hash
        
        # Verificar que el usuario admin por defecto existe
        admin_user = await db.execute_query(
            "SELECT username FROM users WHERE username = ?", 
            (settings.default_username,)
        )
        
        if not admin_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=get_text("auth.default_admin_missing", default="El usuario admin por defecto ya no existe")
            )

        # Validaciones básicas
        if data.new_username == settings.default_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=get_text("auth.new_user_cannot_be_admin", default="El nuevo usuario no puede ser 'admin'")
            )

        # Verificar que no exista ya el nuevo usuario
        existing = await db.execute_query(
            "SELECT username FROM users WHERE username = ?", 
            (data.new_username,)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=get_text("auth.user_exists", default="El usuario ya existe")
            )

        # Crear nuevo usuario con la nueva contraseña
        await db.insert_user(username=data.new_username, password_hash=data.new_password)

        # Eliminar usuario admin por defecto
        await db.execute_update(
            "DELETE FROM users WHERE username = ?", 
            (settings.default_username,)
        )

        # Log opcional
        await db.insert_log("INFO", f"Usuario por defecto reemplazado por: {data.new_username}")

        return {"message": get_text("auth.user_updated_relogin", default="Usuario actualizado. Vuelve a iniciar sesión con tus nuevas credenciales.")}

    except HTTPException:
        raise
    except Exception as e:
        logger.error('first_login_change_error', error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=get_text("errors.internal_server_error", default="Error interno del servidor")
        )

security = HTTPBearer()

@router.post("/login", response_model=TokenResponse)
async def login(user_credentials: UserLogin):
    """Iniciar sesión de usuario"""
    try:
        start_time = time.time()
        
        # Autenticar usuario (puede lanzar HTTPException)
        user = await authenticate_user(user_credentials.username, user_credentials.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=get_text("auth.invalid_credentials", default="Credenciales inválidas")
            )
        
        # Crear token de acceso
        access_token = create_access_token(data={"sub": user["username"]})
        
        # Actualizar último login
        await db.execute_update(
            "UPDATE users SET last_login = datetime('now') WHERE username = ?",
            (user["username"],)
        )
        
        response_time = time.time() - start_time
        
        # Log de autenticación exitosa
        log_auth_event("login_success", user_id=user["username"], success=True)
        log_user_action("login", user_id=user["username"], details=f"response_time={response_time:.3f}s")
        
        from config.settings import settings
        # Solo requerir cambio de contraseña si es admin por defecto
        # No verificamos la contraseña por seguridad
        password_change_required = (user["username"] == settings.default_username)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=3600,  # 1 hora
            password_change_required=password_change_required
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error('login_error', error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.internal_server_error", default="Error interno del servidor")
        )

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    """Registrar nuevo usuario"""
    try:
        start_time = time.time()
        
        # Verificar si el usuario ya existe
        existing_user = await db.execute_query(
            "SELECT username FROM users WHERE username = ?",
            (user_data.username,)
        )
        
        if existing_user:
            log_auth_event("register_failed", username=user_data.username, 
                          details="Usuario ya existe", success=False)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_text("auth.user_already_exists", default="El usuario ya existe")
            )
        
        # Crear nuevo usuario
        await db.insert_user(
            username=user_data.username,
            password_hash=user_data.password  # Se hasheará en insert_user
        )
        
        response_time = time.time() - start_time
        
        # Log de registro exitoso
        log_auth_event("register_success", username=user_data.username, success=True)
        log_user_action("register", user_id=user_data.username, details=f"response_time={response_time:.3f}s")
        
        return UserResponse(
            username=user_data.username,
            email=user_data.email,
            disabled=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error('register_error', error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.internal_server_error", default="Error interno del servidor")
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """Obtener información del usuario actual"""
    try:
        log_user_action("get_profile", user_id=current_user.get('username'))
        
        return UserResponse(
            username=current_user.get('username'),
            email=current_user.get('email'),
            is_active=current_user.get('is_active', True)
        )
        
    except Exception as e:
        logger.error('get_user_info_error', error=str(e), user_id=current_user.get('username'))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.internal_server_error", default="Error interno del servidor")
        )

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_active_user)):
    """Cerrar sesión"""
    try:
        log_auth_event("logout", user_id=current_user.get('username'), success=True)
        log_user_action("logout", user_id=current_user.get('username'))
        
        return {"message": "Sesión cerrada exitosamente"}
        
    except Exception as e:
        logger.error('logout_error', error=str(e), user_id=current_user.get('username'))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.internal_server_error", default="Error interno del servidor")
        )

@router.post("/refresh")
async def refresh_token(current_user: dict = Depends(get_current_active_user)):
    """Renovar token de acceso"""
    try:
        start_time = time.time()
        
        # Crear nuevo token
        new_access_token = create_access_token(data={"sub": current_user.get('username')})
        
        response_time = time.time() - start_time
        
        log_auth_event("token_refresh", user_id=current_user.get('username'), success=True)
        log_user_action("refresh_token", user_id=current_user.get('username'), response_time=response_time)
        
        return TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=3600
        )
        
    except Exception as e:
        logger.error('refresh_token_error', error=str(e), user_id=current_user.get('username'))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.internal_server_error", default="Error interno del servidor")
        )

@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Cambiar contraseña del usuario"""
    try:
        start_time = time.time()
        
        # Verificar contraseña actual
        from core.security import verify_password
        if not verify_password(password_data.current_password, current_user["hashed_password"]):
            log_auth_event("change_password_failed", user_id=current_user.get('username'), 
                          details="Contraseña actual incorrecta", success=False)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=get_text("auth.current_password_incorrect", default="Contraseña actual incorrecta")
            )
        
        # Verificar que no sea la contraseña por defecto
        if is_default_password(current_user["username"], password_data.new_password):
            log_auth_event("change_password_failed", user_id=current_user.get('username'), 
                          details="No puedes usar la contraseña por defecto", success=False)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_text("auth.default_password_not_allowed", default="No puedes usar la contraseña por defecto")
            )
        
        # Cambiar contraseña
        from core.security import get_password_hash
        new_hashed_password = get_password_hash(password_data.new_password)
        
        success = await db.update_user_password(current_user["username"], new_hashed_password)
        if not success:
            log_auth_event("change_password_failed", user_id=current_user.get('username'), 
                          details="Error al cambiar la contraseña", success=False)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=get_text("auth.password_change_error", default="Error al cambiar la contraseña")
            )
        
        # Log del cambio de contraseña
        await db.insert_log("INFO", f"Contraseña cambiada para usuario: {current_user['username']}")
        
        logger.info(f"Contraseña cambiada para usuario: {current_user['username']}")
        
        response_time = time.time() - start_time
        
        log_auth_event("change_password_success", user_id=current_user.get('username'), success=True)
        log_user_action("change_password", user_id=current_user.get('username'), details=f"response_time={response_time:.3f}s")
        
        return {"message": "Contraseña cambiada exitosamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error('change_password_error', error=str(e), user_id=current_user.get('username'))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.internal_server_error", default="Error interno del servidor")
        )

@router.get("/users", response_model=list[UserResponse])
async def get_users(current_user: dict = Depends(get_current_active_user)):
    """Obtener lista de usuarios (solo admin)"""
    try:
        # Verificar si es admin
        if not current_user.get('is_admin', False):
            log_security_event("unauthorized_access", user_id=current_user.get('username'), 
                             endpoint="/users", details="Acceso no autorizado")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=get_text("auth.access_denied", default="Acceso denegado")
            )
        
        # Obtener usuarios
        users = await db.execute_query(
            "SELECT username, email, is_active, is_admin, created_at, last_login FROM users"
        )
        
        log_user_action("get_users", user_id=current_user.get('username'))
        
        return [
            UserResponse(
                username=user['username'],
                email=user['email'],
                is_active=user['is_active']
            )
            for user in users
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error('get_users_error', error=str(e), user_id=current_user.get('username'))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("errors.internal_server_error", default="Error interno del servidor")
        ) 