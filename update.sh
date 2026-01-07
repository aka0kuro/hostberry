#!/bin/bash

# HostBerry - Script de Actualización Rápida
# Wrapper para install.sh --update

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

main() {
    print_info "Iniciando actualización de HostBerry..."
    
    cd "${SCRIPT_DIR}"

    # Verificar si es un repositorio git
    if [ -d ".git" ]; then
        print_info "Repositorio git detectado, buscando actualizaciones..."
        if command -v git &> /dev/null; then
            if git pull; then
                print_success "Código actualizado desde el repositorio"
            else
                print_error "Error al ejecutar git pull. Verifica tu conexión o conflictos."
                exit 1
            fi
        else
            print_info "Git no está instalado, saltando actualización de código."
        fi
    fi

    # Ejecutar el instalador en modo actualización
    if [ -f "${SCRIPT_DIR}/install.sh" ]; then
        print_info "Ejecutando instalador..."
        exec "${SCRIPT_DIR}/install.sh" --update
    else
        print_error "install.sh no encontrado en ${SCRIPT_DIR}"
        exit 1
    fi
}

main "$@"
