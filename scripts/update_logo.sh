#!/bin/bash
# Script para actualizar el logo de HostBerry

# Directorio de instalación
INSTALL_DIR="/opt/hostberry"

# Verificar si el archivo de logo existe
if [ ! -f "${INSTALL_DIR}/img/hostberry.png" ]; then
    echo "Error: No se encontró el archivo del logo en ${INSTALL_DIR}/img/hostberry.png"
    exit 1
fi

# Crear directorios si no existen
mkdir -p "${INSTALL_DIR}/static/img"
mkdir -p "${INSTALL_DIR}/app/static/img"

# Copiar el logo a las ubicaciones correctas
echo "Copiando el logo a las ubicaciones correctas..."
cp "${INSTALL_DIR}/img/hostberry.png" "${INSTALL_DIR}/static/img/"
cp "${INSTALL_DIR}/img/hostberry.png" "${INSTALL_DIR}/app/static/img/"

# Establecer permisos correctos
echo "Estableciendo permisos..."
chown -R www-data:www-data "${INSTALL_DIR}/static/img" "${INSTALL_DIR}/app/static/img"
chmod 644 "${INSTALL_DIR}/static/img/hostberry.png" "${INSTALL_DIR}/app/static/img/hostberry.png"

echo "Logo actualizado correctamente."
echo "URLs del logo:"
echo "- ${INSTALL_DIR}/static/img/hostberry.png"
echo "- ${INSTALL_DIR}/app/static/img/hostberry.png"

echo "Reiniciando Nginx para aplicar los cambios..."
systemctl restart nginx

echo "¡Listo! El logo ha sido actualizado correctamente."
