# HostBerry - Backend Go + Lua

Arquitectura híbrida usando Go como servidor web principal y Lua para scripting del sistema.

## Arquitectura

### Go (Servidor Principal)
- **Framework**: Fiber (similar a Express.js, muy rápido)
- **Responsabilidades**:
  - Servidor HTTP/HTTPS
  - APIs REST
  - Autenticación JWT
  - Base de datos (SQLite/PostgreSQL)
  - Middlewares (CORS, seguridad, logging)
  - Templates HTML (Jinja2-like)

### Lua (Scripting del Sistema)
- **Motor**: Gopher-Lua
- **Responsabilidades**:
  - Ejecución de comandos del sistema
  - Configuración dinámica
  - Tareas específicas (WiFi, VPN, WireGuard, etc.)
  - Scripts personalizables sin recompilar

## Ventajas de esta Arquitectura

1. **Rendimiento**: Go es extremadamente rápido y eficiente en memoria
2. **Flexibilidad**: Lua permite modificar lógica sin recompilar
3. **Seguridad**: Go maneja autenticación/autorización, Lua solo ejecuta comandos validados
4. **Mantenibilidad**: Scripts Lua son fáciles de leer y modificar
5. **Portabilidad**: Binario único de Go, scripts Lua como archivos de texto

## Estructura del Proyecto

```
go-backend/
├── main.go              # Aplicación principal
├── lua_engine.go        # Motor Lua integrado
├── handlers.go          # Handlers HTTP
├── database.go          # Acceso a BD
├── auth.go              # Autenticación JWT
├── lua/
│   └── scripts/
│       ├── system_stats.lua
│       ├── system_restart.lua
│       ├── wifi_scan.lua
│       ├── wifi_connect.lua
│       ├── vpn_connect.lua
│       ├── wireguard_config.lua
│       └── adblock_update.lua
├── website/
│   ├── templates/       # Templates HTML
│   └── static/          # CSS, JS, imágenes
└── config.yaml          # Configuración
```

## Instalación

```bash
# Instalar Go (1.21+)
sudo apt install golang-go

# Instalar dependencias
cd go-backend
go mod download

# Compilar
go build -o hostberry

# Ejecutar
./hostberry
```

## Configuración

Crear `config.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: false
  read_timeout: 30
  write_timeout: 30

database:
  type: "sqlite"
  path: "data/hostberry.db"

security:
  jwt_secret: "cambiar-en-produccion"
  token_expiry: 1440  # minutos
  bcrypt_cost: 10
  rate_limit_rps: 10

lua:
  scripts_path: "lua/scripts"
  enabled: true
```

## Ejemplo de Script Lua

```lua
-- system_stats.lua
local result = {}

local cpu_cmd = "top -bn1 | grep 'Cpu(s)'"
local cpu_output = exec(cpu_cmd)
result.cpu_usage = parse_cpu(cpu_output)

return result
```

## Funciones Go Disponibles en Lua

- `exec(cmd)`: Ejecuta comando del sistema
- `read_file(path)`: Lee archivo
- `write_file(path, content)`: Escribe archivo
- `log(level, message)`: Logging
- `getenv(key)`: Variable de entorno

## Migración desde Python

### Ventajas
- ✅ Mejor rendimiento (especialmente en RPi 3)
- ✅ Menor uso de memoria
- ✅ Binario único (sin dependencias Python)
- ✅ Scripts Lua más ligeros que Python

### Consideraciones
- ⚠️ Reescritura completa del backend
- ⚠️ Aprender Go y Lua
- ⚠️ Migrar lógica de negocio
- ⚠️ Adaptar templates

## Desarrollo

```bash
# Modo desarrollo (con hot-reload)
go run main.go

# Compilar para producción
go build -ldflags="-s -w" -o hostberry

# Compilar para Raspberry Pi (ARM)
GOOS=linux GOARCH=arm GOARM=7 go build -o hostberry-arm
```

## Próximos Pasos

1. Implementar autenticación JWT completa
2. Migrar módulos Python a scripts Lua
3. Implementar base de datos (GORM)
4. Migrar templates HTML
5. Testing y optimización
