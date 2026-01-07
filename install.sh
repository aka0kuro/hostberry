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
MODE="install"  # install o update

# Procesar argumentos
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --update) MODE="update" ;;
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
    DEPS="wget curl build-essential"
    
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
    
    # Instalar otras dependencias
    apt-get install -y $DEPS
    
    print_success "Dependencias instaladas"
}

# Descargar proyecto de GitHub si es necesario
download_project() {
    # Verificar si estamos en un repositorio git válido con todos los archivos necesarios
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
    
    # Configurar sudoers
    cat > "/etc/sudoers.d/hostberry" <<EOF
# Permisos para HostBerry
$USER_NAME ALL=(ALL) NOPASSWD: $SAFE_DIR/set-timezone
$USER_NAME ALL=(ALL) NOPASSWD: /sbin/shutdown
$USER_NAME ALL=(ALL) NOPASSWD: /usr/sbin/shutdown
$USER_NAME ALL=(ALL) NOPASSWD: /usr/bin/shutdown
EOF
    
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

# Limpiar directorio temporal al finalizar
cleanup_temp() {
    if [ -d "$TEMP_CLONE_DIR" ] && [ "$TEMP_CLONE_DIR" != "$SCRIPT_DIR" ]; then
        print_info "Limpiando directorio temporal..."
        rm -rf "$TEMP_CLONE_DIR"
    fi
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
    install_git
    download_project
    clean_previous_installation
    install_dependencies
    create_user
    install_files
    build_project
    create_database
    configure_permissions
    configure_firewall
    create_systemd_service
    start_service
    cleanup_temp
    show_final_info
}

# Ejecutar función principal
main
