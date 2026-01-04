#!/bin/bash

# Script de despliegue de producción para HostBerry FastAPI
# OPTIMIZADO PARA RASPBERRY PI 3 - Consumo reducido de CPU y memoria
# 
# Soporte multilingüe

# Colores para logs
ANSI_GREEN='\033[0;32m'
ANSI_YELLOW='\033[0;33m'
ANSI_RED='\033[0;31m'
ANSI_BLUE='\033[0;34m'
ANSI_RESET='\033[0m'

# Configuración de idioma
# Idioma por defecto: español. Se puede sobrescribir con --language=XX
if [ -z "${LANGUAGE}" ]; then
  # Detectar idioma del sistema
  SYS_LANG="${LC_ALL:-${LC_MESSAGES:-${LANG}}}"
  
  if [[ "$SYS_LANG" == es* ]]; then
    LANGUAGE="es"
  elif [[ -n "$SYS_LANG" ]]; then
    # Si detecta otro idioma que no sea español, usar inglés
    LANGUAGE="en"
  else
    # Si no detecta nada, usar español por defecto
    LANGUAGE="es"
  fi
fi

LOCALES_DIR="locales"
TRANSLATIONS_FILE="$LOCALES_DIR/${LANGUAGE}.json"

# Cache de traducciones para optimizar rendimiento
declare -A TRANSLATIONS_CACHE

# Función para cargar traducciones (optimizada)
load_translations() {
    # Verificar si existe el archivo de idioma seleccionado
    if [[ ! -f "$TRANSLATIONS_FILE" ]]; then
        # Si no existe, intentar con inglés como fallback universal
        if [[ -f "$LOCALES_DIR/en.json" ]]; then
            LANGUAGE="en"
            TRANSLATIONS_FILE="$LOCALES_DIR/en.json"
        else
            # Si ni siquiera existe inglés, usar español (archivo base)
            LANGUAGE="es"
            TRANSLATIONS_FILE="$LOCALES_DIR/es.json"
        fi
    fi
}

# Función para obtener traducción (optimizada)
get_text() {
    local key="$1" default="$2"
    
    # Cache de traducciones para evitar múltiples lecturas
    [[ -n "${TRANSLATIONS_CACHE[$key]}" ]] && {
        echo "${TRANSLATIONS_CACHE[$key]}"
        return 0
    }
    
    # Intentar obtener traducción usando jq (más rápido)
    if command -v jq &> /dev/null && [[ -f "$TRANSLATIONS_FILE" ]]; then
        local translation
        translation=$(jq -r ".setup.$key" "$TRANSLATIONS_FILE" 2>/dev/null)
        [[ "$translation" != "null" && -n "$translation" ]] && {
            TRANSLATIONS_CACHE[$key]="$translation"
            echo "$translation"
            return 0
        }
    fi
    
    # Fallback al texto por defecto
    echo "$default"
}

# Comprobación de puertos 80/443 (optimizada)
check_required_ports() {
    log "$ANSI_YELLOW" "INFO" "$(get_text "checking_ports" "Comprobando puertos requeridos (80/443)...")"
    
    local ports=(80 443) p out proc msg
    
    for p in "${ports[@]}"; do
        # Usar ss si está disponible (más rápido)
        if command -v ss >/dev/null 2>&1; then
            out=$(ss -H -tulpn "sport = :$p" 2>/dev/null || true)
        elif command -v netstat >/dev/null 2>&1; then
            out=$(netstat -tulpn 2>/dev/null | grep ":$p " || true)
        else
            continue
        fi
        
        [[ -n "$out" ]] || continue
        
        # Si es nginx, continuar
        echo "$out" | grep -qi nginx && continue
        
        # Extraer nombre de proceso
        if echo "$out" | grep -q "users:("; then
            proc=$(printf '%s' "$out" | sed -n 's/.*users:(\(("\([^"]\+\)".*/\2/p' | head -n1)
        else
            proc=$(printf '%s' "$out" | awk '{print $NF}' | sed 's/.*\///')
        fi
        
        [[ -n "$proc" ]] || proc="unknown"
        
        msg=$(format_text "$(get_text "port_in_use" "El puerto {port} ya está en uso por {proc}. Libéralo o detén el servicio.")" "port=$p" "proc=$proc")
        die "$msg"
    done
    
    log "$ANSI_GREEN" "INFO" "$(get_text "ports_ok" "Puertos requeridos listos")"
}

# Función para formatear texto con variables
format_text() {
    local text="$1"
    shift
    
    # Reemplazar variables en el texto
    for var in "$@"; do
        # Soporta valores con '=' usando expansión de parámetros
        local name="${var%%=*}"
        local value="${var#*=}"
        # Escapar caracteres especiales para sed (/, \, &, |)
        local escaped_value
        escaped_value=$(printf '%s' "$value" | sed -e 's/[\\/&|]/\\&/g')
        # Usar delimitador '|' para evitar conflictos con '/'
        text=$(printf '%s' "$text" | sed "s|{$name}|$escaped_value|g")
    done
    
    echo "$text"
}

# Variables de producción (layout endurecido en /opt y /var)
# Obtener el usuario real que ejecutó el comando (no root cuando se usa sudo)
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME="/home/$REAL_USER"

# Usuario/grupo de servicio dedicados
SERVICE_NAME="hostberry"
USER="hostberry"
GROUP="hostberry"

# Rutas de despliegue
PROD_DIR="/opt/hostberry"
WEBSITE_DIR="$PROD_DIR/website"
VENV_DIR="$PROD_DIR/venv"
BACKUP_DIR="$REAL_HOME/hostberry_backups"
LOG_DIR="/var/log/hostberry"
CONFIG_DIR="/etc/hostberry"
SSL_DIR="$CONFIG_DIR/ssl"
UPLOADS_DIR="/var/lib/hostberry/uploads"

# Configuración de producción optimizada para RPi 3
PROD_HOST="127.0.0.1"  # Solo localhost para mayor seguridad
PROD_PORT="8000"
WORKERS="1"              # Un solo worker para RPi 3
LOG_LEVEL="WARNING"      # Reducir logging para mejor rendimiento
ENVIRONMENT="production"

# Función para loguear mensajes (optimizada)
log() {
    local color="$1" level="$2" icon
    shift 2
    
    case "$level" in
        INFO) icon="ℹ️" ;;
        WARN) icon="⚠️" ;;
        ERROR) icon="❌" ;;
        SUCCESS) icon="✅" ;;
        *) icon="" ;;
    esac
    
    printf '%b[%s] %s %s%b\n' "$color" "$level" "$icon" "$*" "$ANSI_RESET"
}

# Manejo centralizado de errores (optimizado)
handle_error() {
    log "$ANSI_RED" "ERROR" "$*" >&2
    exit 1
}

# Crear venv evitando que el directorio actual "sombree" módulos stdlib (p.ej. logging.py)
# Esto previene errores tipo: ModuleNotFoundError: No module named 'logging.handlers'; 'logging' is not a package
run_python_venv() {
    local venv_path="$1"

    # Ejecutar desde un cwd seguro (no el directorio desde donde se lanzó setup.sh)
    # y sin PYTHONPATH/PYTHONHOME/PYTHONSTARTUP para minimizar interferencias.
    if python3 -P -c "import sys" >/dev/null 2>&1; then
        ( cd /tmp && env -u PYTHONPATH -u PYTHONHOME -u PYTHONSTARTUP PYTHONSAFEPATH=1 python3 -P -m venv "$venv_path" )
    else
        ( cd /tmp && env -u PYTHONPATH -u PYTHONHOME -u PYTHONSTARTUP python3 -m venv "$venv_path" )
    fi
}

# Función de salida rápida para errores críticos
die() { handle_error "$@"; }

# Verificar permisos y configuración (optimizado)
check_permissions() {
    # Verificar si el usuario puede escribir en su directorio home
    [[ -w "$HOME" ]] || {
        local error_msg
        error_msg=$(get_text "home_not_writable" "No se puede escribir en el directorio home")
        die "$error_msg"
    }
}

# Mostrar ayuda
show_help() {
    # Muestra ayuda conforme al idioma seleccionado (LANGUAGE)
    local _bak_tf="$TRANSLATIONS_FILE"
    if [ "$LANGUAGE" = "en" ]; then
        TRANSLATIONS_FILE="$LOCALES_DIR/en.json"
        local title=$(get_text "title" "Script de Despliegue de Producción - HostBerry FastAPI")
        local usage=$(get_text "usage" "Uso: ./setup.sh [OPCIONES]")
        local options=$(get_text "options" "Opciones:")
        local help_option=$(get_text "help_option" "Mostrar esta ayuda")
        local install_option=$(get_text "install_option" "Instalación completa de producción")
        local update_option=$(get_text "update_option" "Actualizar instalación existente")
        local backup_option=$(get_text "backup_option" "Crear backup antes de actualizar")
        local ssl_option=$(get_text "ssl_option" "Configurar SSL/TLS")
        local examples=$(get_text "examples" "Ejemplos:")
    local install_example=$(get_text "install_example" "sudo ./setup.sh --install")
    local update_example=$(get_text "update_example" "sudo ./setup.sh --update --backup")
        local ssl_example=$(get_text "ssl_example" "sudo ./setup.sh --ssl")
        echo "$title"; echo; echo "$usage"; echo; echo "$options"
    echo "  --help         $help_option"
    echo "  --install      $install_option"
    echo "  --update       $update_option"
    echo "  --backup       $backup_option"
    echo "  --ssl          $ssl_option"
        echo "  --language=XX  Establecer idioma (es/en)"; echo; echo "$examples"
        echo "  $install_example"; echo "  $update_example"; echo "  $ssl_example"; echo
    else
        TRANSLATIONS_FILE="$LOCALES_DIR/es.json"
        local title=$(get_text "title" "Script de Despliegue de Producción - HostBerry FastAPI")
        local usage=$(get_text "usage" "Uso: ./setup.sh [OPCIONES]")
        local options=$(get_text "options" "Opciones:")
        local help_option=$(get_text "help_option" "Mostrar esta ayuda")
        local install_option=$(get_text "install_option" "Instalación completa de producción")
        local update_option=$(get_text "update_option" "Actualizar instalación existente")
        local backup_option=$(get_text "backup_option" "Crear backup antes de actualizar")
        local ssl_option=$(get_text "ssl_option" "Configurar SSL/TLS")
        local examples=$(get_text "examples" "Ejemplos:")
        local install_example=$(get_text "install_example" "sudo ./setup.sh --install")
        local update_example=$(get_text "update_example" "sudo ./setup.sh --update --backup")
        local ssl_example=$(get_text "ssl_example" "sudo ./setup.sh --ssl")
        echo "$title"; echo; echo "$usage"; echo; echo "$options"
        echo "  --help         $help_option"
        echo "  --install      $install_option"
        echo "  --update       $update_option"
        echo "  --backup       $backup_option"
        echo "  --ssl          $ssl_option"
        echo "  --language=XX  Establecer idioma (es/en)"; echo; echo "$examples"
        echo "  $install_example"; echo "  $update_example"; echo "  $ssl_example"; echo
    fi
    TRANSLATIONS_FILE="$_bak_tf"
    exit 0
}

# Verificar integridad del directorio config (simplificada para RPi 3)
verify_config_integrity() {
    local base_dir="$1" operation="$2"
    local config_dir="$base_dir/config"
    
    log "$ANSI_YELLOW" "INFO" "$(format_text "$(get_text 'verifying_config' 'Verificando integridad del directorio config ({operation})...')" "operation=$operation")"
    
    # Verificar que el directorio config existe
    [[ -d "$config_dir" ]] || {
        log "$ANSI_RED" "ERROR" "$(format_text "$(get_text 'config_dir_missing' 'El directorio config no existe en {path}')" "path=$base_dir")"
        return 1
    }
    
    # Verificar archivos críticos
    local critical_files=("settings.py" "__init__.py") file
    for file in "${critical_files[@]}"; do
        [[ -f "$config_dir/$file" && -r "$config_dir/$file" && -s "$config_dir/$file" ]] || {
            log "$ANSI_RED" "ERROR" "$(format_text "$(get_text 'config_file_missing' 'Archivo crítico {file} no existe en {path}')" "file=$file" "path=$config_dir")"
            return 1
        }
    done
    
    # Verificar permisos del directorio (simplificado)
    chmod 755 "$config_dir" 2>/dev/null || true
    
    # Verificar permisos de los archivos Python (simplificado)
    chmod 644 "$config_dir"/*.py 2>/dev/null || true
    
    log "$ANSI_GREEN" "INFO" "$(get_text 'config_integrity_ok' '✅ Integridad del directorio config verificada')"
    return 0
}

# Configurar usuario y permisos
setup_user_permissions() {
    local setting_permissions=$(get_text "setting_permissions" "Configurando permisos de usuario...")
    log "$ANSI_YELLOW" "INFO" "$setting_permissions"
    
    # Crear usuario/grupo de servicio si no existen
    if ! id -u "$USER" >/dev/null 2>&1; then
        if [[ $EUID -eq 0 ]]; then
            useradd --system --home "$PROD_DIR" --shell /usr/sbin/nologin "$USER"
        else
            sudo useradd --system --home "$PROD_DIR" --shell /usr/sbin/nologin "$USER"
        fi
    fi

    # Crear directorios necesarios
    if [[ $EUID -eq 0 ]]; then
        mkdir -p "$PROD_DIR" "$BACKUP_DIR" "$SSL_DIR" "$LOG_DIR" "$UPLOADS_DIR" "$WEBSITE_DIR"
    else
        sudo mkdir -p "$PROD_DIR" "$BACKUP_DIR" "$SSL_DIR" "$LOG_DIR" "$UPLOADS_DIR" "$WEBSITE_DIR"
    fi

    # Ajustar propietarios
    if [[ $EUID -eq 0 ]]; then
        chown -R "$USER:$GROUP" "$PROD_DIR"
        chown -R "$USER:$GROUP" "$LOG_DIR"
        chown -R "$USER:$GROUP" "$SSL_DIR"
        chown -R "$USER:$GROUP" "$WEBSITE_DIR"
        chown -R "$USER:www-data" "$UPLOADS_DIR" 2>/dev/null || true
    else
        sudo chown -R "$USER:$GROUP" "$PROD_DIR"
        sudo chown -R "$USER:$GROUP" "$LOG_DIR"
        sudo chown -R "$USER:$GROUP" "$SSL_DIR"
        sudo chown -R "$USER:$GROUP" "$WEBSITE_DIR"
        sudo chown -R "$USER:www-data" "$UPLOADS_DIR" 2>/dev/null || true
    fi

    # Permisos
    if [[ $EUID -eq 0 ]]; then
        chmod 750 "$PROD_DIR" "$WEBSITE_DIR" "$SSL_DIR"
        chmod 2750 "$UPLOADS_DIR" 2>/dev/null || true
    chmod 755 "$BACKUP_DIR"
    else
        sudo chmod 750 "$PROD_DIR" "$WEBSITE_DIR" "$SSL_DIR"
        sudo chmod 2750 "$UPLOADS_DIR" 2>/dev/null || true
        sudo chmod 755 "$BACKUP_DIR"
    fi

    log "$ANSI_GREEN" "INFO" "$(format_text "$(get_text 'service_permissions_set' 'Permisos del servicio configurados para el usuario {user}')" "user=$USER")"
}

# Escribir /etc/hostberry/app.env
write_app_env() {
    log "$ANSI_YELLOW" "INFO" "$(get_text "writing_app_env" "Escribiendo archivo de entorno de la aplicación optimizado para RPi 3...")"
    local env_path="$CONFIG_DIR/app.env"
    if [[ $EUID -eq 0 ]]; then
        install -d -m 0755 -o root -g root "$CONFIG_DIR"
        cat > "$env_path" << EOF
# HostBerry application environment - Optimizado para RPi 3
ENVIRONMENT=${ENVIRONMENT:-production}
HOST=${PROD_HOST}
PORT=${PROD_PORT}
LOG_LEVEL=${LOG_LEVEL}
WORKERS=${WORKERS}
# Additional
PYTHONPATH=${PROD_DIR}
# Database
DATABASE_URL=sqlite:///var/lib/hostberry/hostberry.db
DB_PATH=/var/lib/hostberry/hostberry.db
RPI_OPTIMIZATION=true
# Optimizaciones para RPi 3
PYTHONOPTIMIZE=2
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1
# Configuración de caché optimizada
CACHE_TTL=300
MAX_CONNECTIONS=50
EOF
        chmod 640 "$env_path"
        chown root:root "$env_path"
    else
        sudo install -d -m 0755 -o root -g root "$CONFIG_DIR"
        sudo bash -c "cat > '$env_path' << 'EOF'
# HostBerry application environment - Optimizado para RPi 3
ENVIRONMENT=${ENVIRONMENT:-production}
HOST=${PROD_HOST}
PORT=${PROD_PORT}
LOG_LEVEL=${LOG_LEVEL}
WORKERS=${WORKERS}
# Additional
PYTHONPATH=${PROD_DIR}
# Database
DATABASE_URL=sqlite:///var/lib/hostberry/hostberry.db
DB_PATH=/var/lib/hostberry/hostberry.db
RPI_OPTIMIZATION=true
# Optimizaciones para RPi 3
PYTHONOPTIMIZE=2
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1
# Configuración de caché optimizada
CACHE_TTL=300
MAX_CONNECTIONS=50
EOF"
        sudo chmod 640 "$env_path"
        sudo chown root:root "$env_path"
    fi
log "$ANSI_GREEN" "INFO" "$(format_text "$(get_text "app_env_written" "Archivo de entorno optimizado escrito en {path}")" "path=$env_path")"
}

setup_polkit_rules() { :; }

setup_secure_sudoers() {
    log "$ANSI_YELLOW" "INFO" "$(get_text 'setup_secure_sudoers_msg' 'Configuring secure sudoers with timeout and logging...')"
    
    # Crear archivo sudoers más seguro
    cat > /etc/sudoers.d/hostberry-secure << EOF
# Reglas sudo seguras para HostBerry (con timeout y logging)
Defaults:hostberry timestamp_timeout=5
Defaults:hostberry logfile=/var/log/sudo-hostberry.log
Defaults:hostberry log_year, log_host, syslog=auth

# Grupo hostberry puede gestionar el servicio del sistema
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/systemctl start hostberry
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop hostberry
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart hostberry
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/systemctl status hostberry
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/systemctl enable hostberry
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/systemctl disable hostberry
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u hostberry --no-pager -n 50

# Comandos específicos sin wildcards
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/nginx -t
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload nginx
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart nginx

# Comandos críticos requieren contraseña
%hostberry ALL=(ALL) /usr/bin/apt-get update
%hostberry ALL=(ALL) /usr/bin/apt-get install --only-upgrade *
%hostberry ALL=(ALL) /usr/bin/apt-get upgrade --only-upgrade

# Comandos específicos de seguridad
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/ufw status
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/ufw allow 80/tcp
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/ufw allow 443/tcp
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/fail2ban-client status
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/fail2ban-client reload

# Comandos de configuración específicos
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/systemctl daemon-reload
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/ln -sf /etc/nginx/sites-available/hostberry /etc/nginx/sites-enabled/
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/ln -sf /etc/nginx/sites-available/hostberry-ssl /etc/nginx/sites-enabled/
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/rm -f /etc/nginx/sites-enabled/default
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/rm -f /etc/nginx/sites-enabled/hostberry
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/rm -f /etc/nginx/sites-enabled/hostberry-ssl

# Escritura de archivos específicos
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/tee /etc/nginx/sites-available/hostberry
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/tee /etc/nginx/sites-available/hostberry-ssl
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/tee /etc/fail2ban/jail.local
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/tee /etc/logrotate.d/hostberry

# Comandos de rendimiento específicos
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/sysctl -p
%hostberry ALL=(ALL) NOPASSWD: /usr/bin/echo powersave > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
EOF

    # Crear archivo de log
    touch /var/log/sudo-hostberry.log
    chmod 640 /var/log/sudo-hostberry.log
    chown root:adm /var/log/sudo-hostberry.log
    
    # Crear grupo hostberry si no existe
    if ! getent group hostberry > /dev/null 2>&1; then
        groupadd hostberry
    fi
    
    # Agregar usuario al grupo
    usermod -a -G hostberry $USER
    
    log "$ANSI_GREEN" "SUCCESS" "$(get_text 'secure_sudoers_configured' 'Secure sudoers configured with timeout and logging')"
}

setup_min_sudoers() {
    log "$ANSI_YELLOW" "INFO" "$(get_text 'setup_min_sudoers_msg' 'Configuring minimal sudoers...')"
    cat > /etc/sudoers.d/hostberry-min << 'EOF'
# Sudoers mínimos para HostBerry
Defaults:%hostberry timestamp_timeout=2, log_year, log_host, syslog=auth

# Permitir sólo acciones indispensables sin password (wrappers controlados)
%hostberry ALL=(root) NOPASSWD: /usr/local/sbin/hostberry-safe/reload-nginx

# Nota: acciones de systemctl para hostberry se autorizan vía Polkit, no por sudoers
# Nota: para leer logs del sistema, añadir usuarios al grupo systemd-journal (sin sudo)
EOF
    chmod 440 /etc/sudoers.d/hostberry-min

    # Crear grupo hostberry si no existe y agregar usuario
    if ! getent group hostberry > /dev/null 2>&1; then
        groupadd hostberry
    fi
    usermod -a -G hostberry $REAL_USER
}

setup_root_wrappers() {
    log "$ANSI_YELLOW" "INFO" "Creando wrappers controlados para comandos root..."
    mkdir -p /usr/local/sbin/hostberry-safe
    chmod 755 /usr/local/sbin/hostberry-safe

    # Wrapper para validar y recargar nginx si la config es válida
    cat > /usr/local/sbin/hostberry-safe/reload-nginx << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
if /usr/bin/nginx -t; then
  exec /usr/bin/systemctl reload nginx
else
  echo "Configuración Nginx inválida" >&2
  exit 1
fi
EOF
    chmod 750 /usr/local/sbin/hostberry-safe/reload-nginx

  # Wrapper para reiniciar servicio de hostberry validando existencia (optimizado)
  cat > /usr/local/sbin/hostberry-safe/restart-app << EOF
#!/usr/bin/env bash
set -euo pipefail
SERVICE="hostberry.service"
if systemctl list-units --full -all | grep -q "\b$SERVICE\b"; then
  # Usar stop y start en lugar de restart para mayor control y velocidad
  /usr/bin/systemctl stop "$SERVICE" --no-block || true
  sleep 1
  exec /usr/bin/systemctl start "$SERVICE"
else
  echo "Servicio $SERVICE no existe" >&2
  exit 1
fi
EOF
    chmod 750 /usr/local/sbin/hostberry-safe/restart-app
}

setup_systemd_user_services() {
    log "$ANSI_YELLOW" "INFO" "$(get_text 'setup_systemd_user_services' 'Configuring systemd user services (safer)...')"
    
    # Habilitar lingering para el usuario (permite servicios sin login)
    loginctl enable-linger $REAL_USER
    
    # Crear directorio para servicios de usuario
    mkdir -p /home/$REAL_USER/.config/systemd/user
    
    # Crear servicio de usuario para hostberry (referencia, pero preferimos system service)
    cat > /home/$REAL_USER/.config/systemd/user/hostberry.service << EOF
[Unit]
Description=HostBerry Web Application
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROD_DIR
ExecStart=$VENV_DIR/bin/uvicorn --app-dir $PROD_DIR main:app --host 127.0.0.1 --port $PROD_PORT
Restart=always
RestartSec=10
Environment=PYTHONPATH=$PROD_DIR

[Install]
WantedBy=default.target
EOF

    # Configurar permisos
    chown -R $REAL_USER:$REAL_USER /home/$REAL_USER/.config/systemd
    chmod 755 /home/$REAL_USER/.config/systemd/user
    
    # Habilitar y iniciar el servicio
    sudo -u $REAL_USER systemctl --user enable hostberry.service
    sudo -u $REAL_USER systemctl --user start hostberry.service
    
    log "$ANSI_GREEN" "SUCCESS" "Servicio de usuario systemd configurado para hostberry"
}

# Instalar dependencias del sistema (optimizada)
install_system_deps() {
    log "$ANSI_YELLOW" "INFO" "$(get_text "installing_deps" "Instalando dependencias del sistema...")"
    
    # Dependencias esenciales optimizadas para RPi 3
    local deps=(
        "python3" "python3-pip" "python3-venv" "python3-dev"
        "build-essential" "git" "curl" "nginx" "ufw"
        "fail2ban" "logrotate" "htop" "openssl" "jq" "rsync" "libnss3-tools"
        "libffi-dev" "libssl-dev"
    )
    
    # Actualizar repositorios e instalar dependencias
    if [[ $EUID -eq 0 ]]; then
        apt-get update || die "$(get_text "apt_update_failed" "No se pudo actualizar apt-get")"
        apt-get install -y "${deps[@]}" || die "$(get_text "deps_failed" "No se pudieron instalar las dependencias")"
    else
        sudo apt-get update || die "$(get_text "apt_update_failed" "No se pudo actualizar apt-get")"
        sudo apt-get install -y "${deps[@]}" || die "$(get_text "deps_failed" "No se pudieron instalar las dependencias")"
    fi
    
    # Instalar mkcert si no está disponible
    if ! command -v mkcert &> /dev/null; then
        local installing_mkcert=$(get_text "installing_mkcert" "Instalando mkcert...")
        log "$ANSI_YELLOW" "INFO" "$installing_mkcert"
        # Descargar e instalar mkcert
        local MKCERT_VERSION="v1.4.4"
        local MKCERT_ARCH="linux-amd64"
        
        # Detectar arquitectura
        if [ "$(uname -m)" = "aarch64" ] || [ "$(uname -m)" = "arm64" ]; then
            MKCERT_ARCH="linux-arm64"
        elif [ "$(uname -m)" = "armv7l" ]; then
            MKCERT_ARCH="linux-arm"
        fi
        
        if [[ $EUID -eq 0 ]]; then
            curl -L "https://github.com/FiloSottile/mkcert/releases/download/${MKCERT_VERSION}/mkcert-${MKCERT_VERSION}-${MKCERT_ARCH}" \
                -o /usr/local/bin/mkcert || handle_error "$(get_text 'mkcert_download_failed' 'No se pudo descargar mkcert')"
            
            chmod +x /usr/local/bin/mkcert || handle_error "$(get_text 'mkcert_chmod_failed' 'No se pudo hacer ejecutable mkcert')"
            
            # Instalar CA root
            mkcert -install || log "$ANSI_YELLOW" "WARN" "$(get_text "mkcert_ca_warning" "No se pudo instalar la CA raíz de mkcert")"
        else
            sudo curl -L "https://github.com/FiloSottile/mkcert/releases/download/${MKCERT_VERSION}/mkcert-${MKCERT_VERSION}-${MKCERT_ARCH}" \
                -o /usr/local/bin/mkcert || handle_error "$(get_text 'mkcert_download_failed' 'No se pudo descargar mkcert')"
            
            sudo chmod +x /usr/local/bin/mkcert || handle_error "$(get_text 'mkcert_chmod_failed' 'No se pudo hacer ejecutable mkcert')"
            
            # Instalar CA root
            sudo mkcert -install || log "$ANSI_YELLOW" "WARN" "$(get_text "mkcert_ca_warning" "No se pudo instalar la CA raíz de mkcert")"
        fi
        
        log "$ANSI_GREEN" "INFO" "$(get_text "mkcert_installed" "mkcert instalado correctamente")"
    fi
    
    log "$ANSI_GREEN" "INFO" "$(get_text "deps_installed" "Dependencias del sistema instaladas")"
}

# Limpiar instalación anterior completamente (optimizada)
clean_previous_installation() {
    log "$ANSI_YELLOW" "INFO" "$(get_text 'cleaning_previous_installation' '🧹 Limpiando instalación anterior de HostBerry...')"
    
    # Crear backup de /opt/hostberry si existe
    if [[ -d "/opt/hostberry" ]]; then
        local backup_dir="$REAL_HOME/hostberry_backup_$(date +%Y%m%d_%H%M%S)"
        log "$ANSI_YELLOW" "INFO" "Creando backup en $backup_dir"
        cp -r "/opt/hostberry" "$backup_dir" || {
            log "$ANSI_YELLOW" "WARN" "No se pudo crear backup, continuando sin él"
        }
    fi
    
    # Detener servicio si está activo
    systemctl is-active --quiet hostberry 2>/dev/null && {
        systemctl stop hostberry 2>/dev/null || true
        systemctl disable hostberry 2>/dev/null || true
    }
    
    # Eliminar unit de systemd
    [[ -f "/etc/systemd/system/hostberry.service" ]] && {
        rm -f "/etc/systemd/system/hostberry.service"
        systemctl daemon-reload 2>/dev/null || true
    }

    # Eliminar directorios de la app y datos
    local dirs=("/opt/hostberry" "/var/log/hostberry" "/var/lib/hostberry" "/etc/hostberry")
    local dir
    for dir in "${dirs[@]}"; do
        [[ -e "$dir" ]] && rm -rf "$dir"
    done

    # Nginx sites
    local nginx_files=(
        "/etc/nginx/sites-available/hostberry"
        "/etc/nginx/sites-available/hostberry-ssl"
        "/etc/nginx/sites-enabled/hostberry"
        "/etc/nginx/sites-enabled/hostberry-ssl"
    )
    local f
    for f in "${nginx_files[@]}"; do
        [[ -e "$f" ]] && rm -f "$f"
    done

    # Logs de nginx relacionados
    local log_files=(
        "/var/log/nginx/hostberry_access.log"
        "/var/log/nginx/hostberry_error.log"
        "/var/log/nginx/hostberry_ssl_access.log"
        "/var/log/nginx/hostberry_ssl_error.log"
    )
    local lf
    for lf in "${log_files[@]}"; do
        [[ -e "$lf" ]] && rm -f "$lf"
    done

    # logrotate/fail2ban reglas
    [[ -f "/etc/logrotate.d/hostberry" ]] && rm -f "/etc/logrotate.d/hostberry"
    [[ -f "/etc/fail2ban/jail.local" ]] && rm -f "/etc/fail2ban/jail.local"

    log "$ANSI_GREEN" "INFO" "$(get_text 'cleanup_done' '✅ Limpieza completa realizada')"
}

# Descargar/actualizar aplicación desde GitHub (repo oficial)
download_application_from_github() {
    local UPDATE_MODE="${1:-false}"
    local GITHUB_REPO="https://github.com/aka0kuro/hostberry.git"
    local TEMP_DIR="/tmp/hostberry_download_$$"
    local VENV_BACKUP=""

    if [ "$UPDATE_MODE" = "true" ]; then
        log "$ANSI_YELLOW" "INFO" "$(get_text "updating_app" "Actualizando aplicación desde GitHub...")"
    else
        log "$ANSI_YELLOW" "INFO" "$(get_text "downloading_app" "Descargando aplicación desde GitHub...")"
    fi

    mkdir -p "$PROD_DIR"

    if [ "$UPDATE_MODE" = "true" ] && [ -d "$PROD_DIR/.git" ]; then
        # Actualizar repo existente en /opt/hostberry
        (
            cd "$PROD_DIR"
            # Backup de config (por seguridad)
            [ -d config ] && cp -r config "/tmp/hostberry_config_backup_$$" 2>/dev/null || true
            git fetch origin main || handle_error "$(get_text 'git_fetch_failed' 'No se pudo actualizar desde GitHub')"
            git reset --hard origin/main || handle_error "$(get_text 'git_reset_failed' 'No se pudo resetear a la versión más reciente')"
            # Restaurar config si se corrompió
            if [ ! -d config ] || [ ! -f config/settings.py ]; then
                if [ -d "/tmp/hostberry_config_backup_$$" ]; then
                    rm -rf config 2>/dev/null || true
                    cp -r "/tmp/hostberry_config_backup_$$" config
                    log "$ANSI_YELLOW" "WARN" "Config restaurado desde backup"
                fi
            fi
            rm -rf "/tmp/hostberry_config_backup_$$" 2>/dev/null || true
        )
    else
        # Clonación limpia preservando venv en UPDATE
        if [ "$UPDATE_MODE" = "true" ] && [ -d "$VENV_DIR" ]; then
            VENV_BACKUP="/tmp/hostberry_venv_backup_$$"
            mv "$VENV_DIR" "$VENV_BACKUP"
        fi
        rm -rf "$PROD_DIR"
        mkdir -p "$PROD_DIR" "$TEMP_DIR"
        git clone --depth 1 --branch main "$GITHUB_REPO" "$TEMP_DIR/hostberry" || handle_error "$(get_text 'git_clone_failed' 'No se pudo clonar el repositorio desde GitHub')"
        rsync -a --delete --exclude='venv' "$TEMP_DIR/hostberry"/ "$PROD_DIR"/ || handle_error "$(get_text 'copy_failed' 'No se pudo copiar archivos al directorio de producción')"
        rm -rf "$TEMP_DIR"
        # Restaurar venv si se había respaldado
        if [ -n "$VENV_BACKUP" ] && [ -d "$VENV_BACKUP" ]; then
            mv "$VENV_BACKUP" "$VENV_DIR"
        fi
    fi

    # Verificar config
    if ! verify_config_integrity "$PROD_DIR" "descarga"; then
        handle_error "$(get_text 'config_corrupted_download' 'El directorio config se corrompió durante la descarga')"
    fi

    # Permisos básicos
    chmod 755 "$PROD_DIR"
    [ -d "$PROD_DIR/config" ] && chmod 755 "$PROD_DIR/config" && chmod 644 "$PROD_DIR/config"/*.py 2>/dev/null || true
    chown -R "$USER:$GROUP" "$PROD_DIR" 2>/dev/null || true

    # .env por defecto si falta
    if [ ! -f "$PROD_DIR/.env" ]; then
        cat > "$PROD_DIR/.env" << EOF
# Configuración de producción para HostBerry
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=WARNING
WORKERS=1
EOF
        chown "$USER:$GROUP" "$PROD_DIR/.env" 2>/dev/null || true
        chmod 600 "$PROD_DIR/.env" 2>/dev/null || true
    fi

    log "$ANSI_GREEN" "INFO" "$(get_text "download_permissions_set" "Permisos y propietarios configurados correctamente")"
}

# Copiar aplicación a directorio de producción
copy_application_to_production() {
    local UPDATE_MODE="${1:-false}"
    
    if [ "$UPDATE_MODE" = "true" ]; then
        log "$ANSI_YELLOW" "INFO" "$(get_text "updating_app" "Actualizando solo archivos modificados en producción...")"
    else
        log "$ANSI_YELLOW" "INFO" "$(get_text "copying_app" "Copiando la aplicación al directorio de producción...")"
    fi
    
    # Crear directorio de producción si no existe
    mkdir -p "$PROD_DIR"
    
    # Obtener el directorio actual (donde está el script)
    local CURRENT_DIR=$(pwd)
    
    # Verificar que el directorio config esté intacto antes de copiar
    if ! verify_config_integrity "$CURRENT_DIR" "origen"; then
        handle_error "$(get_text 'config_corrupted_source' 'El directorio config en el origen está corrupto o no existe')"
    fi
    
    # Determinar qué archivos copiar basado en el modo
    if [ "$UPDATE_MODE" = "true" ]; then
        # Modo UPDATE: Solo archivos modificados y nuevos
        log "$ANSI_YELLOW" "INFO" "$(format_text "$(get_text "updating_files_from_to" "Actualizando archivos modificados de {from} a {to}...")" "from=$CURRENT_DIR" "to=$PROD_DIR")"
        
        # Usar rsync con --update para solo archivos modificados
        if command -v rsync &> /dev/null; then
            # Crear backup del directorio config antes de actualizar
            if [ -d "$PROD_DIR/config" ]; then
                cp -r "$PROD_DIR/config" "$PROD_DIR/config.backup.$(date +%s)" 2>/dev/null || true
            fi
            
            # Usar rsync con opciones más seguras
            rsync -av --update --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='.gitignore' --exclude='node_modules' --exclude='.env' --exclude='setup.sh' --exclude='locales/' --exclude='*.log' --exclude='*.db' --exclude='config.backup.*' "$CURRENT_DIR/" "$PROD_DIR/" || handle_error "$(get_text 'update_failed_rsync' 'No se pudo actualizar la aplicación con rsync')"
            
            # Verificar que config se copió correctamente
            if [ ! -d "$PROD_DIR/config" ] || [ ! -f "$PROD_DIR/config/settings.py" ]; then
                log "$ANSI_YELLOW" "WARN" "$(get_text 'config_update_failed' 'Fallback: restaurando config desde backup...')"
                if [ -d "$PROD_DIR/config.backup.$(date +%s)" ]; then
                    rm -rf "$PROD_DIR/config"
                    cp -r "$PROD_DIR/config.backup.$(date +%s)" "$PROD_DIR/config"
                fi
            fi
        else
            # Fallback: copiar solo archivos Python y web principales
            log "$ANSI_YELLOW" "INFO" "$(get_text "update_fallback_cp" "rsync no disponible, usando cp para archivos principales...")"
            for dir in "core" "api" "models" "website" "config" "main.py" "requirements.txt"; do
                if [ -e "$CURRENT_DIR/$dir" ]; then
                    # Crear backup del directorio config antes de actualizar
                    if [ "$dir" = "config" ] && [ -d "$PROD_DIR/config" ]; then
                        cp -r "$PROD_DIR/config" "$PROD_DIR/config.backup.$(date +%s)" 2>/dev/null || true
                    fi
                    
                    cp -r "$CURRENT_DIR/$dir" "$PROD_DIR/" 2>/dev/null || log "$ANSI_YELLOW" "WARN" "$(format_text "$(get_text "update_file_failed" "No se pudo actualizar {file}")" "file=$dir")"
                    
                    # Verificar que config se copió correctamente
                    if [ "$dir" = "config" ] && [ ! -d "$PROD_DIR/config" ] || [ ! -f "$PROD_DIR/config/settings.py" ]; then
                        log "$ANSI_YELLOW" "WARN" "$(get_text 'config_update_failed' 'Fallback: restaurando config desde backup...')"
                        if [ -d "$PROD_DIR/config.backup.$(date +%s)" ]; then
                            rm -rf "$PROD_DIR/config"
                            cp -r "$PROD_DIR/config.backup.$(date +%s)" "$PROD_DIR/config"
                        fi
                    fi
                fi
            done
        fi
        
        log "$ANSI_GREEN" "INFO" "$(get_text "app_updated" "Aplicación actualizada en {dir}")" "dir=$PROD_DIR"
    else
        # Modo INSTALL: Copiar todos los archivos
        log "$ANSI_YELLOW" "INFO" "$(format_text "$(get_text "copying_files_from_to" "Copiando archivos de {from} a {to}...")" "from=$CURRENT_DIR" "to=$PROD_DIR")"
        
        # Usar rsync si está disponible, sino usar cp
        if command -v rsync &> /dev/null; then
            # Usar rsync con opciones más seguras
            rsync -av --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='.gitignore' --exclude='node_modules' --exclude='.env' --exclude='config.backup.*' "$CURRENT_DIR/" "$PROD_DIR/" || handle_error "$(get_text 'copy_failed_rsync' 'Could not copy application with rsync')"
        else
            # Fallback con cp - más seguro
            for item in "$CURRENT_DIR"/*; do
                if [ -e "$item" ]; then
                    local basename_item=$(basename "$item")
                    if [ "$basename_item" != "venv" ] && [ "$basename_item" != "__pycache__" ] && [ "$basename_item" != ".git" ] && [ "$basename_item" != ".env" ]; then
                        cp -r "$item" "$PROD_DIR/" 2>/dev/null || log "$ANSI_YELLOW" "WARN" "$(format_text "$(get_text "copy_item_failed" "No se pudo copiar {item}")" "item=$basename_item")"
                    fi
                fi
            done
        fi
        
        log "$ANSI_GREEN" "INFO" "$(format_text "$(get_text "app_copied_to" "Aplicación copiada a {dir}")" "dir=$PROD_DIR")"
    fi
    
    # Verificar que el directorio config esté intacto después de la copia
    if ! verify_config_integrity "$PROD_DIR" "destino"; then
        handle_error "$(get_text 'config_corrupted_target' 'El directorio config se corrompió durante la copia')"
    fi
    
    # Configurar permisos de manera más específica y segura
    # Directorios críticos con permisos específicos
    chmod 755 "$PROD_DIR"
    chmod 755 "$PROD_DIR/config"
    chmod 644 "$PROD_DIR/config"/*.py
    chmod 644 "$PROD_DIR/config"/*.pyi 2>/dev/null || true
    
    # Otros directorios con permisos estándar
    find "$PROD_DIR" -type d -exec chmod 755 {} \; 2>/dev/null || true
    find "$PROD_DIR" -type f -name "*.py" -exec chmod 644 {} \; 2>/dev/null || true
    find "$PROD_DIR" -type f -name "*.txt" -exec chmod 644 {} \; 2>/dev/null || true
    find "$PROD_DIR" -type f -name "*.md" -exec chmod 644 {} \; 2>/dev/null || true
    
    # Configurar propietarios
    chown -R "$USER:$GROUP" "$PROD_DIR"
    
    # Crear archivo .env de producción si no existe (solo en install)
    if [ "$UPDATE_MODE" != "true" ] && [ ! -f "$PROD_DIR/.env" ]; then
        cat > "$PROD_DIR/.env" << EOF
# Configuración de producción para HostBerry
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=WARNING
WORKERS=1
EOF
        chown "$USER:$GROUP" "$PROD_DIR/.env"
        chmod 600 "$PROD_DIR/.env"
    fi
    
    # Limpiar backups temporales
    find "$PROD_DIR" -name "config.backup.*" -type d -exec rm -rf {} \; 2>/dev/null || true
    
    log "$ANSI_GREEN" "INFO" "$(get_text "copy_permissions_set" "Permisos y propietarios configurados correctamente")"
}

# Configurar entorno virtual de producción
setup_production_venv() {
    local MODE="${1:-install}"

    log "$ANSI_YELLOW" "INFO" "$(format_text "$(get_text 'setup_venv' 'Configurando entorno virtual de producción optimizado para RPi 3 (modo: {mode})...')" "mode=$MODE")"

    # Asegurar directorio de producción
    mkdir -p "$PROD_DIR"
    chown "$USER:$GROUP" "$PROD_DIR"
    chmod 755 "$PROD_DIR"

    if [ "$MODE" = "install" ]; then
        # Instalación limpia: recrear venv
        if [ -d "$VENV_DIR" ]; then
            log "$ANSI_YELLOW" "INFO" "$(get_text 'venv_removing' 'Eliminando entorno virtual previo...')"
            rm -rf "$VENV_DIR"
        fi

run_python_venv "$VENV_DIR" || handle_error "$(get_text 'venv_failed' 'No se pudo crear el entorno virtual')"

        # Permisos del venv
        chown -R "$USER:$GROUP" "$VENV_DIR"
        chmod -R 755 "$VENV_DIR"

        # Activar venv
        source "$VENV_DIR/bin/activate"

        # Configuración de pip optimizada para RPi 3
        cat > "$VENV_DIR/pip.conf" << EOF
[global]
index-url = https://pypi.org/simple
trusted-host = pypi.org
extra-index-url = 
# Optimizaciones para RPi 3
timeout = 120
retries = 3
no-cache-dir = true
EOF

        # Actualizar herramientas de empaquetado
        python -m pip install --upgrade "pip<25.0" setuptools wheel \
            --index-url https://pypi.org/simple \
            --retries 5 \
            --timeout 60 || handle_error "$(get_text 'pip_update_failed' 'Could not update pip')"

        # Instalar dependencias de producción
        if [ -f "requirements.txt" ]; then
            log "$ANSI_YELLOW" "INFO" "$(get_text 'installing_prod_deps' 'Instalando dependencias de producción...')"

            # Instalar pytz desde PyPI para evitar advertencias de deprecación
            python -m pip install pytz==2023.4 \
                --index-url https://pypi.org/simple \
                --retries 5 \
                --timeout 60 \
                --prefer-binary || handle_error "$(get_text 'pytz_install_failed' 'No se pudo instalar pytz')"

            # Instalar el resto de dependencias
            python -m pip install -r requirements.txt \
                --index-url https://pypi.org/simple \
                --retries 5 \
                --timeout 60 \
                --prefer-binary || handle_error "$(get_text 'deps_failed' 'No se pudieron instalar las dependencias')"
        else
            log "$ANSI_YELLOW" "WARN" "$(get_text 'requirements_not_found' 'No se encontró requirements.txt, instalando dependencias básicas...')"
            python -m pip install fastapi uvicorn python-multipart \
                --index-url https://pypi.org/simple \
                --retries 5 \
                --timeout 60 \
                --prefer-binary || handle_error "$(get_text 'basic_deps_failed' 'No se pudieron instalar las dependencias básicas')"
        fi
    else
        # Modo actualización: NO borrar venv, solo actualizar pip si existe; crear si falta
        if [ -d "$VENV_DIR" ]; then
            log "$ANSI_YELLOW" "INFO" "$(get_text 'venv_exists' 'Se detectó un entorno virtual existente. No será eliminado.')"
        else
            log "$ANSI_YELLOW" "INFO" "$(get_text 'venv_creating' 'No existe un entorno virtual. Creándolo...')"
run_python_venv "$VENV_DIR" || handle_error "$(get_text 'venv_failed' 'No se pudo crear el entorno virtual')"
            chown -R "$USER:$GROUP" "$VENV_DIR"
            chmod -R 755 "$VENV_DIR"
        fi

        # Activar venv
        source "$VENV_DIR/bin/activate"

        # Asegurar configuración de pip
        if [ ! -f "$VENV_DIR/pip.conf" ]; then
            cat > "$VENV_DIR/pip.conf" << EOF
[global]
index-url = https://pypi.org/simple
trusted-host = pypi.org
extra-index-url = 
EOF
        fi

        # Solo actualizar pip (si está desactualizado, pip hará la actualización; si no, no cambia nada)
        log "$ANSI_YELLOW" "INFO" "$(get_text 'pip_updating' 'Actualizando pip dentro del entorno virtual...')"
        python -m pip install --upgrade "pip<25.0" \
            --index-url https://pypi.org/simple \
            --retries 5 \
            --timeout 60 || handle_error "$(get_text 'pip_update_failed' 'No se pudo actualizar pip')"

        if [ -f "$PROD_DIR/requirements.txt" ]; then
            log "$ANSI_YELLOW" "INFO" "$(get_text 'installing_prod_deps' 'Instalando dependencias de producción...')"
            python -m pip install -r "$PROD_DIR/requirements.txt" \
                --index-url https://pypi.org/simple \
                --retries 5 \
                --timeout 60 \
                --prefer-binary || handle_error "$(get_text 'deps_failed' 'No se pudieron instalar las dependencias')"
        fi

        python -c "import uvicorn" 2>/dev/null || {
            python -m pip install uvicorn==0.24.0 \
                --index-url https://pypi.org/simple \
                --retries 5 \
                --timeout 60 \
                --prefer-binary || handle_error "$(get_text 'deps_failed' 'No se pudieron instalar las dependencias')"
        }

        log "$ANSI_GREEN" "INFO" "$(get_text 'venv_updated' 'Entorno virtual actualizado (pip verificado)')"
    fi

    log "$ANSI_GREEN" "INFO" "$(get_text 'venv_created' 'Entorno virtual de producción configurado')"
}

# Configurar directorios de producción
setup_production_dirs() {
    log "$ANSI_YELLOW" "INFO" "$(get_text "setup_dirs" "Configurando directorios de producción...")"
    
    # Crear directorios necesarios
    local dirs=(
        "$LOG_DIR"
        "$CONFIG_DIR"
        "$PROD_DIR/instance"
        "$PROD_DIR/instance/jinja_cache"
        "/var/lib/hostberry"
        "$UPLOADS_DIR"
        "$PROD_DIR/cache"
        "$PROD_DIR/backups"
        "$WEBSITE_DIR/static"
        "$WEBSITE_DIR/templates"
        "$SSL_DIR"
    )
    
    for dir in "${dirs[@]}"; do
        install -d -m 0755 -o "$USER" -g "$GROUP" "$dir"
    done
    
    # Endurecer permisos de la caché de Jinja2
    if [ -d "$PROD_DIR/instance/jinja_cache" ]; then
        chmod 700 "$PROD_DIR/instance/jinja_cache"
    fi
    
    # Crear archivos de log y enlazar directorio de logs dentro de /opt
    touch "$LOG_DIR/access.log" "$LOG_DIR/error.log" "$LOG_DIR/app.log" "$LOG_DIR/hostberry.log"
    chown "$USER:$GROUP" "$LOG_DIR"/*.log
    chmod 644 "$LOG_DIR"/*.log
    
    # Asegurar que /opt/hostberry/logs apunta a /var/log/hostberry para evitar errores de FS de solo lectura
    if [ -L "$PROD_DIR/logs" ] || [ -d "$PROD_DIR/logs" ]; then
        rm -rf "$PROD_DIR/logs"
    fi
    ln -s "$LOG_DIR" "$PROD_DIR/logs"

    # Reubicar base de datos SQLite fuera de /opt (solo lectura) a /var/lib/hostberry
    DB_FILE="/var/lib/hostberry/hostberry.db"
    # Asegurar archivo y permisos
    touch "$DB_FILE"
    chown "$USER:$GROUP" "$DB_FILE"
    chmod 0640 "$DB_FILE"
    # Enlazar desde /opt/hostberry para compatibilidad con el código actual
    if [ -e "$PROD_DIR/hostberry.db" ] && [ ! -L "$PROD_DIR/hostberry.db" ]; then
        mv -f "$PROD_DIR/hostberry.db" "$DB_FILE" 2>/dev/null || true
    fi
    ln -sf "$DB_FILE" "$PROD_DIR/hostberry.db"
    
    log "$ANSI_GREEN" "INFO" "$(get_text "dirs_configured" "Directorios de producción configurados")"
}

# Crear script wrapper genérico
create_startup_script() {
log "$ANSI_YELLOW" "INFO" "$(get_text \"creating_wrapper\" \"Creando script wrapper genérico...\")"
    
    cat > "$PROD_DIR/start_hostberry.sh" << 'EOF'
#!/bin/bash

# Script wrapper genérico para iniciar HostBerry
# Este script se ejecuta desde el directorio de trabajo configurado en systemd

# Obtener el directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Verificar que existe main.py
if [ ! -f "main.py" ]; then
    echo "ERROR: No se encontró main.py en $SCRIPT_DIR"
    exit 1
fi

# Verificar que existe requirements.txt
if [ ! -f "requirements.txt" ]; then
    echo "ERROR: No se encontró requirements.txt en $SCRIPT_DIR"
    exit 1
fi

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Instalar dependencias si no están instaladas
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Instalando dependencias..."
    pip3 install -r requirements.txt
fi

# Iniciar la aplicación vía uvicorn (sin reload en producción)
echo "Iniciando HostBerry en puerto ${PORT:-8000}..."
exec python3 -m uvicorn main:app --host 127.0.0.1 --port "${PORT:-8000}" --workers "${WORKERS:-1}"
EOF
    
    chmod +x "$PROD_DIR/start_hostberry.sh"
    chown "$USER:$GROUP" "$PROD_DIR/start_hostberry.sh"
    
log "$ANSI_GREEN" "INFO" "$(get_text \"wrapper_created\" \"Script wrapper creado\")"
}

# Configurar servicio systemd genérico
setup_systemd_service() {
    log "$ANSI_YELLOW" "INFO" "$(get_text "setup_service" "Configurando servicio systemd optimizado...")"
    
            # Crear el archivo de servicio genérico para cualquier usuario
        # Nota: heredoc sin comillas para expandir variables como $PROD_PORT
        cat > /tmp/hostberry_service.tmp << EOF
[Unit]
Description=HostBerry FastAPI Service
After=network.target

[Service]
Type=simple
User=$USER
Group=$GROUP
WorkingDirectory=$PROD_DIR
EnvironmentFile=-/etc/hostberry/app.env
Environment=DATABASE_URL=sqlite:///var/lib/hostberry/hostberry.db
Environment=DB_PATH=/var/lib/hostberry/hostberry.db
Environment=ENVIRONMENT=production
Environment=LOG_LEVEL=$LOG_LEVEL
Environment=PYTHONPATH=$PROD_DIR
Environment=UVICORN_NO_UVLOOP=1
Environment=UVICORN_NO_HTTPTOOLS=1
Environment=HOSTBERRY_SKIP_RUNTIME_OPTIMIZE=1
# Configuración optimizada para RPi 3
ExecStart=$VENV_DIR/bin/python -m uvicorn --app-dir $PROD_DIR main:app --host 127.0.0.1 --port $PROD_PORT --workers $WORKERS --loop asyncio --http h11 --log-level $LOG_LEVEL --limit-concurrency 100 --limit-max-requests 1000
Restart=always
RestartSec=2
# Timeouts optimizados para reinicio rápido
TimeoutStartSec=15
TimeoutStopSec=10
KillMode=mixed
KillSignal=SIGTERM
StandardOutput=journal
StandardError=journal
# Optimizaciones de recursos
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
MemoryDenyWriteExecute=true
RemoveIPC=true
SystemCallArchitectures=native
SystemCallFilter=@system-service
ReadWritePaths=/var/lib/hostberry/uploads /var/log/hostberry /var/lib/hostberry
# Límites de recursos para RPi 3
MemoryMax=256M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF
    
    # Copiar el archivo de servicio al sistema
    if [[ $EUID -eq 0 ]]; then
        cp /tmp/hostberry_service.tmp "/etc/systemd/system/hostberry.service" || handle_error "$(get_text 'service_copy_failed' 'Could not copy systemd service file')"
        chmod 644 "/etc/systemd/system/hostberry.service"

        # Deshabilitar y eliminar unidades antiguas que no deben existir
        systemctl disable --now hostberry@root.service 2>/dev/null || true
        systemctl disable --now hostberry-fastapi.service 2>/dev/null || true

        # Deshabilitar servicio de usuario si existiera y eliminar archivo del usuario
        su - $REAL_USER -c "systemctl --user disable --now hostberry.service" 2>/dev/null || true
        rm -f "/home/$REAL_USER/.config/systemd/user/hostberry.service" 2>/dev/null || true

        systemctl daemon-reload
        systemctl enable hostberry.service
    else
        sudo cp /tmp/hostberry_service.tmp "/etc/systemd/system/hostberry.service" || handle_error "$(get_text 'service_copy_failed' 'Could not copy systemd service file')"
        sudo chmod 644 "/etc/systemd/system/hostberry.service"

        # Deshabilitar y eliminar unidades antiguas que no deben existir
        sudo systemctl disable --now hostberry@root.service 2>/dev/null || true
        sudo systemctl disable --now hostberry-fastapi.service 2>/dev/null || true

        # Deshabilitar servicio de usuario si existiera y eliminar archivo del usuario
        sudo -u "$REAL_USER" systemctl --user disable --now hostberry.service 2>/dev/null || true
        sudo rm -f "/home/$REAL_USER/.config/systemd/user/hostberry.service" 2>/dev/null || true

        sudo systemctl daemon-reload
        sudo systemctl enable hostberry.service
    fi
    
    # Limpiar archivo temporal
    rm -f /tmp/hostberry_service.tmp
    
    log "$ANSI_GREEN" "INFO" "$(get_text "service_configured" "Servicio systemd configurado y habilitado")"
}

# Configurar Nginx como proxy reverso
setup_nginx() {
    log "$ANSI_YELLOW" "INFO" "$(get_text "setup_nginx" "Configurar Nginx como proxy inverso...")"

    # Renderizar sitio HTTP con envsubst
    log "$ANSI_YELLOW" "INFO" "$(get_text "rendering_nginx_http" "Renderizando sitio HTTP de Nginx...")"
    local HTTP_CONF_TPL='server {
    listen 80;
    server_name _;
    
    # Logs
    access_log /var/log/nginx/hostberry_access.log;
    error_log /var/log/nginx/hostberry_error.log;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src '\''self'\''; script-src '\''self'\'' '\''unsafe-inline'\'' '\''unsafe-eval'\''; style-src '\''self'\'' '\''unsafe-inline'\''; img-src '\''self'\'' data:; font-src '\''self'\''; connect-src '\''self'\''; frame-ancestors '\''self'\''" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/javascript application/json font/svg+xml image/svg+xml;
    gzip_disable "MSIE [1-6]\.";
    
    location / {
        proxy_pass http://127.0.0.1:${PROD_PORT};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # Timeouts optimizados para RPi 3
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        # Buffers optimizados para RPi 3
        proxy_buffering on;
        proxy_buffer_size 2k;
        proxy_buffers 4 2k;
        proxy_busy_buffers_size 4k;
        # Optimizaciones adicionales
        proxy_cache_bypass $http_upgrade;
        proxy_no_cache $http_upgrade;
    }
    
    location /static/ {
        alias ${WEBSITE_DIR}/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /uploads/ {
        alias ${UPLOADS_DIR}/;
        expires 1d;
        add_header Cache-Control "public";
    }
    
    location ~ /\.|~$ { deny all; }
}
'
    # Escribir el HTTP vhost directamente con heredoc para evitar sed
    if [[ $EUID -eq 0 ]]; then
        cat > /etc/nginx/sites-available/hostberry << EOF
server {
    listen 80;
    server_name _;
    
    access_log /var/log/nginx/hostberry_access.log;
    error_log /var/log/nginx/hostberry_error.log;
    
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/javascript application/json font/svg+xml image/svg+xml;
    gzip_disable "MSIE [1-6]\.";
    
    location / {
        proxy_pass http://127.0.0.1:${PROD_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    location /static/ {
        alias ${WEBSITE_DIR}/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /uploads/ {
        alias ${UPLOADS_DIR}/;
        expires 1d;
        add_header Cache-Control "public";
    }
    
    location ~ /\.|~$ { deny all; }
}
EOF
        : <<'NGINX_HTTP_OLD'
server {
    listen 80;
    server_name _;
    
    # Logs
    access_log /var/log/nginx/hostberry_access.log;
    error_log /var/log/nginx/hostberry_error.log;
    
    # Configuración de seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    
    # Configuración de proxy
    location / {
        proxy_pass http://127.0.0.1:$PROD_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffers
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # Configuración para archivos estáticos
    location /static/ {
        alias $WEBSITE_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Configuración para uploads
    location /uploads/ {
        alias $UPLOADS_DIR/;
        expires 1d;
        add_header Cache-Control "public";
    }
    
    # Configuración de seguridad adicional
    location ~ /\. {
        deny all;
    }
    
    location ~ ~$ {
        deny all;
    }
}
NGINX_HTTP_OLD
    else
        sudo bash -c "cat > /etc/nginx/sites-available/hostberry << 'EOF'
server {
    listen 80;
    server_name _;

    access_log /var/log/nginx/hostberry_access.log;
    error_log /var/log/nginx/hostberry_error.log;

    add_header X-Frame-Options \"SAMEORIGIN\" always;
    add_header X-XSS-Protection \"1; mode=block\" always;
    add_header X-Content-Type-Options \"nosniff\" always;
    add_header Referrer-Policy \"strict-origin-when-cross-origin\" always;
    add_header Content-Security-Policy \"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';\" always;
    add_header Permissions-Policy \"geolocation=(), microphone=(), camera=()\" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/javascript application/json font/svg+xml image/svg+xml;
    gzip_disable \"MSIE [1-6]\.\";
    
    location / {
        proxy_pass http://127.0.0.1:${PROD_PORT};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }

    location /static/ {
        alias ${WEBSITE_DIR}/static/;
        expires 1y;
        add_header Cache-Control \"public, immutable\";
    }

    location /uploads/ {
        alias ${UPLOADS_DIR}/;
        expires 1d;
        add_header Cache-Control \"public\";
    }

    location ~ /\\.|~$ { deny all; }
}
EOF"
    fi
    
    # Habilitar sitio y crear placeholder SSL para evitar fallos de include
    if [[ $EUID -eq 0 ]]; then
        ln -sf /etc/nginx/sites-available/hostberry /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default

        # Placeholder de hostberry-ssl si falta
        if [ ! -f /etc/nginx/sites-available/hostberry-ssl ]; then
            echo "# placeholder hostberry-ssl" > /etc/nginx/sites-available/hostberry-ssl
        fi
        ln -sf /etc/nginx/sites-available/hostberry-ssl /etc/nginx/sites-enabled/hostberry-ssl
        
        # Verificar configuración
nginx -t || handle_error "$(get_text 'nginx_invalid' 'Configuración de Nginx inválida')"
        
        # Reiniciar Nginx
        systemctl restart nginx
        systemctl enable nginx
    else
        sudo ln -sf /etc/nginx/sites-available/hostberry /etc/nginx/sites-enabled/
        sudo rm -f /etc/nginx/sites-enabled/default

        # Placeholder de hostberry-ssl si falta
        if [ ! -f /etc/nginx/sites-available/hostberry-ssl ]; then
            echo "# placeholder hostberry-ssl" | sudo tee /etc/nginx/sites-available/hostberry-ssl >/dev/null
        fi
        sudo ln -sf /etc/nginx/sites-available/hostberry-ssl /etc/nginx/sites-enabled/hostberry-ssl
        
        # Verificar configuración
sudo nginx -t || handle_error "$(get_text 'nginx_invalid' 'Configuración de Nginx inválida')"
        
        # Reiniciar Nginx
        sudo systemctl restart nginx
        sudo systemctl enable nginx
    fi
    
    log "$ANSI_GREEN" "INFO" "$(get_text "nginx_configured" "Nginx configurado como proxy reverso")"
}

# Configurar SSL/TLS
setup_ssl() {
    log "$ANSI_YELLOW" "INFO" "$(get_text \"setup_ssl\" \"Configurando SSL/TLS...\")"
    
    # Verificar si mkcert está disponible
    if ! command -v mkcert &> /dev/null; then
        handle_error "$(get_text \"mkcert_not_installed\" \"mkcert no está instalado. Ejecuta --install primero.\")"
    fi
    
    # Obtener IP local y hostname
    local LOCAL_IP=$(hostname -I | awk '{print $1}')
    local HOSTNAME=$(hostname)
    
    log "$ANSI_GREEN" "INFO" "$(get_text \"generating_ssl\" \"Generando certificados SSL con mkcert...\")"
    
    # Crear directorio SSL
    mkdir -p "$SSL_DIR"
    
    # Generar certificado con mkcert
    cd "$SSL_DIR" || handle_error "$(get_text 'ssl_chdir_failed' 'No se pudo cambiar al directorio SSL')"
    
    # Crear certificado para localhost, IP local y hostname
    if [[ $EUID -eq 0 ]]; then
        mkcert -key-file hostberry.key -cert-file hostberry.crt \
            "localhost" "127.0.0.1" "$LOCAL_IP" "$HOSTNAME" "hostberry.local" || \
            handle_error "$(get_text 'ssl_gen_failed' 'No se pudo generar el certificado SSL')"
        
        # Configurar permisos
        chmod 600 hostberry.key
        chmod 644 hostberry.crt
        chown "$USER:$GROUP" hostberry.key hostberry.crt
    else
        sudo mkcert -key-file hostberry.key -cert-file hostberry.crt \
            "localhost" "127.0.0.1" "$LOCAL_IP" "$HOSTNAME" "hostberry.local" || \
            handle_error "$(get_text 'ssl_gen_failed' 'No se pudo generar el certificado SSL')"
        
        # Configurar permisos
        chmod 600 hostberry.key
        chmod 644 hostberry.crt
        chown "$USER:$GROUP" hostberry.key hostberry.crt
    fi
    
    # Volver al directorio original
    cd - > /dev/null
    
    log "$ANSI_GREEN" "INFO" "$(get_text \"ssl_cert_generated\" \"Certificado SSL generado con mkcert\")"
    log "$ANSI_YELLOW" "INFO" "$(get_text \"ssl_valid_for\" \"Certificado válido para:\")"
    log "$ANSI_YELLOW" "INFO" "  - localhost"
    log "$ANSI_YELLOW" "INFO" "  - 127.0.0.1"
    log "$ANSI_YELLOW" "INFO" "  - $LOCAL_IP"
    log "$ANSI_YELLOW" "INFO" "  - $HOSTNAME"
    log "$ANSI_YELLOW" "INFO" "  - hostberry.local"
    
    # Configurar Nginx para SSL
    if [ -f "/etc/nginx/sites-available/hostberry" ]; then
        log "$ANSI_YELLOW" "INFO" "$(get_text \"ssl_nginx_config\" \"Configurando Nginx para SSL...\")"
        
        # Crear configuración SSL de Nginx
        if [[ $EUID -eq 0 ]]; then
            log "$ANSI_YELLOW" "INFO" "$(get_text "rendering_nginx_ssl" "Renderizando sitio SSL de Nginx...")"
            cat > "/etc/nginx/sites-available/hostberry-ssl" << EOF
server {
    listen 443 ssl http2;
    server_name localhost $LOCAL_IP $HOSTNAME hostberry.local;
    
    # Certificados SSL
    ssl_certificate $SSL_DIR/hostberry.crt;
    ssl_certificate_key $SSL_DIR/hostberry.key;
    
    # Configuración SSL moderna
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Logs
    access_log /var/log/nginx/hostberry_ssl_access.log;
    error_log /var/log/nginx/hostberry_ssl_error.log;
    
    # Configuración de seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/javascript application/json font/svg+xml image/svg+xml;
    gzip_disable "MSIE [1-6]\.";
    
    # Configuración de proxy
    location / {
        proxy_pass http://127.0.0.1:$PROD_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffers
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # Configuración para archivos estáticos
    location /static/ {
        alias $WEBSITE_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Configuración para uploads
    location /uploads/ {
        alias $UPLOADS_DIR/;
        expires 1d;
        add_header Cache-Control "public";
    }
}

# Redirección HTTP a HTTPS (fallback si el sitio 80 no fue reescrito)
server {
    listen 80;
    server_name localhost $LOCAL_IP $HOSTNAME hostberry.local;
    return 301 https://\$server_name\$request_uri;
}
EOF
        else
            log "$ANSI_YELLOW" "INFO" "$(get_text "rendering_nginx_ssl" "Renderizando sitio SSL de Nginx...")"
            cat << EOF | sudo tee "/etc/nginx/sites-available/hostberry-ssl" > /dev/null
server {
    listen 443 ssl http2;
    server_name localhost $LOCAL_IP $HOSTNAME hostberry.local;
    
    # Certificados SSL
    ssl_certificate $SSL_DIR/hostberry.crt;
    ssl_certificate_key $SSL_DIR/hostberry.key;
    
    # Configuración SSL moderna
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Logs
    access_log /var/log/nginx/hostberry_ssl_access.log;
    error_log /var/log/nginx/hostberry_ssl_error.log;
    
    # Configuración de seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/javascript application/json font/svg+xml image/svg+xml;
    gzip_disable "MSIE [1-6]\.";
    
    # Configuración de proxy
    location / {
        proxy_pass http://127.0.0.1:$PROD_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffers
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # Configuración para archivos estáticos
    location /static/ {
        alias $WEBSITE_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Configuración para uploads
    location /uploads/ {
        alias $UPLOADS_DIR/;
        expires 1d;
        add_header Cache-Control "public";
    }
}

# Redirección HTTP a HTTPS (fallback si el sitio 80 no fue reescrito)
server {
    listen 80;
    server_name localhost $LOCAL_IP $HOSTNAME hostberry.local;
    return 301 https://\$server_name\$request_uri;
}
EOF
        fi
        
        # Habilitar configuración SSL
        if [[ $EUID -eq 0 ]]; then
            ln -sf /etc/nginx/sites-available/hostberry-ssl /etc/nginx/sites-enabled/
            
            # Además, reescribir sitio HTTP como redirección 80→443 (default_server)
            cat > "/etc/nginx/sites-available/hostberry" << 'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}
EOF
            
            # Verificar configuración
nginx -t || handle_error "$(get_text 'nginx_ssl_invalid' 'Configuración SSL de Nginx inválida')"
            
            # Reiniciar Nginx
            systemctl restart nginx
        else
            sudo ln -sf /etc/nginx/sites-available/hostberry-ssl /etc/nginx/sites-enabled/
            
            # Además, reescribir sitio HTTP como redirección 80→443 (default_server)
            cat << 'EOF' | sudo tee "/etc/nginx/sites-available/hostberry" > /dev/null
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}
EOF
            
            # Verificar configuración
sudo nginx -t || handle_error "$(get_text 'nginx_ssl_invalid' 'Configuración SSL de Nginx inválida')"
            
            # Reiniciar Nginx
            sudo systemctl restart nginx
        fi
        
    log "$ANSI_GREEN" "INFO" "$(get_text \"ssl_nginx_configured\" \"Nginx configurado para SSL y redirección 80→443\")"
    fi
    
    log "$ANSI_GREEN" "INFO" "$(get_text \"ssl_configured\" \"SSL/TLS configurado correctamente con mkcert\")"
}

# Configurar firewall de producción
setup_firewall() {
    log "$ANSI_YELLOW" "INFO" "$(get_text 'setup_firewall' 'Configurando firewall de producción...')"
    
    # Configurar UFW
    if [[ $EUID -eq 0 ]]; then
        ufw --force reset
        ufw default deny incoming
        ufw default allow outgoing
        
        # Puertos esenciales
        ufw allow 22/tcp   # SSH
        ufw allow 80/tcp   # HTTP
        ufw allow 443/tcp  # HTTPS (SSL)
        
        # Habilitar UFW
        ufw --force enable
        
        # Configurar fail2ban
        cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 3
EOF
        
        systemctl restart fail2ban
        systemctl enable fail2ban
    else
        sudo ufw --force reset
        sudo ufw default deny incoming
        sudo ufw default allow outgoing
        
        # Puertos esenciales
        sudo ufw allow 22/tcp   # SSH
        sudo ufw allow 80/tcp   # HTTP
        sudo ufw allow 443/tcp  # HTTPS (SSL)
        
        # Habilitar UFW
        sudo ufw --force enable
        
        # Configurar fail2ban
        cat << EOF | sudo tee /etc/fail2ban/jail.local > /dev/null
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 3
EOF
        
        sudo systemctl restart fail2ban
        sudo systemctl enable fail2ban
    fi
    
    log "$ANSI_GREEN" "INFO" "Firewall y fail2ban configurados"
}

# Configurar monitoreo
setup_monitoring() {
    log "$ANSI_YELLOW" "INFO" "Configurando monitoreo..."
    
    # Crear script de monitoreo
    cat > "$PROD_DIR/monitor.sh" << EOF
#!/bin/bash

# Script de monitoreo para HostBerry
LOG_FILE="\$LOG_DIR/monitor.log"
ALERT_EMAIL="admin@hostberry.local"

# Función para loguear
log() {
    local message="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $message" >> "$LOG_FILE"
}

# Verificar servicio
if ! systemctl is-active --quiet hostberry; then
    log "ERROR: Servicio hostberry no está activo"
    systemctl restart hostberry
fi

# Verificar puerto
if ! netstat -tulpn | grep -q ":8000.*LISTEN"; then
    log "ERROR: Puerto 8000 no está escuchando"
fi

# Verificar memoria
MEMORY_USAGE=\$(free | awk '/^Mem:/ {printf "%.1f", \$3/\$2 * 100.0}')
if (( \$(echo "\$MEMORY_USAGE > 90" | bc -l) )); then
    log "WARNING: Uso de memoria alto: \${MEMORY_USAGE}%"
fi

# Verificar CPU
CPU_USAGE=\$(top -bn1 | grep "Cpu(s)" | awk '{print \$2}' | cut -d'%' -f1)
if (( \$(echo "\$CPU_USAGE > 80" | bc -l) )); then
    log "WARNING: Uso de CPU alto: \${CPU_USAGE}%"
fi

# Verificar disco
DISK_USAGE=\$(df / | awk 'NR==2 {print \$5}' | cut -d'%' -f1)
if [ "\$DISK_USAGE" -gt 90 ]; then
    log "WARNING: Uso de disco alto: \${DISK_USAGE}%"
fi

# Verificar temperatura (RPi)
if [ -f "/sys/class/thermal/thermal_zone0/temp" ]; then
    TEMP=\$(cat /sys/class/thermal/thermal_zone0/temp | awk '{print \$1/1000}')
    if (( \$(echo "\$TEMP > 70" | bc -l) )); then
        log "WARNING: Temperatura alta: \${TEMP}°C"
    fi
fi
EOF
    
    chmod +x "$PROD_DIR/monitor.sh"
    chown "$USER:$GROUP" "$PROD_DIR/monitor.sh"
    
    # Configurar cron para monitoreo optimizado (solo si no existe ya)
    if ! crontab -l 2>/dev/null | grep -q "monitor.sh"; then
        # Monitoreo cada 15 minutos en lugar de cada 5 para reducir carga
        (crontab -l 2>/dev/null; echo "*/15 * * * * $USER $PROD_DIR/monitor.sh") | crontab -
    fi
    
    log "$ANSI_GREEN" "INFO" "Monitoreo configurado"
}

# Configurar logrotate optimizado para RPi 3
setup_logrotate() {
    log "$ANSI_YELLOW" "INFO" "Configurando logrotate optimizado para RPi 3..."
    
    if [[ $EUID -eq 0 ]]; then
        cat > /etc/logrotate.d/hostberry << EOF
$LOG_DIR/*.log {
    # Rotación más frecuente para RPi 3 (menos espacio)
    weekly
    missingok
    rotate 4
    compress
    delaycompress
    notifempty
    create 644 $USER $GROUP
    # Tamaño máximo de archivo (1MB)
    size 1M
    postrotate
        systemctl reload hostberry.service
    endscript
}
EOF
    else
        cat << EOF | sudo tee /etc/logrotate.d/hostberry > /dev/null
$LOG_DIR/*.log {
    # Rotación más frecuente para RPi 3 (menos espacio)
    weekly
    missingok
    rotate 4
    compress
    delaycompress
    notifempty
    create 644 $USER $GROUP
    # Tamaño máximo de archivo (1MB)
    size 1M
    postrotate
        systemctl reload hostberry.service
    endscript
}
EOF
    fi
    
    log "$ANSI_GREEN" "INFO" "Logrotate optimizado configurado para RPi 3"
}

# Crear backup
create_backup() {
    log "$ANSI_YELLOW" "INFO" "$(get_text \"creating_backup\" \"Creating backup...\")"
    
    local BACKUP_PATH="$BACKUP_DIR/hostberry_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_PATH"
    
    # Detener servicio
    if [[ $EUID -eq 0 ]]; then
systemctl stop "hostberry.service" 2>/dev/null || true
    else
sudo systemctl stop "hostberry.service" 2>/dev/null || true
    fi
    
    # Crear backup
    cp -r "$PROD_DIR" "$BACKUP_PATH/" || handle_error "$(get_text 'backup_failed' 'Error creating backup')"
    
    # Reiniciar servicio
    if [[ $EUID -eq 0 ]]; then
systemctl start "hostberry.service" 2>/dev/null || true
    else
sudo systemctl start "hostberry.service" 2>/dev/null || true
    fi
    
    log "$ANSI_GREEN" "INFO" "$(format_text "$(get_text \"backup_created_at\" \"Backup created at: {path}\")" "path=$BACKUP_PATH")"
}

# Optimizaciones de producción
apply_production_optimizations() {
    log "$ANSI_YELLOW" "INFO" "$(get_text 'applying_optimizations' 'Aplicando optimizaciones de producción para RPi 3...')"
    
    # Optimizaciones de sistema optimizadas para RPi 3
    if [[ $EUID -eq 0 ]]; then
        cat >> /etc/sysctl.conf << EOF

# Optimizaciones para HostBerry en RPi 3
net.core.rmem_max = 131072
net.core.wmem_max = 131072
net.ipv4.tcp_rmem = 4096 65536 131072
net.ipv4.tcp_wmem = 4096 65536 131072
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_timestamps = 0
net.ipv4.tcp_sack = 1
vm.swappiness = 5
vm.dirty_ratio = 10
vm.dirty_background_ratio = 3
vm.vfs_cache_pressure = 50
EOF
        
        sysctl -p
    else
        cat << EOF | sudo tee -a /etc/sysctl.conf > /dev/null

# Optimizaciones para HostBerry en RPi 3
net.core.rmem_max = 131072
net.core.wmem_max = 131072
net.ipv4.tcp_rmem = 4096 65536 131072
net.ipv4.tcp_wmem = 4096 65536 131072
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_timestamps = 0
net.ipv4.tcp_sack = 1
vm.swappiness = 5
vm.dirty_ratio = 10
vm.dirty_background_ratio = 3
vm.vfs_cache_pressure = 50
EOF
        
        sudo sysctl -p
    fi
    
    # Optimizaciones para RPi
    if [ -f "/proc/device-tree/model" ]; then
        local MODEL
        MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)
        if [[ "$MODEL" =~ "Raspberry Pi" ]]; then
            log "$ANSI_GREEN" "INFO" "$(get_text 'rpi_optimizations' 'Aplicando optimizaciones específicas para RPi')"
            
                    # CPU governor optimizado para RPi 3
        if [[ $EUID -eq 0 ]]; then
            echo "powersave" > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || true
            
            # Deshabilitar servicios innecesarios para RPi 3
            local unnecessary_services=(
                "bluetooth" "avahi-daemon" "triggerhappy" "hciuart"
                "bluealsa" "pulseaudio" "speech-dispatcher"
                "cups" "cups-browsed" "snapd" "snapd.socket"
                "ModemManager"
            )
            
            # Preserve NetworkManager if active
            if systemctl is-active --quiet NetworkManager; then
                log "$ANSI_YELLOW" "INFO" "NetworkManager is active - preserving service"
            else
                unnecessary_services+=("NetworkManager")
            fi
            
            for service in "${unnecessary_services[@]}"; do
                systemctl disable "$service" 2>/dev/null || true
                systemctl stop "$service" 2>/dev/null || true
            done
            
            # Optimizaciones específicas de CPU para RPi 3
            echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true
            echo 0 > /proc/sys/kernel/nmi_watchdog 2>/dev/null || true
        else
            echo "powersave" | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > /dev/null 2>&1 || true
            
            # Deshabilitar servicios innecesarios para RPi 3
            local unnecessary_services=(
                "bluetooth" "avahi-daemon" "triggerhappy" "hciuart"
                "bluealsa" "pulseaudio" "speech-dispatcher"
                "cups" "cups-browsed" "snapd" "snapd.socket"
                "ModemManager"
            )
            
            for service in "${unnecessary_services[@]}"; do
                sudo systemctl disable "$service" 2>/dev/null || true
                sudo systemctl stop "$service" 2>/dev/null || true
            done
            
            # Optimizaciones específicas de CPU para RPi 3
            echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo > /dev/null 2>&1 || true
            echo 0 | sudo tee /proc/sys/kernel/nmi_watchdog > /dev/null 2>&1 || true
        fi
        fi
    fi
    
    log "$ANSI_GREEN" "INFO" "$(get_text 'optimizations_applied' 'Optimizaciones de producción aplicadas')"
}

# Configurar ZRAM para Raspberry Pi 3
setup_zram() {
    log "$ANSI_YELLOW" "INFO" "$(get_text 'setup_zram' 'Configurando ZRAM (compresión de memoria)...')"
    
    if [[ $EUID -eq 0 ]]; then
        # Crear script de inicio de ZRAM
        cat > /usr/local/sbin/zram-config << 'EOF'
#!/bin/bash
modprobe zram num_devices=1
# Usar 50% de la RAM para ZRAM (ideal para RPi 3 con 1GB)
MEM_TOTAL=$(grep MemTotal /proc/meminfo | awk '{print $2 * 1024}')
ZRAM_SIZE=$(($MEM_TOTAL / 2))
echo "${ZRAM_SIZE}" > /sys/block/zram0/disksize
mkswap /sys/block/zram0
swapon -p 100 /sys/block/zram0
EOF
        chmod +x /usr/local/sbin/zram-config
        
        # Crear servicio systemd para ZRAM
        cat > /etc/systemd/system/zram-config.service << 'EOF'
[Unit]
Description=Configure ZRAM swap
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/zram-config
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
        
        systemctl daemon-reload
        systemctl enable zram-config.service
        systemctl start zram-config.service
        
    else
        # Versión con sudo
        cat << 'EOF' | sudo tee /usr/local/sbin/zram-config > /dev/null
#!/bin/bash
modprobe zram num_devices=1
MEM_TOTAL=$(grep MemTotal /proc/meminfo | awk '{print $2 * 1024}')
ZRAM_SIZE=$(($MEM_TOTAL / 2))
echo "${ZRAM_SIZE}" > /sys/block/zram0/disksize
mkswap /sys/block/zram0
swapon -p 100 /sys/block/zram0
EOF
        sudo chmod +x /usr/local/sbin/zram-config
        
        cat << 'EOF' | sudo tee /etc/systemd/system/zram-config.service > /dev/null
[Unit]
Description=Configure ZRAM swap
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/zram-config
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable zram-config.service
        sudo systemctl start zram-config.service
    fi
    
    log "$ANSI_GREEN" "INFO" "ZRAM configurado y activo"
}

# Verificar instalación
verify_installation() {
    log "$ANSI_YELLOW" "INFO" "$(get_text 'verifying_installation' 'Verificando instalación...')"
    
    # Verificar servicios
    local services=("hostberry.service" "nginx")
    local s
    for s in "${services[@]}"; do
        if systemctl is-active --quiet "$s"; then
            log "$ANSI_GREEN" "SUCCESS" "$(format_text "$(get_text 'service_running' 'Servicio {service} está corriendo')" "service=$s")"
        else
            log "$ANSI_RED" "ERROR" "$(format_text "$(get_text 'service_failed' 'Servicio {service} no está corriendo')" "service=$s")"
            if [ "$s" == "hostberry.service" ]; then
                log "$ANSI_YELLOW" "INFO" "Logs recientes:"
                journalctl -u hostberry.service -n 20 --no-pager
            fi
        fi
    done
    
    # Verificar respuesta HTTP (con múltiples intentos y más tiempo)
    log "$ANSI_YELLOW" "INFO" "$(get_text 'checking_http' 'Comprobando respuesta HTTP...')"
    local http_ok=false
    for i in {1..6}; do
        sleep 5
        if curl -s -o /dev/null -w "%{http_code}" http://localhost 2>/dev/null | grep -q "200\|301\|302"; then
            log "$ANSI_GREEN" "SUCCESS" "$(get_text 'http_ok' 'Respuesta HTTP OK')"
            http_ok=true
            break
        else
            log "$ANSI_YELLOW" "INFO" "Intento $i/6: Esperando respuesta HTTP..."
        fi
    done
    
    if [ "$http_ok" = false ]; then
        log "$ANSI_RED" "ERROR" "$(get_text 'http_failed' 'Fallo en respuesta HTTP')"
        log "$ANSI_YELLOW" "INFO" "Verificando estado del servicio hostberry..."
        if systemctl is-active --quiet hostberry.service; then
            log "$ANSI_YELLOW" "INFO" "El servicio está activo. Puede que necesite más tiempo para iniciar."
            log "$ANSI_YELLOW" "INFO" "Intenta acceder manualmente: http://localhost"
        else
            log "$ANSI_RED" "ERROR" "El servicio hostberry no está activo. Revisa los logs:"
            journalctl -u hostberry.service -n 30 --no-pager || true
        fi
    fi
}

# Mostrar información de producción
show_production_info() {
    local ip_address
    ip_address=$(hostname -I | awk '{print $1}')
    
    echo
    log "$ANSI_GREEN" "INFO" "================================================================"
    log "$ANSI_GREEN" "INFO" "   HOSTBERRY INSTALADO CORRECTAMENTE EN PRODUCCIÓN (Debian/RPi)"
    log "$ANSI_GREEN" "INFO" "================================================================"
    echo
    log "$ANSI_BLUE" "INFO" "URL Local:       http://localhost"
    log "$ANSI_BLUE" "INFO" "URL Red:         http://$ip_address"
    if [ -f "$SSL_DIR/hostberry.crt" ]; then
        log "$ANSI_BLUE" "INFO" "URL Segura:      https://$ip_address (Acepte el certificado)"
    fi
    echo
    log "$ANSI_BLUE" "INFO" "Admin User:      admin"
    log "$ANSI_BLUE" "INFO" "Admin Password:  hostberry"
    echo
    log "$ANSI_BLUE" "INFO" "Logs:            tail -f $LOG_DIR/hostberry_error.log"
    log "$ANSI_BLUE" "INFO" "Servicio:        systemctl status hostberry.service"
    log "$ANSI_BLUE" "INFO" "Monitor:         $PROD_DIR/monitor.sh"
    echo
    log "$ANSI_YELLOW" "INFO" "$(get_text 'restart_note' 'Nota: Si acaba de actualizar, puede requerir reiniciar el servicio.')"
    echo
}

# Mostrar información de actualización exitosa
show_update_info() {
    local ip_address
    ip_address=$(hostname -I | awk '{print $1}')
    local current_date
    current_date=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo
    log "$ANSI_GREEN" "INFO" "================================================================"
    log "$ANSI_GREEN" "INFO" "   HOSTBERRY ACTUALIZADO CORRECTAMENTE (Debian/RPi)"
    log "$ANSI_GREEN" "INFO" "================================================================"
    echo
    log "$ANSI_BLUE" "INFO" "Fecha y hora:    $current_date"
    echo
    log "$ANSI_BLUE" "INFO" "URL Local:       http://localhost"
    log "$ANSI_BLUE" "INFO" "URL Red:         http://$ip_address"
    if [ -f "$SSL_DIR/hostberry.crt" ]; then
        log "$ANSI_BLUE" "INFO" "URL Segura:      https://$ip_address (Acepte el certificado)"
    fi
    echo
    log "$ANSI_BLUE" "INFO" "Admin User:      admin"
    log "$ANSI_BLUE" "INFO" "Admin Password:  hostberry"
    echo
    log "$ANSI_BLUE" "INFO" "Logs:            tail -f $LOG_DIR/hostberry_error.log"
    log "$ANSI_BLUE" "INFO" "Servicio:        systemctl status hostberry.service"
    log "$ANSI_BLUE" "INFO" "Monitor:         $PROD_DIR/monitor.sh"
    echo
    log "$ANSI_GREEN" "SUCCESS" "$(get_text 'update_completed' 'Actualización completada exitosamente')"
    echo
}

# Función principal
main() {
    # Verificar usuario root o sudo
    if [[ $EUID -ne 0 ]]; then
        die "$(get_text 'root_required' 'Este script requiere ejecutarse con sudo o como root')"
    fi

    # Cargar traducciones
    load_translations

    # Parsear argumentos
    local INSTALL_MODE=false
    local UPDATE_MODE=false
    local BACKUP_MODE=false
    local SSL_MODE=false
    
    # Si no hay argumentos, mostrar ayuda
    if [[ $# -eq 0 ]]; then
        show_help
    fi
    
    for arg in "$@"; do
        case $arg in
            --install) INSTALL_MODE=true ;;
            --update)  UPDATE_MODE=true ;;
            --backup)  BACKUP_MODE=true ;;
            --ssl)     SSL_MODE=true ;;
            --help)    show_help ;;
            --language=*) LANGUAGE="${arg#*=}"; load_translations ;;
            *) echo "Opción desconocida: $arg"; show_help ;;
        esac
    done
    
    # Validar combinaciones
    if [[ "$INSTALL_MODE" = true && "$UPDATE_MODE" = true ]]; then
        die "$(get_text 'install_update_conflict' 'No se puede usar --install y --update simultáneamente')"
    fi

    # Ejecutar acciones
    if [[ "$BACKUP_MODE" = true ]]; then
        create_backup
        # Si solo es backup, salir
        if [[ "$INSTALL_MODE" = false && "$UPDATE_MODE" = false && "$SSL_MODE" = false ]]; then
            exit 0
        fi
    fi
    
    if [[ "$INSTALL_MODE" = true ]]; then
        log "$ANSI_GREEN" "INFO" "Iniciando instalación de HostBerry para Raspberry Pi 3 (Debian/Raspbian)..."
        
        check_permissions
        check_required_ports
        
        if [ -d "$PROD_DIR" ]; then
            log "$ANSI_YELLOW" "WARN" "$(get_text 'dir_exists' 'El directorio de producción ya existe. Se recomienda --update o limpiar antes.')"
        fi
        
        clean_previous_installation
        setup_user_permissions
        install_system_deps
        download_application_from_github
        
        # Configurar venv e instalar dependencias python
        log "$ANSI_YELLOW" "INFO" "Configurando entorno Python..."
        run_python_venv "$VENV_DIR" || handle_error "$(get_text 'venv_failed' 'No se pudo crear el entorno virtual')"
        chown -R "$USER:$GROUP" "$VENV_DIR"
        
        # Actualizar pip con opciones optimizadas
        "$VENV_DIR/bin/pip" install --upgrade "pip<25.0" \
            --index-url https://pypi.org/simple \
            --retries 3 \
            --timeout 120 \
            --prefer-binary || handle_error "$(get_text 'pip_update_failed' 'No se pudo actualizar pip')"
        
        # Instalar dependencias con preferencia a binarios
        "$VENV_DIR/bin/pip" install -r "$PROD_DIR/requirements.txt" \
            --index-url https://pypi.org/simple \
            --retries 3 \
            --timeout 120 \
            --prefer-binary || handle_error "$(get_text 'deps_failed' 'No se pudieron instalar las dependencias')"
        
        write_app_env
        setup_firewall
        setup_nginx
        
        # Si se pidió SSL
        if [[ "$SSL_MODE" = true ]]; then
            setup_ssl
        fi
        
        setup_logrotate
        apply_production_optimizations
        setup_zram
        setup_monitoring
        setup_secure_sudoers
        
        # Configurar servicio systemd
        log "$ANSI_YELLOW" "INFO" "Configurando servicio systemd..."
        if [[ $EUID -eq 0 ]]; then
            cat > /etc/systemd/system/hostberry.service << EOF
[Unit]
Description=HostBerry Web Application
After=network.target

[Service]
User=$USER
Group=$GROUP
WorkingDirectory=$PROD_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$CONFIG_DIR/app.env
ExecStart=$VENV_DIR/bin/python -m uvicorn --app-dir $PROD_DIR main:app --host $PROD_HOST --port $PROD_PORT --workers $WORKERS --log-level warning
Restart=always
RestartSec=2
# Timeouts optimizados para reinicio rápido
TimeoutStartSec=15
TimeoutStopSec=10
# Kill mode para terminar procesos rápidamente
KillMode=mixed
KillSignal=SIGTERM
# Limits for RPi 3
MemoryMax=300M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF
            systemctl daemon-reload
            systemctl enable hostberry.service
            systemctl start hostberry.service
        else
            cat << EOF | sudo tee /etc/systemd/system/hostberry.service > /dev/null
[Unit]
Description=HostBerry Web Application
After=network.target

[Service]
User=$USER
Group=$GROUP
WorkingDirectory=$PROD_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$CONFIG_DIR/app.env
ExecStart=$VENV_DIR/bin/python -m uvicorn --app-dir $PROD_DIR main:app --host $PROD_HOST --port $PROD_PORT --workers $WORKERS --log-level warning
Restart=always
RestartSec=2
# Timeouts optimizados para reinicio rápido
TimeoutStartSec=15
TimeoutStopSec=10
# Kill mode para terminar procesos rápidamente
KillMode=mixed
KillSignal=SIGTERM
# Limits for RPi 3
MemoryMax=300M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF
            sudo systemctl daemon-reload
            sudo systemctl enable hostberry.service
            sudo systemctl start hostberry.service
        fi
        
        verify_installation
        show_production_info
        
    elif [[ "$UPDATE_MODE" = true ]]; then
        log "$ANSI_GREEN" "INFO" "Iniciando actualización de HostBerry..."
        
        # Pull updates
        download_application_from_github "true"
        
        # Configurar venv en modo update (instalar/verificar deps)
        setup_production_venv "update"
        
        # Reiniciar servicio
        systemctl restart hostberry.service
        
        # Mostrar información de actualización exitosa
        show_update_info
        
    elif [[ "$SSL_MODE" = true ]]; then
        setup_ssl
        # Reload nginx
        if [[ $EUID -eq 0 ]]; then
            systemctl reload nginx
        else
            sudo systemctl reload nginx
        fi
    fi
}

# Ejecutar main
main "$@"
