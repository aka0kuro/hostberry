#!/bin/bash

# Activar modo estricto
set -euo pipefail

# Configuración global y constantes
readonly ANSI_GREEN='\033[0;32m'
readonly ANSI_YELLOW='\033[0;33m'
readonly ANSI_RED='\033[0;31m'
readonly ANSI_RESET='\033[0m'

# Directorios y rutas principales
readonly SSL_DIR="/etc/hostberry/ssl"
readonly SSL_HOSTNAME="hostberry.local"
readonly VENV_DIR="/opt/hostberry/venv"
readonly REQUIREMENTS="requirements.txt"
readonly SYSTEMD_SERVICE="hostberry-web.service"
readonly BACKUP_DIR="/opt/hostberry_backups"
readonly HOSTBERRY_DIR="/opt/hostberry"
readonly SCRIPTS_DIR="$HOSTBERRY_DIR/scripts"

# Función para loguear mensajes con marca de tiempo
log() {
    local color="$1"
    local level="$2"
    shift 2
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${color}[${timestamp}] [${level}] ${message}${ANSI_RESET}"
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
    local message="${1:-¿Estás seguro?}"
    local default="${2:-y}"
    
    if [ "$default" = "y" ]; then
        prompt="[Y/n]"
    else
        prompt="[y/N]"
    fi
    
    while true; do
        read -r -p "$message $prompt " response
        case "$response" in
            [Yy]*) return 0 ;;
            [Nn]*) return 1 ;;
            *) 
                if [ -z "$response" ]; then
                    [ "$default" = "y" ] && return 0 || return 1
                fi
                ;;
        esac
    done
}

# Función para manejo de errores
handle_error() {
    local error_msg="$*"
    local error_line="${BASH_LINENO[0]}"
    local error_func="${FUNCNAME[1]:-main}"
    
    log "$ANSI_RED" "ERROR" "Error en $error_func (línea $error_line): $error_msg"
    
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
        log "$ANSI_RED" "ERROR" "El script terminó con error (código: $exit_code)"
    else
        log "$ANSI_GREEN" "INFO" "Script completado exitosamente"
    fi
    
    # Cualquier otra limpieza necesaria
    
    exit $exit_code
}

# Mostrar resumen de acciones
show_summary() {
    log "$ANSI_YELLOW" "INFO" "=== Resumen de acciones ==="
    log "$ANSI_YELLOW" "INFO" "Directorio principal: $HOSTBERRY_DIR"
    log "$ANSI_YELLOW" "INFO" "Directorio de logs: $HOSTBERRY_DIR/logs"
    log "$ANSI_YELLOW" "INFO" "Directorio de scripts: $SCRIPTS_DIR"
    log "$ANSI_YELLOW" "INFO" "Directorio de certificados SSL: $SSL_DIR"
    log "$ANSI_YELLOW" "INFO" "Servicio systemd: $SYSTEMD_SERVICE"
    log "$ANSI_YELLOW" "INFO" "=========================="
}

# Verificar compatibilidad del sistema
check_system_compatibility() {
    log "$ANSI_YELLOW" "INFO" "Verificando compatibilidad del sistema..."
    
    # Verificar sistema operativo
    if [ ! -f /etc/os-release ]; then
        log "$ANSI_RED" "ERROR" "No se pudo determinar el sistema operativo"
        return 1
    fi
    
    # Verificar arquitectura
    local arch
    arch=$(uname -m)
    if [ "$arch" != "armv7l" ] && [ "$arch" != "aarch64" ]; then
        log "$ANSI_YELLOW" "WARN" "Este script está diseñado para Raspberry Pi (ARM). Arquitectura detectada: $arch"
        if ! confirm "¿Desea continuar de todos modos?"; then
            exit 1
        fi
    fi
    
    # Verificar versión de Python
    if ! command_exists python3; then
        log "$ANSI_RED" "ERROR" "Python 3 no está instalado"
        return 1
    fi
    
    log "$ANSI_GREEN" "INFO" "Sistema compatible verificado correctamente"
    return 0
}

# Instalar dependencias del sistema
install_system_deps() {
    log "$ANSI_YELLOW" "INFO" "Instalando dependencias del sistema..."
    
    # Actualizar lista de paquetes
    run_cmd apt-get update
    
    # Instalar paquetes necesarios
    run_cmd apt-get install -y python3-pip python3-venv python3-dev \
        git curl wget \
        openvpn resolvconf dnsmasq hostapd isc-dhcp-server \
        iptables nftables ufw openssl \
        libnss3-tools
    
    log "$ANSI_GREEN" "INFO" "Dependencias del sistema instaladas correctamente"
}

# Configurar entorno virtual de Python
setup_python_venv() {
    log "$ANSI_YELLOW" "INFO" "Configurando entorno virtual de Python..."
    
    # Crear directorio si no existe
    mkdir -p "$HOSTBERRY_DIR"
    
    # Crear entorno virtual
    if [ ! -d "$VENV_DIR" ]; then
        run_cmd python3 -m venv "$VENV_DIR"
        log "$ANSI_GREEN" "INFO" "Entorno virtual creado en $VENV_DIR"
    else
        log "$ANSI_YELLOW" "INFO" "El entorno virtual ya existe en $VENV_DIR"
    fi
    
    # Instalar dependencias de Python
    if [ -f "$HOSTBERRY_DIR/$REQUIREMENTS" ]; then
        log "$ANSI_YELLOW" "INFO" "Instalando dependencias de Python..."
        run_cmd "$VENV_DIR/bin/pip" install --upgrade pip
        run_cmd "$VENV_DIR/bin/pip" install -r "$HOSTBERRY_DIR/$REQUIREMENTS"
    else
        log "$ANSI_YELLOW" "WARN" "No se encontró el archivo $REQUIREMENTS"
    fi
    
    log "$ANSI_GREEN" "INFO" "Entorno virtual configurado correctamente"
}

# Verificar si se está ejecutando como root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        log "$ANSI_RED" "ERROR" "Este script debe ejecutarse como root"
        exit 1
    fi
}

# Obtener la IP del sistema
get_system_ip() {
    local ip
    ip=$(hostname -I | awk '{print $1}')
    if [ -z "$ip" ]; then
        ip="127.0.0.1"
    fi
    echo "$ip"
}

# Mostrar ayuda
show_help() {
    echo "Uso: $0 [OPCIONES]"
    echo "Configura e instala HostBerry en el sistema"
    echo ""
    echo "Opciones:"
    echo "  --install     Instalar HostBerry"
    echo "  --update      Actualizar instalación existente"
    echo "  --cert        Generar certificados SSL"
    echo "  --network     Configurar red"
    echo "  --nginx       Configurar Nginx"
    echo "  --help        Mostrar esta ayuda y salir"
    echo ""
    exit 0
}

# Procesar argumentos de línea de comandos
process_arguments() {
    local install_flag=0
    local update_flag=0
    local cert_flag=0
    local network_flag=0
    local nginx_flag=0
    local show_help_flag=0
    
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    while [ $# -gt 0 ]; do
        case "$1" in
            --help)
                show_help_flag=1
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
                show_help_flag=1
                ;;
        esac
        shift
    done
    
    if [ "$show_help_flag" -eq 1 ]; then
        show_help
    fi
    
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
    
    # Si no se especificó ninguna acción, mostrar ayuda
    if [ "$install_flag" -eq 0 ] && [ "$update_flag" -eq 0 ] && \
       [ "$cert_flag" -eq 0 ] && [ "$network_flag" -eq 0 ] && \
       [ "$nginx_flag" -eq 0 ]; then
        show_help
        exit 1
    fi
}

# Función para verificar requisitos previos de SSL
check_ssl_prerequisites() {
    log "$ANSI_YELLOW" "INFO" "Verificando requisitos previos para SSL..."
    
    # Verificar si mkcert está instalado
    if ! command_exists mkcert; then
        log "$ANSI_RED" "ERROR" "mkcert no está instalado. Por favor, instálelo primero."
        log "$ANSI_YELLOW" "INFO" "Puede instalarlo con: sudo apt install libnss3-tools mkcert"
        return 1
    fi
    
    log "$ANSI_GREEN" "INFO" "Requisitos previos para SSL verificados correctamente"
    return 0
}

# Función para generar certificados SSL
generate_ssl_cert() {
    log "$ANSI_YELLOW" "INFO" "Generando certificados SSL..."
    
    # Verificar requisitos previos
    if ! check_ssl_prerequisites; then
        return 1
    fi
    
    # Crear directorio de certificados si no existe
    mkdir -p "$SSL_DIR"
    
    # Verificar si ya existen certificados
    if [ -f "$SSL_DIR/$SSL_HOSTNAME.pem" ] && [ -f "$SSL_DIR/$SSL_HOSTNAME-key.pem" ]; then
        log "$ANSI_YELLOW" "INFO" "Los certificados SSL ya existen en $SSL_DIR/"
        if ! confirm "¿Desea sobrescribir los certificados existentes?"; then
            return 0
        fi
    fi
    
    # Generar certificados autofirmados
    log "$ANSI_YELLOW" "INFO" "Generando certificados autofirmados para $SSL_HOSTNAME..."
    
    # Instalar CA local
    mkcert -install
    
    # Generar certificado para el hostname
    mkcert "$SSL_HOSTNAME" "*.$SSL_HOSTNAME" "localhost" 127.0.0.1 ::1
    
    # Mover certificados al directorio de SSL
    mv "$SSL_HOSTNAME.pem" "$SSL_HOSTNAME-key.pem" "$SSL_DIR/"
    
    # Asegurar permisos
    chmod 600 "$SSL_DIR/$SSL_HOSTNAME-key.pem"
    chmod 644 "$SSL_DIR/$SSL_HOSTNAME.pem"
    chown -R root:root "$SSL_DIR"
    
    log "$ANSI_GREEN" "INFO" "Certificados SSL generados correctamente en $SSL_DIR/"
    return 0
}

# Configurar red y firewall
configure_network() {
    log "$ANSI_YELLOW" "INFO" "Configurando red y firewall..."
    
    # Habilitar IP forwarding
    echo 1 > /proc/sys/net/ipv4/ip_forward
    echo "net.ipv4.ip_forward=1" | tee -a /etc/sysctl.conf
    
    # Configurar NAT
    run_cmd iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    run_cmd iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    run_cmd iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT
    
    # Asegurarse de que el directorio de iptables exista
    if [ ! -d "/etc/iptables" ]; then
        log "$ANSI_YELLOW" "INFO" "Creando directorio /etc/iptables/..."
        run_cmd mkdir -p /etc/iptables
    fi
    
    # Guardar reglas de iptables
    log "$ANSI_YELLOW" "INFO" "Guardando reglas de iptables..."
    run_cmd iptables-save > /etc/iptables/rules.v4 || {
        log "$ANSI_RED" "ERROR" "No se pudo guardar las reglas de iptables"
        log "$ANSI_YELLOW" "INFO" "Intentando con sudo..."
        sudo iptables-save | sudo tee /etc/iptables/rules.v4 >/dev/null || {
            log "$ANSI_RED" "ERROR" "No se pudo guardar las reglas de iptables con sudo"
            return 1
        }
    }
    
    # Hacer que las reglas persistan después del reinicio
    if command -v netfilter-persistent >/dev/null 2>&1; then
        log "$ANSI_YELLOW" "INFO" "Haciendo que las reglas de iptables persistan..."
        run_cmd netfilter-persistent save
    fi
    
    log "$ANSI_GREEN" "INFO" "Red y firewall configurados correctamente"
    return 0
}

# Función para restaurar backup de HostBerry
restore_hostberry_backup() {
    log "$ANSI_YELLOW" "INFO" "Iniciando restauración de respaldo..."
    
    # Verificar si existe el directorio de backups
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
        log "$ANSI_RED" "ERROR" "No se encontraron archivos de respaldo en $BACKUP_DIR"
        return 1
    fi
    
    # Mostrar lista de backups disponibles
    log "$ANSI_YELLOW" "INFO" "Respaldos disponibles en $BACKUP_DIR:"
    local i=1
    local backups=()
    
    while IFS= read -r -d $'\0' file; do
        backups+=("$file")
        echo "  $i) $(basename "$file")"
        ((i++))
    done < <(find "$BACKUP_DIR" -type f -name "hostberry_*.tar.gz" -print0 | sort -zr)
    
    if [ ${#backups[@]} -eq 0 ]; then
        log "$ANSI_RED" "ERROR" "No se encontraron archivos de respaldo válidos"
        return 1
    fi
    
    # Solicitar selección de backup
    local selection=0
    while [[ ! "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt ${#backups[@]} ]; do
        read -rp "Seleccione el número del respaldo a restaurar (1-${#backups[@]}): " selection
    done
    
    local selected_backup="${backups[$((selection-1))]}"
    
    # Confirmar restauración
    if ! confirm "¿Está seguro de restaurar desde $(basename "$selected_backup")?" "n"; then
        log "$ANSI_YELLOW" "INFO" "Restauración cancelada"
        return 0
    fi
    
    # Detener servicios si están en ejecución
    if systemctl is-active --quiet hostberry; then
        run_cmd systemctl stop hostberry
    fi
    
    # Extraer backup
    log "$ANSI_YELLOW" "INFO" "Restaurando desde $(basename "$selected_backup")..."
    run_cmd tar -xzf "$selected_backup" -C / --strip-components=1
    
    # Asegurar permisos
    chown -R root:root "$HOSTBERRY_DIR"
    chmod -R 755 "$HOSTBERRY_DIR"
    
    # Reiniciar servicios
    run_cmd systemctl daemon-reload
    run_cmd systemctl restart hostberry
    
    log "$ANSI_GREEN" "INFO" "Restauración completada exitosamente"
    return 0
}

# Función para actualizar desde GitHub
update_from_github() {
    local temp_dir
    temp_dir=$(mktemp -d)
    
    log "$ANSI_YELLOW" "INFO" "Actualizando desde GitHub..."
    
    # Clonar el repositorio en un directorio temporal
    run_cmd git clone --depth 1 "https://github.com/aka0kuro/hostberry.git" "$temp_dir"
    
    # Copiar archivos, excluyendo directorios específicos
    log "$ANSI_YELLOW" "INFO" "Copiando archivos..."
    rsync -av --exclude='.git' --exclude='venv' --exclude='__pycache__' "$temp_dir/" "$HOSTBERRY_DIR/"
    
    # Limpiar
    rm -rf "$temp_dir"
    
    # Actualizar dependencias de Python
    if [ -f "$HOSTBERRY_DIR/requirements.txt" ]; then
        log "$ANSI_YELLOW" "INFO" "Actualizando dependencias de Python..."
        "$VENV_DIR/bin/pip" install --upgrade -r "$HOSTBERRY_DIR/requirements.txt"
    fi
    
    # Asegurar permisos
    chown -R root:root "$HOSTBERRY_DIR"
    find "$HOSTBERRY_DIR" -type d -exec chmod 755 {} \;
    find "$HOSTBERRY_DIR" -type f -exec chmod 644 {} \;
    chmod +x "$HOSTBERRY_DIR/setup.sh"
    
    log "$ANSI_GREEN" "INFO" "Actualización completada exitosamente"
    return 0
}

# Actualizar HostBerry
update_hostberry() {
    log "$ANSI_YELLOW" "INFO" "Iniciando actualización de HostBerry..."
    
    # Verificar si hay actualizaciones disponibles
    if ! check_for_updates; then
        log "$ANSI_YELLOW" "INFO" "No hay actualizaciones disponibles"
        return 0
    fi
    
    # Confirmar actualización
    if ! confirm "¿Desea continuar con la actualización?" "y"; then
        log "$ANSI_YELLOW" "INFO" "Actualización cancelada"
        return 0
    fi
    
    # Crear respaldo antes de actualizar
    if ! create_backup; then
        log "$ANSI_RED" "ERROR" "No se pudo crear un respaldo. Abortando actualización"
        return 1
    fi
    
    # Actualizar desde GitHub
    if ! update_from_github; then
        log "$ANSI_RED" "ERROR" "Error al actualizar desde GitHub"
        return 1
    fi
    
    # Reiniciar servicios
    log "$ANSI_YELLOW" "INFO" "Reiniciando servicios..."
    if systemctl is-active --quiet hostberry; then
        run_cmd systemctl restart hostberry
    fi
    
    log "$ANSI_GREEN" "INFO" "HostBerry ha sido actualizado exitosamente"
    return 0
}

# Función para mostrar información de acceso
show_access_info() {
    local ip
    ip=$(get_system_ip)
    
    log "$ANSI_GREEN" "INFO" "=========================================="
    log "$ANSI_GREEN" "INFO" "HostBerry instalado correctamente"
    log "$ANSI_GREEN" "INFO" "Accede a la interfaz web en: http://$ip"
    log "$ANSI_GREEN" "INFO" "O usa: http://$(hostname).local"
    log "$ANSI_GREEN" "INFO" "=========================================="
}

# Función para verificar y configurar el firewall
configure_firewall() {
    log "$ANSI_YELLOW" "INFO" "Configurando firewall..."
    
    # Habilitar UFW si no está activo
    if ! ufw status | grep -q "Status: active"; then
        log "$ANSI_YELLOW" "INFO" "Habilitando UFW..."
        run_cmd ufw --force enable
    fi
    
    # Permitir puertos necesarios
    run_cmd ufw allow 22/tcp    # SSH
    run_cmd ufw allow 80/tcp    # HTTP
    run_cmd ufw allow 443/tcp   # HTTPS
    
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
    local remote_url
    remote_url=$(git -C "$HOSTBERRY_DIR" config --get remote.origin.url)
    if [ -z "$remote_url" ]; then
        log "$ANSI_YELLOW" "WARN" "No se pudo determinar la URL del repositorio remoto."
        return 1
    fi
    
    # Crear un directorio temporal para clonar
    local temp_dir
    temp_dir=$(mktemp -d)
    local current_branch
    current_branch=$(git -C "$HOSTBERRY_DIR" rev-parse --abbrev-ref HEAD)
    local current_commit
    current_commit=$(git -C "$HOSTBERRY_DIR" rev-parse HEAD)
    
    # Clonar el repositorio en modo shallow para ahorrar ancho de banda
    log "$ANSI_YELLOW" "INFO" "Obteniendo información de actualizaciones..."
    if git clone --depth 1 --single-branch --branch "$current_branch" "$remote_url" "$temp_dir" 2>/dev/null; then
        # Obtener el último commit remoto
        local remote_commit
        remote_commit=$(git -C "$temp_dir" rev-parse HEAD)
        
        # Comparar commits
        if [ "$current_commit" != "$remote_commit" ]; then
            log "$ANSI_YELLOW" "INFO" "Hay actualizaciones disponibles!"
            log "$ANSI_YELLOW" "INFO" "Versión actual: $current_commit"
            log "$ANSI_YELLOW" "INFO" "Versión más reciente: $remote_commit"
            
            # Obtener mensaje del último commit
            local commit_message
            commit_message=$(git -C "$temp_dir" log -1 --pretty=%B)
            log "$ANSI_YELLOW" "INFO" "Últimos cambios:\n$commit_message"
            
            rm -rf "$temp_dir"
            return 0
        else
            log "$ANSI_GREEN" "INFO" "Ya tienes la última versión."
            rm -rf "$temp_dir"
            return 1
        fi
    else
        log "$ANSI_RED" "ERROR" "No se pudo verificar actualizaciones. Verifica tu conexión a Internet."
        rm -rf "$temp_dir"
        return 1
    fi
}

# Función para crear un respaldo antes de actualizar
create_backup() {
    log "$ANSI_YELLOW" "INFO" "Creando respaldo de la instalación actual..."
    
    # Crear directorio de respaldos si no existe
    mkdir -p "$BACKUP_DIR"
    
    # Nombre del archivo de respaldo
    local backup_file
    backup_file="${BACKUP_DIR}/hostberry_$(date +%Y%m%d_%H%M%S).tar.gz"
    
    # Crear respaldo
    log "$ANSI_YELLOW" "INFO" "Creando respaldo en $backup_file..."
    
    # Excluir directorios grandes y archivos temporales
    if tar --exclude='venv' --exclude='__pycache__' --exclude='.git' -czf "$backup_file" -C / "${HOSTBERRY_DIR#/}" 2>/dev/null; then
        log "$ANSI_GREEN" "INFO" "Respaldo creado exitosamente: $backup_file"
        return 0
    else
        log "$ANSI_RED" "ERROR" "Error al crear el respaldo"
        return 1
    fi
}

# Función para verificar y reiniciar el servicio
verify_service() {
    log "$ANSI_YELLOW" "INFO" "Verificando servicio web..."
    
    # Verificar si el servicio está activo
    if ! systemctl is-active --quiet hostberry; then
        log "$ANSI_YELLOW" "WARN" "El servicio no está activo. Iniciando..."
        systemctl start hostberry || {
            log "$ANSI_RED" "ERROR" "No se pudo iniciar el servicio"
            return 1
        }
    fi
    
    # Verificar que el puerto esté escuchando
    if ! command -v netstat >/dev/null || ! netstat -tulpn 2>/dev/null | grep -q ":80.*LISTEN"; then
        echo "[INFO] El puerto 80 no está en uso o no se pudo verificar"
    else
        echo "[INFO] Servicio web en puerto 80 verificado"
    fi
}

# Función para realizar la instalación completa
perform_installation() {
    log "$ANSI_YELLOW" "INFO" "Iniciando instalación de HostBerry..."
    
    # Verificar compatibilidad del sistema
    check_system_compatibility
    
    # Instalar dependencias del sistema
    install_system_deps
    
    # Configurar entorno virtual de Python
    setup_python_venv
    
    # Configurar Gunicorn
    configure_gunicorn
    
    # Configurar red y firewall
    configure_network
    
    # Configurar certificados SSL
    setup_ssl_certificates
    
    # Verificar y reiniciar el servicio
    verify_service
    
    # Mostrar información de acceso
    show_access_info
    
    log "$ANSI_GREEN" "INFO" "Instalación completada exitosamente"
}

# Función para instalar mkcert
install_mkcert() {
    if ! command -v mkcert &> /dev/null; then
        log "$ANSI_YELLOW" "INFO" "Instalando mkcert..."
        
        # Instalar dependencias necesarias
        if [ -f /etc/debian_version ] || [ -f /etc/raspbian_version ]; then
            # Para Debian/Ubuntu/Raspberry Pi OS
            run_cmd sudo apt-get update
            run_cmd sudo apt-get install -y libnss3-tools wget
        elif [ -f /etc/redhat-release ]; then
            # Para RHEL/CentOS
            run_cmd sudo yum install -y nss-tools wget
        fi
        
        # Instalar mkcert
        if ! command -v mkcert &> /dev/null; then
            # Determinar la arquitectura
            ARCHITECTURE=$(uname -m)
            MKCERT_URL=""
            
            case "$ARCHITECTURE" in
                "x86_64")
                    MKCERT_URL="https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-linux-amd64"
                    ;;
                "armv7l" | "armv8l" | "aarch64")
                    # Para Raspberry Pi 3/4 (ARM 32/64 bits)
                    MKCERT_URL="https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-linux-arm"
                    ;;
                *)
                    log "$ANSI_RED" "ERROR" "Arquitectura no soportada: $ARCHITECTURE"
                    return 1
                    ;;
            esac
            
            log "$ANSI_YELLOW" "INFO" "Descargando mkcert para $ARCHITECTURE..."
            run_cmd sudo wget -O /usr/local/bin/mkcert "$MKCERT_URL"
            run_cmd sudo chmod +x /usr/local/bin/mkcert
        fi
    fi
    
    # Crear CA local si no existe
    if [ ! -f "$HOME/.local/share/mkcert/rootCA.pem" ]; then
        log "$ANSI_YELLOW" "INFO" "Creando CA local..."
        # Usar sudo para instalar la CA en el almacén del sistema
        sudo mkcert -install
    fi
}

# Función para configurar certificados SSL locales con mkcert
setup_ssl_certificates() {
    log "$ANSI_YELLOW" "INFO" "Configurando certificados SSL locales con mkcert..."
    
    # Instalar mkcert si no está instalado
    install_mkcert
    
    # Obtener el nombre de dominio
    local domain
    domain=$(get_domain_name || echo "localhost")
    
    # Directorio para los certificados
    local certs_dir="/etc/ssl/certs"
    local key_dir="/etc/ssl/private"
    
    # Crear directorios si no existen
    run_cmd sudo mkdir -p "$certs_dir" "$key_dir"
    
    # Generar certificados
    log "$ANSI_YELLOW" "INFO" "Generando certificados para $domain..."
    
    # Generar certificado para el dominio y localhost
    if mkcert -cert-file /tmp/cert.pem -key-file /tmp/key.pem "$domain" "localhost" 127.0.0.1 ::1; then
        # Mover certificados a ubicaciones estándar
        run_cmd sudo mv /tmp/cert.pem "$certs_dir/$domain.crt"
        run_cmd sudo mv /tmp/key.pem "$key_dir/$domain.key"
        run_cmd sudo chmod 644 "$certs_dir/$domain.crt"
        run_cmd sudo chmod 600 "$key_dir/$domain.key"
        
        log "$ANSI_GREEN" "INFO" "Certificados generados exitosamente en:"
        log "$ANSI_GREEN" "INFO" "  - Certificado: $certs_dir/$domain.crt"
        log "$ANSI_GREEN" "INFO" "  - Clave privada: $key_dir/$domain.key"
        
        # Configurar Nginx para usar los certificados
        configure_nginx_ssl "$domain" "$certs_dir/$domain.crt" "$key_dir/$domain.key"
        
        return 0
    else
        log "$ANSI_RED" "ERROR" "Error al generar los certificados con mkcert"
        return 1
    fi
}

# Función para configurar Nginx con SSL
configure_nginx_ssl() {
    local domain=$1
    local cert_path=$2
    local key_path=$3
    
    log "$ANSI_YELLOW" "INFO" "Configurando Nginx para usar los certificados SSL..."
    
    # Crear configuración de Nginx para SSL
    local nginx_conf="/etc/nginx/sites-available/$domain"
    
    # Crear configuración SSL
    cat << EOF | sudo tee "$nginx_conf" > /dev/null
server {
    listen 80;
    listen [::]:80;
    server_name $domain;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $domain;
    
    ssl_certificate $cert_path;
    ssl_certificate_key $key_path;
    
    # Configuración SSL recomendada
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Configuración de la aplicación
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    # Habilitar el sitio
    if [ -f "/etc/nginx/sites-enabled/$domain" ]; then
        run_cmd sudo rm "/etc/nginx/sites-enabled/$domain"
    fi
    run_cmd sudo ln -s "$nginx_conf" "/etc/nginx/sites-enabled/"
    
    # Verificar configuración de Nginx
    if sudo nginx -t; then
        log "$ANSI_GREEN" "INFO" "Configuración de Nginx verificada correctamente"
        # Reiniciar Nginx
        if systemctl is-active --quiet nginx; then
            run_cmd sudo systemctl restart nginx
        else
            run_cmd sudo systemctl start nginx
        fi
    else
        log "$ANSI_RED" "ERROR" "Error en la configuración de Nginx"
        return 1
    fi
}

# Función para configurar Gunicorn
configure_gunicorn() {
    echo "[INFO] Creando configuración de Gunicorn..."
    
    # Crear directorio de configuración si no existe
    mkdir -p "$HOSTBERRY_DIR/conf"
    
    # Crear archivo de configuración
    cat > "$HOSTBERRY_DIR/conf/gunicorn.conf.py" << 'EOF'
import multiprocessing
import os

# Configuración básica
bind = "0.0.0.0:80"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 120
keepalive = 5
max_requests = 1000
loglevel = "info"
accesslog = "/var/log/hostberry/access.log"
errorlog = "/var/log/hostberry/error.log"
backlog = 2048
graceful_timeout = 30

# Configuración de logs
accesslog = "/opt/hostberry/logs/access.log"
errorlog = "/opt/hostberry/logs/error.log"
loglevel = "info"

# Configuración de seguridad
user = "root"
group = "root"

# Configuración de rendimiento
preload_app = True
reuse_port = True

# Configuración de timeouts
timeout = 300
keepalive = 5
EOF
    
    log "$ANSI_GREEN" "INFO" "Configuración de Gunicorn creada en $HOSTBERRY_DIR/conf/gunicorn.conf.py"
}

# Función principal
main() {
    # Verificar si se está ejecutando como root
    check_root
    
    # Procesar argumentos de línea de comandos
    process_arguments "$@"
    
    # Mostrar resumen de acciones
    show_summary
    
    # Crear directorios necesarios
    mkdir -p "$HOSTBERRY_DIR"
    mkdir -p "$HOSTBERRY_DIR/logs"
    mkdir -p "$HOSTBERRY_DIR/conf"
    
    # Configurar Gunicorn
    configure_gunicorn
    
    log "$ANSI_GREEN" "INFO" "Configuración completada exitosamente"
    exit 0
}

# Ejecutar la función principal
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
