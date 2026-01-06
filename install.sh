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
SERVICE_NAME="hostberry"
USER_NAME="hostberry"
GROUP_NAME="hostberry"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CONFIG_FILE="${INSTALL_DIR}/config.yaml"
LOG_DIR="/var/log/hostberry"
DATA_DIR="${INSTALL_DIR}/data"

# Modo de operación
MODE="install"  # install o update

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

# Instalar dependencias del sistema
install_dependencies() {
    print_info "Instalando dependencias del sistema..."
    
    # Actualizar lista de paquetes
    apt-get update -qq
    
    # Instalar dependencias básicas
    DEPS="wget curl git build-essential"
    
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
        cd /tmp
        wget -q "${GO_URL}" -O "${GO_TAR}"
        
        print_info "Instalando Go..."
        rm -rf /usr/local/go
        tar -C /usr/local -xzf "${GO_TAR}"
        rm "${GO_TAR}"
        
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
    
    # Instalar otras dependencias
    apt-get install -y $DEPS
    
    print_success "Dependencias instaladas"
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
    
    # Crear directorios
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "${INSTALL_DIR}/lua/scripts"
    mkdir -p "${INSTALL_DIR}/locales"
    mkdir -p "${INSTALL_DIR}/website/static"
    mkdir -p "${INSTALL_DIR}/website/templates"
    
    # Obtener ruta del script actual
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
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
        cp -r "${SCRIPT_DIR}/website/"* "${INSTALL_DIR}/website/" 2>/dev/null || true
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
    print_info "Compilando HostBerry..."
    
    cd "$INSTALL_DIR"
    
    # Asegurar que Go está en el PATH
    export PATH=$PATH:/usr/local/go/bin
    
    # Descargar dependencias
    print_info "Descargando dependencias de Go..."
    /usr/local/go/bin/go mod download 2>/dev/null || go mod download
    /usr/local/go/bin/go mod tidy 2>/dev/null || go mod tidy
    
    # Compilar
    print_info "Compilando binario..."
    CGO_ENABLED=1 /usr/local/go/bin/go build -ldflags="-s -w" -o "${INSTALL_DIR}/hostberry" . 2>/dev/null || \
    CGO_ENABLED=1 go build -ldflags="-s -w" -o "${INSTALL_DIR}/hostberry" .
    
    if [ -f "${INSTALL_DIR}/hostberry" ]; then
        chmod +x "${INSTALL_DIR}/hostberry"
        chown "$USER_NAME:$GROUP_NAME" "${INSTALL_DIR}/hostberry"
        print_success "Compilación exitosa"
    else
        print_error "Error en la compilación"
        exit 1
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
    else
        print_info "Base de datos se creará automáticamente al iniciar el servicio"
    fi
    
    print_success "Directorio de base de datos preparado"
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
NoNewPrivileges=true
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
    echo -e "${GREEN}  HostBerry instalado correctamente${NC}"
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
    echo "  http://${IP}:${PORT}"
    echo "  http://localhost:${PORT}"
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

# Función principal
main() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Instalador de HostBerry${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    check_root
    detect_os
    install_dependencies
    create_user
    install_files
    build_project
    create_database
    create_systemd_service
    start_service
    show_final_info
}

# Ejecutar función principal
main
