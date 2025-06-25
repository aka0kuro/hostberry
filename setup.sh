#!/bin/bash
#
# HostBerry Installer - Instala y actualiza HostBerry
# Basado en el instalador de RaspAP
#
# Uso: setup.sh [opciones]
#
# Opciones:
#   -y, --yes, --assume-yes     Responde "sí" a todas las preguntas
#   -u, --update                Actualizar instalación existente
#   -b, --backup                Crear respaldo antes de actualizar
#   -h, --help                  Mostrar este mensaje de ayuda
#   -v, --version               Mostrar información de versión
#   -c, --cert                  Instalar certificado SSL
#   -r, --restore <archivo>     Restaurar desde archivo de respaldo
#   -d, --debug                 Habilitar modo depuración
#   -f, --force                 Forzar instalación incluso si ya está instalado

# Configuración global
set -eo pipefail

# Constantes
readonly VERSION="2.0.0"
readonly REPO_OWNER="aka0kuro"
readonly REPO_NAME="hostberry"
readonly GIT_REPO="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
readonly INSTALL_DIR="/opt/hostberry"
readonly CONFIG_DIR="/etc/hostberry"
readonly LOG_FILE="/var/log/hostberry-install.log"
readonly REQUIREMENTS_FILE="${INSTALL_DIR}/requirements.txt"
readonly SERVICE_FILE="/etc/systemd/system/hostberry.service"
readonly BACKUP_DIR="/var/backups/hostberry"
readonly NGINX_SITE="/etc/nginx/sites-available/hostberry"
readonly NGINX_SITE_ENABLED="/etc/nginx/sites-enabled/hostberry"

# Colores
readonly COL_NC='\e[0m' # Sin color
readonly COL_LIGHT_GREEN='\e[1;32m'
readonly COL_LIGHT_RED='\e[1;31m'
readonly COL_LIGHT_CYAN='\e[1;36m'
readonly COL_LIGHT_YELLOW='\e[1;33m'
readonly COL_LIGHT_BLUE='\e[1;34m'
TICK="[${COL_LIGHT_GREEN}✓${COL_NC}]"
CROSS="[${COL_LIGHT_RED}✗${COL_NC}]"
INFO="[i]"
DONE="[${COL_LIGHT_GREEN}✓${COL_NC}]"
WARN="[${COL_LIGHT_YELLOW}!${COL_NC}]"

# Variables globales
ASSUME_YES=0
DO_UPDATE=0
DO_BACKUP=0
DO_RESTORE=""
INSTALL_CERT=0
DEBUG=0
FORCE=0
CURRENT_USER=$(who | awk '{print $1}')

# Inicializar logging
setup_logging() {
    local log_dir
    log_dir=$(dirname "${LOG_FILE}")
    mkdir -p "${log_dir}"
    exec > >(tee -a "${LOG_FILE}")
    exec 2>&1
    _install_log "Iniciando registro en ${LOG_FILE}"
}

# Mostrar mensaje de registro
_install_log() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[${timestamp}] $*"
}

# Mostrar estado de la instalación
_install_status() {
    case $1 in
        0)
            echo -e " ${TICK} $2"
            ;;
        *)
            echo -e " ${CROSS} $2"
            if [ "${DEBUG}" -eq 1 ]; then
                _install_log "Error: $1"
            fi
            return 1
            ;;
    esac
}

# Mostrar separador
_install_divider() {
    echo -e "${COL_LIGHT_BLUE}----------------------------------------${COL_NC}"
}  

# Verificar si se ejecuta como root
check_root() {
    _install_log "Verificando privilegios de superusuario"
    if [ "$(id -u)" -ne 0 ]; then
        _install_log "Este script debe ejecutarse como root"
        exit 1
    fi
    return 0
}

# Verificar conexión a internet
check_internet() {
    _install_log "Verificando conexión a internet"
    if ! ping -q -c 1 -W 5 8.8.8.8 &> /dev/null; then
        _install_log "No se detectó conexión a internet"
        return 1
    fi
    return 0
}

# Mostrar mensaje de bienvenida
display_welcome() {
    _install_divider
    echo -e "     ${COL_LIGHT_CYAN}Instalador de HostBerry${COL_NC} v${VERSION}"
    echo ""
    echo -e "  Este instalador configurará o actualizará HostBerry"
    echo -e "  en su sistema."
    _install_divider
}

# Mostrar ayuda
show_help() {
    grep '^#/' "$0" | cut -c 4-
    exit 0
}

# Mostrar versión
show_version() {
    echo "HostBerry Installer v${VERSION}"
    exit 0
}

# Analizar argumentos de línea de comandos
parse_arguments() {
    while [ $# -gt 0 ]; do
        case $1 in
            -y|--yes|--assume-yes)
                ASSUME_YES=1
                ;;
            -u|--update)
                DO_UPDATE=1
                ;;
            -b|--backup)
                DO_BACKUP=1
                ;;
            -r|--restore)
                shift
                DO_RESTORE="$1"
                ;;
            -c|--cert)
                INSTALL_CERT=1
                ;;
            -d|--debug)
                DEBUG=1
                set -x
                ;;
            -f|--force)
                FORCE=1
                ;;
            -h|--help)
                show_help
                ;;
            -v|--version)
                show_version
                ;;
            *)
                _install_log "Opción desconocida: $1"
                show_help
                ;;
        esac
        shift
    done
}

# Verificar requisitos del sistema
check_requirements() {
    _install_log "Verificando requisitos del sistema"
    
    local missing=()
    local install_needed=0
    
    # Comandos requeridos
    local required_commands=(
        python3
        pip3
        git
        systemctl
        nginx
    )
    
    for cmd in "${required_commands[@]}"; do
        if ! command -v "${cmd}" &> /dev/null; then
            missing+=("${cmd}")
            install_needed=1
        fi
    done
    
    # Si faltan dependencias, intentar instalarlas
    if [ ${install_needed} -eq 1 ]; then
        _install_log "Instalando dependencias faltantes: ${missing[*]}"
        if ! install_dependencies; then
            _install_log "Error al instalar dependencias faltantes"
            return 1
        fi
        
        # Verificar nuevamente después de la instalación
        missing=()
        for cmd in "${required_commands[@]}"; do
            if ! command -v "${cmd}" &> /dev/null; then
                missing+=("${cmd}")
            fi
        done
        
        if [ ${#missing[@]} -gt 0 ]; then
            _install_log "No se pudieron instalar los siguientes comandos: ${missing[*]}"
            return 1
        fi
    fi
    
    # Versión mínima de Python
    local python_version
    python_version=$(python3 -c 'import sys; print("{}.{}".format(sys.version_info.major, sys.version_info.minor))' 2>/dev/null)
    if [ $? -ne 0 ] || [ "$(echo "${python_version:-0} < 3.7" | bc 2>/dev/null)" = "1" ]; then
        _install_log "Se requiere Python 3.7 o superior. Instalando versión compatible..."
        
        if [ -f /etc/debian_version ]; then
            apt-get install -y python3.9 python3.9-venv
            update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1
        elif [ -f /etc/redhat-release ]; then
            dnf install -y python39 python39-pip
            update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1
        else
            _install_log "No se pudo instalar Python 3.9 automáticamente en esta distribución"
            return 1
        fi
    fi
    
    return 0
}

# Instalar dependencias del sistema
install_dependencies() {
    _install_log "Instalando dependencias del sistema"
    
    # Verificar si estamos ejecutando como root
    if [ "$(id -u)" -ne 0 ]; then
        _install_log "Se requieren privilegios de superusuario para instalar dependencias"
        return 1
    fi
    
    if [ -f /etc/debian_version ]; then
        # Distribuciones basadas en Debian
        _install_log "Detectado sistema basado en Debian/Ubuntu"
        
        # Actualizar lista de paquetes
        if ! apt-get update; then
            _install_log "Error al actualizar la lista de paquetes"
            return 1
        fi
        
        # Instalar paquetes necesarios
        local deb_pkgs=(
            python3
            python3-venv
            python3-pip
            python3-dev
            nginx
            git
            build-essential
            libssl-dev
            libffi-dev
            python3-setuptools
            python3-wheel
            bc
        )
        
        _install_log "Instalando paquetes: ${deb_pkgs[*]}"
        if ! DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${deb_pkgs[@]}"; then
            _install_log "Error al instalar paquetes con apt"
            return 1
        fi
        
        # Verificar que nginx se haya instalado correctamente
        if ! command -v nginx &> /dev/null; then
            _install_log "Intentando instalar nginx desde el repositorio principal..."
            if ! apt-get install -y nginx; then
                _install_log "No se pudo instalar nginx"
                return 1
            fi
        fi
        
    elif [ -f /etc/redhat-release ]; then
        # Distribuciones basadas en RedHat
        dnf install -y \
            python3 \
            python3-pip \
            python3-devel \
            nginx \
            git \
            gcc \
            openssl-devel \
            libffi-devel \
            python3-setuptools \
            python3-wheel
    else
        _install_log "Distribución no soportada"
        return 1
    fi
    
    return $?
}

# Configurar entorno virtual de Python
setup_python_venv() {
    _install_log "Configurando entorno virtual de Python"
    
    if [ ! -d "${INSTALL_DIR}" ]; then
        mkdir -p "${INSTALL_DIR}"
    fi
    
    # Crear entorno virtual
    python3 -m venv "${INSTALL_DIR}/venv"
    
    # Activar entorno virtual
    # shellcheck source=/dev/null
    source "${INSTALL_DIR}/venv/bin/activate"
    
    # Actualizar pip
    pip install --upgrade pip setuptools wheel
    
    return $?
}

# Instalar dependencias de Python
install_python_deps() {
    _install_log "Instalando dependencias de Python"
    
    if [ ! -f "${REQUIREMENTS_FILE}" ]; then
        _install_log "Archivo de requisitos no encontrado: ${REQUIREMENTS_FILE}"
        return 1
    fi
    
    # Actualizar pip y setuptools primero
    pip install --upgrade pip setuptools wheel
    
    # Instalar dependencias en dos pasos para manejar mejor los errores
    _install_log "Instalando dependencias desde requirements.txt..."
    if ! pip install -r "${REQUIREMENTS_FILE}"; then
        _install_log "Error al instalar dependencias. Reintentando con --no-cache-dir..."
        if ! pip install --no-cache-dir -r "${REQUIREMENTS_FILE}"; then
            _install_log "Error crítico: No se pudieron instalar las dependencias"
            return 1
        fi
    fi
    
    # Verificar que las dependencias principales estén instaladas
    _install_log "Verificando instalación de dependencias críticas..."
    if ! python -c "import flask_sqlalchemy, flask_login, flask_migrate, flask_babel, flask_wtf"; then
        _install_log "Error: No se pudieron importar todas las dependencias críticas"
        return 1
    fi
    
    _install_log "Dependencias de Python instaladas correctamente"
    return 0
}

# Configurar servicio systemd
setup_systemd_service() {
    _install_log "Configurando servicio systemd"
    
    # Crear directorio de instalación si no existe
    mkdir -p "${INSTALL_DIR}"
    
    # Crear archivo de servicio optimizado para Raspberry Pi 3
    cat > "/etc/systemd/system/hostberry.service" << EOL
[Unit]
Description=HostBerry Web Interface
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/venv/bin"

# Limpiar el socket antiguo si existe
ExecStartPre=/bin/rm -f ${INSTALL_DIR}/hostberry.sock

# Usar solo 1 worker en Raspberry Pi 3 para mejor rendimiento
# Usar sync worker en lugar del predeterminado para mejor compatibilidad
# Usar wsgi:app como punto de entrada de la aplicación
ExecStart=${INSTALL_DIR}/venv/bin/gunicorn \
    --workers 1 \
    --worker-class sync \
    --bind unix:${INSTALL_DIR}/hostberry.sock \
    -m 007 \
    wsgi:app

# Limpiar el socket después de detener el servicio
ExecStopPost=/bin/rm -f ${INSTALL_DIR}/hostberry.sock

# Configuración de tiempo de espera más generosa para hardware limitado
TimeoutStartSec=300
# Asegurar que el servicio se reinicie si falla
Restart=on-failure
RestartSec=10s
# Límites de recursos para evitar sobrecargar la Raspberry Pi
MemoryMax=256M
CPUQuota=80%

[Install]
WantedBy=multi-user.target
EOL
    
    # Recargar systemd
    systemctl daemon-reload
    
    # Habilitar e iniciar el servicio
    systemctl enable hostberry
    systemctl start hostberry
    
    # Verificar que el servicio se haya iniciado correctamente
    if ! systemctl is-active --quiet hostberry; then
        _install_log "Error al iniciar el servicio hostberry"
        journalctl -u hostberry -n 30 --no-pager
        return 1
    fi
    
    return 0
}

# Configurar Nginx
setup_nginx() {
    _install_log "Configurando Nginx"
    
    # Instalar Nginx si no está instalado
    if ! command -v nginx &> /dev/null; then
        _install_log "Instalando Nginx"
        apt-get install -y nginx
    fi
    
    # Detener Nginx temporalmente
    if systemctl is-active --quiet nginx; then
        systemctl stop nginx
    fi
    
    # Eliminar configuración por defecto si existe
    if [ -f "/etc/nginx/sites-enabled/default" ]; then
        rm -f "/etc/nginx/sites-enabled/default"
    fi
    
    # Crear directorios necesarios
    _install_log "Creando directorios estáticos"
    mkdir -p "${INSTALL_DIR}/static/img"
    mkdir -p "${INSTALL_DIR}/app/static/img"
    

    # Crear directorios estáticos si no existen
    _install_log "Creando directorios estáticos..."
    mkdir -p "${INSTALL_DIR}/static/img"
    mkdir -p "${INSTALL_DIR}/media"
    
    # Copiar imagen del logo si existe
    if [ -f "${INSTALL_DIR}/img/hostberry.png" ]; then
        _install_log "Copiando imagen del logo..."
        cp "${INSTALL_DIR}/img/hostberry.png" "${INSTALL_DIR}/static/img/"
        cp "${INSTALL_DIR}/img/hostberry.png" "${INSTALL_DIR}/app/static/img/"
    fi
    
    # Establecer permisos correctos
    _install_log "Estableciendo permisos..."
    chown -R www-data:www-data "${INSTALL_DIR}"
    find "${INSTALL_DIR}" -type d -exec chmod 755 {} \;
    find "${INSTALL_DIR}" -type f -exec chmod 644 {} \;
    chmod +x "${INSTALL_DIR}/venv/bin/"*
    
    # Crear configuración de Nginx
    _install_log "Creando configuración de Nginx..."
    
    cat > "${NGINX_SITE}" << EOL
server {
    listen 80;
    server_name _;
    
    # Tamaño máximo de subida de archivos (100MB)
    client_max_body_size 100M;
    
    # Configuración de timeouts
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    fastcgi_read_timeout 300s;
    
    location / {
        proxy_pass http://unix:${INSTALL_DIR}/hostberry.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Configuración para archivos estáticos
    location /static/ {
        alias ${INSTALL_DIR}/static/;
        expires 30d;
        access_log off;
        add_header Cache-Control "public, no-transform";
    }
    
    location /media/ {
        alias ${INSTALL_DIR}/media/;
        expires 30d;
        access_log off;
    }
    
    # Deshabilitar acceso a archivos ocultos
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOL
    
    # Habilitar sitio
    ln -sf "${NGINX_SITE}" "${NGINX_SITE_ENABLED}"
    
    # Probar configuración
    if ! nginx -t; then
        _install_log "Error en la configuración de Nginx"
        return 1
    fi
    
    # Establecer permisos correctos
    _install_log "Estableciendo permisos..."
    chown -R www-data:www-data "${INSTALL_DIR}"
    find "${INSTALL_DIR}" -type d -exec chmod 755 {} \;
    find "${INSTALL_DIR}" -type f -exec chmod 644 {} \;
    chmod +x "${INSTALL_DIR}/setup.sh"
    chmod +x "${INSTALL_DIR}/scripts/"*.sh
    
    # Permisos especiales para directorios de escritura
    chmod -R 775 "${INSTALL_DIR}/app/static"
    chmod -R 775 "${INSTALL_DIR}/media"
    
    # Permisos para el socket
    chmod 775 "${INSTALL_DIR}"
    
    # Reiniciar servicios
    systemctl daemon-reload
    systemctl restart nginx
    systemctl restart hostberry
    
    _install_status $? "Configuración de permisos y servicios completada"
    return $?
}

# Configurar certificado SSL
setup_ssl_certificate() {
    _install_log "Configurando certificado SSL"
    
    if [ ! -d "${CONFIG_DIR}/ssl" ]; then
        mkdir -p "${CONFIG_DIR}/ssl"
{{ ... }}
    fi
    
    # Generar certificado autofirmado
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "${CONFIG_DIR}/ssl/hostberry.key" \
        -out "${CONFIG_DIR}/ssl/hostberry.crt" \
        -subj "/CN=hostberry.local"
    
    # Actualizar configuración de Nginx para usar SSL
    if [ -f "${NGINX_SITE}" ]; then
        sed -i 's/listen 80;/listen 443 ssl;\n    ssl_certificate \/etc\/hostberry\/ssl\/hostberry.crt;\n    ssl_certificate_key \/etc\/hostberry\/ssl\/hostberry.key;/' "${NGINX_SITE}"
        
        # Redirigir HTTP a HTTPS
        echo -e "server {\n    listen 80;\n    server_name _;\n    return 301 https://\$host\$request_uri;\n}" | tee "${NGINX_SITE}.http" > /dev/null
        
        # Recargar Nginx
        systemctl reload nginx
    fi
    
    return 0
}

# Crear respaldo
create_backup() {
    _install_log "Creando respaldo"
    
    local timestamp
    timestamp=$(date +%Y%m%d%H%M%S)
    local backup_dir="${BACKUP_DIR}/hostberry_${timestamp}"
    
    mkdir -p "${backup_dir}"
    
    # Copiar configuración
    if [ -d "${CONFIG_DIR}" ]; then
        cp -r "${CONFIG_DIR}" "${backup_dir}/"
    fi
    
    # Copiar base de datos
    if [ -f "${INSTALL_DIR}/db.sqlite3" ]; then
        cp "${INSTALL_DIR}/db.sqlite3" "${backup_dir}/"
    fi
    
    # Crear archivo comprimido
    local backup_file="${BACKUP_DIR}/hostberry_backup_${timestamp}.tar.gz"
    tar -czf "${backup_file}" -C "${backup_dir}" .
    
    # Limpiar
    rm -rf "${backup_dir}"
    
    _install_log "Respaldo creado: ${backup_file}"
    echo "${backup_file}"
    
    return 0
}

# Restaurar desde respaldo
restore_backup() {
    local backup_file="$1"
    
    if [ ! -f "${backup_file}" ]; then
        _install_log "Archivo de respaldo no encontrado: ${backup_file}"
        return 1
    fi
    
    _install_log "Restaurando desde respaldo: ${backup_file}"
    
    # Detener servicios
    systemctl stop hostberry
    
    # Extraer respaldo
    local temp_dir
    temp_dir=$(mktemp -d)
    tar -xzf "${backup_file}" -C "${temp_dir}"
    
    # Restaurar configuración
    if [ -d "${temp_dir}/$(basename "${CONFIG_DIR}")" ]; then
        cp -r "${temp_dir}/$(basename "${CONFIG_DIR}")" "$(dirname "${CONFIG_DIR}")"
    fi
    
    # Restaurar base de datos
    if [ -f "${temp_dir}/db.sqlite3" ]; then
        cp "${temp_dir}/db.sqlite3" "${INSTALL_DIR}/"
    fi
    
    # Limpiar
    rm -rf "${temp_dir}"
    
    # Iniciar servicios
    systemctl start hostberry
    
    _install_log "Restauración completada"
    return 0
}

# Actualizar desde GitHub
update_from_github() {
    _install_log "Actualizando desde GitHub"
    
    if [ ! -d "${INSTALL_DIR}/.git" ]; then
        _install_log "No se puede actualizar: ${INSTALL_DIR} no es un repositorio git"
        return 1
    fi
    
    # Configurar git safe.directory para evitar advertencias de propiedad
    git config --global --add safe.directory "${INSTALL_DIR}"

    # Guardar cambios locales
    cd "${INSTALL_DIR}" || return 1
    
    # Obtener cambios remotos
    git fetch --all
    
    # Verificar si hay actualizaciones
    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD)

    # Validar que current_branch no esté vacío
    if [ -z "$current_branch" ]; then
        _install_log "No se pudo determinar la rama actual de git."
        return 1
    fi

    local rev_count
    rev_count=$(git rev-list HEAD...origin/${current_branch} --count 2>/dev/null)
    # Validar que rev_count es un número
    if ! [[ "$rev_count" =~ ^[0-9]+$ ]]; then
        _install_log "No se pudo obtener el número de commits para comparar actualizaciones."
        return 1
    fi

    if [ "$rev_count" -eq 0 ]; then
        _install_log "No hay actualizaciones disponibles"
        return 0
    fi
    
    # Crear respaldo antes de actualizar
    if [ "${DO_BACKUP}" -eq 1 ]; then
        create_backup
    fi
    
    # Actualizar código
    git reset --hard "origin/${current_branch}"
    
    # Actualizar dependencias
    source "${INSTALL_DIR}/venv/bin/activate"
    install_python_deps
    
    # [Eliminado] Aplicar migraciones (no aplica en Flask/HostBerry)
    # python manage.py migrate --noinput
    
    # [Eliminado] Recolectar archivos estáticos (no aplica en Flask/HostBerry)
    # python manage.py collectstatic --noinput
    
    # Ajustar permisos del socket para Nginx (www-data)
    if [ -S "/opt/hostberry/hostberry.sock" ]; then
        chown www-data:www-data /opt/hostberry/hostberry.sock
        chmod 660 /opt/hostberry/hostberry.sock
    fi

    # Reiniciar servicios
    systemctl restart hostberry
    systemctl restart nginx

    _install_log "Actualización completada"
    return 0
}

# Instalar HostBerry
install_hostberry() {
    _install_log "Instalando HostBerry"
    
    # Crear directorio de instalación
    mkdir -p "${INSTALL_DIR}"
    chown -R www-data:www-data "${INSTALL_DIR}"
    
    # Clonar repositorio
    if [ ! -d "${INSTALL_DIR}/.git" ]; then
        git clone "${GIT_REPO}" "${INSTALL_DIR}"
    else
        _install_log "El directorio ${INSTALL_DIR} ya existe. Usando -f para forzar reinstalación."
        if [ "${FORCE}" -ne 1 ] && [ "${DO_UPDATE}" -ne 1 ]; then
            _install_log "Use --force para forzar la instalación o --update para actualizar"
            return 1
        fi
    fi
    
    cd "${INSTALL_DIR}" || return 1
    
    # Configurar permisos
    chown -R www-data:www-data "${INSTALL_DIR}/static" "${INSTALL_DIR}/app/static"
    chmod -R 755 "${INSTALL_DIR}/static" "${INSTALL_DIR}/app/static"
    
    # Configurar entorno virtual
    setup_python_venv
    
    # Instalar dependencias de Python
    install_python_deps
    
    # Verificar si existe el script de inicialización de la base de datos
    if [ -f "${INSTALL_DIR}/scripts/init_db.py" ]; then
        _install_log "Inicializando base de datos..."
        cd "${INSTALL_DIR}" || return 1
        
        # Configurar variables de entorno para el usuario administrador
        export FLASK_APP="app"
        export FLASK_ENV="development"
        export DEFAULT_ADMIN_USER="admin"
        export DEFAULT_ADMIN_PASSWORD="admin123"
        export DEFAULT_ADMIN_EMAIL="admin@localhost.local"
        
        # Ejecutar el script de inicialización
        if ! python -m scripts.init_db; then
            _install_log "Error al inicializar la base de datos. Revisa los logs para más detalles."
            return 1
        fi
        
        _install_log "Base de datos inicializada correctamente"
    else
        _install_log "No se encontró el script de inicialización de la base de datos"
        return 1
    fi
    
    # Recolectar archivos estáticos si existe el directorio
    if [ -d "${INSTALL_DIR}/app/static" ]; then
        _install_log "Recolectando archivos estáticos..."
        mkdir -p "${INSTALL_DIR}/app/static"
        # Crear archivos estáticos necesarios si no existen
        touch "${INSTALL_DIR}/app/static/.keep"
    fi
    
    # Configurar servicio systemd
    setup_systemd_service
    
    # Configurar Nginx
    setup_nginx
    
    # Configurar certificado SSL si es necesario
    if [ "${INSTALL_CERT}" -eq 1 ]; then
        setup_ssl_certificate
    fi
    
    # Iniciar servicio
    systemctl start hostberry
    
    _install_log "Instalación completada"
    return 0
}

# Mostrar información de acceso
show_access_info() {
    local ip_address
    ip_address=$(hostname -I | awk '{print $1}')
    
    _install_divider
    echo -e "${COL_LIGHT_GREEN}Instalación completada${COL_NC}"
    echo ""
    echo -e "HostBerry está ahora disponible en:"
    echo -e "  - ${COL_LIGHT_CYAN}http://${ip_address}${COL_NC}"
    
    if [ "${INSTALL_CERT}" -eq 1 ]; then
        echo -e "  - ${COL_LIGHT_CYAN}https://${ip_address}${COL_NC} (con advertencia de certificado)"
    fi
    
    echo ""
    echo -e "Credenciales por defecto:"
    echo -e "  - Usuario: ${COL_LIGHT_YELLOW}admin${COL_NC}"
    echo -e "  - Contraseña: ${COL_LIGHT_YELLOW}admin$123{COL_NC}"
    echo ""
    echo -e "Recuerde cambiar la contraseña después del primer inicio de sesión."
    _install_divider
}

# Función principal
main() {
    # Configurar logging
    setup_logging
    
    # Mostrar mensaje de bienvenida
    display_welcome
    
    # Analizar argumentos
    parse_arguments "$@"
    
    # Verificar privilegios de superusuario
    check_root
    
    # Verificar conexión a internet
    if ! check_internet; then
        _install_log "Se requiere conexión a internet para continuar"
        exit 1
    fi
    
    # Restaurar desde respaldo si se especificó
    if [ -n "${DO_RESTORE}" ]; then
        if ! restore_backup "${DO_RESTORE}"; then
            _install_log "Error al restaurar desde el respaldo"
            exit 1
        fi
        exit 0
    fi
    
    # Actualizar instalación existente
    if [ "${DO_UPDATE}" -eq 1 ]; then
        if ! update_from_github; then
            _install_log "Error al actualizar HostBerry"
            exit 1
        fi
        exit 0
    fi
    
    # Verificar requisitos del sistema
    if ! check_requirements; then
        _install_log "No se cumplen los requisitos del sistema"
        exit 1
    fi
    
    # Instalar dependencias del sistema
    if ! install_dependencies; then
        _install_log "Error al instalar dependencias del sistema"
        exit 1
    fi
    
    # Instalar HostBerry
    if ! install_hostberry; then
        _install_log "Error al instalar HostBerry"
        exit 1
    fi
    
    # Mostrar información de acceso
    show_access_info
    
    _install_log "Proceso completado con éxito"
    return 0
}

# Ejecutar función principal
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
