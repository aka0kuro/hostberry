#!/bin/bash

# HostBerry - Script de Actualización Rápida
# Wrapper para install.sh --update

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/install.sh" ]; then
    exec "${SCRIPT_DIR}/install.sh" --update
else
    echo "Error: install.sh no encontrado"
    exit 1
fi
