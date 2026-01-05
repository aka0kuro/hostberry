#!/bin/bash
# Script para actualizar Chart.js localmente
# Uso: ./scripts/update_chartjs.sh [versión]
# Ejemplo: ./scripts/update_chartjs.sh 4.4.1

VERSION=${1:-"4.4.1"}
LIB_DIR="website/static/js/lib"
CDN_URL="https://cdn.jsdelivr.net/npm/chart.js@${VERSION}/dist/chart.umd.min.js"

echo "Descargando Chart.js versión ${VERSION}..."

# Crear directorio si no existe
mkdir -p "${LIB_DIR}"

# Descargar Chart.js
if curl -L -o "${LIB_DIR}/chart.umd.min.js" "${CDN_URL}"; then
    echo "✓ Chart.js ${VERSION} descargado correctamente en ${LIB_DIR}/chart.umd.min.js"
    ls -lh "${LIB_DIR}/chart.umd.min.js"
else
    echo "✗ Error al descargar Chart.js"
    exit 1
fi

