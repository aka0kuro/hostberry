#!/bin/bash

# HostBerry - Script de Desinstalación

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
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Desinstalador de HostBerry${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    check_root
    
    # Detener y deshabilitar servicio
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        print_info "Deteniendo servicio..."
        systemctl stop "${SERVICE_NAME}"
        systemctl disable "${SERVICE_NAME}"
        print_success "Servicio detenido"
    fi
    
    # Eliminar servicio systemd
    if [ -f "$SERVICE_FILE" ]; then
        print_info "Eliminando servicio systemd..."
        rm -f "$SERVICE_FILE"
        systemctl daemon-reload
        print_success "Servicio eliminado"
    fi
    
    # Preguntar si eliminar datos
    echo ""
    read -p "¿Deseas eliminar los datos y archivos de configuración? (s/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        # Eliminar directorio de instalación
        if [ -d "$INSTALL_DIR" ]; then
            print_info "Eliminando archivos de instalación..."
            rm -rf "$INSTALL_DIR"
            print_success "Archivos eliminados"
        fi
        
        # Eliminar logs
        if [ -d "/var/log/hostberry" ]; then
            print_info "Eliminando logs..."
            rm -rf "/var/log/hostberry"
            print_success "Logs eliminados"
        fi
        
        # Eliminar usuario (opcional)
        read -p "¿Deseas eliminar el usuario ${USER_NAME}? (s/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            if id "$USER_NAME" &>/dev/null; then
                print_info "Eliminando usuario ${USER_NAME}..."
                userdel "$USER_NAME" 2>/dev/null || true
                print_success "Usuario eliminado"
            fi
        fi
    else
        print_info "Archivos conservados en $INSTALL_DIR"
    fi
    
    echo ""
    print_success "HostBerry desinstalado correctamente"
    echo ""
}

main
