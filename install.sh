#!/bin/bash

# HostBerry - Script de Instalación para Linux
# Compatible con Debian, Ubuntu, Raspberry Pi OS

set -e  # Salir si hay algún error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables de configuración
INSTALL_DIR="/opt/hostberry"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="hostberry"
USER_NAME="hostberry"
GROUP_NAME="hostberry"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CONFIG_FILE="${INSTALL_DIR}/config.yaml"
LOG_DIR="/var/log/hostberry"
DATA_DIR="${INSTALL_DIR}/data"
GITHUB_REPO="https://github.com/aka0kuro/Hostberry.git"
TEMP_CLONE_DIR="/tmp/hostberry-install"

# Modo de operación
MODE="install"  # install, update o uninstall

# Procesar argumentos
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --update) MODE="update" ;;
        --uninstall) MODE="uninstall" ;;
        *) echo "Opción desconocida: $1"; exit 1 ;;
    esac
    shift
done

# Función para imprimir mensajes
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar si se ejecuta como root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        print_error "Este script debe ejecutarse como root (usa sudo)"
        exit 1
    fi
}

# Detectar sistema operativo
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
        print_info "Sistema detectado: $OS $OS_VERSION"
    else
        print_error "No se pudo detectar el sistema operativo"
        exit 1
    fi
}

# Instalar git (necesario para descargar el proyecto)
install_git() {
    if ! command -v git &> /dev/null; then
        print_info "Instalando git (necesario para descargar el proyecto)..."
        apt-get update -qq
        apt-get install -y git
        print_success "Git instalado"
    else
        print_success "Git ya está instalado: $(git --version)"
    fi
}

# Instalar dependencias del sistema
install_dependencies() {
    print_info "Instalando dependencias del sistema..."
    
    # Actualizar lista de paquetes
    apt-get update -qq
    
    # Instalar dependencias básicas
    DEPS="wget curl build-essential iw"
    
    # Instalar hostapd y herramientas relacionadas
    print_info "Instalando hostapd y herramientas WiFi..."
    apt-get install -y hostapd dnsmasq iptables || print_warning "Algunos paquetes de hostapd no se pudieron instalar"
    print_success "Paquetes de hostapd instalados"
    
    # Verificar si Go está instalado
    if ! command -v go &> /dev/null; then
        print_info "Go no está instalado, instalando..."
        
        # Detectar arquitectura
        ARCH=$(uname -m)
        case $ARCH in
            x86_64)
                GO_ARCH="amd64"
                ;;
            armv7l|armv6l)
                GO_ARCH="armv6l"
                ;;
            aarch64)
                GO_ARCH="arm64"
                ;;
            *)
                print_warning "Arquitectura no reconocida: $ARCH, intentando instalar desde repositorio"
                apt-get install -y golang-go
                return
                ;;
        esac
        
        # Descargar e instalar Go
        GO_VERSION="1.21.5"
        GO_TAR="go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
        GO_URL="https://go.dev/dl/${GO_TAR}"
        
        print_info "Descargando Go ${GO_VERSION}..."
        wget -q "${GO_URL}" -O "/tmp/${GO_TAR}"
        
        print_info "Instalando Go..."
        rm -rf /usr/local/go
        tar -C /usr/local -xzf "/tmp/${GO_TAR}"
        rm "/tmp/${GO_TAR}"
        
        # Agregar Go al PATH
        if ! grep -q "/usr/local/go/bin" /etc/profile; then
            echo 'export PATH=$PATH:/usr/local/go/bin' >> /etc/profile
        fi
        export PATH=$PATH:/usr/local/go/bin
        
        print_success "Go ${GO_VERSION} instalado"
    else
        print_success "Go ya está instalado: $(go version)"
        export PATH=$PATH:/usr/local/go/bin
    fi
    
    # Instalar Lua si no está
    if ! command -v lua5.1 &> /dev/null && ! command -v lua &> /dev/null; then
        print_info "Instalando Lua..."
        apt-get install -y lua5.1 || apt-get install -y lua
    fi
    
    # Verificar e instalar iw si no está disponible (ya está en DEPS, pero verificamos por si acaso)
    if ! command -v iw &> /dev/null; then
        print_info "Instalando iw (herramienta para gestión WiFi)..."
        apt-get install -y iw || print_warning "No se pudo instalar iw, puede que no esté disponible en este sistema"
    else
        print_success "iw ya está instalado"
    fi
    
    # Instalar otras dependencias
    apt-get install -y $DEPS
    
    print_success "Dependencias instaladas"
}

# Descargar proyecto de GitHub si es necesario
download_project() {
    # En modo update, verificar primero si tenemos código local con todos los archivos
    if [ "$MODE" = "update" ]; then
        # Verificar si estamos en un repositorio git válido con todos los archivos necesarios
        local has_all_files=true
        for item in "website" "lua" "locales" "main.go" "go.mod"; do
            if [ ! -e "${SCRIPT_DIR}/${item}" ]; then
                has_all_files=false
                break
            fi
        done
        
        # Si tenemos todos los archivos localmente, usar el directorio actual (preferir código local)
        if [ "$has_all_files" = true ]; then
            print_info "Modo actualización: usando código local en ${SCRIPT_DIR}"
            print_warning "⚠️  Si quieres actualizar desde GitHub, ejecuta desde un directorio vacío o sin el repo completo"
            return 0
        fi
        
        # Si no tenemos código local, descargar desde GitHub
        print_info "Modo actualización: descargando desde GitHub (no se encontró código local)..."
        
        # Limpiar directorio temporal si existe
        if [ -d "$TEMP_CLONE_DIR" ]; then
            rm -rf "$TEMP_CLONE_DIR"
        fi
        
        # Clonar repositorio
        if git clone "$GITHUB_REPO" "$TEMP_CLONE_DIR" 2>/dev/null; then
            print_success "Proyecto descargado desde GitHub"
            SCRIPT_DIR="$TEMP_CLONE_DIR"
            return 0
        else
            print_error "Error al descargar el proyecto desde GitHub"
            print_info "Verifica tu conexión a internet y que el repositorio sea accesible"
            exit 1
        fi
    fi
    
    # En modo install, verificar si estamos en un repositorio git válido con todos los archivos necesarios
    local has_all_files=true
    for item in "website" "lua" "locales" "main.go" "go.mod"; do
        if [ ! -e "${SCRIPT_DIR}/${item}" ]; then
            has_all_files=false
            break
        fi
    done
    
    # Si tenemos todos los archivos, usar el directorio actual
    if [ "$has_all_files" = true ]; then
        print_info "Usando proyecto local en ${SCRIPT_DIR}"
        return 0
    fi
    
    # Si no, descargar de GitHub
    print_info "Descargando proyecto desde GitHub..."
    
    # Limpiar directorio temporal si existe
    if [ -d "$TEMP_CLONE_DIR" ]; then
        rm -rf "$TEMP_CLONE_DIR"
    fi
    
    # Clonar repositorio
    if git clone "$GITHUB_REPO" "$TEMP_CLONE_DIR" 2>/dev/null; then
        print_success "Proyecto descargado desde GitHub"
        SCRIPT_DIR="$TEMP_CLONE_DIR"
        return 0
    else
        print_error "Error al descargar el proyecto desde GitHub"
        print_info "Verifica tu conexión a internet y que el repositorio sea accesible"
        exit 1
    fi
}

# Limpiar instalación anterior
clean_previous_installation() {
    if [ -d "$INSTALL_DIR" ]; then
        if [ "$MODE" = "update" ]; then
            # En modo actualización, preservar datos y configuración
            print_info "Modo actualización: preservando datos y configuración..."
            
            # Detener servicio si está corriendo
            if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
                print_info "Deteniendo servicio ${SERVICE_NAME}..."
                systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
                # Esperar un momento para que el servicio se detenga completamente
                sleep 2
            fi
            
            # Crear directorio temporal para guardar datos importantes
            TEMP_BACKUP_DIR="/tmp/hostberry-update-backup-$$"
            mkdir -p "$TEMP_BACKUP_DIR"
            
            # Hacer backup de la base de datos ANTES de eliminar nada
            if [ -d "$DATA_DIR" ]; then
                print_info "Guardando backup de base de datos..."
                # Copiar todo el contenido del directorio data
                if cp -r "$DATA_DIR" "$TEMP_BACKUP_DIR/data" 2>/dev/null; then
                    print_success "Backup de base de datos guardado en $TEMP_BACKUP_DIR/data"
                    # Verificar que el archivo de BD existe en el backup
                    if [ -f "$TEMP_BACKUP_DIR/data/hostberry.db" ]; then
                        DB_SIZE=$(du -h "$TEMP_BACKUP_DIR/data/hostberry.db" | cut -f1)
                        print_info "Base de datos respaldada: $DB_SIZE"
                    fi
                else
                    print_error "ERROR: No se pudo hacer backup de la base de datos"
                    print_error "Abortando actualización para proteger los datos"
                    rm -rf "$TEMP_BACKUP_DIR"
                    exit 1
                fi
            else
                print_warning "Directorio de datos no encontrado: $DATA_DIR"
            fi
            
            # Hacer backup de la configuración
            if [ -f "$CONFIG_FILE" ]; then
                print_info "Guardando backup de configuración..."
                if cp "$CONFIG_FILE" "$TEMP_BACKUP_DIR/config.yaml" 2>/dev/null; then
                    print_success "Configuración respaldada"
                else
                    print_warning "No se pudo hacer backup de la configuración"
                fi
            fi
            
            # Mover el directorio data fuera temporalmente para preservarlo
            TEMP_DATA_DIR="/tmp/hostberry-data-temp-$$"
            if [ -d "$DATA_DIR" ]; then
                print_info "Moviendo directorio de datos temporalmente para preservarlo..."
                # Verificar que el directorio data contiene la base de datos
                if [ -f "$DATA_DIR/hostberry.db" ]; then
                    DB_SIZE=$(du -h "$DATA_DIR/hostberry.db" | cut -f1)
                    print_info "Base de datos encontrada: $DB_SIZE"
                fi
                
                if mv "$DATA_DIR" "$TEMP_DATA_DIR" 2>/dev/null; then
                    print_success "Directorio de datos movido temporalmente a $TEMP_DATA_DIR"
                    # Verificar que el archivo de BD está en el directorio temporal
                    if [ -f "$TEMP_DATA_DIR/hostberry.db" ]; then
                        print_success "Base de datos preservada en directorio temporal"
                    else
                        print_warning "Advertencia: No se encontró hostberry.db en el directorio temporal"
                    fi
                else
                    print_error "ERROR: No se pudo mover el directorio de datos"
                    print_error "Abortando actualización para proteger los datos"
                    rm -rf "$TEMP_BACKUP_DIR"
                    exit 1
                fi
            else
                print_warning "Directorio de datos no existe: $DATA_DIR (primera instalación?)"
            fi
            
            # Eliminar directorio de instalación (data ya está fuera)
            print_info "Eliminando archivos antiguos (preservando datos)..."
            # Asegurarse de que no eliminamos el directorio data si aún existe
            if [ -d "$DATA_DIR" ]; then
                print_warning "Advertencia: El directorio data aún existe, moviéndolo antes de eliminar..."
                mv "$DATA_DIR" "$TEMP_DATA_DIR" 2>/dev/null || {
                    print_error "ERROR: No se pudo mover el directorio de datos antes de eliminar"
                    exit 1
                }
            fi
            rm -rf "$INSTALL_DIR"
            print_success "Archivos antiguos eliminados"
            
            # Restaurar directorio de datos
            if [ -d "$TEMP_DATA_DIR" ]; then
                print_info "Restaurando directorio de datos..."
                mkdir -p "$(dirname "$DATA_DIR")"
                if mv "$TEMP_DATA_DIR" "$DATA_DIR" 2>/dev/null; then
                    print_success "Directorio de datos restaurado"
                    # Verificar que la BD existe
                    if [ -f "$DATA_DIR/hostberry.db" ]; then
                        DB_SIZE=$(du -h "$DATA_DIR/hostberry.db" | cut -f1)
                        print_success "✅ Base de datos preservada exitosamente: $DB_SIZE"
                    else
                        print_warning "Advertencia: No se encontró hostberry.db después de restaurar"
                        # Intentar restaurar desde backup
                        if [ -d "$TEMP_BACKUP_DIR/data" ] && [ -f "$TEMP_BACKUP_DIR/data/hostberry.db" ]; then
                            print_info "Intentando restaurar desde backup..."
                            cp -r "$TEMP_BACKUP_DIR/data/"* "$DATA_DIR/" 2>/dev/null && {
                                print_success "Base de datos restaurada desde backup"
                            } || {
                                print_error "ERROR: No se pudo restaurar desde backup"
                            }
                        fi
                    fi
                else
                    print_error "ERROR: No se pudo restaurar el directorio de datos"
                    print_error "Intentando restaurar desde backup..."
                    # Intentar restaurar desde backup como fallback
                    if [ -d "$TEMP_BACKUP_DIR/data" ]; then
                        mkdir -p "$DATA_DIR"
                        if cp -r "$TEMP_BACKUP_DIR/data/"* "$DATA_DIR/" 2>/dev/null; then
                            print_success "Base de datos restaurada desde backup"
                            if [ -f "$DATA_DIR/hostberry.db" ]; then
                                DB_SIZE=$(du -h "$DATA_DIR/hostberry.db" | cut -f1)
                                print_success "Base de datos verificada: $DB_SIZE"
                            fi
                        else
                            print_error "ERROR CRÍTICO: No se pudo restaurar la base de datos"
                            print_error "El backup está en: $TEMP_BACKUP_DIR"
                            print_error "El directorio temporal está en: $TEMP_DATA_DIR"
                            exit 1
                        fi
                    else
                        print_error "ERROR CRÍTICO: No hay backup disponible"
                        print_error "El directorio temporal está en: $TEMP_DATA_DIR"
                        exit 1
                    fi
                fi
            elif [ -d "$TEMP_BACKUP_DIR/data" ]; then
                # Si no se pudo mover, restaurar desde backup
                print_info "Restaurando base de datos desde backup..."
                mkdir -p "$DATA_DIR"
                if cp -r "$TEMP_BACKUP_DIR/data/"* "$DATA_DIR/" 2>/dev/null; then
                    print_success "Base de datos restaurada desde backup"
                    if [ -f "$DATA_DIR/hostberry.db" ]; then
                        DB_SIZE=$(du -h "$DATA_DIR/hostberry.db" | cut -f1)
                        print_success "Base de datos verificada: $DB_SIZE"
                    fi
                else
                    print_error "ERROR CRÍTICO: No se pudo restaurar la base de datos"
                    print_error "El backup está en: $TEMP_BACKUP_DIR"
                    exit 1
                fi
            else
                print_warning "No se encontró directorio de datos ni backup para restaurar"
                print_info "Se creará una nueva base de datos al iniciar el servicio"
            fi
            
            # Restaurar configuración
            if [ -f "$TEMP_BACKUP_DIR/config.yaml" ]; then
                print_info "Restaurando configuración..."
                mkdir -p "$(dirname "$CONFIG_FILE")"
                cp "$TEMP_BACKUP_DIR/config.yaml" "$CONFIG_FILE" 2>/dev/null || true
            fi
            
            # Limpiar backup temporal
            rm -rf "$TEMP_BACKUP_DIR"
            
            print_success "Archivos actualizados, datos preservados"
        else
            # En modo instalación, eliminar todo
            print_info "Eliminando instalación anterior en $INSTALL_DIR..."
            
            # Detener servicio si está corriendo
            if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
                print_info "Deteniendo servicio ${SERVICE_NAME}..."
                systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
            fi
            
            # Deshabilitar servicio
            if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
                print_info "Deshabilitando servicio ${SERVICE_NAME}..."
                systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
            fi
            
            # Eliminar directorio de instalación
            rm -rf "$INSTALL_DIR"
            print_success "Instalación anterior eliminada"
        fi
    else
        print_info "No hay instalación anterior que eliminar"
    fi
}

# Crear usuario del sistema
create_user() {
    if id "$USER_NAME" &>/dev/null; then
        print_info "Usuario $USER_NAME ya existe"
    else
        print_info "Creando usuario $USER_NAME..."
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$USER_NAME"
        print_success "Usuario $USER_NAME creado"
    fi
}

# Copiar archivos del proyecto
install_files() {
    print_info "Instalando archivos en $INSTALL_DIR..."
    
    # Verificar que estamos en el directorio correcto con todos los archivos
    local missing_files=0
    for item in "website" "lua" "locales" "main.go" "go.mod"; do
        if [ ! -e "${SCRIPT_DIR}/${item}" ]; then
            print_warning "No se encontró '${item}' en ${SCRIPT_DIR}"
            missing_files=$((missing_files + 1))
        fi
    done

    if [ $missing_files -gt 0 ]; then
        print_error "Error: Faltan archivos del proyecto en ${SCRIPT_DIR}"
        print_info "Asegúrate de ejecutar el script desde la raíz del repositorio clonado."
        print_info "Si has descargado solo el script, necesitas descargar el proyecto completo."
        exit 1
    fi

    # Crear directorios
    mkdir -p "$INSTALL_DIR"

    mkdir -p "$LOG_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "${INSTALL_DIR}/lua/scripts"
    mkdir -p "${INSTALL_DIR}/locales"
    mkdir -p "${INSTALL_DIR}/website/static"
    mkdir -p "${INSTALL_DIR}/website/templates"
    
    # Copiar archivos necesarios
    print_info "Copiando archivos del proyecto..."
    
    # Archivos Go
    cp -f "${SCRIPT_DIR}"/*.go "${INSTALL_DIR}/" 2>/dev/null || true
    cp -f "${SCRIPT_DIR}/go.mod" "${INSTALL_DIR}/" 2>/dev/null || true
    cp -f "${SCRIPT_DIR}/go.sum" "${INSTALL_DIR}/" 2>/dev/null || true
    
    # Directorios
    if [ -d "${SCRIPT_DIR}/lua/scripts" ]; then
        cp -r "${SCRIPT_DIR}/lua/scripts/"* "${INSTALL_DIR}/lua/scripts/" 2>/dev/null || true
    fi
    
    if [ -d "${SCRIPT_DIR}/locales" ]; then
        cp -r "${SCRIPT_DIR}/locales/"* "${INSTALL_DIR}/locales/" 2>/dev/null || true
    fi
    
    if [ -d "${SCRIPT_DIR}/website" ]; then
        print_info "Copiando templates y archivos estáticos..."
        
        # Asegurar que los directorios destino existen
        mkdir -p "${INSTALL_DIR}/website/templates"
        mkdir -p "${INSTALL_DIR}/website/static"
        
        # Copiar templates con verificación
        if [ -d "${SCRIPT_DIR}/website/templates" ]; then
            print_info "Copiando templates desde ${SCRIPT_DIR}/website/templates..."
            if ! cp -r "${SCRIPT_DIR}/website/templates/"* "${INSTALL_DIR}/website/templates/" 2>/dev/null; then
                print_error "Error al copiar templates"
                exit 1
            fi
            TEMPLATE_COUNT=$(find "${INSTALL_DIR}/website/templates" -name "*.html" 2>/dev/null | wc -l)
            if [ "$TEMPLATE_COUNT" -gt 0 ]; then
                print_success "Templates copiados: $TEMPLATE_COUNT archivos .html"
                # Verificar que base.html y dashboard.html existen (críticos)
                if [ -f "${INSTALL_DIR}/website/templates/base.html" ]; then
                    print_success "  ✅ base.html encontrado"
                else
                    print_error "  ❌ base.html NO encontrado (CRÍTICO)"
                    exit 1
                fi
                if [ -f "${INSTALL_DIR}/website/templates/dashboard.html" ]; then
                    print_success "  ✅ dashboard.html encontrado"
                else
                    print_error "  ❌ dashboard.html NO encontrado (CRÍTICO)"
                    exit 1
                fi
                if [ -f "${INSTALL_DIR}/website/templates/login.html" ]; then
                    print_success "  ✅ login.html encontrado"
                else
                    print_error "  ❌ login.html NO encontrado (CRÍTICO)"
                    exit 1
                fi
            else
                print_error "Error: No se encontraron templates después de copiar"
                exit 1
            fi
        else
            print_error "Error: Directorio ${SCRIPT_DIR}/website/templates no existe"
            exit 1
        fi
        
        # Copiar archivos estáticos
        if [ -d "${SCRIPT_DIR}/website/static" ]; then
            print_info "Copiando archivos estáticos..."
            cp -r "${SCRIPT_DIR}/website/static/"* "${INSTALL_DIR}/website/static/" 2>/dev/null || true
            STATIC_COUNT=$(find "${INSTALL_DIR}/website/static" -type f 2>/dev/null | wc -l)
            if [ "$STATIC_COUNT" -gt 0 ]; then
                print_info "Archivos estáticos copiados: $STATIC_COUNT archivos"
            fi
        fi
    else
        print_error "Error: Directorio website no encontrado en ${SCRIPT_DIR}"
        exit 1
    fi
    
    # Configuración
    if [ ! -f "$CONFIG_FILE" ]; then
        if [ -f "${SCRIPT_DIR}/config.yaml.example" ]; then
            cp "${SCRIPT_DIR}/config.yaml.example" "$CONFIG_FILE"
            print_info "Archivo de configuración creado desde ejemplo"
        else
            # Crear config básico
            cat > "$CONFIG_FILE" <<EOF
server:
  host: "0.0.0.0"
  port: 8000
  debug: false
  read_timeout: 30
  write_timeout: 30

database:
  type: "sqlite"
  path: "${DATA_DIR}/hostberry.db"

security:
  jwt_secret: "$(openssl rand -hex 32)"
  token_expiry: 1440
  bcrypt_cost: 10
  rate_limit_rps: 10

lua:
  scripts_path: "${INSTALL_DIR}/lua/scripts"
  enabled: true
EOF
            print_info "Archivo de configuración creado con valores por defecto"
        fi
    else
        print_info "Archivo de configuración ya existe, no se sobrescribe"
    fi
    
    # Permisos
    chown -R "$USER_NAME:$GROUP_NAME" "$INSTALL_DIR"
    chown -R "$USER_NAME:$GROUP_NAME" "$LOG_DIR"
    chown -R "$USER_NAME:$GROUP_NAME" "$DATA_DIR"
    chmod 755 "$INSTALL_DIR"
    chmod 644 "$CONFIG_FILE"
    
    print_success "Archivos instalados"
}

# Compilar el proyecto
build_project() {
    print_info "Compilando HostBerry en ${INSTALL_DIR}..."
    
    # Verificar que estamos en el directorio correcto
    if [ ! -d "$INSTALL_DIR" ]; then
        print_error "Error: Directorio de instalación no existe: $INSTALL_DIR"
        exit 1
    fi
    
    # Cambiar al directorio de instalación
    cd "$INSTALL_DIR" || {
        print_error "Error: No se pudo cambiar al directorio $INSTALL_DIR"
        exit 1
    }
    
    print_info "Directorio de trabajo: $(pwd)"
    
    # Verificar que los templates están presentes antes de compilar
    if [ ! -d "${INSTALL_DIR}/website/templates" ]; then
        print_error "Error: Directorio de templates no encontrado: ${INSTALL_DIR}/website/templates"
        print_info "Verificando estructura del directorio..."
        ls -la "${INSTALL_DIR}/" 2>/dev/null || true
        exit 1
    fi
    
    TEMPLATE_COUNT=$(find "${INSTALL_DIR}/website/templates" -name "*.html" 2>/dev/null | wc -l)
    if [ "$TEMPLATE_COUNT" -eq 0 ]; then
        print_error "Error: No se encontraron archivos .html en ${INSTALL_DIR}/website/templates"
        print_info "Contenido del directorio:"
        ls -la "${INSTALL_DIR}/website/templates/" 2>/dev/null || true
        exit 1
    fi
    print_success "Verificado: $TEMPLATE_COUNT templates encontrados en ${INSTALL_DIR}/website/templates"
    
    # Verificar que main.go existe
    if [ ! -f "${INSTALL_DIR}/main.go" ]; then
        print_error "Error: main.go no encontrado en ${INSTALL_DIR}"
        print_info "Archivos .go encontrados:"
        ls -la "${INSTALL_DIR}"/*.go 2>/dev/null || true
        exit 1
    fi
    
    # Verificar que go.mod existe
    if [ ! -f "${INSTALL_DIR}/go.mod" ]; then
        print_error "Error: go.mod no encontrado en ${INSTALL_DIR}"
        exit 1
    fi
    
    # Asegurar que Go está en el PATH
    export PATH=$PATH:/usr/local/go/bin
    
    # Verificar que Go está disponible
    if ! command -v go &> /dev/null; then
        print_error "Error: Go no está instalado o no está en el PATH"
        exit 1
    fi
    
    print_info "Go versión: $(go version)"
    
    # Descargar dependencias
    print_info "Descargando dependencias de Go..."
    if ! go mod download; then
        print_error "Error al descargar dependencias"
        exit 1
    fi
    
    if ! go mod tidy; then
        print_warning "Advertencia: go mod tidy tuvo problemas, continuando..."
    fi
    
    # Verificar estructura antes de compilar
    print_info "Verificando estructura antes de compilar..."
    print_info "  - main.go: ${INSTALL_DIR}/main.go"
    if [ -f "${INSTALL_DIR}/main.go" ]; then
        print_success "  ✅ main.go encontrado"
    else
        print_error "  ❌ main.go NO encontrado"
        exit 1
    fi
    
    print_info "  - templates: ${INSTALL_DIR}/website/templates"
    if [ -d "${INSTALL_DIR}/website/templates" ]; then
        TEMPLATE_LIST=$(ls -1 "${INSTALL_DIR}/website/templates"/*.html 2>/dev/null | wc -l)
        print_success "  ✅ Directorio de templates encontrado con $TEMPLATE_LIST archivos"
        # Listar algunos templates para verificación
        print_info "  Templates encontrados:"
        ls -1 "${INSTALL_DIR}/website/templates"/*.html 2>/dev/null | head -5 | while read file; do
            print_info "    - $(basename "$file")"
        done
    else
        print_error "  ❌ Directorio de templates NO encontrado"
        exit 1
    fi
    
    # Compilar
    print_info "Compilando binario (los templates se embebarán automáticamente desde ${INSTALL_DIR}/website/templates)..."
    print_info "La directiva //go:embed buscará templates en: website/templates (relativo a main.go en ${INSTALL_DIR})"
    print_info "Directorio actual: $(pwd)"
    
    if CGO_ENABLED=1 go build -ldflags="-s -w" -o "${INSTALL_DIR}/hostberry" .; then
        if [ -f "${INSTALL_DIR}/hostberry" ]; then
            chmod +x "${INSTALL_DIR}/hostberry"
            chown "$USER_NAME:$GROUP_NAME" "${INSTALL_DIR}/hostberry"
            BINARY_SIZE=$(du -h "${INSTALL_DIR}/hostberry" | cut -f1)
            print_success "Compilación exitosa (templates embebidos en el binario)"
            print_info "Tamaño del binario: $BINARY_SIZE"
        else
            print_error "Error: El binario no se creó en ${INSTALL_DIR}/hostberry"
            exit 1
        fi
    else
        print_error "Error en la compilación"
        print_info "Revisa los errores de compilación arriba"
        exit 1
    fi
}

# Configurar firewall
configure_firewall() {
    print_info "Configurando firewall..."
    
    PORT=$(grep -E "^  port:" "$CONFIG_FILE" 2>/dev/null | awk '{print $2}' | tr -d '"' || echo "8000")
    
    # Verificar si ufw está instalado y activo
    if command -v ufw &> /dev/null; then
        if ufw status | grep -q "Status: active"; then
            print_info "Firewall UFW activo, permitiendo puerto $PORT..."
            ufw allow "$PORT/tcp" 2>/dev/null || true
            print_success "Puerto $PORT permitido en firewall"
        else
            print_info "Firewall UFW instalado pero no activo"
        fi
    elif command -v firewall-cmd &> /dev/null; then
        # Firewalld (CentOS/RHEL)
        print_info "Configurando firewalld..."
        firewall-cmd --permanent --add-port="$PORT/tcp" 2>/dev/null || true
        firewall-cmd --reload 2>/dev/null || true
        print_success "Puerto $PORT configurado en firewalld"
    else
        print_info "No se encontró firewall configurado (ufw o firewalld)"
        print_warning "Asegúrate de permitir el puerto $PORT en tu firewall manualmente"
    fi
}

# Crear base de datos inicial
create_database() {
    print_info "Preparando base de datos..."
    
    # Asegurar que el directorio de datos existe
    mkdir -p "$DATA_DIR"
    chown -R "$USER_NAME:$GROUP_NAME" "$DATA_DIR"
    chmod 755 "$DATA_DIR"
    
    # El archivo de BD se creará automáticamente al iniciar el servicio
    # pero creamos el directorio y verificamos permisos
    DB_FILE="${DATA_DIR}/hostberry.db"
    if [ -f "$DB_FILE" ]; then
        print_info "Base de datos existente encontrada: $DB_FILE"
        chown "$USER_NAME:$GROUP_NAME" "$DB_FILE"
        chmod 644 "$DB_FILE"
        print_warning "Si la BD tiene datos antiguos, el usuario admin puede no crearse automáticamente"
    else
        print_info "Base de datos se creará automáticamente al iniciar el servicio"
        print_info "El usuario admin se creará automáticamente si la BD está vacía"
    fi
    
    print_success "Directorio de base de datos preparado: $DATA_DIR"
}

# Configurar permisos y sudoers
configure_permissions() {
    print_info "Configurando permisos y sudoers..."
    
    # Crear directorio para scripts seguros
    SAFE_DIR="/usr/local/sbin/hostberry-safe"
    mkdir -p "$SAFE_DIR"
    
    # Crear script set-timezone
    cat > "$SAFE_DIR/set-timezone" <<EOF
#!/bin/bash
TZ="\$1"
if [ -z "\$TZ" ]; then echo "Timezone required"; exit 1; fi
if [ ! -f "/usr/share/zoneinfo/\$TZ" ]; then echo "Invalid timezone"; exit 1; fi
timedatectl set-timezone "\$TZ"
EOF
    chmod 750 "$SAFE_DIR/set-timezone"
    chown root:$GROUP_NAME "$SAFE_DIR/set-timezone"
    
    # Detectar rutas de comandos WiFi
    NMCLI_PATH=""
    RFKILL_PATH=""
    IFCONFIG_PATH=""
    IW_PATH=""
    IWCONFIG_PATH=""
    
    # Buscar nmcli
    if command -v nmcli &> /dev/null; then
        NMCLI_PATH=$(command -v nmcli)
    elif [ -f "/usr/bin/nmcli" ]; then
        NMCLI_PATH="/usr/bin/nmcli"
    fi
    
    # Buscar rfkill
    if command -v rfkill &> /dev/null; then
        RFKILL_PATH=$(command -v rfkill)
    elif [ -f "/usr/sbin/rfkill" ]; then
        RFKILL_PATH="/usr/sbin/rfkill"
    fi
    
    # Buscar ifconfig
    if command -v ifconfig &> /dev/null; then
        IFCONFIG_PATH=$(command -v ifconfig)
    elif [ -f "/sbin/ifconfig" ]; then
        IFCONFIG_PATH="/sbin/ifconfig"
    elif [ -f "/usr/sbin/ifconfig" ]; then
        IFCONFIG_PATH="/usr/sbin/ifconfig"
    fi
    
    # Buscar iw (para cambiar región WiFi)
    if command -v iw &> /dev/null; then
        IW_PATH=$(command -v iw)
    elif [ -f "/usr/sbin/iw" ]; then
        IW_PATH="/usr/sbin/iw"
    elif [ -f "/sbin/iw" ]; then
        IW_PATH="/sbin/iw"
    fi
    
    # Buscar iwconfig (para gestión WiFi)
    if command -v iwconfig &> /dev/null; then
        IWCONFIG_PATH=$(command -v iwconfig)
    elif [ -f "/usr/sbin/iwconfig" ]; then
        IWCONFIG_PATH="/usr/sbin/iwconfig"
    elif [ -f "/sbin/iwconfig" ]; then
        IWCONFIG_PATH="/sbin/iwconfig"
    fi
    
    # Detectar rutas de comandos de sistema
    REBOOT_PATH=""
    SHUTDOWN_PATH=""
    
    # Buscar reboot
    if command -v reboot &> /dev/null; then
        REBOOT_PATH=$(command -v reboot)
    elif [ -f "/usr/sbin/reboot" ]; then
        REBOOT_PATH="/usr/sbin/reboot"
    elif [ -f "/sbin/reboot" ]; then
        REBOOT_PATH="/sbin/reboot"
    fi
    
    # Buscar shutdown (ya detectado arriba, pero asegurarse)
    if command -v shutdown &> /dev/null; then
        SHUTDOWN_PATH=$(command -v shutdown)
    elif [ -f "/usr/sbin/shutdown" ]; then
        SHUTDOWN_PATH="/usr/sbin/shutdown"
    elif [ -f "/sbin/shutdown" ]; then
        SHUTDOWN_PATH="/sbin/shutdown"
    fi
    
    # Configurar sudoers con configuración para evitar logs en sistemas read-only
    cat > "/etc/sudoers.d/hostberry" <<EOF
# Permisos para HostBerry
# Deshabilitar logging de sudo para evitar errores en sistemas read-only
Defaults!ALL !logfile
Defaults!ALL !syslog
$USER_NAME ALL=(ALL) NOPASSWD: $SAFE_DIR/set-timezone
EOF
    
    # Agregar permisos para shutdown si está disponible
    if [ -n "$SHUTDOWN_PATH" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SHUTDOWN_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para shutdown: $SHUTDOWN_PATH"
    fi
    
    # Agregar permisos para reboot si está disponible
    if [ -n "$REBOOT_PATH" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $REBOOT_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para reboot: $REBOOT_PATH"
    fi
    
    # También agregar permisos para systemctl (más moderno y confiable)
    if command -v systemctl &> /dev/null; then
        SYSTEMCTL_PATH=$(command -v systemctl)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH reboot" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH poweroff" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH shutdown" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para systemctl: $SYSTEMCTL_PATH"
    fi
    
    # Agregar permisos WiFi si los comandos están disponibles
    if [ -n "$NMCLI_PATH" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $NMCLI_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para nmcli: $NMCLI_PATH"
    fi
    
    if [ -n "$RFKILL_PATH" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $RFKILL_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para rfkill: $RFKILL_PATH"
    fi
    
    if [ -n "$IFCONFIG_PATH" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $IFCONFIG_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para ifconfig: $IFCONFIG_PATH"
    fi
    
    if [ -n "$IW_PATH" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $IW_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para iw: $IW_PATH"
    fi
    
    if [ -n "$IWCONFIG_PATH" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $IWCONFIG_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para iwconfig: $IWCONFIG_PATH"
    fi
    
    # Agregar permisos para hostapd y systemctl hostapd
    if command -v hostapd &> /dev/null; then
        HOSTAPD_PATH=$(command -v hostapd)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $HOSTAPD_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para hostapd: $HOSTAPD_PATH"
    fi
    
    if command -v hostapd_cli &> /dev/null; then
        HOSTAPD_CLI_PATH=$(command -v hostapd_cli)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $HOSTAPD_CLI_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para hostapd_cli: $HOSTAPD_CLI_PATH"
    fi
    
    # Agregar permisos para systemctl con hostapd y dnsmasq
    if command -v systemctl &> /dev/null; then
        SYSTEMCTL_PATH=$(command -v systemctl)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH start hostapd" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH stop hostapd" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH restart hostapd" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH status hostapd" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH enable hostapd" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH disable hostapd" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH start dnsmasq" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH stop dnsmasq" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH restart dnsmasq" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH enable dnsmasq" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH disable dnsmasq" >> "/etc/sudoers.d/hostberry"
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH daemon-reload" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para systemctl hostapd y dnsmasq"
    fi
    
    # Agregar permisos para ip (configuración de interfaces de red)
    if command -v ip &> /dev/null; then
        IP_PATH=$(command -v ip)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $IP_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para ip: $IP_PATH"
    elif [ -f "/usr/sbin/ip" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: /usr/sbin/ip" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para ip: /usr/sbin/ip"
    elif [ -f "/sbin/ip" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: /sbin/ip" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para ip: /sbin/ip"
    fi
    
    # Agregar permisos para sysctl (habilitar IP forwarding)
    if command -v sysctl &> /dev/null; then
        SYSCTL_PATH=$(command -v sysctl)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $SYSCTL_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para sysctl: $SYSCTL_PATH"
    elif [ -f "/usr/sbin/sysctl" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: /usr/sbin/sysctl" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para sysctl: /usr/sbin/sysctl"
    elif [ -f "/sbin/sysctl" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: /sbin/sysctl" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para sysctl: /sbin/sysctl"
    fi
    
    # Agregar permisos para iptables (configuración de NAT)
    if command -v iptables &> /dev/null; then
        IPTABLES_PATH=$(command -v iptables)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $IPTABLES_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para iptables: $IPTABLES_PATH"
    elif [ -f "/usr/sbin/iptables" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: /usr/sbin/iptables" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para iptables: /usr/sbin/iptables"
    elif [ -f "/sbin/iptables" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: /sbin/iptables" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para iptables: /sbin/iptables"
    fi
    
    # Agregar permisos para comandos básicos necesarios para hostapd
    # cp (para copiar archivos de configuración)
    if command -v cp &> /dev/null; then
        CP_PATH=$(command -v cp)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $CP_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para cp: $CP_PATH"
    elif [ -f "/bin/cp" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: /bin/cp" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para cp: /bin/cp"
    fi
    
    # mkdir (para crear directorios de configuración)
    if command -v mkdir &> /dev/null; then
        MKDIR_PATH=$(command -v mkdir)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $MKDIR_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para mkdir: $MKDIR_PATH"
    elif [ -f "/bin/mkdir" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: /bin/mkdir" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para mkdir: /bin/mkdir"
    fi
    
    # chmod (para establecer permisos de archivos)
    if command -v chmod &> /dev/null; then
        CHMOD_PATH=$(command -v chmod)
        echo "$USER_NAME ALL=(ALL) NOPASSWD: $CHMOD_PATH" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para chmod: $CHMOD_PATH"
    elif [ -f "/bin/chmod" ]; then
        echo "$USER_NAME ALL=(ALL) NOPASSWD: /bin/chmod" >> "/etc/sudoers.d/hostberry"
        print_info "Permisos agregados para chmod: /bin/chmod"
    fi
    
    # Crear directorio /etc/hostapd con permisos correctos
    print_info "Creando directorio /etc/hostapd..."
    if [ ! -d "/etc/hostapd" ]; then
        mkdir -p /etc/hostapd
        chmod 755 /etc/hostapd
        print_success "Directorio /etc/hostapd creado con permisos 755"
    else
        chmod 755 /etc/hostapd 2>/dev/null || true
        print_info "Directorio /etc/hostapd ya existe, permisos verificados"
    fi
    
    # Crear también el directorio para systemd override si no existe
    if [ ! -d "/etc/systemd/system/hostapd.service.d" ]; then
        mkdir -p /etc/systemd/system/hostapd.service.d
        print_info "Directorio systemd override para hostapd creado"
    fi
    
    # Validar configuración de sudoers
    if visudo -c -f "/etc/sudoers.d/hostberry" 2>/dev/null; then
        chmod 440 "/etc/sudoers.d/hostberry"
        print_success "Permisos y sudoers configurados correctamente"
    else
        print_warning "Advertencia: Error al validar configuración de sudoers"
        print_info "Revisa manualmente: visudo -c -f /etc/sudoers.d/hostberry"
        chmod 440 "/etc/sudoers.d/hostberry"
    fi
}

# Crear configuración por defecto de HostAPD
create_hostapd_default_config() {
    print_info "Creando configuración por defecto de HostAPD..."
    
    # Valores por defecto
    HOSTAPD_INTERFACE="wlan0"
    HOSTAPD_SSID="hostberry-ap"
    HOSTAPD_PASSWORD="hostberry12"
    HOSTAPD_CHANNEL="6"
    HOSTAPD_GATEWAY="192.168.4.1"
    HOSTAPD_DHCP_START="192.168.4.2"
    HOSTAPD_DHCP_END="192.168.4.254"
    HOSTAPD_LEASE_TIME="12h"
    
    # Crear archivo de configuración de hostapd si no existe
    HOSTAPD_CONFIG="/etc/hostapd/hostapd.conf"
    if [ ! -f "$HOSTAPD_CONFIG" ]; then
        print_info "Creando archivo de configuración de HostAPD: $HOSTAPD_CONFIG"
        cat > "$HOSTAPD_CONFIG" <<EOF
interface=${HOSTAPD_INTERFACE}
driver=nl80211
ssid=${HOSTAPD_SSID}
hw_mode=g
channel=${HOSTAPD_CHANNEL}
wpa=2
wpa_passphrase=${HOSTAPD_PASSWORD}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF
        chmod 644 "$HOSTAPD_CONFIG"
        print_success "Archivo de configuración de HostAPD creado con valores por defecto"
        print_info "  - Interfaz: $HOSTAPD_INTERFACE"
        print_info "  - SSID: $HOSTAPD_SSID"
        print_info "  - Contraseña: $HOSTAPD_PASSWORD"
        print_info "  - Gateway: $HOSTAPD_GATEWAY"
    else
        print_info "Archivo de configuración de HostAPD ya existe, no se sobrescribe"
    fi
    
    # Crear archivo de configuración de dnsmasq si no existe o hacer backup
    DNSMASQ_CONFIG="/etc/dnsmasq.conf"
    if [ -f "$DNSMASQ_CONFIG" ]; then
        # Hacer backup si no existe
        if [ ! -f "${DNSMASQ_CONFIG}.backup" ]; then
            cp "$DNSMASQ_CONFIG" "${DNSMASQ_CONFIG}.backup"
            print_info "Backup de configuración de dnsmasq creado"
        fi
        # Verificar si ya tiene configuración de hostapd
        if grep -q "interface=${HOSTAPD_INTERFACE}" "$DNSMASQ_CONFIG" 2>/dev/null; then
            print_info "Configuración de dnsmasq para HostAPD ya existe"
        else
            print_info "Agregando configuración de dnsmasq para HostAPD..."
            cat >> "$DNSMASQ_CONFIG" <<EOF

# Configuración para HostAPD (agregada por HostBerry)
interface=${HOSTAPD_INTERFACE}
dhcp-range=${HOSTAPD_DHCP_START},${HOSTAPD_DHCP_END},255.255.255.0,${HOSTAPD_LEASE_TIME}
dhcp-option=3,${HOSTAPD_GATEWAY}
dhcp-option=6,${HOSTAPD_GATEWAY}
server=8.8.8.8
server=8.8.4.4
EOF
            print_success "Configuración de dnsmasq actualizada"
        fi
    else
        # Crear archivo de configuración de dnsmasq desde cero
        print_info "Creando archivo de configuración de dnsmasq..."
        cat > "$DNSMASQ_CONFIG" <<EOF
# Configuración de dnsmasq para HostAPD (creada por HostBerry)
interface=${HOSTAPD_INTERFACE}
dhcp-range=${HOSTAPD_DHCP_START},${HOSTAPD_DHCP_END},255.255.255.0,${HOSTAPD_LEASE_TIME}
dhcp-option=3,${HOSTAPD_GATEWAY}
dhcp-option=6,${HOSTAPD_GATEWAY}
server=8.8.8.8
server=8.8.4.4
EOF
        chmod 644 "$DNSMASQ_CONFIG"
        print_success "Archivo de configuración de dnsmasq creado"
    fi
    
    # Crear archivo de override de systemd para hostapd si no existe
    OVERRIDE_DIR="/etc/systemd/system/hostapd.service.d"
    OVERRIDE_FILE="${OVERRIDE_DIR}/override.conf"
    if [ ! -f "$OVERRIDE_FILE" ]; then
        print_info "Creando archivo de override de systemd para hostapd..."
        mkdir -p "$OVERRIDE_DIR"
        cat > "$OVERRIDE_FILE" <<EOF
[Service]
ExecStart=
ExecStart=/usr/sbin/hostapd -B ${HOSTAPD_CONFIG}
EOF
        chmod 644 "$OVERRIDE_FILE"
        print_success "Archivo de override de systemd creado"
    else
        print_info "Archivo de override de systemd ya existe"
    fi
    
    print_success "Configuración por defecto de HostAPD creada"
}

# Crear servicio systemd
create_systemd_service() {
    print_info "Creando servicio systemd..."
    
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=HostBerry - Sistema de Gestión de Red
After=network.target

[Service]
Type=simple
User=${USER_NAME}
Group=${GROUP_NAME}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/hostberry
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

# Seguridad
# NoNewPrivileges=true  # Deshabilitado para permitir sudo en comandos WiFi
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${INSTALL_DIR} ${LOG_DIR} ${DATA_DIR}

# Recursos
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
    
    # Recargar systemd
    systemctl daemon-reload
    
    print_success "Servicio systemd creado: $SERVICE_FILE"
}

# Iniciar servicio
start_service() {
    print_info "Iniciando servicio ${SERVICE_NAME}..."
    
    systemctl enable "${SERVICE_NAME}"
    systemctl start "${SERVICE_NAME}"
    systemctl restart "${SERVICE_NAME}"
    
    # Esperar un momento y verificar
    sleep 2
    
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        print_success "Servicio iniciado correctamente"
        print_info "Estado: $(systemctl is-active ${SERVICE_NAME})"
        
        # Esperar un poco más para que se cree el usuario admin
        sleep 2
        
        # Verificar si se creó el usuario admin
        print_info "Verificando creación de usuario admin..."
        if journalctl -u "${SERVICE_NAME}" -n 20 --no-pager | grep -q "Usuario admin creado exitosamente"; then
            print_success "Usuario admin creado correctamente"
        elif journalctl -u "${SERVICE_NAME}" -n 20 --no-pager | grep -q "Error creando usuario admin"; then
            print_warning "Hubo un error al crear el usuario admin"
            print_info "Revisa los logs: sudo journalctl -u ${SERVICE_NAME} -n 50"
        else
            print_info "Revisa los logs para ver el estado del usuario admin:"
            print_info "  sudo journalctl -u ${SERVICE_NAME} -n 50 | grep -i admin"
        fi
    else
        print_warning "El servicio no se inició correctamente"
        print_info "Revisa los logs con: journalctl -u ${SERVICE_NAME} -f"
    fi
}

# Mostrar información final
show_final_info() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    if [ "$MODE" = "update" ]; then
        echo -e "${GREEN}  HostBerry actualizado correctamente${NC}"
    elif [ "$MODE" = "uninstall" ]; then
        echo -e "${GREEN}  HostBerry desinstalado correctamente${NC}"
    else
        echo -e "${GREEN}  HostBerry instalado correctamente${NC}"
    fi
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}Ubicación de instalación:${NC} $INSTALL_DIR"
    echo -e "${BLUE}Archivo de configuración:${NC} $CONFIG_FILE"
    echo -e "${BLUE}Logs del servicio:${NC} journalctl -u ${SERVICE_NAME} -f"
    echo -e "${BLUE}Logs de aplicación:${NC} $LOG_DIR"
    echo ""
    echo -e "${YELLOW}Comandos útiles:${NC}"
    echo "  Iniciar:    sudo systemctl start ${SERVICE_NAME}"
    echo "  Detener:    sudo systemctl stop ${SERVICE_NAME}"
    echo "  Reiniciar:  sudo systemctl restart ${SERVICE_NAME}"
    echo "  Estado:     sudo systemctl status ${SERVICE_NAME}"
    echo "  Logs:       sudo journalctl -u ${SERVICE_NAME} -f"
    echo ""
    
    # Obtener IP del sistema
    IP=$(hostname -I | awk '{print $1}')
    PORT=$(grep -E "^  port:" "$CONFIG_FILE" | awk '{print $2}' | tr -d '"' || echo "8000")
    
    echo -e "${GREEN}Accede a la interfaz web:${NC}"
    if [ -n "$IP" ] && [ "$IP" != "127.0.0.1" ] && [ "$IP" != "" ]; then
        echo "  🌐 http://${IP}:${PORT}  (desde otros dispositivos en la red)"
    fi
    echo "  💻 http://localhost:${PORT}  (desde este dispositivo)"
    echo "  💻 http://127.0.0.1:${PORT}  (desde este dispositivo)"
    echo ""
    echo -e "${BLUE}Nota sobre acceso por red:${NC}"
    echo "  El servidor está configurado para escuchar en 0.0.0.0 (todas las interfaces)"
    echo "  Esto permite acceso desde cualquier dispositivo en tu red local usando la IP."
    if command -v ufw &> /dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
        if ufw status 2>/dev/null | grep -q "$PORT/tcp"; then
            echo "  ✅ Firewall UFW configurado - puerto $PORT permitido"
        else
            echo "  ⚠️  Firewall UFW activo - verifica que el puerto $PORT esté permitido"
        fi
    elif command -v firewall-cmd &> /dev/null; then
        echo "  ✅ Firewalld configurado - puerto $PORT permitido"
    else
        echo "  ℹ️  No se detectó firewall activo"
    fi
    echo ""
    echo -e "${YELLOW}Credenciales por defecto:${NC}"
    echo "  Usuario: admin"
    echo "  Contraseña: admin"
    echo -e "${RED}(Cambia la contraseña en el primer inicio)${NC}"
    echo ""
    echo -e "${BLUE}Nota sobre el usuario admin:${NC}"
    echo "  El usuario admin se crea automáticamente si la base de datos está vacía."
    echo "  Revisa los logs para verificar la creación:"
    echo "  sudo journalctl -u ${SERVICE_NAME} -n 50 | grep -i admin"
    echo ""
}

# Limpiar directorio temporal al finalizar
cleanup_temp() {
    if [ -d "$TEMP_CLONE_DIR" ] && [ "$TEMP_CLONE_DIR" != "$SCRIPT_DIR" ]; then
        print_info "Limpiando directorio temporal..."
        rm -rf "$TEMP_CLONE_DIR"
    fi
}

# Función principal
main() {
    local mode_label="INSTALACIÓN"
    if [ "$MODE" = "update" ]; then
        mode_label="ACTUALIZACIÓN"
    elif [ "$MODE" = "uninstall" ]; then
        mode_label="DESINSTALACIÓN"
    fi

    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  HostBerry - ${mode_label}${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    check_root
    detect_os
    install_git
    download_project
    clean_previous_installation
    install_dependencies
    create_user
    install_files
    build_project
    create_database
    configure_permissions
    create_hostapd_default_config
    configure_firewall
    create_systemd_service
    start_service
    cleanup_temp
    show_final_info
}

# Ejecutar función principal
main
