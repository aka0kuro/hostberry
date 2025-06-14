#!/bin/bash

# Script para limpiar archivos migrados a la nueva estructura modular
# Este script eliminará archivos de la raíz que ya han sido migrados

# Directorio raíz del proyecto
PROJECT_ROOT="/home/cantar/hostberry"

# Archivos y directorios a eliminar (relativos a PROJECT_ROOT)
FILES_TO_REMOVE=(
    "app.py"           # Código principal migrado a módulos
    "run.py"           # Punto de entrada principal (ya tenemos wsgi.py)
    "config.py"        # Configuración movida a app/config/
    "hostberry_config.py"  # Configuración movida a app/config/
)

# Mostrar advertencia
echo "ADVERTENCIA: Este script eliminará los siguientes archivos:"
for file in "${FILES_TO_REMOVE[@]}"; do
    echo "- $PROJECT_ROOT/$file"
done

echo -e "\n¿Estás seguro de que deseas continuar? (s/n) "
read -r response
if [[ ! "$response" =~ ^[Ss]$ ]]; then
    echo "Operación cancelada."
    exit 1
fi

# Eliminar archivos
for file in "${FILES_TO_REMOVE[@]}"; do
    full_path="$PROJECT_ROOT/$file"
    if [ -e "$full_path" ]; then
        echo "Eliminando $full_path..."
        rm -f "$full_path"
    fi
done

echo "\nLimpieza completada. Se recomienda verificar que todo funcione correctamente."

# Mostrar estructura actual
echo -e "\nEstructura actual del proyecto:"
tree -L 2 /home/cantar/hostberry/ || ls -la /home/cantar/hostberry/
