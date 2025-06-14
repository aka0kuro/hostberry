#!/bin/bash

# ============================================
# Configuración global y constantes
# ============================================

# Colores para logs
readonly ANSI_GREEN='\033[0;32m'
readonly ANSI_YELLOW='\033[0;33m'
readonly ANSI_RED='\033[0;31m'
readonly ANSI_RESET='\033[0m'

# ============================================
# Configuración de rutas y constantes
# ============================================

# Directorios y rutas principales
readonly SSL_DIR="/etc/hostberry/ssl"
readonly SSL_HOSTNAME="hostberry.local"
readonly VENV_DIR="/opt/hostberry/venv"
readonly REQUIREMENTS="requirements.txt"
readonly SYSTEMD_SERVICE="hostberry-web.service"
readonly BACKUP_DIR="/opt/hostberry_backups"
readonly HOSTBERRY_DIR="/opt/hostberry"
readonly SCRIPTS_DIR="$HOSTBERRY_DIR/scripts"

# Dependencias del sistema agrupadas por funcionalidad
readonly DEPS=(
    # Python y herramientas básicas
    python3 python3-pip python3-venv git curl wget
    
    # Red y seguridad
    openvpn resolvconf dnsmasq hostapd isc-dhcp-server 
    iptables nftables ufw openssl
    
    # Herramientas adicionales
    libnss3-tools
)

# ============================================
# Funciones de utilidad
# ============================================

# Función para loguear mensajes con marca de tiempo
# Uso: log "color" "nivel" "mensaje"
log() {
    local color="$1"
    local level="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    shift 2
    echo -e "${color}[${timestamp}] [${level}] $*${ANSI_RESET}" >&2
}

# Función para ejecutar comandos con manejo de errores
run_cmd() {
    local cmd=("$@")
    log "$ANSI_YELLOW" "EXEC" "Ejecutando: ${cmd[*]}"
    
    if "${cmd[@]}"; then
        return 0
    else
        local status=$?
        log "$ANSI_RED" "ERROR" "Comando falló con estado $status: ${cmd[*]}"
        return $status
    fi
}

# Función para verificar si un comando está instalado
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Función para confirmar acción con el usuario
confirm() {
    local prompt="${1:-¿Continuar?} [y/N] "
    local response
    
    read -r -p "$prompt" response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# ============================================
# Manejo de errores
# ============================================

# Manejo centralizado de errores
handle_error() {
    local error_msg="$*"
    local error_line="${BASH_LINENO[0]}"
    local error_func="${FUNCNAME[1]:-main}"
    
    log "$ANSI_RED" "ERROR" "Error en $error_func (línea $error_line): $error_msg"
    
    # Intentar restaurar servicios si es necesario
    if [ -x "$SCRIPTS_DIR/restore_services.sh" ]; then
        log "$ANSI_YELLOW" "INFO" "Intentando restaurar servicios..."
        "$SCRIPTS_DIR/restore_services.sh" || true
    fi
    
    exit 1
}

# Configurar trap para manejar la salida del script
trap 'cleanup' EXIT INT TERM

# Función de limpieza al salir
cleanup() {
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        log "$ANSI_YELLOW" "WARNING" "Error detectado (código $exit_code), realizando limpieza..."
    fi
    
    # Restaurar estado de mensajes de dpkg si es necesario
    if [ -f /etc/apt/apt.conf.d/20auto-removals.bak ]; then
        mv /etc/apt/apt.conf.d/20auto-removals.bak /etc/apt/apt.conf.d/20auto-removals 2>/dev/null || true
    fi
    
    log "$ANSI_GREEN" "INFO" "Limpieza completada. Saliendo con código $exit_code"
    exit $exit_code
}



# Mostrar resumen de acciones
show_summary() {
    log "$ANSI_GREEN" "INFO" "Resumen de acciones"
    echo "[RESUMEN] Acciones solicitadas:"
    [ "$UPDATE_MODE" = true ] && echo "  - Actualización de HostBerry"
    [ "$GENERATE_CERT" = true ] && echo "  - Generar certificados SSL"
    [ "$CONFIGURE_NETWORK" = true ] && echo "  - Configurar red y firewall"
    echo
}

# ============================================
# Verificación del sistema
# ============================================

# Verificar compatibilidad del sistema
check_system_compatibility() {
    log "$ANSI_YELLOW" "INFO" "Verificando compatibilidad del sistema..."
    
    # Verificar sistema operativo
    if [ ! -f /etc/os-release ]; then
        handle_error "No se pudo determinar el sistema operativo"
    fi
    
    # Obtener información del sistema operativo
    # shellcheck source=/dev/null
    . /etc/os-release
    
    # Verificar si es una distribución compatible
    if [[ "$ID" != "debian" && "$ID" != "ubuntu" && "$ID_LIKE" != *"debian"* ]]; then
        handle_error "Este script solo es compatible con distribuciones basadas en Debian/Ubuntu"
    fi
    
    # Verificar arquitectura
    local arch
    arch=$(uname -m)
    if [[ ! " aarch64 armv7l x86_64 " == *" $arch "* ]]; then
        handle_error "Arquitectura no soportada: $arch"
    fi
    
    log "$ANSI_GREEN" "INFO" "Sistema compatible detectado: $PRETTY_NAME ($arch)"
    return 0
}

# ============================================
# Gestión de dependencias
# ============================================

# Verificar e instalar dependencias del sistema
install_system_deps() {
    log "$ANSI_YELLOW" "INFO" "Verificando e instalando dependencias del sistema..."
    
    # Verificar si estamos en un sistema basado en Debian/Ubuntu
    if ! command_exists apt-get; then
        handle_error "Este script solo es compatible con sistemas basados en Debian/Ubuntu"
    fi
    
    # Actualizar lista de paquetes
    log "$ANSI_YELLOW" "INFO" "Actualizando lista de paquetes..."
    if ! run_cmd apt-get update; then
        log "$ANSI_YELLOW" "WARNING" "No se pudo actualizar la lista de paquetes"
    fi
    
    # Instalar dependencias
    log "$ANSI_YELLOW" "INFO" "Instalando paquetes requeridos..."
    for dep in "${DEPS[@]}"; do
        if ! dpkg -l | grep -q "^ii[[:space:]]*$dep[[:space:]]"; then
            log "$ANSI_YELLOW" "INFO" "Instalando: $dep"
            if ! run_cmd apt-get install -y "$dep"; then
                log "$ANSI_YELLOW" "WARNING" "No se pudo instalar $dep"
            fi
        else
            log "$ANSI_GREEN" "INFO" "$dep ya está instalado"
        fi
    done
    
    log "$ANSI_GREEN" "INFO" "Dependencias del sistema verificadas e instaladas correctamente"
    return 0
}

# ============================================
# Configuración del entorno virtual
# ============================================

# Configurar el entorno virtual de Python
setup_python_venv() {
    log "$ANSI_YELLOW" "INFO" "Configurando entorno virtual de Python..."
    
    # Crear directorio principal si no existe
    if ! mkdir -p "$HOSTBERRY_DIR"; then
        handle_error "No se pudo crear el directorio: $HOSTBERRY_DIR"
    fi
    
    # Establecer permisos seguros
    run_cmd chmod 755 "$HOSTBERRY_DIR"
    run_cmd chown root:root "$HOSTBERRY_DIR"
    
    # Eliminar entorno virtual existente si existe
    if [ -d "$VENV_DIR" ]; then
        log "$ANSI_YELLOW" "INFO" "Eliminando entorno virtual existente..."
        rm -rf "$VENV_DIR" || handle_error "No se pudo eliminar el entorno virtual existente"
    fi
    
    # Crear nuevo entorno virtual
    log "$ANSI_YELLOW" "INFO" "Creando nuevo entorno virtual en $VENV_DIR..."
    if ! python3 -m venv "$VENV_DIR"; then
        handle_error "Error al crear el entorno virtual"
    fi
    
    # Activar el entorno virtual
    # shellcheck source=/dev/null
    if ! source "$VENV_DIR/bin/activate"; then
        handle_error "No se pudo activar el entorno virtual"
    fi
    
    # Actualizar pip
    log "$ANSI_YELLOW" "INFO" "Actualizando pip..."
    if ! pip install --upgrade pip; then
        handle_error "No se pudo actualizar pip"
    fi
    
    # Instalar dependencias básicas primero
    log "$ANSI_YELLOW" "INFO" "Instalando dependencias básicas..."
    if ! pip install --no-cache-dir "pytz==2024.1"; then
        handle_error "No se pudo instalar pytz"
    fi
    
    # Buscar archivo de requisitos
    local req_file="$REQUIREMENTS"
    [ ! -f "$req_file" ] && req_file="$HOSTBERRY_DIR/$REQUIREMENTS"
    [ ! -f "$req_file" ] && req_file="$(dirname "$0")/$REQUIREMENTS"
    
    if [ ! -f "$req_file" ]; then
        handle_error "No se encontró el archivo de requisitos en ninguna ruta esperada"
    fi
    
    # Instalar dependencias desde requirements.txt (excluyendo pytz que ya está instalado)
    log "$ANSI_YELLOW" "INFO" "Instalando dependencias desde $req_file..."
    if ! grep -v "^pytz" "$req_file" | pip install --upgrade -r /dev/stdin; then
        handle_error "Error al instalar las dependencias de Python"
    fi
    
    # Asegurar permisos finales
    run_cmd chmod -R 755 "$VENV_DIR"
    run_cmd chown -R root:root "$VENV_DIR"
    
    log "$ANSI_GREEN" "INFO" "Entorno virtual configurado correctamente en $VENV_DIR"
    return 0
}

# ============================================
# Funciones auxiliares
# ============================================

# Verificar si el script se está ejecutando como root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        handle_error "Este script debe ejecutarse como usuario root"
    fi
}

# Verificar si un comando está disponible
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Obtener la IP del sistema
get_system_ip() {
    local ip
    ip=$(hostname -I | awk '{print $1}' 2>/dev/null)
    if [ -z "$ip" ]; then
        ip=$(ip route get 1.1.1.1 | grep -oP 'src \K\S+' 2>/dev/null || echo "127.0.0.1")
    fi
    echo "$ip"
}

# Mostrar ayuda
show_help() {
    echo "Uso: $0 [OPCIONES]"
    echo
    echo "Opciones:"
    echo "  --help         Mostrar esta ayuda y salir"
    echo "  --install      Instalación limpia completa (recomendado)"
    echo "  --update       Actualizar la instalación de HostBerry"
    echo "  --cert         Generar certificados SSL con mkcert"
    echo "  --network      Configurar firewall y red para Raspberry Pi"
    echo "  --nginx        Configurar Nginx como proxy inverso"
    echo
    echo "Ejemplos:"
    echo "  sudo $0 --install         Instalación limpia recomendada"
    echo "  sudo $0 --update          Actualizar HostBerry"
    echo "  sudo $0 --cert            Generar certificados SSL"
    echo "  sudo $0 --network         Configurar red y firewall"
    echo "  sudo $0 --nginx           Configurar Nginx"
    echo "  sudo $0 --update --cert   Actualizar e instalar certificados"
    echo
    echo "Para más información, consulta la documentación de HostBerry."
    exit 0
}

# Procesar argumentos de línea de comandos
process_arguments() {
    local install_flag=0
    local update_flag=0
    local cert_flag=0
    local network_flag=0
    local nginx_flag=0
    
    if [ $# -eq 0 ]; then
        show_help
    fi
    
    while [ $# -gt 0 ]; do
        case "$1" in
            --help)
                show_help
                ;;
            --install)
                install_flag=1
                ;;
            --update)
                update_flag=1
                ;;
            --cert)
                cert_flag=1
                ;;
            --network)
                network_flag=1
                ;;
            --nginx)
                nginx_flag=1
                ;;
            *)
                log "$ANSI_RED" "ERROR" "Opción no válida: $1"
                show_help
                ;;
        esac
        shift
    done
    
    # Ejecutar acciones según las banderas
    if [ "$install_flag" -eq 1 ]; then
        perform_installation
    fi
    
    if [ "$update_flag" -eq 1 ]; then
        perform_update
    fi
    
    if [ "$cert_flag" -eq 1 ]; then
        setup_ssl_certificates
    fi
    
    if [ "$network_flag" -eq 1 ]; then
        configure_network
    fi
    
    if [ "$nginx_flag" -eq 1 ]; then
        configure_nginx
    fi
}

# Función para verificar requisitos previos de SSL
check_ssl_prerequisites() {
    # Verificar si ya existen certificados
    if [ -f "$SSL_DIR/hostberry.crt" ] && [ -f "$SSL_DIR/hostberry.key" ]; then
        log "$ANSI_YELLOW" "WARNING" "Ya existen certificados en $SSL_DIR"
        read -p "¿Desea sobrescribirlos? [s/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Ss]$ ]]; then
            log "$ANSI_GREEN" "INFO" "Usando certificados existentes"
            return 1
        fi
    fi
    return 0
}

# Función para generar certificados SSL
generate_ssl_cert() {
    log "$ANSI_YELLOW" "INFO" "Iniciando generación de certificados SSL..."
    
    # Verificar requisitos previos
    if ! check_ssl_prerequisites; then
        return 0
    }

    # Verificar si ya está instalado mkcert
    if ! command -v mkcert &> /dev/null; then
        log "$ANSI_YELLOW" "INFO" "Instalando mkcert..."
        
        # Instalar dependencias
        apt-get update
        apt-get install -y wget libnss3-tools

        # Descargar mkcert para Raspberry Pi 64-bit
        wget https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-arm64 -O /usr/local/bin/mkcert
        chmod +x /usr/local/bin/mkcert
    fi

    # Directorio para certificados
    mkdir -p "$SSL_DIR"
    cd "$SSL_DIR" || handle_error "No se pudo acceder al directorio SSL"
    
    # Obtener IP local
    local LOCAL_IP=$(hostname -I | awk '{print $1}')
    
    log "$ANSI_GREEN" "INFO" "Generando certificados para:"
    echo "  * $LOCAL_IP:5000"

    # Instalar mkcert para el sistema
    mkcert -install || handle_error "No se pudo instalar mkcert en el sistema"

    # Generar certificados
    mkcert -cert-file hostberry.crt -key-file hostberry.key \
        "hostberry.local" \
        "localhost" \
        "127.0.0.1" \
        "$LOCAL_IP" || handle_error "No se pudieron generar los certificados"

    # Verificar certificados
    if [ ! -f hostberry.crt ] || [ ! -f hostberry.key ]; then
        handle_error "No se generaron los certificados correctamente"
    fi

    # Establecer permisos
    chmod 600 hostberry.key
    chmod 644 hostberry.crt
    
    # Verificar la clave privada
    if ! openssl rsa -check -in hostberry.key > /dev/null 2>&1; then
        handle_error "La clave privada no es válida"
    fi
    
    # Verificar que la clave coincide con el certificado
    local CERT_HASH=$(openssl x509 -noout -modulus -in hostberry.crt | openssl md5)
    local KEY_HASH=$(openssl rsa -noout -modulus -in hostberry.key | openssl md5)
    
    if [ "$CERT_HASH" != "$KEY_HASH" ]; then
        handle_error "La clave privada no coincide con el certificado"
    fi
    
    log "$ANSI_GREEN" "INFO" "Certificados SSL generados exitosamente en $SSL_DIR"
    log "$ANSI_GREEN" "INFO" "Detalles del certificado:"
    openssl x509 -in hostberry.crt -text -noout | grep -E 'Subject:|Not Before:|Not After :' | sed 's/^/      /'
}

# Configurar red y firewall
configure_network() {
    log "$ANSI_GREEN" "INFO" "Configurando red y firewall..."
    
    # Instalar UFW si no está
    apt-get install -y ufw || handle_error "No se pudo instalar UFW"
    
    # Permitir puertos esenciales
    ufw allow 22/tcp   # SSH
    ufw allow 80/tcp   # HTTP
    ufw allow 443/tcp  # HTTPS
    ufw allow 5000/tcp # HostBerry Flask/Gunicorn

    
    # Habilitar reenvío de IP
    sed -i 's/^#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf
    sysctl -p || handle_error "No se pudo aplicar la configuración de sysctl"
    
    # Configurar NAT para compartir Internet
    local IFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
    iptables -t nat -A POSTROUTING -o "$IFACE" -j MASQUERADE
    
    # Guardar reglas
    mkdir -p /etc/iptables
    iptables-save > /etc/iptables/rules.v4 || handle_error "No se pudieron guardar las reglas de iptables"
    
    # Habilitar UFW
    ufw --force enable || handle_error "No se pudo habilitar UFW"
    log "$ANSI_GREEN" "INFO" "Red y firewall configurados correctamente."
}

# Función para restaurar backup de HostBerry
restore_hostberry_backup() {
    local BACKUP_DIR="/opt/hosteberry_backup"
    local HOSTBERRY_DIR="/opt/hostberry"
    local HOME_HOSTBERRY_DIR="/home/blag0rag/hostberry"

    # Validar existencia del directorio de backup
    if [ ! -d "$BACKUP_DIR" ]; then
        handle_error "El directorio de backup $BACKUP_DIR no existe"
    fi

    log "$ANSI_YELLOW" "INFO" "Iniciando restauración de backup de HostBerry"

    # Detener servicios antes de restaurar
    systemctl stop hostberry-web.service || log "$ANSI_RED" "WARN" "No se pudo detener el servicio web"

    # Restaurar archivos de la aplicación
    if [ -d "$BACKUP_DIR/hostberry" ]; then
        cp -r "$BACKUP_DIR/hostberry/"* "$HOSTBERRY_DIR/" || handle_error "Error al restaurar archivos de /opt/hostberry"
        log "$ANSI_GREEN" "INFO" "Archivos de /opt/hostberry restaurados"
    fi

    # Restaurar archivos de configuración del usuario
    if [ -d "$BACKUP_DIR/home/hostberry" ]; then
        cp -r "$BACKUP_DIR/home/hostberry/"* "$HOME_HOSTBERRY_DIR/" || handle_error "Error al restaurar archivos de home"
        log "$ANSI_GREEN" "INFO" "Archivos de home restaurados"
    fi

    # Restaurar permisos
    chown -R hostberry:hostberry "$HOSTBERRY_DIR" || log "$ANSI_RED" "WARN" "No se pudieron restaurar permisos en $HOSTBERRY_DIR"
    chown -R blag0rag:blag0rag "$HOME_HOSTBERRY_DIR" || log "$ANSI_RED" "WARN" "No se pudieron restaurar permisos en $HOME_HOSTBERRY_DIR"

    # Reiniciar servicios
    systemctl daemon-reload
    systemctl restart hostberry-web.service || handle_error "No se pudo reiniciar el servicio web"

    log "$ANSI_GREEN" "SUCCESS" "Backup de HostBerry restaurado exitosamente"
}

# Función para actualizar desde GitHub
update_from_github() {
    local backup_dir=""
    local current_branch=""
    
    log "$ANSI_YELLOW" "INFO" "Iniciando proceso de actualización..."
    
    # Verificar si git está instalado
    if ! command -v git &> /dev/null; then
        log "$ANSI_YELLOW" "INFO" "Instalando git..."
        apt-get install -y git || handle_error "No se pudo instalar git"
    fi
    
    # Si el directorio de git ya existe, actualizar en lugar de clonar
    if [ -d "$HOSTBERRY_DIR/.git" ]; then
        log "$ANSI_YELLOW" "INFO" "Actualizando repositorio existente..."
        current_branch=$(git -C "$HOSTBERRY_DIR" rev-parse --abbrev-ref HEAD)
        
        # Crear respaldo antes de actualizar
        backup_dir=$(create_backup)
        
        # Limpiar cambios locales
        git -C "$HOSTBERRY_DIR" reset --hard HEAD || handle_error "Error al limpiar cambios locales"
        
        # Obtener cambios remotos
        if ! git -C "$HOSTBERRY_DIR" fetch origin "$current_branch"; then
            log "$ANSI_RED" "ERROR" "No se pudieron obtener los cambios remotos"
            return 1
        fi
        
        # Aplicar cambios
        if ! git -C "$HOSTBERRY_DIR" reset --hard "origin/$current_branch"; then
            log "$ANSI_RED" "ERROR" "Error al aplicar los cambios"
            return 1
        fi
        
        # Limpiar archivos sin seguimiento
        git -C "$HOSTBERRY_DIR" clean -fd
        
        log "$ANSI_GREEN" "INFO" "Repositorio actualizado exitosamente"
    else
        # Si no existe el repositorio, clonar
        log "$ANSI_YELLOW" "INFO" "Clonando repositorio por primera vez..."
        
        # Crear directorio si no existe
        mkdir -p "$(dirname "$HOSTBERRY_DIR")"
        
        if ! git clone https://github.com/aka0kuro/hostberry.git "$HOSTBERRY_DIR"; then
            handle_error "No se pudo clonar el repositorio"
        fi
        
        current_branch=$(git -C "$HOSTBERRY_DIR" rev-parse --abbrev-ref HEAD)
        log "$ANSI_GREEN" "INFO" "Repositorio clonado exitosamente en la rama $current_branch"
    fi
    
    # Actualizar submódulos si existen
    if [ -f "$HOSTBERRY_DIR/.gitmodules" ]; then
        log "$ANSI_YELLOW" "INFO" "Actualizando submódulos..."
        (cd "$HOSTBERRY_DIR" && git submodule update --init --recursive) || \
            log "$ANSI_YELLOW" "WARN" "No se pudieron actualizar los submódulos"
    fi
    
    # Actualizar permisos
    log "$ANSI_YELLOW" "INFO" "Actualizando permisos..."
    chmod -R 755 "$HOSTBERRY_DIR"
    find "$HOSTBERRY_DIR" -type f -exec chmod 644 {} \;
    find "$HOSTBERRY_DIR/scripts" -type f -name "*.sh" -exec chmod +x {} \;
    
    # Asegurar que el directorio pertenece al usuario correcto
    chown -R root:root "$HOSTBERRY_DIR" || log "$ANSI_YELLOW" "WARN" "No se pudieron cambiar los permisos del directorio"
    
    log "$ANSI_GREEN" "INFO" "Actualización completada exitosamente"
    
    # Mostrar información de la versión actualizada
    local new_version=$(git -C "$HOSTBERRY_DIR" describe --tags 2>/dev/null || echo "desconocida")
    log "$ANSI_GREEN" "INFO" "Versión actual: $new_version"
    
    # Si se creó un respaldo, mostrar información
    if [ -n "$backup_dir" ]; then
        log "$ANSI_GREEN" "INFO" "Se creó un respaldo en: $backup_dir"
    fi
}

# Actualizar HostBerry
update_hostberry() {
    log "$ANSI_GREEN" "INFO" "Iniciando actualización de HostBerry..."
    
    # Verificar si hay actualizaciones disponibles
    if ! check_for_updates; then
        log "$ANSI_YELLOW" "INFO" "No hay actualizaciones disponibles."
        return 0
    fi
    
    # Preguntar confirmación al usuario
    read -p "¿Desea proceder con la actualización? [s/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[SsYy]$ ]]; then
        log "$ANSI_YELLOW" "INFO" "Actualización cancelada por el usuario"
        return 0
    fi
    
    # Detener servicios si están en ejecución
    if systemctl is-active --quiet hostberry-web.service; then
        log "$ANSI_YELLOW" "INFO" "Deteniendo servicio hostberry-web..."
        systemctl stop hostberry-web.service || handle_error "No se pudo detener el servicio hostberry-web"
    fi
    
    # Crear backup si existe instalación previa
    if [ -d "$HOSTBERRY_DIR" ]; then
        local backup_dir=$(create_backup)
        log "$ANSI_GREEN" "INFO" "Respaldo creado en: $backup_dir"
        
        # Crear directorio de backup si no existe
        mkdir -p "$BACKUP_DIR"
        
        # Crear backup con marca de tiempo
        local BACKUP_PATH="$BACKUP_DIR/hostberry_backup_$(date +%Y%m%d_%H%M%S)"
        cp -r "$HOSTBERRY_DIR" "$BACKUP_PATH" || handle_error "No se pudo crear el backup"
        log "$ANSI_GREEN" "INFO" "Backup creado en: $BACKUP_PATH"
        
        # Mantener solo los 2 backups más recientes
        log "$ANSI_YELLOW" "INFO" "Limpiando backups antiguos..."
        cd "$BACKUP_DIR" || handle_error "No se pudo acceder al directorio de backups"
        ls -t | tail -n +3 | xargs -r rm -rf
        log "$ANSI_GREEN" "INFO" "Se mantienen solo los 2 backups más recientes"
    fi
    
    # Actualizar desde GitHub
    update_from_github
    
    # Crear directorio de logs y archivos necesarios
    log "$ANSI_YELLOW" "INFO" "Creando directorio de logs..."
    mkdir -p "$HOSTBERRY_DIR/logs"
    chmod 755 "$HOSTBERRY_DIR/logs"
    touch "$HOSTBERRY_DIR/logs/access.log" "$HOSTBERRY_DIR/logs/error.log"
    
    chmod 644 "$HOSTBERRY_DIR/logs/access.log" "$HOSTBERRY_DIR/logs/error.log"
    chown -R root:root "$HOSTBERRY_DIR/logs"
    log "$ANSI_GREEN" "INFO" "Directorio de logs creado y configurado"
    
    # Actualizar dependencias y configuración
    check_and_install_deps
    setup_venv
    
    # Actualizar permisos de scripts
    if [ -d "$SCRIPTS_DIR" ]; then
        log "$ANSI_YELLOW" "INFO" "Actualizando permisos de scripts..."
        find "$SCRIPTS_DIR" -name "*.sh" -type f -exec chmod +x {} \; || handle_error "No se pudieron actualizar los permisos de los scripts"
        log "$ANSI_GREEN" "INFO" "Permisos de scripts actualizados en $SCRIPTS_DIR"
    else
        log "$ANSI_YELLOW" "WARN" "Directorio de scripts no encontrado en $SCRIPTS_DIR"
    fi
    
    # Actualizar servicio systemd
    if [ -f "$HOSTBERRY_DIR/$SYSTEMD_SERVICE" ]; then
        log "$ANSI_YELLOW" "INFO" "Copiando archivo de servicio systemd..."
        cp "$HOSTBERRY_DIR/$SYSTEMD_SERVICE" /etc/systemd/system/ || handle_error "No se pudo actualizar el archivo de servicio"
        systemctl daemon-reload
        systemctl enable hostberry-web.service
        log "$ANSI_GREEN" "INFO" "Servicio systemd actualizado y habilitado"
    else
        log "$ANSI_YELLOW" "WARN" "Archivo de servicio no encontrado en $HOSTBERRY_DIR/$SYSTEMD_SERVICE"
        log "$ANSI_YELLOW" "INFO" "Creando archivo de servicio systemd..."
        
        # Crear archivo de configuración de Gunicorn
        log "$ANSI_YELLOW" "INFO" "Creando configuración de Gunicorn..."
        cat > "$HOSTBERRY_DIR/gunicorn.conf.py" << 'EOF'
import multiprocessing
import os

# Configuración básica
bind = "0.0.0.0:80"
workers = 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
backlog = 2048
graceful_timeout = 30

# Configuración de logs
accesslog = "/opt/hostberry/logs/access.log"
errorlog = "/opt/hostberry/logs/error.log"
loglevel = "debug"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'
capture_output = True
enable_stdio_inheritance = True

# Configuración de seguridad
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Configuración de procesos
preload_app = True
daemon = False
pidfile = "/opt/hostberry/gunicorn.pid"
umask = 0o022
user = "root"
group = "root"

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_fork(server, worker):
    server.log.info("Pre-fork worker (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")

def worker_exit(server, worker):
    server.log.info("Worker exited (pid: %s)", worker.pid)
EOF
        
        # Crear archivo de servicio systemd
        log "$ANSI_YELLOW" "INFO" "Creando archivo de servicio systemd..."
        cat > /etc/systemd/system/hostberry-web.service << 'EOF'
[Unit]
Description=HostBerry Web Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/hostberry
ExecStart=/opt/hostberry/venv/bin/gunicorn \
    --workers 1 \
    --bind 0.0.0.0:80 \
    --access-logfile /opt/hostberry/logs/access.log \
    --error-logfile /opt/hostberry/logs/error.log \
    --log-level debug \
    --access-logformat '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s' \
    --capture-output \
    --enable-stdio-inheritance \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --worker-class sync \
    --worker-connections 1000 \
    --backlog 2048 \
    --graceful-timeout 30 \
    app.wsgi:app
Restart=always
RestartSec=10
Environment="FLASK_ENV=production"
Environment="PYTHONUNBUFFERED=1"
Environment="GUNICORN_CMD_ARGS=--config /opt/hostberry/gunicorn.conf.py"

[Install]
WantedBy=multi-user.target
EOF
        
        # Asegurar que gunicorn esté instalado
        if ! "$VENV_DIR/bin/pip" show gunicorn > /dev/null 2>&1; then
            log "$ANSI_YELLOW" "INFO" "Instalando Gunicorn..."
            "$VENV_DIR/bin/pip" install gunicorn || handle_error "No se pudo instalar Gunicorn"
        fi
        
        systemctl daemon-reload
        systemctl enable hostberry-web.service
        log "$ANSI_GREEN" "INFO" "Servicio systemd creado y habilitado"
    fi
    
    # Generar certificados si se solicita
    if [ "$GENERATE_CERT" = true ]; then
        generate_ssl_cert
    fi
    
    # Reiniciar servicio
    if systemctl is-active --quiet hostberry-web.service; then
        systemctl restart hostberry-web.service || handle_error "No se pudo reiniciar el servicio"
        log "$ANSI_GREEN" "INFO" "Servicio hostberry-web reiniciado"
    else
        log "$ANSI_YELLOW" "WARN" "Servicio hostberry-web no está activo, omitiendo reinicio"
    fi
    
    log "$ANSI_GREEN" "INFO" "Actualización de HostBerry completada."
}

# Función para mostrar información de acceso
show_access_info() {
    log "$ANSI_YELLOW" "INFO" "Obteniendo información de acceso..."
    
    # Obtener la IP local
    local LOCAL_IP=$(hostname -I | awk '{print $1}')
    
    log "$ANSI_GREEN" "INFO" "HostBerry está listo para usar"
    log "$ANSI_YELLOW" "INFO" "Puedes acceder a HostBerry desde cualquier dispositivo en la red usando:"
    log "$ANSI_YELLOW" "INFO" "http://${LOCAL_IP}"
    log "$ANSI_YELLOW" "INFO" ""
    log "$ANSI_YELLOW" "INFO" "Asegúrate de que el dispositivo esté en la misma red que este servidor"
}

# Función para verificar y configurar el firewall
configure_firewall() {
    log "$ANSI_YELLOW" "INFO" "Configurando firewall..."
    
    # Asegurarse de que UFW está instalado
    if ! command -v ufw &> /dev/null; then
        apt-get install -y ufw || handle_error "No se pudo instalar UFW"
    fi
    
    # Permitir puertos esenciales
    ufw allow 22/tcp   # SSH
    ufw allow 80/tcp   # HTTP
    ufw allow 443/tcp  # HTTPS
    
    # Habilitar UFW si no está activo
    if ! ufw status | grep -q "Status: active"; then
        ufw --force enable || handle_error "No se pudo habilitar UFW"
    fi
    
    log "$ANSI_GREEN" "INFO" "Firewall configurado correctamente"
}

# Función para verificar actualizaciones disponibles sin autenticación
check_for_updates() {
    log "$ANSI_YELLOW" "INFO" "Verificando actualizaciones disponibles..."
    
    # Si no hay directorio de git, no se puede verificar actualizaciones
    if [ ! -d "$HOSTBERRY_DIR/.git" ]; then
        log "$ANSI_YELLOW" "WARN" "No se encontró repositorio git. No se puede verificar actualizaciones."
        return 1
    fi
    
    # Obtener información del repositorio remoto
    local remote_url=$(git -C "$HOSTBERRY_DIR" config --get remote.origin.url)
    if [ -z "$remote_url" ]; then
        log "$ANSI_YELLOW" "WARN" "No se pudo determinar la URL del repositorio remoto."
        return 1
    fi
    
    # Crear un directorio temporal para clonar
    local temp_dir=$(mktemp -d)
    local current_branch=$(git -C "$HOSTBERRY_DIR" rev-parse --abbrev-ref HEAD)
    local current_commit=$(git -C "$HOSTBERRY_DIR" rev-parse HEAD)
    
    # Clonar el repositorio en modo shallow para ahorrar ancho de banda
    log "$ANSI_YELLOW" "INFO" "Obteniendo información de actualizaciones..."
    if git clone --depth 1 --single-branch --branch "$current_branch" "$remote_url" "$temp_dir" 2>/dev/null; then
        # Obtener el último commit remoto
        local remote_commit=$(git -C "$temp_dir" rev-parse HEAD)
        
        # Comparar commits
        if [ "$current_commit" = "$remote_commit" ]; then
            log "$ANSI_GREEN" "INFO" "No hay actualizaciones disponibles. Ya estás en la última versión."
            rm -rf "$temp_dir"
            return 1
        else
            # Obtener los cambios entre commits
            log "$ANSI_YELLOW" "INFO" "¡Hay actualizaciones disponibles!"
            log "$ANSI_YELLOW" "INFO" "Cambios pendientes de aplicar:"
            
            # Usar git log para mostrar los cambios (limitado a los últimos 5 para no saturar)
            (cd "$HOSTBERRY_DIR" && git fetch --depth 5 && \
             git log --oneline --graph --decorate --abbrev-commit "$current_commit..origin/$current_branch" 2>/dev/null || \
             echo "No se pudieron obtener los detalles de los cambios")
            
            rm -rf "$temp_dir"
            return 0
        fi
    else
        log "$ANSI_YELLOW" "WARN" "No se pudo verificar actualizaciones. Verifica tu conexión a internet."
        [ -d "$temp_dir" ] && rm -rf "$temp_dir"
        return 1
    fi
}

# Función para crear un respaldo antes de actualizar
create_backup() {
    local backup_dir="$BACKUP_DIR/$(date +%Y%m%d_%H%M%S)"
    log "$ANSI_YELLOW" "INFO" "Creando respaldo en $backup_dir..."
    
    mkdir -p "$backup_dir"
    
    # Copiar directorio de la aplicación
    cp -r "$HOSTBERRY_DIR" "$backup_dir/" || handle_error "No se pudo crear el respaldo"
    
    # Copiar archivos de configuración importantes
    if [ -d "/etc/hostberry" ]; then
        cp -r /etc/hostberry "$backup_dir/etc/" || log "$ANSI_YELLOW" "WARN" "No se pudo respaldar /etc/hostberry"
    fi
    
    # Crear un archivo de metadatos del respaldo
    {
        echo "Fecha: $(date)"
        echo "Versión actual: $(git -C "$HOSTBERRY_DIR" describe --tags 2>/dev/null || echo "Desconocida")"
        echo "Commit: $(git -C "$HOSTBERRY_DIR" rev-parse HEAD 2>/dev/null || echo "Desconocido")"
        echo "Sistema: $(uname -a)"
    } > "$backup_dir/backup_info.txt"
    
    log "$ANSI_GREEN" "INFO" "Respaldo creado exitosamente en $backup_dir"
    echo "$backup_dir"  # Devolver la ruta del respaldo
}

# Función para verificar y reiniciar el servicio
verify_service() {
    log "$ANSI_YELLOW" "INFO" "Verificando servicio web..."
    
    # Reiniciar el servicio
    systemctl daemon-reload
    systemctl restart hostberry-web.service || handle_error "No se pudo reiniciar el servicio"
    
    # Esperar a que el servicio esté activo
    sleep 5
    
    # Verificar estado
    if ! systemctl is-active --quiet hostberry-web.service; then
        log "$ANSI_RED" "ERROR" "El servicio no está activo. Revisando logs..."
        journalctl -u hostberry-web.service -n 50 --no-pager
        handle_error "El servicio no se pudo iniciar correctamente"
    fi
    
    # Verificar que el puerto está escuchando
    if ! netstat -tulpn | grep -q ":80.*LISTEN"; then
        log "$ANSI_RED" "ERROR" "El puerto 80 no está escuchando"
        handle_error "El servicio no está escuchando en el puerto 80"
    fi
    
    log "$ANSI_GREEN" "INFO" "Servicio web verificado y funcionando correctamente"
}

# Procesar argumentos y ejecutar acciones
main() {
    # Configurar localización para evitar problemas con caracteres especiales
    export LC_ALL=C.UTF-8
    export LANG=C.UTF-8
    
    # Procesar argumentos
    local GENERATE_CERT=false
    local CONFIGURE_NETWORK=false
    local UPDATE_MODE=false
    
    # Verificar compatibilidad del sistema
    check_system_compatibility
    
    # Crear directorio de scripts si no existe
    mkdir -p "$SCRIPTS_DIR"
    INSTALL_MODE=false

    for arg in "$@"; do
        case $arg in
            --help)
                SHOW_HELP=true
                ;;
            --update)
                UPDATE_MODE=true
                ;;
            --cert)
                GENERATE_CERT=true
                ;;
            --network)
                CONFIGURE_NETWORK=true
                ;;
            --install)
                INSTALL_MODE=true
                ;;
            *)
                log "$ANSI_RED" "ERROR" "Opción desconocida: $arg"
                SHOW_HELP=true
                ;;
        esac
    done

    if [ "$SHOW_HELP" = true ]; then
        show_help
    fi

    if [ "$INSTALL_MODE" = true ]; then
        update_hostberry
        configure_network
        generate_ssl_cert
        show_access_info
        exit 0
    fi

    if [ "$SHOW_HELP" = true ] || [ $# -eq 0 ]; then
        show_help
    fi

    check_root
    show_summary

    # Crear directorio principal si no existe
    mkdir -p "$HOSTBERRY_DIR"
    chmod 755 "$HOSTBERRY_DIR"
    chown root:root "$HOSTBERRY_DIR"

    # Crear directorio de logs y archivos necesarios
    log "$ANSI_YELLOW" "INFO" "Creando directorio de logs..."
    mkdir -p "$HOSTBERRY_DIR/logs"
    chmod 755 "$HOSTBERRY_DIR/logs"
    touch "$HOSTBERRY_DIR/logs/access.log" "$HOSTBERRY_DIR/logs/error.log"
    chmod 644 "$HOSTBERRY_DIR/logs/access.log" "$HOSTBERRY_DIR/logs/error.log"
    chown -R root:root "$HOSTBERRY_DIR/logs"
    log "$ANSI_GREEN" "INFO" "Directorio de logs creado y configurado"

    # Crear directorio de scripts si no existe
    mkdir -p "$SCRIPTS_DIR"
    chmod 755 "$SCRIPTS_DIR"
    chown root:root "$SCRIPTS_DIR"

    if [ "$UPDATE_MODE" = true ]; then
        update_hostberry
        configure_firewall
        verify_service
        show_access_info
    fi
    
    if [ "$GENERATE_CERT" = true ]; then
        generate_ssl_cert
    fi
    
    if [ "$CONFIGURE_NETWORK" = true ]; then
        configure_network
    fi
    
    # Si no se pasó ningún argumento relevante, realizar instalación inicial
    if [ "$UPDATE_MODE" = false ] && [ "$GENERATE_CERT" = false ] && [ "$CONFIGURE_NETWORK" = false ]; then
        log "$ANSI_YELLOW" "INFO" "Iniciando instalación inicial..."
        check_and_install_deps
        setup_venv
        configure_firewall
        verify_service
        show_access_info
        
        # Crear archivo de configuración de Gunicorn
        log "$ANSI_YELLOW" "INFO" "Creando configuración de Gunicorn..."
        cat > "$HOSTBERRY_DIR/gunicorn.conf.py" << 'EOF'
import multiprocessing
import os

# Configuración básica
bind = "0.0.0.0:80"
workers = 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
backlog = 2048
graceful_timeout = 30

# Configuración de logs
accesslog = "/opt/hostberry/logs/access.log"
errorlog = "/opt/hostberry/logs/error.log"
loglevel = "debug"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'
capture_output = True
enable_stdio_inheritance = True

# Configuración de seguridad
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Configuración de procesos
preload_app = True
daemon = False
pidfile = "/opt/hostberry/gunicorn.pid"
umask = 0o022
user = "root"
group = "root"

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_fork(server, worker):
    server.log.info("Pre-fork worker (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")
    fi
}

# ============================================
# Punto de entrada principal
# ============================================

# Función principal
main() {
    # Verificar si se está ejecutando como root
    check_root
    
    # Procesar argumentos de línea de comandos
    process_arguments "$@"
    
    # Mostrar resumen de acciones
    show_summary
    
    log "$ANSI_GREEN" "INFO" "Script completado exitosamente"
    exit 0
}

# Ejecutar la función principal
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi

# Activar modo estricto
set -euo pipefail
main "$@"
