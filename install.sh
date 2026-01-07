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
    
    # LIMPIEZA DE LEGACY (PYTHON)
    # Eliminar archivos antiguos de la versión Python para evitar conflictos
    if [ -d "$INSTALL_DIR" ]; then
        print_info "Limpiando archivos antiguos de Python en $INSTALL_DIR..."
        rm -rf "$INSTALL_DIR/venv" "$INSTALL_DIR/api" "$INSTALL_DIR/core" "$INSTALL_DIR/models" "$INSTALL_DIR/system"
        rm -f "$INSTALL_DIR/main.py" "$INSTALL_DIR/requirements.txt" "$INSTALL_DIR/setup.sh"
    fi

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
    
    # Configurar sudoers
    cat > "/etc/sudoers.d/hostberry" <<EOF
# Permisos para HostBerry
$USER_NAME ALL=(ALL) NOPASSWD: $SAFE_DIR/set-timezone
$USER_NAME ALL=(ALL) NOPASSWD: /sbin/shutdown
$USER_NAME ALL=(ALL) NOPASSWD: /usr/sbin/shutdown
$USER_NAME ALL=(ALL) NOPASSWD: /usr/bin/shutdown
EOF
    chmod 440 "/etc/sudoers.d/hostberry"
    
    print_success "Permisos y sudoers configurados"
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
    configure_firewall
    create_systemd_service
    start_service
    show_final_info
}

# Ejecutar función principal
main
