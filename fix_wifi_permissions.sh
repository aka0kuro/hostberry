#!/bin/bash
# Script para agregar permisos WiFi faltantes (especialmente para iw)

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verificar que se ejecuta como root
if [ "$EUID" -ne 0 ]; then 
    print_error "Por favor, ejecuta este script como root (sudo)"
    exit 1
fi

print_info "Agregando permisos WiFi faltantes para HostBerry..."

# Detectar usuario de HostBerry
USER_NAME="hostberry"
if ! id "$USER_NAME" &>/dev/null; then
    print_error "Usuario $USER_NAME no encontrado"
    exit 1
fi

# Buscar ruta de iw
IW_PATH=""
if command -v iw &> /dev/null; then
    IW_PATH=$(command -v iw)
elif [ -f "/usr/sbin/iw" ]; then
    IW_PATH="/usr/sbin/iw"
elif [ -f "/sbin/iw" ]; then
    IW_PATH="/sbin/iw"
fi

if [ -z "$IW_PATH" ]; then
    print_warning "Comando 'iw' no encontrado. Instalando..."
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y iw
        IW_PATH=$(command -v iw)
    elif command -v yum &> /dev/null; then
        yum install -y iw
        IW_PATH=$(command -v iw)
    elif command -v pacman &> /dev/null; then
        pacman -S --noconfirm iw
        IW_PATH=$(command -v iw)
    else
        print_error "No se pudo instalar 'iw'. Por favor, instálalo manualmente."
        exit 1
    fi
fi

if [ -z "$IW_PATH" ]; then
    print_error "No se pudo encontrar o instalar 'iw'"
    exit 1
fi

print_info "Ruta de iw encontrada: $IW_PATH"

# Verificar si existe el archivo sudoers
SUDOERS_FILE="/etc/sudoers.d/hostberry"
if [ ! -f "$SUDOERS_FILE" ]; then
    print_warning "Archivo sudoers no encontrado. Creando uno nuevo..."
    touch "$SUDOERS_FILE"
    chmod 440 "$SUDOERS_FILE"
fi

# Verificar si ya existe el permiso para iw
if grep -q "$IW_PATH" "$SUDOERS_FILE" 2>/dev/null; then
    print_info "Permiso para iw ya existe en sudoers"
else
    print_info "Agregando permiso para iw en sudoers..."
    echo "$USER_NAME ALL=(ALL) NOPASSWD: $IW_PATH" >> "$SUDOERS_FILE"
    print_success "Permiso agregado para iw"
fi

# Validar configuración de sudoers
if visudo -c -f "$SUDOERS_FILE" 2>/dev/null; then
    chmod 440 "$SUDOERS_FILE"
    print_success "Configuración de sudoers validada correctamente"
else
    print_error "Error al validar configuración de sudoers"
    print_info "Revisa manualmente: visudo -c -f $SUDOERS_FILE"
    exit 1
fi

print_success "Permisos WiFi configurados correctamente"
print_info "Puedes cambiar la región WiFi desde la interfaz web ahora"
