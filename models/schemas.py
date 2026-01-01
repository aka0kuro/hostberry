"""
Modelos Pydantic para la API de HostBerry
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from core.i18n import get_text

# Modelos de autenticación
class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)

class UserResponse(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    disabled: bool = False

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    password_change_required: bool = False

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    email: Optional[str] = None
    password: str = Field(..., min_length=8, max_length=100)
    
    @validator('password')
    def validate_password_strength(cls, v):
        from core.security_middleware import validate_password_strength
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v

class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        from core.security_middleware import validate_password_strength
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError(get_text("auth.passwords_dont_match", default="Las contraseñas no coinciden"))
        return v

class FirstLoginChange(BaseModel):
    new_username: str = Field(..., min_length=3, max_length=50)
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str = Field(..., min_length=8, max_length=100)

    @validator('new_password')
    def validate_password_strength_first(cls, v):
        from core.security_middleware import validate_password_strength
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v

    @validator('confirm_password')
    def passwords_match_first(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError(get_text("auth.passwords_dont_match", default="Las contraseñas no coinciden"))
        return v

# Modelos de WiFi
class WiFiNetwork(BaseModel):
    ssid: str = Field(..., max_length=32)
    security: Optional[str] = None
    signal_strength: Optional[int] = None
    frequency: Optional[int] = None
    connected: bool = False

class WiFiConnect(BaseModel):
    ssid: str = Field(..., max_length=32)
    password: Optional[str] = Field(None, min_length=8, max_length=63)
    security: Optional[str] = None

class WiFiStatus(BaseModel):
    connected: bool
    ssid: Optional[str] = None
    ip_address: Optional[str] = None
    signal_strength: Optional[int] = None
    interface: Optional[str] = None

# Modelos del sistema
class SystemStats(BaseModel):
    cpu_usage: float = Field(..., ge=0, le=100)
    memory_usage: float = Field(..., ge=0, le=100)
    disk_usage: float = Field(..., ge=0, le=100)
    cpu_temperature: Optional[float] = None
    uptime: Optional[int] = None

class NetworkStats(BaseModel):
    interface: str
    ip_address: str
    upload_speed: float
    download_speed: float
    bytes_sent: int
    bytes_recv: int

class SystemInfo(BaseModel):
    hostname: str
    platform: str
    python_version: str
    uptime: int
    load_average: List[float]

# Modelos de VPN
class VPNConfig(BaseModel):
    server: str = Field(..., max_length=255)
    port: int = Field(..., ge=1, le=65535)
    protocol: str = Field(..., pattern="^(udp|tcp)$")
    username: Optional[str] = None
    password: Optional[str] = None
    config_file: Optional[str] = None

class VPNStatus(BaseModel):
    connected: bool
    server: Optional[str] = None
    ip_address: Optional[str] = None
    bytes_sent: int = 0
    bytes_recv: int = 0

# Modelos de WireGuard
class WireGuardConfig(BaseModel):
    private_key: str = Field(..., min_length=44, max_length=44)
    public_key: str = Field(..., min_length=44, max_length=44)
    address: str = Field(..., pattern="^\\d+\\.\\d+\\.\\d+\\.\\d+/\\d+$")
    dns: Optional[str] = None
    endpoint: Optional[str] = None
    listen_port: Optional[int] = Field(None, ge=1, le=65535)
    mtu: Optional[int] = Field(None, ge=1280, le=9000)

class WireGuardStatus(BaseModel):
    running: bool
    interface: str
    public_key: Optional[str] = None
    listen_port: Optional[int] = None
    peers: List[Dict[str, Any]] = []

# Modelos de AdBlock
class AdBlockConfig(BaseModel):
    enabled: bool = True
    update_interval: int = Field(86400, ge=3600, le=604800)  # 1 hora a 1 semana
    block_youtube_ads: bool = True
    whitelist_mode: bool = False
    custom_domains: List[str] = []
    whitelist_domains: List[str] = []

class AdBlockStatus(BaseModel):
    enabled: bool
    last_update: Optional[datetime] = None
    total_domains: int = 0
    blocked_requests: int = 0
    update_progress: Optional[float] = None

# Modelos de HostAPD
class HostAPDConfig(BaseModel):
    interface: str = Field(..., max_length=20)
    ssid: str = Field(..., max_length=32)
    channel: int = Field(1, ge=1, le=14)
    password: Optional[str] = Field(None, min_length=8, max_length=63)
    security: str = Field("wpa2", pattern="^(none|wep|wpa|wpa2)$")
    country_code: str = Field("ES", max_length=2)

class HostAPDStatus(BaseModel):
    running: bool
    interface: str
    ssid: str
    connected_clients: int = 0
    channel: int
    security: str

# Modelos de respuesta
class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None

# Modelos de logs
class LogEntry(BaseModel):
    id: int
    level: str
    message: str
    timestamp: datetime
    user_id: Optional[int] = None

class LogFilter(BaseModel):
    level: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)

# Modelos de configuración
class Configuration(BaseModel):
    key: str = Field(..., max_length=100)
    value: str
    description: Optional[str] = None
    updated_at: datetime

class ConfigurationUpdate(BaseModel):
    value: str
    description: Optional[str] = None

# Modelos de estadísticas
class Statistic(BaseModel):
    metric: str
    value: float
    timestamp: datetime

class StatisticFilter(BaseModel):
    metric: str
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)

# Modelos de servicios
class ServiceStatus(BaseModel):
    name: str
    status: str
    config: Optional[str] = None
    updated_at: datetime

class ServiceUpdate(BaseModel):
    status: str
    config: Optional[str] = None 