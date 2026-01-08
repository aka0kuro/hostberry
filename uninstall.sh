#!/bin/bash

# HostBerry - Script de Desinstalación
# Este script es un wrapper que llama a install.sh --uninstall

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
INSTALL_DIR="/opt/hostberry"
SERVICE_NAME="hostberry"
USER_NAME="hostberry"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then 
        echo -e "${RED}[ERROR]${NC} Este script debe ejecutarse como root (usa sudo)"
        exit 1
    fi
}

main() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Ejecutar el instalador en modo desinstalación
    if [ -f "${SCRIPT_DIR}/install.sh" ]; then
        exec "${SCRIPT_DIR}/install.sh" --uninstall
    else
        print_error "install.sh no encontrado en ${SCRIPT_DIR}"
        exit 1
    fi
}

main
