# HostBerry - Sistema de Gestión de Red

Sistema de gestión de red para Raspberry Pi, migrado a Go + Lua para mejor rendimiento y despliegue como binario único.

## 🚀 Características

- **Backend en Go**: Alto rendimiento y binario único
- **Scripts Lua**: Operaciones del sistema mediante Lua
- **Interfaz Web Moderna**: UI responsive con tema claro/oscuro
- **Multi-idioma**: Soporte para Español e Inglés
- **Gestión de Red**: WiFi, VPN, WireGuard, AdBlock
- **Monitoreo en Tiempo Real**: Dashboard con métricas del sistema

## 📋 Requisitos

- Go 1.21 o superior
- SQLite (incluido) o PostgreSQL/MySQL
- Lua 5.1+ (para scripts del sistema)
- Linux (probado en Raspberry Pi / Debian)

## 🔧 Instalación en Raspberry Pi 3

### Opción 1: Compilar directamente en Raspberry Pi

```bash
# Instalar Go en Raspberry Pi
sudo apt update
sudo apt install golang-go

# Clonar repositorio
git clone https://github.com/aka0kuro/Hostberry.git
cd Hostberry

# Instalar dependencias
go mod download

# Compilar
make build

# O directamente
go build -o hostberry
```

### Opción 2: Compilar en otra máquina y transferir

```bash
# En tu máquina de desarrollo
git clone https://github.com/aka0kuro/Hostberry.git
cd Hostberry
make build-arm

# Transferir a Raspberry Pi
scp hostberry-arm pi@raspberrypi.local:~/
scp -r website locales lua config.yaml.example pi@raspberrypi.local:~/Hostberry/
```

### En Raspberry Pi 3

```bash
# Compilar directamente en la Raspberry Pi
make build

# O compilar en otra máquina y transferir
make build-arm
scp hostberry-arm pi@raspberrypi.local:~/
```

## ⚙️ Configuración

Copia `config.yaml.example` a `config.yaml` y ajusta la configuración:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: false

database:
  type: "sqlite"
  path: "data/hostberry.db"

security:
  jwt_secret: "cambiar-en-produccion"
  token_expiry: 1440
  bcrypt_cost: 10
  rate_limit_rps: 10

lua:
  scripts_path: "lua/scripts"
  enabled: true
```

## 🏃 Ejecución

```bash
# Modo desarrollo
make run

# O directamente
./hostberry
```

La aplicación estará disponible en `http://localhost:8000`

**Credenciales por defecto:**
- Usuario: `admin`
- Contraseña: `admin` (cambiar en primer inicio)

## 📁 Estructura del Proyecto

```
Hostberry/
├── main.go              # Punto de entrada
├── auth.go              # Autenticación JWT
├── database.go          # Modelos y conexión DB
├── handlers.go          # Handlers HTTP
├── middleware.go        # Middlewares
├── i18n.go             # Internacionalización
├── templates.go        # Sistema de templates
├── lua_engine.go       # Motor Lua
├── validators.go       # Validación de datos
├── health.go           # Health checks
├── rate_limiter.go     # Rate limiting
├── website/
│   ├── templates/     # Templates HTML
│   └── static/        # CSS, JS, imágenes
├── locales/            # Traducciones JSON
└── lua/scripts/        # Scripts Lua del sistema
```

## 🔌 Endpoints

### Web
- `GET /` - Redirige a dashboard
- `GET /dashboard` - Dashboard principal
- `GET /login` - Página de login
- `GET /settings` - Configuración
- `GET /network` - Gestión de red
- `GET /wifi` - Gestión WiFi
- `GET /vpn` - Gestión VPN
- `GET /wireguard` - Gestión WireGuard
- `GET /adblock` - Gestión AdBlock

### API
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/auth/me` - Usuario actual
- `GET /api/v1/system/stats` - Estadísticas del sistema
- `GET /api/v1/system/logs` - Logs del sistema
- `POST /api/v1/system/restart` - Reiniciar sistema
- `GET /api/v1/network/interfaces` - Interfaces de red
- `GET /api/v1/wifi/scan` - Escanear redes WiFi
- `POST /api/v1/wifi/connect` - Conectar a WiFi

### Health Checks
- `GET /health` - Health check completo
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness check

## 🛠️ Desarrollo

### Compilar para Raspberry Pi (ARM)

```bash
make build-arm
```

### Tests

```bash
make test
```

### Formatear código

```bash
make fmt
```

## 📝 Migración desde Python

Este proyecto fue migrado desde Python/FastAPI a Go/Fiber. Los templates HTML fueron convertidos de Jinja2 a Go templates, y la lógica del sistema se ejecuta mediante scripts Lua.

## 🔒 Seguridad

- Autenticación JWT
- Rate limiting por IP/usuario
- Validación de inputs
- Headers de seguridad HTTP
- Bcrypt para contraseñas

## 📄 Licencia

[Especificar licencia]

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor, abre un issue o pull request.

## 📧 Soporte

Para soporte, abre un issue en GitHub.
