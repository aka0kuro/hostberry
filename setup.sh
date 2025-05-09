#!/bin/bash

# Colores para logs
ANSI_GREEN='\033[0;32m'
ANSI_YELLOW='\033[0;33m'
ANSI_RED='\033[0;31m'
ANSI_RESET='\033[0m'

# Variables globales
SSL_DIR="/etc/hostberry/ssl"
SSL_HOSTNAME="hostberry.local"
VENV_DIR="venv"
REQUIREMENTS="requirements.txt"
SYSTEMD_SERVICE="hostberry-web.service"
BACKUP_DIR="/opt/hostberry_backups"
HOSTBERRY_DIR="/opt/hostberry"
SCRIPTS_DIR="$HOSTBERRY_DIR/scripts"

# Dependencias del sistema
DEPS=(python3 python3-pip python3-venv openvpn resolvconf git curl dnsmasq hostapd iptables nftables libnss3-tools ufw openssl wget)

# Función para loguear mensajes
log() {
    local color="$1"; shift
    local level="$1"; shift
    echo -e "${color}[$level] $*${ANSI_RESET}"
}

# Manejo centralizado de errores
handle_error() {
    log "$ANSI_RED" "ERROR" "$*" >&2
    exit 1
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

# Comprobar si el script se ejecuta como root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        handle_error "Este script debe ejecutarse como root (sudo)"
    fi
}

# Mostrar ayuda
show_help() {
    echo "Uso: ./setup.sh [OPCIONES]"
    echo
    echo "Opciones:"
    echo "  --help         Mostrar esta ayuda y salir"
    echo "  --update       Actualizar la instalación de HostBerry"
    echo "  --cert         Generar certificados SSL con mkcert"
    echo "  --network      Configurar firewall y red para Raspberry Pi"
    echo
    echo "Ejemplos:"
    echo "  sudo ./setup.sh                   Instalación inicial"
    echo "  sudo ./setup.sh --update          Actualizar HostBerry"
    echo "  sudo ./setup.sh --cert            Generar certificados SSL"
    echo "  sudo ./setup.sh --network         Configurar red y firewall"
    echo "  sudo ./setup.sh --update --cert   Actualizar e instalar certificados"
    echo
    echo "Para más información, consulta la documentación de HostBerry."
    exit 0
}

# Comprobar e instalar dependencias
check_and_install_deps() {
    log "$ANSI_YELLOW" "INFO" "Comprobando dependencias del sistema..."
    apt-get update || handle_error "No se pudo actualizar apt-get"
    apt-get install -y "${DEPS[@]}" || handle_error "No se pudieron instalar las dependencias del sistema"
}

# Crear o recrear entorno virtual
setup_venv() {
    if [ -d "$VENV_DIR" ]; then
        log "$ANSI_YELLOW" "INFO" "Eliminando entorno virtual anterior..."
        rm -rf "$VENV_DIR"
    fi
    log "$ANSI_YELLOW" "INFO" "Creando entorno virtual..."
    python3 -m venv "$VENV_DIR" || handle_error "No se pudo crear el entorno virtual"
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip || handle_error "No se pudo actualizar pip"
    
    # Verificar si estamos en el directorio correcto
    if [ ! -f "$REQUIREMENTS" ]; then
        # Intentar encontrar requirements.txt en el directorio actual o en el directorio padre
        if [ -f "/opt/hostberry/$REQUIREMENTS" ]; then
            REQUIREMENTS="/opt/hostberry/$REQUIREMENTS"
        elif [ -f "$(dirname "$0")/$REQUIREMENTS" ]; then
            REQUIREMENTS="$(dirname "$0")/$REQUIREMENTS"
        else
            handle_error "No se pudo encontrar el archivo $REQUIREMENTS"
        fi
    fi
    
    log "$ANSI_YELLOW" "INFO" "Instalando dependencias desde $REQUIREMENTS..."
    pip install --upgrade -r "$REQUIREMENTS" || handle_error "No se pudieron instalar las dependencias de Python"
}

# Función para generar certificados SSL
generate_ssl_cert() {
    log "$ANSI_YELLOW" "INFO" "Iniciando generación de certificados SSL..."

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
    
    # Obtener nombres de host y IP local
    local HOSTNAME=$(hostname)
    local DOMAIN=$(hostname -d || echo "local")
    local LOCAL_IP=$(hostname -I | awk '{print $1}')

    log "$ANSI_GREEN" "INFO" "Generando certificados para:"
    echo "  * hostberry.local"
    echo "  * $HOSTNAME"
    echo "  * localhost"
    echo "  * 127.0.0.1"
    echo "  * $LOCAL_IP"

    # Instalar mkcert para el sistema
    mkcert -install || handle_error "No se pudo instalar mkcert en el sistema"

    # Generar certificados
    mkcert -cert-file hostberry.crt -key-file hostberry.key \
        "hostberry.local" \
        "$HOSTNAME" \
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
    ufw allow 53/udp   # DNS
    ufw allow 67/udp   # DHCP
    ufw allow 68/udp   # DHCP
    
    # Habilitar reenvío de IP
    sed -i 's/^#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf
    sysctl -p || handle_error "No se pudo aplicar la configuración de sysctl"
    
    # Configurar NAT para compartir Internet
    local IFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
    iptables -t nat -A POSTROUTING -o "$IFACE" -j MASQUERADE
    
    # Guardar reglas
    iptables-save > /etc/iptables/rules.v4 || handle_error "No se pudieron guardar las reglas de iptables"
    
    # Habilitar UFW
    ufw --force enable || handle_error "No se pudo habilitar UFW"
    
    log "$ANSI_GREEN" "INFO" "Red y firewall configurados correctamente."
}

# Función para actualizar desde GitHub
update_from_github() {
    log "$ANSI_YELLOW" "INFO" "Actualizando desde GitHub..."
    
    # Verificar si git está instalado
    if ! command -v git &> /dev/null; then
        log "$ANSI_YELLOW" "INFO" "Instalando git..."
        apt-get install -y git || handle_error "No se pudo instalar git"
    fi
    
    # Eliminar el directorio existente y clonar de nuevo
    log "$ANSI_YELLOW" "INFO" "Eliminando directorio existente..."
    rm -rf "$HOSTBERRY_DIR"
    
    log "$ANSI_YELLOW" "INFO" "Clonando repositorio..."
    git clone https://github.com/aka0kuro/hostberry.git "$HOSTBERRY_DIR" || handle_error "No se pudo clonar el repositorio"
    
    # Actualizar permisos
    chmod -R 755 "$HOSTBERRY_DIR"
    find "$HOSTBERRY_DIR" -type f -exec chmod 644 {} \;
    find "$HOSTBERRY_DIR/scripts" -type f -name "*.sh" -exec chmod +x {} \;
    
    # Asegurar que el directorio pertenece al usuario correcto
    chown -R root:root "$HOSTBERRY_DIR" || log "$ANSI_YELLOW" "WARN" "No se pudieron cambiar los permisos del directorio"
    
    log "$ANSI_GREEN" "INFO" "Actualización desde GitHub completada"
}

# Actualizar HostBerry
update_hostberry() {
    log "$ANSI_GREEN" "INFO" "Iniciando actualización de HostBerry..."
    
    # Crear backup si existe instalación previa
    if [ -d "$HOSTBERRY_DIR" ]; then
        systemctl stop hostberry-web.service 2>/dev/null || true
        
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
loglevel = "info"

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
    pass

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")
EOF
        
        # Crear archivo de servicio systemd
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
    --log-level info \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --worker-class sync \
    --worker-connections 1000 \
    --backlog 2048 \
    --graceful-timeout 30 \
    app:app
Restart=always
RestartSec=10
Environment="FLASK_APP=app.py"
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

# Procesar argumentos y ejecutar acciones
main() {
    UPDATE_MODE=false
    GENERATE_CERT=false
    CONFIGURE_NETWORK=false
    SHOW_HELP=false

    for arg in "$@"; do
        case $arg in
            --update)
                UPDATE_MODE=true
                ;;
            --cert)
                GENERATE_CERT=true
                ;;
            --network)
                CONFIGURE_NETWORK=true
                ;;
            -h|--help)
                SHOW_HELP=true
                ;;
            *)
                ;;
        esac
    done

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
loglevel = "info"

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
    pass

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")
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
    --log-level info \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --worker-class sync \
    --worker-connections 1000 \
    --backlog 2048 \
    --graceful-timeout 30 \
    app:app
Restart=always
RestartSec=10
Environment="FLASK_APP=app.py"
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
}

# Activar modo estricto
set -euo pipefail

# Ejecutar script principal
main "$@"
